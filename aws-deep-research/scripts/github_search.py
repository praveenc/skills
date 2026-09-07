# /// script
# requires-python = ">=3.13"
# dependencies = [
#   "requests>=2.32",
#   "rich>=14.3.3",
# ]
# ///
"""
GitHub Repository Search - direct GitHub REST API client.

Calls the GitHub REST "Search repositories" endpoint directly (no MCP hop,
no Bedrock dependency) and writes condensed results to a markdown file.
Designed to run inside a subagent so that raw repo data never enters the
parent agent's context window.

Requires:
    - GITHUB_TOKEN environment variable (a GitHub personal access token)

Usage:
    uv run github_search.py -q "bedrock agents sample" \
        -o output/research/bedrock-agents/github-repos.md

    uv run github_search.py -q "serverless patterns" -q "lambda cdk examples" \
        -o output/research/serverless/github-repos.md --top 5 --json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from rich.console import Console

console = Console(stderr=True)

GITHUB_SEARCH_URL = "https://api.github.com/search/repositories"
REQUEST_TIMEOUT = 20


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


# ── GitHub REST helpers ──────────────────────────────────────────────────────


def fetch_repos(
    query: str,
    token: str,
    top: int,
    *,
    logger: ResearchLogger,
) -> tuple[list[dict[str, Any]], str]:
    """GET /search/repositories for one query.

    Returns (raw repo items, status). status is one of "ok", "rate_limited",
    or "error" (any other non-200 response). Raises requests.RequestException
    on a network failure - the caller treats that as fatal.
    """
    import requests  # deferred: keeps this module importable without requests installed

    resp = requests.get(
        GITHUB_SEARCH_URL,
        params={"q": query, "sort": "stars", "order": "desc", "per_page": top},
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        timeout=REQUEST_TIMEOUT,
    )

    if resp.status_code == 200:
        return resp.json().get("items", []), "ok"

    if resp.status_code in (403, 429) and resp.headers.get("X-RateLimit-Remaining") == "0":
        logger.log("rate_limited", query=query, status_code=resp.status_code)
        return [], "rate_limited"

    logger.log(
        "http_error",
        query=query,
        status_code=resp.status_code,
        body=resp.text[:300],
    )
    return [], "error"


def extract_repo(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize a raw GitHub search-result repo object to the fields we keep."""
    license_info = raw.get("license") or {}
    return {
        "full_name": raw.get("full_name", ""),
        "html_url": raw.get("html_url", ""),
        "description": raw.get("description") or "",
        "stargazers_count": raw.get("stargazers_count", 0),
        "language": raw.get("language") or "",
        "license": license_info.get("spdx_id") or "unknown",
        "pushed_at": raw.get("pushed_at", ""),
        "topics": raw.get("topics", []),
    }


# ── Core research logic ─────────────────────────────────────────────────────


def research_github(
    queries: list[str],
    token: str,
    *,
    top: int,
    logger: ResearchLogger,
) -> list[dict[str, Any]]:
    """Run a GitHub repo search for each query. Returns structured findings."""
    findings: list[dict[str, Any]] = []

    for query in queries:
        console.print(f"[cyan]Searching GitHub:[/cyan] {query}")
        t0 = time.monotonic()
        items, status = fetch_repos(query, token, top, logger=logger)
        duration_ms = round((time.monotonic() - t0) * 1000)
        logger.log(
            "search",
            query=query,
            status=status,
            results_count=len(items),
            duration_ms=duration_ms,
        )

        if status == "rate_limited":
            console.print("  [yellow]Rate limited - skipping[/yellow]")
        elif status == "error":
            console.print("  [yellow]Search failed - skipping[/yellow]")
        elif not items:
            console.print("  [yellow]No results[/yellow]")
        else:
            console.print(f"  [green]{len(items)} repos found[/green]")

        findings.append(
            {"query": query, "repos": [extract_repo(r) for r in items]},
        )

    return findings


# ── Output formatters ────────────────────────────────────────────────────────


def _format_repo(lines: list[str], repo: dict[str, Any]) -> None:
    lines.append(f"### {repo['full_name']}\n")
    lines.append(f"- **URL**: {repo['html_url']}")
    lines.append(f"- **Stars**: {repo['stargazers_count']}")
    lines.append(f"- **Language**: {repo['language'] or 'unknown'}")
    lines.append(f"- **License**: {repo['license']}")
    lines.append(f"- **Updated**: {repo['pushed_at']}")
    lines.append(f"- **Description**: {repo['description'] or 'No description'}")
    if repo.get("topics"):
        lines.append(f"- **Topics**: {', '.join(repo['topics'])}")
    lines.append("")


def format_markdown(findings: list[dict[str, Any]]) -> str:
    """Render findings as a markdown GitHub research document."""
    lines: list[str] = [
        "# GitHub Repository Research\n",
        f"**Date**: {datetime.now(UTC).strftime('%Y-%m-%d')}",
        f"**Queries**: {len(findings)}\n",
    ]

    source_urls: list[str] = []

    for finding in findings:
        lines.append(f"## {finding['query']}\n")
        repos = finding.get("repos", [])

        if not repos:
            lines.append("*No repositories found.*\n")
            continue

        for repo in repos:
            _format_repo(lines, repo)
            if repo.get("html_url"):
                source_urls.append(repo["html_url"])

        lines.append("---\n")

    # Deduplicated source list
    lines.append("## Source URLs\n")
    seen: set[str] = set()
    idx = 1
    for url in source_urls:
        if url not in seen:
            seen.add(url)
            lines.append(f"{idx}. {url}")
            idx += 1

    lines.append("")
    return "\n".join(lines)


def format_json(findings: list[dict[str, Any]]) -> str:
    """Render findings as JSON."""
    return json.dumps(findings, indent=2, default=str)


# ── CLI ──────────────────────────────────────────────────────────────────────


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Search GitHub repositories via the REST API and write results.",
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
        "--top",
        type=int,
        default=5,
        help="Max repos per query (default: 5)",
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


def main(args: argparse.Namespace) -> int:
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if not token:
        console.print("[red]GITHUB_TOKEN is not set[/red]")
        print(json.dumps({"status": "failed", "reason": "no_github_token"}))
        return 1

    logger = ResearchLogger(Path(args.log_dir) if args.log_dir else None)
    t_start = time.monotonic()
    logger.log("start", queries=args.query, top=args.top)

    import requests  # deferred: keeps this module importable without requests installed

    try:
        findings = research_github(args.query, token, top=args.top, logger=logger)
    except requests.RequestException as e:
        summary = {"status": "failed", "reason": f"network_error: {e}"}
        logger.log("network_error", error=str(e))
        logger.close()
        print(json.dumps(summary))
        return 2

    total_repos = sum(len(f["repos"]) for f in findings)

    if total_repos == 0:
        summary = {
            "status": "failed",
            "reason": "no_results",
            "queries": len(findings),
        }
        logger.log(
            "done",
            **summary,
            duration_ms=round((time.monotonic() - t_start) * 1000),
        )
        logger.close()
        print(json.dumps(summary))
        return 1

    # Write output
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    text = format_json(findings) if args.json_output else format_markdown(findings)
    out_path.write_text(text, encoding="utf-8")
    console.print(f"[green]Wrote {len(text):,} chars to {out_path}[/green]")

    any_empty = any(len(f["repos"]) == 0 for f in findings)
    summary = {
        "status": "partial" if any_empty else "success",
        "queries": len(findings),
        "repos_found": total_repos,
        "output_file": str(out_path),
        "output_size_chars": len(text),
    }

    duration_ms = round((time.monotonic() - t_start) * 1000)
    logger.log("done", **summary, duration_ms=duration_ms)
    logger.close()

    print(json.dumps(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main(parse_args()))
