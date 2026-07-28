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


async def discover_services(
    session: ClientSession,
    keyword: str,
) -> list[dict[str, Any]]:
    """Search for AWS services matching a keyword."""
    raw = await call_tool(session, "discover_services", {"keyword": keyword})
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        return raw.get("services", raw.get("results", [raw]))
    if isinstance(raw, str):
        # Sometimes returns plain text description
        return [{"description": raw}]
    return []


async def get_pricing_attributes(
    session: ClientSession,
    service_code: str,
) -> list[dict[str, Any]]:
    """Get available pricing attributes for a service."""
    raw = await call_tool(
        session,
        "get_attribute_values",
        {"ServiceCode": service_code, "max_results": 20},
    )
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        return raw.get("attributes", raw.get("results", [raw]))
    return []


async def query_pricing(
    session: ClientSession,
    service_code: str,
    filters: list[dict[str, str]] | None = None,
    *,
    max_results: int = 15,
) -> list[dict[str, Any]]:
    """Query pricing data with optional filters."""
    args: dict[str, Any] = {
        "ServiceCode": service_code,
        "max_results": max_results,
    }
    if filters:
        args["Filters"] = filters
    raw = await call_tool(session, "get_products", args)
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        return raw.get("products", raw.get("results", raw.get("PriceList", [raw])))
    if isinstance(raw, str):
        return [{"raw": raw}]
    return []


async def compare_pricing(
    session: ClientSession,
    service_code: str,
    regions: list[str],
    filters: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Compare pricing across regions."""
    args: dict[str, Any] = {
        "ServiceCode": service_code,
        "regions": regions,
    }
    if filters:
        args["Filters"] = filters
    raw = await call_tool(session, "compare_pricing", args)
    if isinstance(raw, dict):
        return raw
    return {"raw": raw}


async def generate_cost_report(
    session: ClientSession,
    service_code: str,
    usage_params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Generate a cost analysis report."""
    args: dict[str, Any] = {"ServiceCode": service_code}
    if usage_params:
        args.update(usage_params)
    raw = await call_tool(session, "generate_cost_report", args)
    if isinstance(raw, dict):
        return raw
    return {"raw": raw}


# ── Core research logic ─────────────────────────────────────────────────────


async def research_pricing(  # noqa: PLR0913
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
    tools = available_tools or []

    for query in queries:
        console.print(f"[cyan]Researching pricing:[/cyan] {query}")
        finding: dict[str, Any] = {"query": query, "region": region}
        t0 = time.monotonic()

        # Step 1: Discover relevant services
        # Extract likely service keywords from the query
        keywords = _extract_service_keywords(query)
        services_found: list[dict[str, Any]] = []

        for kw in keywords[:3]:  # Max 3 keyword searches
            console.print(f"  [dim]Discovering services for: {kw}[/dim]")
            try:
                results = await discover_services(session, kw)
                services_found.extend(results)
                log("discover", keyword=kw, results_count=len(results))
            except Exception as e:  # noqa: BLE001
                console.print(f"  [yellow]Discovery failed for {kw}: {e}[/yellow]")
                log("discover_error", keyword=kw, error=str(e))

        finding["services_discovered"] = services_found

        # Step 2: Query pricing for discovered services
        service_codes = _extract_service_codes(services_found)
        pricing_results: list[dict[str, Any]] = []

        for sc in service_codes[:3]:  # Max 3 services per query
            console.print(f"  [dim]Querying pricing for: {sc}[/dim]")
            try:
                if "get_products" in tools:
                    products = await query_pricing(
                        session,
                        sc,
                        max_results=max_results,
                    )
                    pricing_results.append(
                        {
                            "service_code": sc,
                            "products": products[:max_results],
                        },
                    )
                    log("pricing", service=sc, products_count=len(products))
                else:
                    # Fallback: try discover_services with more detail
                    detail = await discover_services(session, sc)
                    pricing_results.append(
                        {
                            "service_code": sc,
                            "info": detail,
                        },
                    )
            except Exception as e:  # noqa: BLE001
                console.print(f"  [yellow]Pricing query failed for {sc}: {e}[/yellow]")
                log("pricing_error", service=sc, error=str(e))
                pricing_results.append(
                    {
                        "service_code": sc,
                        "error": str(e),
                    },
                )

        finding["pricing"] = pricing_results

        # Step 3: Try cost report if available
        if "generate_cost_report" in tools and service_codes:
            try:
                console.print("  [dim]Generating cost report...[/dim]")
                report = await generate_cost_report(session, service_codes[0])
                finding["cost_report"] = report
                log("cost_report", service=service_codes[0])
            except Exception as e:  # noqa: BLE001
                log("cost_report_error", error=str(e))

        duration_ms = round((time.monotonic() - t0) * 1000)
        finding["duration_ms"] = duration_ms
        log("query_done", query=query, duration_ms=duration_ms)
        all_findings.append(finding)

    return all_findings


def _extract_service_keywords(query: str) -> list[str]:
    """Extract likely AWS service names from a pricing query."""
    # Common service name patterns
    service_map = {
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

    query_lower = query.lower()
    keywords = []

    for name, code in service_map.items():
        if name in query_lower:
            keywords.append(code)

    # If no known service matched, use raw query words as keywords
    if not keywords:
        words = [
            w
            for w in query.split()
            if len(w) > 2  # noqa: PLR2004 w.lower() not in
            and {
                "the",
                "and",
                "for",
                "how",
                "much",
                "does",
                "cost",
                "pricing",
                "price",
                "compare",
                "between",
                "aws",
                "amazon",
                "region",
            }
        ]
        keywords = words[:3]

    return keywords


def _extract_service_codes(services: list[dict[str, Any]]) -> list[str]:
    """Extract unique service codes from discovery results."""
    codes: list[str] = []
    seen: set[str] = set()
    for svc in services:
        code = svc.get("ServiceCode", svc.get("service_code", ""))
        if code and code not in seen:
            seen.add(code)
            codes.append(code)
    return codes


# ── Output formatters ────────────────────────────────────────────────────────

_COMPACT_JSON_MAX = 1000


def _format_services(lines: list[str], services: list[dict[str, Any]]) -> None:
    """Format discovered services section."""
    lines.append("### Services Found\n")
    for svc in services[:5]:
        code = svc.get("ServiceCode", "")
        desc = svc.get("description", svc.get("ServiceName", ""))
        if code:
            lines.append(f"- **{code}**: {desc}")
        elif desc:
            lines.append(f"- {str(desc)[:300]}")
    lines.append("")


def _format_pricing_section(lines: list[str], pricing: list[dict[str, Any]]) -> None:
    """Format pricing data for all services."""
    for p in pricing:
        sc = p.get("service_code", "Unknown")
        lines.append(f"### Pricing: {sc}\n")

        if "error" in p:
            lines.append(f"*Error querying pricing: {p['error']}*\n")
            continue

        products = p.get("products", p.get("info", []))
        if isinstance(products, list):
            for prod in products[:10]:
                if isinstance(prod, dict):
                    _format_product(lines, prod)
                else:
                    lines.append(f"- {str(prod)[:500]}")
        elif isinstance(products, dict):
            _format_product(lines, products)
        else:
            lines.append(f"{str(products)[:2000]}\n")


def format_markdown(findings: list[dict[str, Any]], region: str) -> str:
    """Render findings as a markdown pricing research document."""
    lines: list[str] = [
        "# AWS Pricing Research\n",
        f"**Date**: {datetime.now(UTC).strftime('%Y-%m-%d')}",
        f"**Region**: {region}",
        f"**Queries**: {len(findings)}\n",
    ]

    for finding in findings:
        query = finding["query"]
        lines.append(f"## {query}\n")

        services = finding.get("services_discovered", [])
        if services:
            _format_services(lines, services)

        pricing = finding.get("pricing", [])
        if pricing:
            _format_pricing_section(lines, pricing)

        report = finding.get("cost_report")
        if report:
            lines.append("### Cost Analysis\n")
            if isinstance(report, dict):
                lines.append(
                    f"```json\n{json.dumps(report, indent=2, default=str)[:3000]}\n```\n",
                )
            else:
                lines.append(f"{str(report)[:2000]}\n")

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


async def main(args: argparse.Namespace) -> None:
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

            # Discover available tools
            tools = await list_tools(session)
            console.print(f"  [dim]Available tools: {', '.join(tools)}[/dim]")
            logger.log("tools", tools=tools)

            findings = await research_pricing(
                session,
                args.query,
                region=args.region,
                max_results=args.max_results,
                logger=logger,
                available_tools=tools,
            )

    # Write output
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if args.json_output:
        text = format_json(findings)
    else:
        text = format_markdown(findings, args.region)

    out_path.write_text(text, encoding="utf-8")  # noqa: ASYNC240
    console.print(f"[green]✓ Wrote {len(text):,} chars to {out_path}[/green]")

    # Print brief summary to stdout
    total_services = sum(len(f.get("pricing", [])) for f in findings)
    summary = {
        "status": "success",
        "queries": len(findings),
        "services_queried": total_services,
        "region": args.region,
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
