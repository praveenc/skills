# /// script
# requires-python = ">=3.13"
# dependencies = [
#   "mcp>=1.26.0",
#   "rich>=14.3.3",
# ]
# ///
"""
AWS Pricing Search - standalone MCP client.

Spawns awslabs.aws-pricing-mcp-server as a child process (stdio),
runs service discovery + pricing queries, and writes condensed results
to a markdown file.  Designed to run inside a subagent so that raw
pricing data never enters the parent agent's context window.

The script automates the interactive exploration pattern:
  1. Discover services matching the query
  2. Get pricing attributes for each service
  3. Query pricing with appropriate filters
  4. Format results with tables and cost estimates

Usage:
    uv run aws_pricing_search.py -q "EC2 m7i instance pricing us-east-1" \
        -o output/research/ec2-pricing/aws-pricing.md

    uv run aws_pricing_search.py -q "S3 storage pricing" \
        -q "S3 request pricing" \
        -o output/research/s3-costs/aws-pricing.md --json

    uv run aws_pricing_search.py -q "Compare RDS Aurora vs RDS MySQL pricing" \
        -o output/research/rds-compare/aws-pricing.md --region us-west-2
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
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
            "script": "aws_pricing_search",
            "event": event,
            **data,
        }
        self._fh.write(json.dumps(entry, default=str) + "\n")
        self._fh.flush()

    def close(self) -> None:
        if self._fh:
            self._fh.close()


# ── Server config ────────────────────────────────────────────────────────────


def make_server_params(region: str = "us-east-1") -> StdioServerParameters:
    """Build server params with the appropriate AWS region."""
    env = {
        "FASTMCP_LOG_LEVEL": "ERROR",
        "AWS_REGION": region,
    }
    # Forward AWS credentials from environment
    for key in (
        "AWS_PROFILE",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "AWS_DEFAULT_REGION",
    ):
        val = os.environ.get(key)
        if val:
            env[key] = val
    # Override region for pricing API (must be us-east-1 or ap-south-1)
    env["AWS_REGION"] = region

    return StdioServerParameters(
        command="uvx",
        args=["awslabs.aws-pricing-mcp-server@latest"],
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
    """Discover available tools on the pricing server."""
    result = await session.list_tools()
    return [t.name for t in result.tools]


# Tools the aws-pricing-mcp-server (awslabs.aws-pricing-mcp-server) actually
# registers. The prior code called discover_services/get_products/
# compare_pricing/generate_cost_report(ServiceCode=...), none of which exist on
# the server, so every run returned zero products while reporting success.
REQUIRED_TOOLS = {"get_pricing"}


async def discover_service_codes(session: ClientSession, keyword: str) -> list[str]:
    """get_pricing_service_codes(filter=<regex>) → matching AWS service codes."""
    raw = await call_tool(session, "get_pricing_service_codes", {"filter": keyword})
    if isinstance(raw, list):
        return [c for c in raw if isinstance(c, str)]
    if isinstance(raw, dict):
        codes = raw.get("service_codes") or raw.get("result") or raw.get("data") or []
        return [c for c in codes if isinstance(c, str)] if isinstance(codes, list) else []
    return []


async def get_pricing_data(
    session: ClientSession,
    service_code: str,
    region: str,
    *,
    max_results: int = 15,
    max_chars: int = 50000,
) -> dict[str, Any]:
    """get_pricing(...) → {status, service_name, data:[items], ...} or an error dict.

    On success the pricing items are under `data`; each item carries the Price
    List `product.attributes` and `terms.OnDemand...priceDimensions` that
    _format_product renders into $/unit lines. On empty/too-large/invalid the
    server returns an error dict with a `message`, which we surface verbatim.
    """
    raw = await call_tool(
        session,
        "get_pricing",
        {
            "service_code": service_code,
            "region": region,
            "max_results": max_results,
            "max_allowed_characters": max_chars,
        },
    )
    return raw if isinstance(raw, dict) else {"status": "error", "raw": raw}


# ── Core research logic ─────────────────────────────────────────────────────


async def research_pricing(
    session: ClientSession,
    queries: list[str],
    *,
    region: str = "us-east-1",
    max_results: int = 15,
    logger: ResearchLogger | None = None,
    available_tools: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Run pricing research for each query. Returns structured findings."""
    all_findings: list[dict[str, Any]] = []
    log = logger.log if logger else lambda *_a, **_kw: None
    tools = set(available_tools or [])
    can_discover = "get_pricing_service_codes" in tools

    for query in queries:
        console.print(f"[cyan]Researching pricing:[/cyan] {query}")
        finding: dict[str, Any] = {"query": query, "region": region}
        t0 = time.monotonic()

        # Step 1: resolve query keywords to AWS service codes. Known names
        # (ec2 → AmazonEC2) map directly; unknown terms are discovered via
        # get_pricing_service_codes when the tool is available.
        service_codes: list[str] = []
        seen: set[str] = set()
        for cand in _extract_service_keywords(query)[:3]:
            if cand in KNOWN_CODES:
                resolved = [cand]
            elif can_discover:
                try:
                    resolved = (await discover_service_codes(session, cand))[:2]
                    log("discover", keyword=cand, results_count=len(resolved))
                except Exception as e:  # noqa: BLE001
                    console.print(f"  [yellow]Discovery failed for {cand}: {e}[/yellow]")
                    log("discover_error", keyword=cand, error=str(e))
                    resolved = []
            else:
                resolved = [cand]  # best effort: treat the token as a code
            for sc in resolved:
                if sc not in seen:
                    seen.add(sc)
                    service_codes.append(sc)

        finding["service_codes"] = service_codes

        # Step 2: query pricing for each resolved service code.
        pricing_results: list[dict[str, Any]] = []
        for sc in service_codes[:3]:
            console.print(f"  [dim]Querying pricing for: {sc}[/dim]")
            try:
                data = await get_pricing_data(session, sc, region, max_results=max_results)
                items = data.get("data") if isinstance(data.get("data"), list) else []
                status = data.get("status", "success" if items else "empty")
                pricing_results.append(
                    {
                        "service_code": sc,
                        "status": status,
                        "data": items,
                        "message": data.get("message") or data.get("error_type") or "",
                    },
                )
                log("pricing", service=sc, status=status, products_count=len(items))
            except Exception as e:  # noqa: BLE001
                console.print(f"  [yellow]Pricing query failed for {sc}: {e}[/yellow]")
                log("pricing_error", service=sc, error=str(e))
                pricing_results.append({"service_code": sc, "status": "error", "data": [], "message": str(e)})

        finding["pricing"] = pricing_results
        finding["products_count"] = sum(len(p["data"]) for p in pricing_results)
        finding["duration_ms"] = round((time.monotonic() - t0) * 1000)
        log("query_done", query=query, products=finding["products_count"], duration_ms=finding["duration_ms"])
        all_findings.append(finding)

    return all_findings


# Common AWS service names → Price List service codes. Values are valid
# `service_code` inputs to get_pricing; a query term not found here is resolved
# via get_pricing_service_codes at runtime.
SERVICE_MAP = {
    "ec2": "AmazonEC2",
    "s3": "AmazonS3",
    "rds": "AmazonRDS",
    "aurora": "AmazonRDS",
    "lambda": "AWSLambda",
    "dynamodb": "AmazonDynamoDB",
    "ecs": "AmazonECS",
    "eks": "AmazonEKS",
    "fargate": "AmazonECS",
    "bedrock": "AmazonBedrock",
    "sagemaker": "AmazonSageMaker",
    "opensearch": "AmazonES",
    "elasticache": "AmazonElastiCache",
    "cloudfront": "AmazonCloudFront",
    "redshift": "AmazonRedshift",
    "kinesis": "AmazonKinesis",
    "emr": "ElasticMapReduce",
    "msk": "AmazonMSK",
    "neptune": "AmazonNeptune",
    "documentdb": "AmazonDocDB",
    "memorydb": "AmazonMemoryDB",
    "api gateway": "AmazonApiGateway",
    "step functions": "AWSStepFunctions",
    "eventbridge": "AmazonEventBridge",
    "sqs": "AWSQueueService",
    "sns": "AmazonSNS",
    "glue": "AWSGlue",
    "athena": "AmazonAthena",
}
KNOWN_CODES = frozenset(SERVICE_MAP.values())

_STOP_WORDS = frozenset({
    "the", "and", "for", "how", "much", "does", "cost", "pricing",
    "price", "compare", "between", "aws", "amazon", "region",
})


def _extract_service_keywords(query: str) -> list[str]:
    """Map a pricing query to candidate service codes, else salient keywords."""
    query_lower = query.lower()
    keywords = [code for name, code in SERVICE_MAP.items() if name in query_lower]
    if not keywords:
        # No known service matched: fall back to salient query words. The prior
        # predicate `len(w) > 2 and {set literal}` was always true (a non-empty
        # set is truthy), so no stop word was ever filtered - fixed here.
        keywords = [
            w for w in query.split()
            if len(w) > 2 and w.lower() not in _STOP_WORDS  # noqa: PLR2004
        ][:3]
    return keywords


# ── Output formatters ────────────────────────────────────────────────────────

_COMPACT_JSON_MAX = 1000


def _format_pricing_section(lines: list[str], pricing: list[dict[str, Any]]) -> None:
    """Format pricing data (the `data` list from get_pricing) per service."""
    for p in pricing:
        sc = p.get("service_code", "Unknown")
        lines.append(f"### Pricing: {sc}\n")

        items = p.get("data", [])
        if not items:
            msg = p.get("message") or p.get("status") or "no results"
            lines.append(f"*No pricing returned ({p.get('status', 'empty')}): {str(msg)[:400]}*\n")
            continue

        for prod in items[:10]:
            if isinstance(prod, dict):
                _format_product(lines, prod)
            else:
                lines.append(f"- {str(prod)[:500]}")
        lines.append("")


def format_markdown(findings: list[dict[str, Any]], region: str) -> str:
    """Render findings as a markdown pricing research document."""
    lines: list[str] = [
        "# AWS Pricing Research\n",
        f"**Date**: {datetime.now(UTC).strftime('%Y-%m-%d')}",
        f"**Region**: {region}",
        f"**Queries**: {len(findings)}\n",
    ]

    for finding in findings:
        lines.append(f"## {finding['query']}\n")

        codes = finding.get("service_codes", [])
        if codes:
            lines.append(f"**Service codes**: {', '.join(codes)}\n")

        pricing = finding.get("pricing", [])
        if pricing:
            _format_pricing_section(lines, pricing)
        else:
            lines.append("*No service codes resolved for this query.*\n")

        lines.append("---\n")

    lines.append("")
    return "\n".join(lines)


def _format_product(lines: list[str], prod: dict[str, Any]) -> None:
    """Format a single pricing product entry."""
    # Try to extract useful fields from various pricing response formats
    attrs = prod.get("attributes", prod.get("product", {}).get("attributes", {}))
    terms = prod.get("terms", {})

    if attrs:
        desc = attrs.get("instanceType", attrs.get("usagetype", attrs.get("group", "")))
        location = attrs.get("location", attrs.get("regionCode", ""))
        lines.append(f"**{desc}** ({location})")

        # Extract price from terms
        for term_type in ("OnDemand", "Reserved"):
            term_data = terms.get(term_type, {})
            for _, offer in term_data.items() if isinstance(term_data, dict) else []:
                if isinstance(offer, dict):
                    for dim in offer.get("priceDimensions", {}).values():
                        price = dim.get("pricePerUnit", {}).get("USD", "N/A")
                        unit = dim.get("unit", "")
                        desc_text = dim.get("description", "")
                        lines.append(f"  - {term_type}: ${price}/{unit} - {desc_text}")

    elif "raw" in prod:
        lines.append(f"- {str(prod['raw'])[:500]}")
    else:
        # Compact JSON fallback
        compact = json.dumps(prod, default=str)
        if len(compact) > _COMPACT_JSON_MAX:
            compact = compact[:_COMPACT_JSON_MAX] + "..."
        lines.append(f"```json\n{compact}\n```")

    lines.append("")


def format_json(findings: list[dict[str, Any]]) -> str:
    """Render findings as JSON."""
    return json.dumps(findings, indent=2, default=str)


# ── CLI ──────────────────────────────────────────────────────────────────────


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Search AWS pricing via local MCP server and write results.",
    )
    p.add_argument(
        "-q",
        "--query",
        action="append",
        required=True,
        help="Pricing query (repeatable)",
    )
    p.add_argument(
        "-o",
        "--output",
        required=True,
        help="Output file path (.md or .json)",
    )
    p.add_argument(
        "-r",
        "--region",
        default="us-east-1",
        help="AWS region for pricing queries (default: us-east-1)",
    )
    p.add_argument(
        "--max-results",
        type=int,
        default=15,
        help="Max pricing results per service (default: 15)",
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


async def main(args: argparse.Namespace) -> int:
    logger = ResearchLogger(Path(args.log_dir) if args.log_dir else None)
    t_start = time.monotonic()
    logger.log("start", queries=args.query, region=args.region)

    server_params = make_server_params(args.region)
    console.print(
        f"[bold]Connecting to aws-pricing-mcp-server (region={args.region})...[/bold]",
    )

    async with stdio_client(server_params) as (read_stream, write_stream):  # noqa: SIM117
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            console.print("[green]Connected.[/green]")
            logger.log("connected")

            tools = await list_tools(session)
            logger.log("tools", tools=tools)

            # Fail fast if the pricing server does not expose the tools we call,
            # instead of returning zero products while reporting success.
            missing = REQUIRED_TOOLS - set(tools)
            if missing:
                console.print(f"[red]Required tools missing: {sorted(missing)}[/red]")
                console.print(f"[dim]Available: {', '.join(tools)}[/dim]")
                logger.log("fatal", reason="missing_tools", missing=sorted(missing), available=tools)
                logger.close()
                print(json.dumps({"status": "failed", "reason": "missing_tools",
                                  "missing": sorted(missing)}))
                return 1

            findings = await research_pricing(
                session,
                args.query,
                region=args.region,
                max_results=args.max_results,
                logger=logger,
                available_tools=tools,
            )

    total_products = sum(f.get("products_count", 0) for f in findings)

    # Fail fast on total failure: write no -o file so the size gate reports
    # MISSING and the subagent writes a SKIPPED note, rather than shipping an
    # empty pricing file that passes the gate and reads as success.
    if total_products == 0:
        console.print("[red]Zero pricing products across all queries.[/red]")
        logger.log("done", status="failed", queries=len(findings), products=0,
                   duration_ms=round((time.monotonic() - t_start) * 1000))
        logger.close()
        print(json.dumps({"status": "failed", "reason": "no_products",
                          "queries": len(findings), "products": 0}))
        return 1

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = format_json(findings) if args.json_output else format_markdown(findings, args.region)
    out_path.write_text(text, encoding="utf-8")  # noqa: ASYNC240
    console.print(f"[green]✓ Wrote {len(text):,} chars to {out_path}[/green]")

    empty = sum(1 for f in findings if f.get("products_count", 0) == 0)
    summary = {
        "status": "partial" if empty else "success",
        "queries": len(findings),
        "products": total_products,
        "region": args.region,
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
        console.print(f"[red]aws_pricing_search failed: {exc}[/red]")
        print(json.dumps({"status": "failed", "reason": str(exc)}))
        sys.exit(2)
