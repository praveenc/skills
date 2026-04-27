# /// script
# requires-python = ">=3.13"
# dependencies = [
#   "mcp>=1.26.0",
#   "rich>=14.3.3",
# ]
# ///
"""
AWS Documentation Search — standalone MCP client.

Connects to the AWS MCP Server (Preview) via mcp-proxy-for-aws, which handles
SigV4 authentication using local AWS credentials. Runs aws___search_documentation
+ aws___read_documentation calls and writes condensed results to a markdown file.

Designed to run inside a subagent so that raw documentation never enters the
parent agent's context window.

Requires:
    - AWS credentials configured (aws configure / SSO / env vars)
    - mcp-proxy-for-aws (auto-installed via uvx)

Usage:
    uv run aws_doc_search.py -q "Aurora Optimized Reads" -q "Aurora instance types" \
        -o output/research/aurora/aws-docs.md

    uv run aws_doc_search.py -q "What is Amazon Bedrock" \
        -o output/research/bedrock/aws-docs.md --top 2 --json

    uv run aws_doc_search.py -q "S3 Files" -o out.md --region us-west-2
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
            self._fh = open(log_dir / "research.log", "a", encoding="utf-8")

    def log(self, event: str, **data: Any) -> None:
        if not self._fh:
            return
        entry = {
            "ts": datetime.now(UTC).isoformat(),
            "script": "aws_doc_search",
            "event": event,
            **data,
        }
        self._fh.write(json.dumps(entry, default=str) + "\n")
        self._fh.flush()

    def close(self) -> None:
        if self._fh:
            self._fh.close()


# ── Server config ────────────────────────────────────────────────────────────────────────

AWS_MCP_ENDPOINT = "https://aws-mcp.us-east-1.api.aws/mcp"


def make_server_params(region: str = "us-east-1", profile: str | None = None) -> StdioServerParameters:
    """Build server params for mcp-proxy-for-aws connecting to AWS MCP Server."""
    env = {
        k: v
        for k, v in os.environ.items()
        if k.startswith(("AWS_", "HOME", "PATH", "USER"))
    }
    env["AWS_REGION"] = region
    if profile:
        env["AWS_PROFILE"] = profile

    args = [
        "mcp-proxy-for-aws@latest",
        AWS_MCP_ENDPOINT,
        "--metadata",
        f"AWS_REGION={region}",
        "--log-level",
        "ERROR",
    ]
    if profile:
        args.extend(["--profile", profile])

    return StdioServerParameters(command="uvx", args=args, env=env)


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


async def search_docs(
    session: ClientSession,
    query: str,
    *,
    limit: int = 10,
    topics: list[str] | None = None,
) -> list[dict[str, Any]]:
    """aws___search_documentation → list of {url, title, context, sections}."""
    arguments: dict[str, Any] = {"search_phrase": query, "limit": limit}
    if topics:
        arguments["topics"] = topics
    raw = await call_tool(
        session,
        "aws___search_documentation",
        arguments,
    )
    if isinstance(raw, dict):
        # Handle nested result structure
        result = raw.get("content", raw).get("result", raw.get("search_results", []))
        if isinstance(result, list):
            return result
        return raw.get("search_results", [])
    if isinstance(raw, list):
        return raw
    return []


async def read_doc(
    session: ClientSession,
    url: str,
    *,
    max_length: int = 5000,
) -> str:
    """aws___read_documentation → markdown string."""
    raw = await call_tool(
        session,
        "aws___read_documentation",
        {"url": url, "max_length": max_length},
    )
    if isinstance(raw, dict):
        return raw.get("result", str(raw))
    return str(raw) if raw else ""


# ── Core research logic ─────────────────────────────────────────────────────


async def research_queries(
    session: ClientSession,
    queries: list[str],
    *,
    top: int = 3,
    max_length: int = 5000,
    topics: list[str] | None = None,
    logger: ResearchLogger | None = None,
) -> list[dict[str, Any]]:
    """Run search + read for each query.  Returns structured findings."""
    all_findings: list[dict[str, Any]] = []
    log = logger.log if logger else lambda *a, **kw: None

    for query in queries:
        console.print(f"[cyan]Searching:[/cyan] {query}")
        t0 = time.monotonic()
        results = await search_docs(session, query, limit=top + 2, topics=topics)
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
            context = hit.get("context", "")
            sections_available = hit.get("sections", [])

            entry: dict[str, Any] = {
                "url": url,
                "title": title,
                "context": context,
            }

            # Read full page
            t1 = time.monotonic()
            if url:
                console.print(f"  [dim]Reading {url}[/dim]")
                content = await read_doc(session, url, max_length=max_length)
            else:
                content = ""
            read_ms = round((time.monotonic() - t1) * 1000)

            log("read", url=url, chars=len(content), duration_ms=read_ms)

            entry["content"] = content
            entry["sections_available"] = sections_available
            query_results.append(entry)

        all_findings.append({"query": query, "results": query_results})

    return all_findings


# ── Output formatters ────────────────────────────────────────────────────────


def format_markdown(findings: list[dict[str, Any]]) -> str:
    """Render findings as a markdown research document."""
    lines: list[str] = [
        "# AWS Documentation Research\n",
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
            context = entry.get("context", "")

            lines.append(f"### {title}\n")
            lines.append(f"**URL**: {url}\n")

            if context:
                lines.append(
                    f"**Summary**: {context[:300]}{'...' if len(context) > 300 else ''}\n",
                )

            if content:
                # Truncate very long pages to keep output manageable
                if len(content) > 6000:
                    content = (
                        content[:6000]
                        + "\n\n*[truncated — full page available at URL]*"
                    )
                lines.append(f"{content}\n")

            if url:
                source_urls.append((url, title))

        lines.append("---\n")

    # Deduplicated source list
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
    """Render findings as JSON."""
    return json.dumps(findings, indent=2, default=str)


# ── CLI ──────────────────────────────────────────────────────────────────────


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Search AWS docs via AWS MCP Server (Preview) and write results.",
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
        default=3,
        help="Number of results to read per query (default: 3)",
    )
    p.add_argument(
        "--region",
        type=str,
        default="us-east-1",
        help="AWS region for the MCP server (default: us-east-1)",
    )
    p.add_argument(
        "--profile",
        type=str,
        default=None,
        help="AWS profile name (default: uses AWS_PROFILE env var or default)",
    )
    p.add_argument(
        "--topics",
        type=str,
        default=None,
        help="Comma-separated doc topics to search: reference_documentation,current_awareness,"
        "troubleshooting,amplify_docs,cdk_docs,cdk_constructs,cloudformation,agent_sops,general",
    )
    p.add_argument(
        "--max-length",
        type=int,
        default=5000,
        help="Max chars per doc page (default: 5000)",
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
    logger.log("start", queries=args.query, top=args.top, max_length=args.max_length)

    server_params = make_server_params(args.region, args.profile)
    console.print(
        f"[bold]Connecting to AWS MCP Server (region={args.region})...[/bold]",
    )

    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            console.print("[green]Connected.[/green]")
            logger.log("connected")

            topics_list = [t.strip() for t in args.topics.split(",")] if args.topics else None

            findings = await research_queries(
                session,
                args.query,
                top=args.top,
                max_length=args.max_length,
                topics=topics_list,
                logger=logger,
            )

    # Write output
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if args.json_output:
        text = format_json(findings)
    else:
        text = format_markdown(findings)

    out_path.write_text(text, encoding="utf-8")
    console.print(f"[green]✓ Wrote {len(text):,} chars to {out_path}[/green]")

    # Print brief summary to stdout for the calling agent
    total_pages = sum(len(g["results"]) for g in findings)
    total_sources = len(
        {entry["url"] for g in findings for entry in g["results"] if entry.get("url")},
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
