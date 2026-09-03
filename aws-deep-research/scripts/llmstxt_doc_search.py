# /// script
# requires-python = ">=3.13"
# dependencies = [
#   "mcp>=1.26.0",
#   "rich>=14.3.3",
# ]
# ///
"""
llms.txt Documentation Search - standalone MCP client (PRIMARY AWS-docs source).

Spawns the @praveenc/llmstxt-doc-search MCP server as a stdio child and runs
`search_docs` + `fetch_doc`. That server BM25-indexes the titles in each
registered `llms.txt` and fetches full doc content on demand, so it is the
fast, reliable primary source for AWS Bedrock, Bedrock AgentCore, and the
Well-Architected agentic-ai-lens guides (plus Strands, Kiro).

Portable: the server ships on npm, so `npx -y @praveenc/llmstxt-doc-search`
runs it on any host with Node - no absolute path, no per-machine config. Its
five default sources (aws-bedrock-userguide, aws-bedrock-agentcore-devguide,
aws-agentic-ai-lens, strands, kiro) seed on first run and persist to
~/.config/llmstxt-doc-search/sources.json. Override the launch command with
LLMSTXT_MCP_CMD (e.g. a local dev build) if desired.

This is the primary AWS-docs researcher path; scripts/aws_doc_search.py
(mcp-proxy-for-aws, SigV4) remains the fallback for general docs.aws.amazon.com
pages that no llms.txt source covers.

Designed to run inside a subagent so raw docs never enter the parent context.

Requires:
    - Node.js on PATH (for npx) - check with `node --version`
    - Network access (to fetch each llms.txt index and doc pages)

Usage:
    uv run llmstxt_doc_search.py -q "AgentCore Runtime IAM execution role" \
        -o output/research/agentcore/aws-docs.md
    uv run llmstxt_doc_search.py -q "prompt caching" \
        --source aws-bedrock-userguide -o out.md --top 3 --max-length 20000

Exit codes:
    0  at least one doc record written to -o
    1  a required tool is missing, or zero records across all queries
       (no -o file is written, so verify_findings.sh reports MISSING)
    2  connection / usage error
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shlex
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from rich.console import Console

console = Console(stderr=True)

# The server ships on npm; npx runs it anywhere Node is present. Overridable so
# a local dev build (node dist/index.js) or `npx tsx src/index.ts` can be used.
DEFAULT_MCP_CMD = ["npx", "-y", "@praveenc/llmstxt-doc-search"]
REQUIRED_TOOLS = {"search_docs", "fetch_doc"}
DEFAULT_MAX_LENGTH = 15000


# ── Logging ──────────────────────────────────────────────────────────────────


class ResearchLogger:
    """Append-only structured logger that writes to a research.log file."""

    def __init__(self, log_dir: Path | None) -> None:
        self.log_dir = log_dir
        self._fh = None
        if log_dir:
            log_dir.mkdir(parents=True, exist_ok=True)
            self._fh = open(log_dir / "research.log", "a", encoding="utf-8")

    def log(self, event: str, **data: Any) -> None:
        if not self._fh:
            return
        entry = {
            "ts": datetime.now(UTC).isoformat(),
            "script": "llmstxt_doc_search",
            "event": event,
            **data,
        }
        self._fh.write(json.dumps(entry, default=str) + "\n")
        self._fh.flush()

    def close(self) -> None:
        if self._fh:
            self._fh.close()


# ── Server config ──────────────────────────────────────────────────────────────


def make_server_params() -> StdioServerParameters:
    """Build server params for the llmstxt-doc-search MCP server.

    Uses `npx -y @praveenc/llmstxt-doc-search` by default (portable). Set
    LLMSTXT_MCP_CMD to a full command line to point at a local build.
    """
    override = os.environ.get("LLMSTXT_MCP_CMD", "").strip()
    cmd = shlex.split(override) if override else DEFAULT_MCP_CMD
    return StdioServerParameters(command=cmd[0], args=cmd[1:], env=dict(os.environ))


# ── MCP helpers ──────────────────────────────────────────────────────────────


async def call_tool(session: ClientSession, name: str, arguments: dict[str, Any]) -> Any:
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
    """Discover available tools on the llmstxt-doc-search server."""
    result = await session.list_tools()
    return [t.name for t in result.tools]


async def search(
    session: ClientSession,
    query: str,
    *,
    k: int,
    source: str | None = None,
) -> list[dict[str, Any]]:
    """search_docs → list of {source, url, title, score, snippet}."""
    arguments: dict[str, Any] = {"query": query, "k": k}
    if source:
        arguments["source"] = source
    raw = await call_tool(session, "search_docs", arguments)
    if isinstance(raw, dict):
        results = raw.get("results", [])
        return results if isinstance(results, list) else []
    if isinstance(raw, list):
        return raw
    return []


async def fetch(session: ClientSession, url: str) -> str:
    """fetch_doc → full markdown/HTML content of a result URL."""
    raw = await call_tool(session, "fetch_doc", {"url": url})
    if isinstance(raw, dict):
        return raw.get("content", raw.get("text", raw.get("markdown", str(raw))))
    return str(raw) if raw else ""


# ── Core research logic ───────────────────────────────────────────────────────


async def research_queries(
    session: ClientSession,
    queries: list[str],
    *,
    top: int = 3,
    max_length: int = DEFAULT_MAX_LENGTH,
    source: str | None = None,
    logger: ResearchLogger | None = None,
) -> list[dict[str, Any]]:
    """Run search + fetch for each query. Returns structured findings."""
    all_findings: list[dict[str, Any]] = []
    log = logger.log if logger else lambda *_a, **_kw: None

    for query in queries:
        console.print(f"[cyan]Searching:[/cyan] {query}")
        t0 = time.monotonic()
        results = await search(session, query, k=top + 2, source=source)
        search_ms = round((time.monotonic() - t0) * 1000)
        log("search", query=query, source=source, results_count=len(results), duration_ms=search_ms)

        if not results:
            console.print("  [yellow]No results[/yellow]")
            all_findings.append({"query": query, "results": []})
            continue

        console.print(f"  [green]{len(results)} results[/green]")
        query_results: list[dict[str, Any]] = []

        for hit in results[:top]:
            url = hit.get("url", "")
            entry: dict[str, Any] = {
                "url": url,
                "title": hit.get("title", ""),
                "source": hit.get("source", ""),
                "score": hit.get("score", ""),
                "snippet": hit.get("snippet", ""),
            }
            t1 = time.monotonic()
            content = await fetch(session, url) if url else ""
            read_ms = round((time.monotonic() - t1) * 1000)
            truncated = False
            if len(content) > max_length:
                content = content[:max_length]
                truncated = True
            entry["content"] = content
            entry["truncated"] = truncated
            log("read", url=url, chars=len(content), truncated=truncated, duration_ms=read_ms)
            query_results.append(entry)

        all_findings.append({"query": query, "results": query_results})

    return all_findings


# ── Output formatters ──────────────────────────────────────────────────────────


def format_markdown(findings: list[dict[str, Any]]) -> str:
    """Render findings as a markdown research document."""
    lines: list[str] = [
        "# AWS Documentation Research (llms.txt)\n",
        f"**Date**: {datetime.now(UTC).strftime('%Y-%m-%d')}",
        f"**Queries**: {len(findings)}\n",
    ]
    source_urls: list[tuple[str, str]] = []

    for group in findings:
        lines.append(f"## {group['query']}\n")
        results = group["results"]
        if not results:
            lines.append("*No results found.*\n")
            continue
        for entry in results:
            title = entry.get("title", "Untitled")
            url = entry.get("url", "")
            content = entry.get("content", "")
            lines.append(f"### {title}\n")
            lines.append(f"**Source**: {entry.get('source', '')}  ")
            lines.append(f"**URL**: {url}\n")
            if content:
                lines.append(f"{content}\n")
                if entry.get("truncated"):
                    lines.append("*[truncated - re-fetch with a larger --max-length for the full page]*\n")
            if url:
                source_urls.append((url, title))
        lines.append("---\n")

    lines.append("## Source URLs\n")
    seen: set[str] = set()
    idx = 1
    for url, title in source_urls:
        if url not in seen:
            seen.add(url)
            lines.append(f"{idx}. {url} - {title}")
            idx += 1
    lines.append("")
    return "\n".join(lines)


def format_json(findings: list[dict[str, Any]]) -> str:
    return json.dumps(findings, indent=2, default=str)


# ── CLI ────────────────────────────────────────────────────────────────────────


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Search AWS/Bedrock/AgentCore docs via the llmstxt-doc-search MCP server.",
    )
    p.add_argument("-q", "--query", action="append", required=True, help="Search query (repeatable)")
    p.add_argument("-o", "--output", required=True, help="Output file path (.md or .json)")
    p.add_argument("-t", "--top", type=int, default=3, help="Results to read per query (default: 3)")
    p.add_argument(
        "--source",
        default=None,
        help="Scope to one registered source (e.g. aws-bedrock-agentcore-devguide, "
        "aws-bedrock-userguide, aws-agentic-ai-lens). Omit to search all sources.",
    )
    p.add_argument(
        "--max-length",
        type=int,
        default=DEFAULT_MAX_LENGTH,
        help=f"Max chars per doc page (default: {DEFAULT_MAX_LENGTH})",
    )
    p.add_argument("--json", action="store_true", dest="json_output", help="Output JSON instead of markdown")
    p.add_argument("--log-dir", default=None, help="Directory to append research.log traces (JSON lines)")
    return p.parse_args(argv)


async def main(args: argparse.Namespace) -> int:
    logger = ResearchLogger(Path(args.log_dir) if args.log_dir else None)
    t_start = time.monotonic()
    logger.log("start", queries=args.query, source=args.source, max_length=args.max_length)

    server_params = make_server_params()
    console.print("[bold]Connecting to llmstxt-doc-search...[/bold]")

    async with stdio_client(server_params) as (read_stream, write_stream):  # noqa: SIM117
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            tools = await list_tools(session)
            logger.log("tools", tools=tools)

            # Fail fast if the server does not expose the tools we depend on,
            # instead of silently returning nothing and reporting success.
            missing = REQUIRED_TOOLS - set(tools)
            if missing:
                console.print(f"[red]Required tools missing: {sorted(missing)}[/red]")
                console.print(f"[dim]Available: {', '.join(tools)}[/dim]")
                logger.log("fatal", reason="missing_tools", missing=sorted(missing), available=tools)
                logger.close()
                print(json.dumps({"status": "failed", "reason": "missing_tools",
                                  "missing": sorted(missing)}))
                return 1

            console.print("[green]Connected.[/green]")
            findings = await research_queries(
                session,
                args.query,
                top=args.top,
                max_length=args.max_length,
                source=args.source,
                logger=logger,
            )

    total_pages = sum(len(g["results"]) for g in findings)

    # Fail fast on total failure: write no -o file so the size gate reports
    # MISSING and the subagent writes a SKIPPED note, rather than shipping an
    # empty "no results" file that passes the gate.
    if total_pages == 0:
        console.print("[red]Zero documents fetched across all queries.[/red]")
        logger.log("done", status="failed", queries=len(findings), pages_read=0,
                   duration_ms=round((time.monotonic() - t_start) * 1000))
        logger.close()
        print(json.dumps({"status": "failed", "reason": "no_results",
                          "queries": len(findings), "pages_read": 0}))
        return 1

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = format_json(findings) if args.json_output else format_markdown(findings)
    out_path.write_text(text, encoding="utf-8")
    console.print(f"[green]✓ Wrote {len(text):,} chars to {out_path}[/green]")

    total_sources = len({e["url"] for g in findings for e in g["results"] if e.get("url")})
    empty_queries = sum(1 for g in findings if not g["results"])
    summary = {
        "status": "partial" if empty_queries else "success",
        "queries": len(findings),
        "pages_read": total_pages,
        "unique_sources": total_sources,
        "empty_queries": empty_queries,
        "output_file": str(out_path),
        "output_size_chars": len(text),
    }
    logger.log("done", **summary, duration_ms=round((time.monotonic() - t_start) * 1000))
    logger.close()
    print(json.dumps(summary))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main(parse_args())))
    except (ConnectionError, OSError, RuntimeError) as exc:
        console.print(f"[red]llmstxt_doc_search failed: {exc}[/red]")
        print(json.dumps({"status": "failed", "reason": str(exc)}))
        sys.exit(2)
