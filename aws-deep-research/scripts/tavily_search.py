# /// script
# requires-python = ">=3.13"
# dependencies = [
#   "requests>=2.31.0",
#   "rich>=13.7.0",
#   "trafilatura[all]>=2.0.0",
#   "defusedxml"
# ]
# ///
"""
Tavily Search API Client with Scraper Integration

A comprehensive script that searches using Tavily Search API, saves results,
extracts URLs, and passes them to trafilatura_scraper.py for content extraction.

Tavily provides 1,000 free API credits per month. Combined with Brave Search's
2,000 free searches, you can maximize free-tier usage across both APIs.

Usage:
    uv run tavily_search.py "search query" [--depth basic|advanced|fast] [--topic general|news|finance]
    uv run tavily_search.py "python frameworks 2024" --depth advanced --max-results 10
    uv run tavily_search.py "AI news" --topic news --time-range week
"""

import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
from common import (
    budget_status,
    filter_blocked_urls,
    record_search,
    run_scraper,
    sanitize_folder_name,
    save_urls_to_file,
)
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
)
from rich.table import Table

from read_env import config_path, read_env_value

# Type aliases for clarity
type SearchResults = dict[str, Any]
type URLList = list[str]
type UsageInfo = dict[str, Any]

# Exit codes
EXIT_SUCCESS = 0
EXIT_GENERAL_ERROR = 1
EXIT_INVALID_ARGS = 2
EXIT_AUTH_ERROR = 3
EXIT_RATE_LIMIT = 4
EXIT_NETWORK_ERROR = 5

# Constants
API_BASE_URL = "https://api.tavily.com"
SEARCH_ENDPOINT = "/search"
USAGE_ENDPOINT = "/usage"

# API limits
FREE_TIER_MONTHLY_LIMIT = 1000
DEFAULT_MAX_RESULTS = 5
MAX_RESULTS_LIMIT = 20
REQUEST_TIMEOUT = 60

# Rate limits (requests per minute)
DEV_RATE_LIMIT_RPM = 100
PROD_RATE_LIMIT_RPM = 1000

# Search depth costs
DEPTH_COSTS = {
    "basic": 1,
    "advanced": 2,
    "fast": 1,
    "ultra-fast": 1,
}

console = Console()


@dataclass
class UsageTracker:
    """Tracks Tavily API usage information."""

    # Key-level usage
    key_usage: int = 0
    key_limit: int = FREE_TIER_MONTHLY_LIMIT
    key_search_usage: int = 0
    key_extract_usage: int = 0

    # Account-level usage
    current_plan: str = "Researcher"
    plan_usage: int = 0
    plan_limit: int = FREE_TIER_MONTHLY_LIMIT
    account_search_usage: int = 0
    account_extract_usage: int = 0

    last_updated: datetime = field(default_factory=lambda: datetime.now(UTC))

    def update_from_response(self, usage_data: dict[str, Any]) -> None:
        """Update tracker from /usage endpoint response."""
        self.last_updated = datetime.now(UTC)

        if key_data := usage_data.get("key"):
            self.key_usage = key_data.get("usage") or 0
            self.key_limit = key_data.get("limit") or FREE_TIER_MONTHLY_LIMIT
            self.key_search_usage = key_data.get("search_usage", 0)
            self.key_extract_usage = key_data.get("extract_usage", 0)

        if account_data := usage_data.get("account"):
            self.current_plan = account_data.get("current_plan", "Researcher")
            self.plan_usage = account_data.get("plan_usage", 0)
            self.plan_limit = account_data.get("plan_limit", FREE_TIER_MONTHLY_LIMIT)
            self.account_search_usage = account_data.get("search_usage", 0)
            self.account_extract_usage = account_data.get("extract_usage", 0)

    def update_from_search_response(self, response_data: dict[str, Any]) -> None:
        """Update usage from search response if include_usage was set."""
        if usage := response_data.get("usage"):
            credits_used = usage.get("credits", 0)
            self.key_usage += credits_used
            self.key_search_usage += credits_used
            self.plan_usage += credits_used
            self.account_search_usage += credits_used

    @property
    def key_remaining(self) -> int:
        """Calculate remaining credits for this API key."""
        return max(0, self.key_limit - self.key_usage)

    @property
    def plan_remaining(self) -> int:
        """Calculate remaining credits for the plan."""
        return max(0, self.plan_limit - self.plan_usage)

    def display_summary(self) -> Panel:
        """Create a Rich Panel showing usage status."""
        # Calculate percentages
        key_pct = (self.key_usage / self.key_limit * 100) if self.key_limit > 0 else 0
        plan_pct = (
            (self.plan_usage / self.plan_limit * 100) if self.plan_limit > 0 else 0
        )

        # Color code based on usage
        key_color = "green" if key_pct < 75 else "yellow" if key_pct < 90 else "red"
        plan_color = "green" if plan_pct < 75 else "yellow" if plan_pct < 90 else "red"

        content = (
            f"[bold cyan]Plan:[/bold cyan] {self.current_plan}\n\n"
            f"[bold cyan]API Key Usage[/bold cyan]\n"
            f"  Used: {self.key_usage} / {self.key_limit}\n"
            f"  Remaining: [{key_color}]{self.key_remaining}[/{key_color}]\n"
            f"  Search: {self.key_search_usage} | Extract: {self.key_extract_usage}\n\n"
            f"[bold cyan]Account Usage[/bold cyan]\n"
            f"  Used: {self.plan_usage} / {self.plan_limit}\n"
            f"  Remaining: [{plan_color}]{self.plan_remaining}[/{plan_color}]\n"
            f"  Search: {self.account_search_usage} | Extract: {self.account_extract_usage}"
        )

        return Panel(
            content,
            title="[bold]Tavily API Usage[/bold]",
            border_style="blue",
        )

    def check_quota(self, estimated_cost: int = 1) -> tuple[bool, str]:
        """Check if we have enough credits. Returns (can_proceed, message)."""
        if self.key_remaining < estimated_cost:
            return (
                False,
                f"API key quota exhausted. Remaining: {self.key_remaining}, Need: {estimated_cost}",
            )
        if self.plan_remaining < estimated_cost:
            return (
                False,
                f"Plan quota exhausted. Remaining: {self.plan_remaining}, Need: {estimated_cost}",
            )
        return True, ""


def load_api_key() -> str:
    """Load Tavily API key from environment or external config."""
    api_key = os.getenv("TAVILY_API_KEY") or read_env_value(
        config_path(), "TAVILY_API_KEY"
    )

    if not api_key:
        console.print(
            Panel(
                "[red]TAVILY_API_KEY not found![/red]\n\n"
                "Please set your API key in one of these ways:\n"
                "1. Add TAVILY_API_KEY to ~/.config/aws-deep-research/config.env\n"
                "2. Or set environment variable: export TAVILY_API_KEY=tvly-your_key_here\n\n"
                "Get your API key at: https://app.tavily.com",
                title="Configuration Error",
                border_style="red",
            ),
        )
        sys.exit(EXIT_AUTH_ERROR)

    return api_key


def get_usage(api_key: str) -> UsageInfo:
    """Fetch current API usage from Tavily."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.get(
            f"{API_BASE_URL}{USAGE_ENDPOINT}",
            headers=headers,
            timeout=REQUEST_TIMEOUT,
        )

        if response.status_code == 200:
            return response.json()
        console.print(
            f"[yellow]Could not fetch usage info: HTTP {response.status_code}[/yellow]",
        )
        return {}

    except requests.exceptions.RequestException as e:
        console.print(f"[yellow]Could not fetch usage info: {e}[/yellow]")
        return {}


def perform_search(
    api_key: str,
    query: str,
    search_depth: str = "basic",
    topic: str = "general",
    max_results: int = DEFAULT_MAX_RESULTS,
    time_range: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    include_answer: bool | str = False,
    include_raw_content: bool | str = False,
    include_images: bool = False,
    include_domains: list[str] | None = None,
    exclude_domains: list[str] | None = None,
    country: str | None = None,
    chunks_per_source: int | None = None,
    usage_tracker: UsageTracker | None = None,
) -> tuple[SearchResults, UsageTracker]:
    """Execute the Tavily Search API request."""
    if usage_tracker is None:
        usage_tracker = UsageTracker()

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    # Build request payload
    payload: dict[str, Any] = {
        "query": query,
        "search_depth": search_depth,
        "topic": topic,
        "max_results": min(max_results, MAX_RESULTS_LIMIT),
        "include_usage": True,  # Always include usage info
    }

    # Add optional parameters
    if time_range:
        payload["time_range"] = time_range
    if start_date:
        payload["start_date"] = start_date
    if end_date:
        payload["end_date"] = end_date
    if include_answer:
        payload["include_answer"] = include_answer
    if include_raw_content:
        payload["include_raw_content"] = include_raw_content
    if include_images:
        payload["include_images"] = include_images
    if include_domains:
        payload["include_domains"] = include_domains
    if exclude_domains:
        payload["exclude_domains"] = exclude_domains
    if country:
        payload["country"] = country
    if chunks_per_source and search_depth == "advanced":
        payload["chunks_per_source"] = chunks_per_source

    # Check quota before making request
    estimated_cost = DEPTH_COSTS.get(search_depth, 1)
    can_proceed, message = usage_tracker.check_quota(estimated_cost)
    if not can_proceed:
        console.print(f"[red]{message}[/red]")
        console.print(usage_tracker.display_summary())
        sys.exit(EXIT_RATE_LIMIT)

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
            console=console,
        ) as progress:
            progress.add_task("[cyan]Calling Tavily Search API...", total=None)
            response = requests.post(
                f"{API_BASE_URL}{SEARCH_ENDPOINT}",
                headers=headers,
                json=payload,
                timeout=REQUEST_TIMEOUT,
            )

        # Handle HTTP errors
        if response.status_code == 401:
            console.print(
                "[red]Invalid API key (401). Please check your TAVILY_API_KEY.[/red]",
            )
            sys.exit(EXIT_AUTH_ERROR)
        elif response.status_code == 403:
            console.print(
                "[red]Access forbidden (403). Check your API key permissions.[/red]",
            )
            sys.exit(EXIT_AUTH_ERROR)
        elif response.status_code == 429:
            console.print(
                "[red]Rate limit exceeded (429). Please wait before retrying.[/red]",
            )
            console.print(
                "[dim]Dev keys: 100 requests/min, Production keys: 1000 requests/min[/dim]",
            )
            sys.exit(EXIT_RATE_LIMIT)
        elif response.status_code != 200:
            console.print(f"[red]API error: HTTP {response.status_code}[/red]")
            try:
                error_detail = response.json()
                console.print(f"[dim]{json.dumps(error_detail, indent=2)[:500]}[/dim]")
            except (ValueError, KeyError):
                console.print(f"[dim]{response.text[:500]}[/dim]")
            sys.exit(EXIT_GENERAL_ERROR)

        result = response.json()

        # Update usage tracker from response
        usage_tracker.update_from_search_response(result)

        return result, usage_tracker

    except requests.exceptions.Timeout:
        console.print(f"[red]Request timed out after {REQUEST_TIMEOUT}s[/red]")
        sys.exit(EXIT_NETWORK_ERROR)
    except requests.exceptions.SSLError as e:
        console.print(f"[red]SSL certificate error: {e}[/red]")
        console.print(
            "[dim]The API endpoint's SSL certificate could not be verified.[/dim]",
        )
        sys.exit(EXIT_NETWORK_ERROR)
    except requests.exceptions.ConnectionError as e:
        console.print(f"[red]Network connection error: {e}[/red]")
        sys.exit(EXIT_NETWORK_ERROR)
    except requests.exceptions.RequestException as e:
        console.print(f"[red]Request failed: {e}[/red]")
        sys.exit(EXIT_GENERAL_ERROR)


def save_response(results: SearchResults, output_dir: Path, query: str) -> Path:
    """Save the full API response to a JSON file."""
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    filename = f"tavily_response_{timestamp}.json"
    filepath = output_dir / filename

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    console.print(f"[green]✓ Saved API response to:[/green] {filepath}")
    return filepath


def extract_urls_from_response(results: SearchResults) -> URLList:
    """Extract URLs from the Tavily API response."""
    urls: URLList = []

    # Results are in the 'results' array
    search_results = results.get("results", [])
    for result in search_results:
        if url := result.get("url"):
            urls.append(url)

    # Filter against the shared domain blocklist before returning.
    kept, dropped = filter_blocked_urls(urls)
    if dropped:
        console.print(
            f"[yellow]⚠ Blocklist filtered {len(dropped)} URL(s):[/yellow] "
            + ", ".join(dropped[:5])
            + (" …" if len(dropped) > 5 else "")
        )
    return kept


def display_search_results(results: SearchResults, urls: URLList) -> None:
    """Display search results in a formatted table."""
    table = Table(title="Tavily Search Results", show_lines=True)
    table.add_column("#", style="dim", width=4)
    table.add_column("Title", style="cyan", max_width=45)
    table.add_column("URL", style="green", max_width=55)
    table.add_column("Score", style="yellow", width=6)
    table.add_column("Content Preview", style="dim", max_width=35)

    search_results = results.get("results", [])

    for idx, item in enumerate(search_results, 1):
        title = item.get("title", "N/A")[:45]
        url = item.get("url", "N/A")
        score = f"{item.get('score', 0):.2f}"
        content = item.get("content", "")[:35]
        table.add_row(str(idx), title, url, score, content)

    console.print()
    console.print(table)

    # Show answer if available
    if answer := results.get("answer"):
        console.print()
        console.print(
            Panel(
                answer,
                title="[bold]AI-Generated Answer[/bold]",
                border_style="cyan",
            ),
        )

    # Show response time
    if response_time := results.get("response_time"):
        console.print(f"\n[dim]Response time: {response_time:.2f}s[/dim]")

    console.print(f"\n[bold]Total URLs extracted:[/bold] {len(urls)}")


def save_raw_content(results: SearchResults, output_dir: Path) -> int:
    """
    Save Tavily's pre-fetched raw_content as markdown files.

    Returns the number of files saved.
    """
    saved = 0
    for item in results.get("results", []):
        raw_content = item.get("raw_content")
        if not raw_content:
            continue

        url = item.get("url", "unknown")
        title = item.get("title", "untitled")

        parsed = urlparse(url)
        domain = parsed.netloc.replace("www.", "").replace(".", "_")
        domain_dir = output_dir / domain
        domain_dir.mkdir(parents=True, exist_ok=True)

        safe_title = re.sub(r"[^a-zA-Z0-9_-]", "_", title)[:60]
        path_hash = hashlib.md5(url.encode()).hexdigest()[:8]  # noqa: S324
        filepath = domain_dir / f"{safe_title}_{path_hash}.md"

        content = f"<!-- Source: {url} -->\n# {title}\n\n{raw_content}"
        filepath.write_text(content, encoding="utf-8")
        saved += 1
        console.print(f"[green]✓ Saved raw content:[/green] {filepath}")

    return saved


def main() -> None:
    """Main entry point for the Tavily Search script."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Search using Tavily Search API and optionally scrape results",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic search (1 credit)
  %(prog)s "python frameworks 2024"

  # Advanced search with more results (2 credits)
  %(prog)s "machine learning" --depth advanced --max-results 15

  # News search with time filter
  %(prog)s "artificial intelligence" --topic news --time-range week

  # Search with AI-generated answer
  %(prog)s "what is RAG in AI" --include-answer

  # Include full page content for deeper analysis
  %(prog)s "climate change solutions" --include-raw-content

  # Domain filtering
  %(prog)s "tech news" --include-domains techcrunch.com,wired.com

  # Search only (no scraping)
  %(prog)s "best restaurants" --no-scrape

Search Depth Options:
  basic     - Balanced relevance/latency, 1 credit (default)
  advanced  - Highest relevance, 2 credits
  fast      - Lower latency, chunked results, 1 credit
  ultra-fast - Minimal latency, 1 credit

Topic Options:
  general  - Broad search (default)
  news     - News sources with publish dates
  finance  - Financial information

Time Range Options:
  day (d), week (w), month (m), year (y)
  Or use --start-date and --end-date with YYYY-MM-DD format

Credit Usage:
  - Free tier: 1,000 credits/month
  - Basic/fast/ultra-fast search: 1 credit
  - Advanced search: 2 credits
        """,
    )

    parser.add_argument(
        "query",
        type=str,
        help="Search query string (max 400 characters recommended)",
    )
    parser.add_argument(
        "-d",
        "--depth",
        type=str,
        choices=["basic", "advanced", "fast", "ultra-fast"],
        default="basic",
        help="Search depth (default: basic, 1 credit; advanced costs 2 credits)",
    )
    parser.add_argument(
        "-t",
        "--topic",
        type=str,
        choices=["general", "news", "finance"],
        default="general",
        help="Search topic/category (default: general)",
    )
    parser.add_argument(
        "-m",
        "--max-results",
        type=int,
        default=DEFAULT_MAX_RESULTS,
        help=f"Number of results (max {MAX_RESULTS_LIMIT}, default: {DEFAULT_MAX_RESULTS})",
    )
    parser.add_argument(
        "--time-range",
        type=str,
        choices=["day", "week", "month", "year", "d", "w", "m", "y"],
        help="Filter by relative time range",
    )
    parser.add_argument(
        "--start-date",
        type=str,
        help="Filter results after this date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        help="Filter results before this date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--include-answer",
        action="store_true",
        help="Include AI-generated answer to the query",
    )
    parser.add_argument(
        "--include-raw-content",
        action="store_true",
        help="Include full extracted page content in markdown",
    )
    parser.add_argument(
        "--include-images",
        action="store_true",
        help="Include related images in results",
    )
    parser.add_argument(
        "--include-domains",
        type=str,
        help="Comma-separated list of domains to include",
    )
    parser.add_argument(
        "--exclude-domains",
        type=str,
        help="Comma-separated list of domains to exclude",
    )
    parser.add_argument(
        "--country",
        type=str,
        help="Boost results from specific country (e.g., 'united states')",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory (default: output/research/web-search/tavily/<sanitized_query>)",
    )
    parser.add_argument(
        "--no-scrape",
        action="store_true",
        help="Skip scraping - only search and save results",
    )
    parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Auto-confirm prompts (non-interactive mode for automation)",
    )
    parser.add_argument(
        "--check-usage",
        action="store_true",
        help="Only check and display current API usage, then exit",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output results as JSON (suppresses Rich console output for automation)",
    )

    args = parser.parse_args()

    # Suppress Rich output in JSON mode
    if args.json_output:
        global console
        console = Console(quiet=True)

    # Load API key
    api_key = load_api_key()

    # Initialize usage tracker
    usage_tracker = UsageTracker()

    # Fetch current usage
    console.print()
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True,
        console=console,
    ) as progress:
        progress.add_task("[cyan]Fetching API usage...", total=None)
        usage_data = get_usage(api_key)

    if usage_data:
        usage_tracker.update_from_response(usage_data)

    # If only checking usage, display and exit
    if args.check_usage:
        console.print(usage_tracker.display_summary())
        sys.exit(0)

    # Calculate estimated cost
    estimated_cost = DEPTH_COSTS.get(args.depth, 1)

    # Display header
    console.print(
        Panel(
            f"[bold cyan]Tavily Search API Client[/bold cyan]\n"
            f"Query: [green]{args.query}[/green]\n"
            f"Depth: {args.depth} ({estimated_cost} credit{'s' if estimated_cost > 1 else ''})\n"
            f"Topic: {args.topic}\n"
            f"Max Results: {args.max_results}",
            border_style="cyan",
        ),
    )

    # Set up output directory
    if args.output_dir is None:
        console.print(
            "[red]Error: --output-dir / -o is required.[/red]\n"
            "[yellow]The aws-deep-research skill writes all intermediate artifacts "
            "under $WORK_DIR/<slug>/downloads/.[/yellow]\n"
            "[yellow]Pass:  -o $WORK_DIR/<slug>/downloads/tavily[/yellow]"
        )
        sys.exit(EXIT_INVALID_ARGS)

    args.output_dir.mkdir(parents=True, exist_ok=True)

    # Parse domain lists
    include_domains = None
    if args.include_domains:
        include_domains = [d.strip() for d in args.include_domains.split(",")]

    exclude_domains = None
    if args.exclude_domains:
        exclude_domains = [d.strip() for d in args.exclude_domains.split(",")]

    # Perform the search
    results, usage_tracker = perform_search(
        api_key=api_key,
        query=args.query,
        search_depth=args.depth,
        topic=args.topic,
        max_results=args.max_results,
        time_range=args.time_range,
        start_date=args.start_date,
        end_date=args.end_date,
        include_answer=args.include_answer,
        include_raw_content="markdown" if args.include_raw_content else False,
        include_images=args.include_images,
        include_domains=include_domains,
        exclude_domains=exclude_domains,
        country=args.country,
        usage_tracker=usage_tracker,
    )

    # Record credits used this request against the persistent monthly budget.
    record_search("tavily", count=estimated_cost)
    budget = budget_status("tavily")

    # Display usage status
    console.print()
    console.print(usage_tracker.display_summary())
    if budget["over_80"]:
        console.print(
            f"[yellow]⚠ Tavily budget at {budget['pct_used']}% "
            f"({budget['used']}/{budget['cap']}) this month - prefer MCP-only.[/yellow]"
        )

    # Check for empty results
    if not results:
        console.print("[yellow]No results returned from API[/yellow]")
        sys.exit(0)

    # Save full response
    save_response(results, args.output_dir, args.query)

    # Extract URLs
    urls = extract_urls_from_response(results)

    # Display results
    display_search_results(results, urls)

    if not urls:
        console.print("[yellow]No URLs found in search results[/yellow]")
        sys.exit(0)

    # Save URLs to file
    save_urls_to_file(urls, args.output_dir)

    # If raw content was fetched, save it directly and skip scraping
    if args.include_raw_content:
        saved_count = save_raw_content(results, args.output_dir)
        if saved_count > 0:
            console.print(
                f"\n[green]Saved {saved_count} pages from Tavily's "
                f"pre-fetched content (no scraping needed)[/green]",
            )
            args.no_scrape = True

    # Run scraper if not disabled
    if not args.no_scrape:
        console.print()
        from rich.prompt import Confirm

        if args.yes or Confirm.ask(
            f"[yellow]Proceed to scrape {len(urls)} URLs?[/yellow]",
        ):
            run_scraper(
                urls,
                args.output_dir,
                yes=args.yes,
                json_output=args.json_output,
            )
        else:
            console.print("[dim]Scraping skipped by user[/dim]")
    else:
        console.print("\n[dim]Scraping disabled (--no-scrape flag)[/dim]")

    # Final output
    if args.json_output:
        import json as json_mod

        summary = {
            "status": "success",
            "query": args.query,
            "search_depth": args.depth,
            "topic": args.topic,
            "result_count": len(urls),
            "urls": urls,
            "output_dir": str(args.output_dir),
            "credits_used": estimated_cost,
            "key_remaining": usage_tracker.key_remaining,
            "plan_remaining": usage_tracker.plan_remaining,
            "budget": budget,
        }
        print(json_mod.dumps(summary, indent=2))
    else:
        console.print()
        console.print(
            Panel(
                f"[green]Search completed successfully![/green]\n\n"
                f"Results saved to: {args.output_dir}\n"
                f"Credits used this request: {estimated_cost}\n"
                f"API key credits remaining: [bold]{usage_tracker.key_remaining}[/bold]",
                title="Complete",
                border_style="green",
            ),
        )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
        sys.exit(130)
