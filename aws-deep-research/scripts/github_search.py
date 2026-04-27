# /// script
# requires-python = ">=3.13"
# dependencies = [
#   "mcp>=1.26.0",
#   "rich>=14.3.3",
# ]
# ///
"""
GitHub Repository Search — standalone MCP client.

Spawns awslabs.git-repo-research-mcp-server as a child process (stdio),
searches AWS-related GitHub organizations for relevant repositories,
and writes condensed results to a markdown file.  Designed to run inside
a subagent so that raw repo data never enters the parent agent's context.

Usage:
    uv run github_search.py -q "bedrock agents sample" \
        -o output/research/bedrock-agents/github-repos.md

    uv run github_search.py -q "serverless patterns" -q "lambda cdk examples" \
        -o output/research/serverless/github-repos.md --top 5 --json

    uv run github_search.py -q "opensearch vector search" \
        -o output/research/vector-search/github-repos.md \
        --deep-index  # Index top repo for semantic search
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from rich.console import Console

console = Console(stderr=True)


# ── Logging ──────────────────────────────────────────────────────────────────


class ResearchLogger:
    """Append-only structured logger that writes to a research.log file."""

    def __init__(self, log_dir: Path | None) -> None:
        self.log_dir = log_dir
        self._fh = None
        if log_dir:
            log_dir.mkdir(parents=True, exist_ok=True)
            self._fh = (log_dir / "research.log").open("a", encoding="utf-8")

    def log(self, event: str, **data: Any) -> None:
        if not self._fh:
            return
        entry = {
            "ts": datetime.now(UTC).isoformat(),
            "script": "github_search",
            "event": event,
            **data,
        }
        self._fh.write(json.dumps(entry, default=str) + "\n")
        self._fh.flush()

    def close(self) -> None:
        if self._fh:
            self._fh.close()


# ── Server config ────────────────────────────────────────────────────────────


def make_server_params() -> StdioServerParameters:
    """Build server params with GitHub token and AWS credentials."""
    env = {
        "FASTMCP_LOG_LEVEL": "ERROR",
    }
    # Forward credentials
    for key in (
        "GITHUB_TOKEN",
        "AWS_PROFILE",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "AWS_DEFAULT_REGION",
        "AWS_REGION",
    ):
        val = os.environ.get(key)
        if val:
            env[key] = val

    return StdioServerParameters(
        command="uvx",
        args=["awslabs.git-repo-research-mcp-server@latest"],
        env=env,
    )


# ── MCP helpers ──────────────────────────────────────────────────────────────


async def call_tool(
    session: ClientSession,
    name: str,
    arguments: dict[str, Any],
) -> Any:
    """Call an MCP tool and return parsed JSON or raw text."""
    result = await session.call_tool(name, arguments)
    if not result.content:
        return None
    text = result.content[0].text
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return text


async def list_tools(session: ClientSession) -> list[str]:
    """Discover available tools on the server."""
    result = await session.list_tools()
    return [t.name for t in result.tools]


async def search_repos(
    session: ClientSession,
    keywords: list[str],
    *,
    num_results: int = 5,
) -> list[dict[str, Any]]:
    """search_repos_on_github → list of repo results."""
    raw = await call_tool(
        session,
        "search_repos_on_github",
        {"keywords": keywords, "num_results": num_results},
    )
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        return raw.get("repositories", raw.get("results", raw.get("items", [raw])))
    if isinstance(raw, str):
        return [{"description": raw}]
    return []


async def index_repo(
    session: ClientSession,
    repo_path: str,
    output_path: str | None = None,
) -> dict[str, Any]:
    """create_research_repository → index a repo for semantic search."""
    args: dict[str, Any] = {"repository_path": repo_path}
    if output_path:
        args["output_path"] = output_path
    raw = await call_tool(session, "create_research_repository", args)
    if isinstance(raw, dict):
        return raw
    return {"result": raw}


async def search_indexed_repo(
    session: ClientSession,
    index_path: str,
    query: str,
    *,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """search_research_repository → semantic search within indexed repo."""
    raw = await call_tool(
        session,
        "search_research_repository",
        {"index_path": index_path, "query": query, "limit": limit},
    )
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        return raw.get("results", [raw])
    return []


async def access_repo_file(
    session: ClientSession,
    filepath: str,
) -> str:
    """access_file → read a file from an indexed repo."""
    raw = await call_tool(session, "access_file", {"filepath": filepath})
    if isinstance(raw, str):
        return raw
    if isinstance(raw, dict):
        return raw.get("content", str(raw))
    return str(raw) if raw else ""


# ── Core research logic ─────────────────────────────────────────────────────


async def research_github(  # noqa: PLR0913
    session: ClientSession,
    queries: list[str],
    *,
    top: int = 5,
    deep_index: bool = False,
    logger: ResearchLogger | None = None,
    available_tools: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Run GitHub search for each query. Returns structured findings."""
    all_findings: list[dict[str, Any]] = []
    log = logger.log if logger else lambda *_a, **_kw: None
    tools = available_tools or []
    seen_repos: set[str] = set()  # Dedup across queries

    for query in queries:
        console.print(f"[cyan]Searching GitHub:[/cyan] {query}")
        finding: dict[str, Any] = {"query": query}
        t0 = time.monotonic()

        # Build keyword variations
        keywords = _build_keywords(query)
        repos: list[dict[str, Any]] = []

        for kw_set in keywords[:2]:  # Max 2 keyword searches
            console.print(f"  [dim]Keywords: {kw_set}[/dim]")
            try:
                results = await search_repos(session, kw_set, num_results=top)
                for r in results:
                    repo_url = r.get("html_url", r.get("url", r.get("full_name", "")))
                    if repo_url and repo_url not in seen_repos:
                        seen_repos.add(repo_url)
                        repos.append(r)
                log("search", keywords=kw_set, results_count=len(results))
            except Exception as e:  # noqa: BLE001
                console.print(f"  [yellow]Search failed: {e}[/yellow]")
                log("search_error", keywords=kw_set, error=str(e))

        finding["repos"] = repos[:top]
        console.print(f"  [green]{len(repos)} unique repos found[/green]")

        # Deep indexing: index the top repo and do semantic search
        if deep_index and repos and "create_research_repository" in tools:
            best = repos[0]
            repo_path = best.get("html_url", best.get("clone_url", ""))
            if repo_path:
                console.print(f"  [dim]Indexing {repo_path}...[/dim]")
                try:
                    idx_result = await index_repo(session, repo_path)
                    index_path = idx_result.get("index_path", "")
                    log("index", repo=repo_path, index_path=index_path)

                    if index_path and "search_research_repository" in tools:
                        console.print("  [dim]Semantic search in indexed repo...[/dim]")
                        semantic = await search_indexed_repo(
                            session,
                            index_path,
                            query,
                            limit=5,
                        )
                        finding["semantic_search"] = semantic
                        log("semantic_search", results_count=len(semantic))
                except Exception as e:  # noqa: BLE001
                    console.print(f"  [yellow]Indexing failed: {e}[/yellow]")
                    log("index_error", error=str(e))

        duration_ms = round((time.monotonic() - t0) * 1000)
        finding["duration_ms"] = duration_ms
        log("query_done", query=query, duration_ms=duration_ms)
        all_findings.append(finding)

    return all_findings


def _build_keywords(query: str) -> list[list[str]]:
    """Build keyword variations for GitHub search."""
    # Remove common filler words
    stop_words = {
        "the",
        "and",
        "for",
        "how",
        "to",
        "with",
        "on",
        "aws",
        "amazon",
        "using",
        "example",
        "sample",
        "code",
    }
    words = [w for w in query.lower().split() if w not in stop_words and len(w) > 1]

    # Primary: all significant words
    primary = words[:5]
    # Secondary: narrower (first 3 words)
    secondary = words[:3]

    variations = [primary]
    if secondary != primary:
        variations.append(secondary)

    return variations


# ── Output formatters ────────────────────────────────────────────────────────

_DATE_TRUNC_LEN = 10
_SNIPPET_MAX = 500


def _format_repo(lines: list[str], repo: dict[str, Any]) -> str | None:
    """Format a single repo entry. Returns URL if present, else None."""
    name = repo.get("full_name", repo.get("name", "Unknown"))
    url = repo.get("html_url", repo.get("url", ""))
    description = repo.get("description", "No description")
    stars = repo.get("stargazers_count", repo.get("stars", "N/A"))
    updated = repo.get("updated_at", repo.get("pushed_at", ""))
    language = repo.get("language", "")
    license_info = repo.get("license", {})
    license_name = ""
    if isinstance(license_info, dict):
        license_name = license_info.get("spdx_id", license_info.get("name", ""))

    lines.append(f"### {name}\n")
    lines.append(f"- **URL**: {url}")
    lines.append(f"- **Description**: {description}")
    lines.append(f"- **Stars**: {stars}")
    if language:
        lines.append(f"- **Language**: {language}")
    if license_name:
        lines.append(f"- **License**: {license_name}")
    if updated:
        updated_str = (
            updated[:_DATE_TRUNC_LEN]
            if len(str(updated)) >= _DATE_TRUNC_LEN
            else updated
        )
        lines.append(f"- **Last updated**: {updated_str}")
    lines.append("")
    return url or None


def _format_semantic_results(lines: list[str], semantic: list[dict[str, Any]]) -> None:
    """Format semantic search results section."""
    lines.append("### Deep Index Search Results\n")
    for hit in semantic[:5]:
        filepath = hit.get("filepath", hit.get("path", ""))
        snippet = hit.get("content", hit.get("snippet", ""))
        score = hit.get("score", "")
        lines.append(f"- **`{filepath}`**" + (f" (score: {score})" if score else ""))
        if snippet:
            if len(snippet) > _SNIPPET_MAX:
                snippet = snippet[:_SNIPPET_MAX] + "..."
            lines.append(f"  ```\n  {snippet}\n  ```")
    lines.append("")


def format_markdown(findings: list[dict[str, Any]]) -> str:
    """Render findings as a markdown GitHub research document."""
    lines: list[str] = [
        "# GitHub Repository Research\n",
        f"**Date**: {datetime.now(UTC).strftime('%Y-%m-%d')}",
        f"**Queries**: {len(findings)}\n",
    ]

    source_urls: list[tuple[str, str]] = []

    for finding in findings:
        query = finding["query"]
        repos = finding.get("repos", [])
        lines.append(f"## {query}\n")

        if not repos:
            lines.append("*No repositories found.*\n")
            continue

        for repo in repos:
            name = repo.get("full_name", repo.get("name", "Unknown"))
            url = _format_repo(lines, repo)
            if url:
                source_urls.append((url, name))

        semantic = finding.get("semantic_search", [])
        if semantic:
            _format_semantic_results(lines, semantic)

        lines.append("---\n")

    # Source URLs
    lines.append("## Source URLs\n")
    seen: set[str] = set()
    idx = 1
    for url, name in source_urls:
        if url and url not in seen:
            seen.add(url)
            lines.append(f"{idx}. {url} — {name}")
            idx += 1

    lines.append("")
    return "\n".join(lines)


def format_json(findings: list[dict[str, Any]]) -> str:
    return json.dumps(findings, indent=2, default=str)


# ── CLI ──────────────────────────────────────────────────────────────────────


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Search GitHub repos via MCP server and write results.",
    )
    p.add_argument(
        "-q",
        "--query",
        action="append",
        required=True,
        help="Search query (repeatable)",
    )
    p.add_argument(
        "-o",
        "--output",
        required=True,
        help="Output file path (.md or .json)",
    )
    p.add_argument(
        "-t",
        "--top",
        type=int,
        default=5,
        help="Max repos per query (default: 5)",
    )
    p.add_argument(
        "--deep-index",
        action="store_true",
        help="Index top repo and run semantic search",
    )
    p.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output JSON instead of markdown",
    )
    p.add_argument(
        "--log-dir",
        type=str,
        default=None,
        help="Directory to append research.log traces (JSON lines)",
    )
    return p.parse_args(argv)


async def main(args: argparse.Namespace) -> None:
    # Check GITHUB_TOKEN
    if not os.environ.get("GITHUB_TOKEN"):
        console.print(
            "[yellow]⚠ GITHUB_TOKEN not set — GitHub search may have limited results[/yellow]",
        )

    logger = ResearchLogger(Path(args.log_dir) if args.log_dir else None)
    t_start = time.monotonic()
    logger.log("start", queries=args.query, top=args.top, deep_index=args.deep_index)

    server_params = make_server_params()
    console.print("[bold]Connecting to git-repo-research-mcp-server...[/bold]")

    async with stdio_client(server_params) as (read_stream, write_stream):  # noqa: SIM117
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            console.print("[green]Connected.[/green]")
            logger.log("connected")

            # Discover available tools
            tools = await list_tools(session)
            console.print(f"  [dim]Available tools: {', '.join(tools)}[/dim]")
            logger.log("tools", tools=tools)

            findings = await research_github(
                session,
                args.query,
                top=args.top,
                deep_index=args.deep_index,
                logger=logger,
                available_tools=tools,
            )

    # Write output
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    text = format_json(findings) if args.json_output else format_markdown(findings)
    out_path.write_text(text, encoding="utf-8")  # noqa: ASYNC240
    console.print(f"[green]✓ Wrote {len(text):,} chars to {out_path}[/green]")

    # Summary
    total_repos = sum(len(f.get("repos", [])) for f in findings)
    summary = {
        "status": "success",
        "queries": len(findings),
        "repos_found": total_repos,
        "output_file": str(out_path),
        "output_size_chars": len(text),
    }

    duration_ms = round((time.monotonic() - t_start) * 1000)
    logger.log("done", **summary, duration_ms=duration_ms)
    logger.close()

    print(json.dumps(summary))


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(main(args))
