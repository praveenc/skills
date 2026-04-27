# /// script
# requires-python = ">=3.13"
# dependencies = [
#   "mcp>=1.26.0",
#   "rich>=14.3.3",
# ]
# ///
"""
Bedrock AgentCore Documentation Search — standalone MCP client.

Spawns awslabs.amazon-bedrock-agentcore-mcp-server as a child process (stdio),
runs search_agentcore_docs + fetch_agentcore_doc calls, and writes condensed
results to a markdown file.

Usage:
    uv run agentcore_search.py -q "AgentCore Runtime deployment" \
        -q "AgentCore Memory integration" \
        -o output/research/agentcore-topic/agentcore.md

    uv run agentcore_search.py -q "AgentCore Gateway" -o out.md --top 3 --json
"""

from __future__ import annotations

import argparse
import asyncio
import json
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
            self._fh = open(log_dir / "research.log", "a", encoding="utf-8")

    def log(self, event: str, **data: Any) -> None:
        if not self._fh:
            return
        entry = {
            "ts": datetime.now(UTC).isoformat(),
            "script": "agentcore_search",
            "event": event,
            **data,
        }
        self._fh.write(json.dumps(entry, default=str) + "\n")
        self._fh.flush()

    def close(self) -> None:
        if self._fh:
            self._fh.close()


SERVER_PARAMS = StdioServerParameters(
    command="uvx",
    args=["awslabs.amazon-bedrock-agentcore-mcp-server@latest"],
    env={"FASTMCP_LOG_LEVEL": "ERROR"},
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


async def search_agentcore(
    session: ClientSession,
    query: str,
    *,
    k: int = 5,
) -> list[dict[str, Any]]:
    """search_agentcore_docs → list of {url, title, score, snippet}."""
    raw = await call_tool(session, "search_agentcore_docs", {"query": query, "k": k})
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        return raw.get("results", [raw])
    return []


async def fetch_doc(session: ClientSession, uri: str) -> str:
    """fetch_agentcore_doc → full document content."""
    raw = await call_tool(session, "fetch_agentcore_doc", {"uri": uri})
    if isinstance(raw, dict):
        return raw.get("content", str(raw))
    return str(raw) if raw else ""


# ── Core research logic ─────────────────────────────────────────────────────


async def research_queries(
    session: ClientSession,
    queries: list[str],
    *,
    top: int = 3,
    logger: ResearchLogger | None = None,
) -> list[dict[str, Any]]:
    """Run search + fetch for each query. Returns structured findings."""
    all_findings: list[dict[str, Any]] = []
    log = logger.log if logger else lambda *a, **kw: None

    for query in queries:
        console.print(f"[cyan]Searching:[/cyan] {query}")
        t0 = time.monotonic()
        results = await search_agentcore(session, query, k=top + 2)
        search_ms = round((time.monotonic() - t0) * 1000)

        log("search", query=query, results_count=len(results), duration_ms=search_ms)

        if not results:
            console.print("  [yellow]No results[/yellow]")
            all_findings.append({"query": query, "results": []})
            continue

        console.print(f"  [green]{len(results)} results[/green]")
        query_results: list[dict[str, Any]] = []

        for hit in results[:top]:
            url = hit.get("url", "")
            title = hit.get("title", "")
            snippet = hit.get("snippet", "")
            score = hit.get("score", 0)

            entry: dict[str, Any] = {
                "url": url,
                "title": title,
                "snippet": snippet,
                "score": score,
            }

            if url:
                console.print(f"  [dim]Fetching {url}[/dim]")
                t1 = time.monotonic()
                content = await fetch_doc(session, url)
                read_ms = round((time.monotonic() - t1) * 1000)
                # Truncate very long pages
                if len(content) > 6000:
                    content = content[:6000] + "\n\n*[truncated]*"
                entry["content"] = content
                log("fetch", url=url, chars=len(content), duration_ms=read_ms)
            else:
                entry["content"] = snippet

            query_results.append(entry)

        all_findings.append({"query": query, "results": query_results})

    return all_findings


# ── Output formatters ────────────────────────────────────────────────────────


def format_markdown(findings: list[dict[str, Any]]) -> str:
    """Render findings as markdown."""
    lines: list[str] = [
        "# AgentCore Documentation Research\n",
        f"**Date**: {datetime.now(UTC).strftime('%Y-%m-%d')}",
        f"**Queries**: {len(findings)}\n",
    ]

    source_urls: list[tuple[str, str]] = []

    for group in findings:
        query = group["query"]
        results = group["results"]
        lines.append(f"## {query}\n")

        if not results:
            lines.append("*No results found.*\n")
            continue

        for entry in results:
            title = entry.get("title", "Untitled")
            url = entry.get("url", "")
            content = entry.get("content", "")
            snippet = entry.get("snippet", "")

            lines.append(f"### {title}\n")
            if url:
                lines.append(f"**URL**: {url}\n")
            if snippet:
                lines.append(f"**Summary**: {snippet[:300]}\n")
            if content:
                lines.append(f"{content}\n")
            if url:
                source_urls.append((url, title))

        lines.append("---\n")

    lines.append("## Source URLs\n")
    seen: set[str] = set()
    idx = 1
    for url, title in source_urls:
        if url not in seen:
            seen.add(url)
            lines.append(f"{idx}. {url} — {title}")
            idx += 1

    lines.append("")
    return "\n".join(lines)


def format_json(findings: list[dict[str, Any]]) -> str:
    return json.dumps(findings, indent=2, default=str)


# ── CLI ──────────────────────────────────────────────────────────────────────


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Search AgentCore docs via local MCP server.",
    )
    p.add_argument(
        "-q",
        "--query",
        action="append",
        required=True,
        help="Search query (repeatable)",
    )
    p.add_argument("-o", "--output", required=True, help="Output file path")
    p.add_argument(
        "-t",
        "--top",
        type=int,
        default=3,
        help="Results to fetch per query (default: 3)",
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
    logger = ResearchLogger(Path(args.log_dir) if args.log_dir else None)
    t_start = time.monotonic()
    logger.log("start", queries=args.query, top=args.top)

    console.print("[bold]Connecting to bedrock-agentcore-mcp-server...[/bold]")

    async with stdio_client(SERVER_PARAMS) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            console.print("[green]Connected.[/green]")
            logger.log("connected")

            findings = await research_queries(
                session,
                args.query,
                top=args.top,
                logger=logger,
            )

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    text = format_json(findings) if args.json_output else format_markdown(findings)
    out_path.write_text(text, encoding="utf-8")
    console.print(f"[green]✓ Wrote {len(text):,} chars to {out_path}[/green]")

    total_pages = sum(len(g["results"]) for g in findings)
    total_sources = len(
        {e["url"] for g in findings for e in g["results"] if e.get("url")},
    )
    summary = {
        "status": "success",
        "queries": len(findings),
        "pages_read": total_pages,
        "unique_sources": total_sources,
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
