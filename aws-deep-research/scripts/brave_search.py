# /// script
# requires-python = ">=3.13"
# dependencies = [
#   "requests>=2.31.0",
#   "python-dotenv>=1.0.0",
#   "rich>=13.7.0",
#   "trafilatura[all]>=2.0.0",
#   "defusedxml"
# ]
# ///
"""
Brave Search API Client with Scraper Integration

A comprehensive script that searches using Brave Search API, saves results,
extracts URLs, and passes them to trafilatura_scraper.py for content extraction.

Usage:
    uv run brave_search.py "search query" [--type web|news|videos|images] [--goggle URL]
    uv run brave_search.py "python frameworks 2024" --type web --count 10
    uv run brave_search.py "AI news" --type news --freshness pd
"""

import json
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import requests
from common import (
    budget_status,
    filter_blocked_urls,
    record_search,
    run_scraper,
    sanitize_folder_name,
    save_urls_to_file,
)
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
)
from rich.table import Table

# Type aliases for clarity
type SearchResults = dict[str, Any]
type URLList = list[str]
type RateLimitInfo = dict[str, Any]

# Exit codes
EXIT_SUCCESS = 0
EXIT_GENERAL_ERROR = 1
EXIT_INVALID_ARGS = 2
EXIT_AUTH_ERROR = 3
EXIT_RATE_LIMIT = 4
EXIT_NETWORK_ERROR = 5

# Constants
API_BASE_URL = "https://api.search.brave.com/res/v1"
SEARCH_ENDPOINTS = {
    "web": "/web/search",
    "news": "/news/search",
    "videos": "/videos/search",
    "images": "/images/search",
}
DEFAULT_COUNT = 20
MAX_COUNT = 100
REQUEST_TIMEOUT = 30

# Rate limit constants
FREE_TIER_MONTHLY_LIMIT = 2000
DEFAULT_PER_SECOND_LIMIT = 1

console = Console()


@dataclass
class RateLimitTracker:
    """Tracks API rate limit information from response headers."""

    per_second_limit: int = DEFAULT_PER_SECOND_LIMIT
    monthly_limit: int | float = FREE_TIER_MONTHLY_LIMIT
    per_second_remaining: int = DEFAULT_PER_SECOND_LIMIT
    monthly_remaining: int = FREE_TIER_MONTHLY_LIMIT
    per_second_reset: int = 1
    monthly_reset: int = 0
    last_updated: datetime = field(default_factory=lambda: datetime.now(UTC))

    def update_from_headers(self, headers: dict[str, str]) -> None:
        """Parse rate limit headers and update tracker state."""
        self.last_updated = datetime.now(UTC)

        # Parse X-RateLimit-Limit: "1, 15000"
        if limit_header := headers.get("X-RateLimit-Limit"):
            parts = [p.strip() for p in limit_header.split(",")]
            if len(parts) >= 2:
                self.per_second_limit = int(parts[0])
                self.monthly_limit = int(parts[1]) if parts[1] != "0" else float("inf")

        # Parse X-RateLimit-Remaining: "1, 1000"
        if remaining_header := headers.get("X-RateLimit-Remaining"):
            parts = [p.strip() for p in remaining_header.split(",")]
            if len(parts) >= 2:
                self.per_second_remaining = int(parts[0])
                self.monthly_remaining = int(parts[1])

        # Parse X-RateLimit-Reset: "1, 1419704"
        if reset_header := headers.get("X-RateLimit-Reset"):
            parts = [p.strip() for p in reset_header.split(",")]
            if len(parts) >= 2:
                self.per_second_reset = int(parts[0])
                self.monthly_reset = int(parts[1])

    def display_summary(self) -> Panel:
        """Create a Rich Panel showing rate limit status."""
        monthly_limit_str = (
            str(self.monthly_limit)
            if self.monthly_limit != float("inf")
            else "Unlimited"
        )
        monthly_used = (
            self.monthly_limit - self.monthly_remaining
            if self.monthly_limit != float("inf")
            else "N/A"
        )

        # Calculate reset time in human-readable format
        if self.monthly_reset > 0:
            days = self.monthly_reset // 86400
            hours = (self.monthly_reset % 86400) // 3600
            reset_str = f"{days}d {hours}h"
        else:
            reset_str = "N/A"

        content = (
            f"[bold cyan]Monthly Quota[/bold cyan]\n"
            f"  Limit: {monthly_limit_str}\n"
            f"  Used: {monthly_used}\n"
            f"  Remaining: [green]{self.monthly_remaining}[/green]\n"
            f"  Resets in: {reset_str}\n\n"
            f"[bold cyan]Per-Second Rate[/bold cyan]\n"
            f"  Limit: {self.per_second_limit} req/sec\n"
            f"  Available: {self.per_second_remaining}"
        )

        return Panel(
            content,
            title="[bold]Brave Search API Quota[/bold]",
            border_style="blue",
        )

    def check_quota(self) -> tuple[bool, str]:
        """Check if we can make another request. Returns (can_proceed, message)."""
        if self.monthly_remaining <= 0:
            return (
                False,
                "Monthly quota exhausted. Please wait for reset or upgrade plan.",
            )
        if self.per_second_remaining <= 0:
            return True, f"Per-second limit hit. Waiting {self.per_second_reset}s..."
        return True, ""


def load_api_key() -> str:
    """Load Brave Search API key from environment or .env file."""
    load_dotenv()
    api_key = os.getenv("BRAVE_SEARCH_API_KEY")

    if not api_key:
        console.print(
            Panel(
                "[red]BRAVE_SEARCH_API_KEY not found![/red]\n\n"
                "Please set your API key in one of these ways:\n"
                "1. Create a .env file with: BRAVE_SEARCH_API_KEY=your_key_here\n"
                "2. Set environment variable: export BRAVE_SEARCH_API_KEY=your_key_here\n\n"
                "Get your API key at: https://brave.com/search/api/",
                title="Configuration Error",
                border_style="red",
            ),
        )
        sys.exit(EXIT_AUTH_ERROR)

    return api_key


def build_search_url(
    search_type: str,
    query: str,
    count: int = DEFAULT_COUNT,
    offset: int = 0,
    country: str = "us",
    freshness: str | None = None,
    goggle_url: str | None = None,
    safe_search: str = "moderate",
    result_filter: str | None = None,
) -> str:
    """Build the full API URL with query parameters."""
    endpoint = SEARCH_ENDPOINTS.get(search_type)
    if not endpoint:
        raise ValueError(
            f"Invalid search type: {search_type}. Valid types: {list(SEARCH_ENDPOINTS.keys())}",
        )

    params = {
        "q": query,
        "count": min(count, MAX_COUNT),
        "offset": offset,
        "country": country,
        "safesearch": safe_search,
    }

    # Add optional parameters
    if freshness:
        params["freshness"] = freshness
    if goggle_url:
        params["goggles_id"] = goggle_url
    if result_filter:
        params["result_filter"] = result_filter

    return f"{API_BASE_URL}{endpoint}?{urlencode(params)}"


def perform_search(
    api_key: str,
    url: str,
    rate_tracker: RateLimitTracker,
) -> tuple[SearchResults, RateLimitTracker]:
    """Execute the API search request and handle rate limiting."""
    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": api_key,
    }

    # Check if we need to wait for rate limit
    can_proceed, message = rate_tracker.check_quota()
    if not can_proceed:
        console.print(f"[red]{message}[/red]")
        sys.exit(EXIT_RATE_LIMIT)
    if message:
        console.print(f"[yellow]{message}[/yellow]")
        time.sleep(rate_tracker.per_second_reset)

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
            console=console,
        ) as progress:
            progress.add_task("[cyan]Calling Brave Search API...", total=None)
            response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)

        # Update rate limit tracker from response headers
        rate_tracker.update_from_headers(dict(response.headers))

        # Handle HTTP errors
        if response.status_code == 429:
            console.print(
                "[red]Rate limit exceeded (429). Please wait before retrying.[/red]",
            )
            console.print(rate_tracker.display_summary())
            sys.exit(EXIT_RATE_LIMIT)
        elif response.status_code == 401:
            console.print(
                "[red]Invalid API key (401). Please check your BRAVE_SEARCH_API_KEY.[/red]",
            )
            sys.exit(EXIT_AUTH_ERROR)
        elif response.status_code == 403:
            console.print(
                "[red]Access forbidden (403). Your plan may not support this endpoint.[/red]",
            )
            sys.exit(EXIT_AUTH_ERROR)
        elif response.status_code != 200:
            console.print(f"[red]API error: HTTP {response.status_code}[/red]")
            console.print(f"[dim]{response.text[:500]}[/dim]")
            sys.exit(EXIT_GENERAL_ERROR)

        return response.json(), rate_tracker

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
    filename = f"brave_response_{timestamp}.json"
    filepath = output_dir / filename

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    console.print(f"[green]✓ Saved API response to:[/green] {filepath}")
    return filepath


def extract_urls_from_response(results: SearchResults, search_type: str) -> URLList:
    """Extract URLs from the API response based on search type."""
    urls: URLList = []

    if search_type == "web":
        # Web search results are in 'web.results'
        web_results = results.get("web", {}).get("results", [])
        for result in web_results:
            if url := result.get("url"):
                urls.append(url)

        # Also check for news results embedded in web search
        news_results = results.get("news", {}).get("results", [])
        for result in news_results:
            if url := result.get("url"):
                urls.append(url)

    elif search_type == "news":
        # News search results
        news_results = results.get("results", [])
        for result in news_results:
            if url := result.get("url"):
                urls.append(url)

    elif search_type == "videos":
        # Video search results - extract page URLs (not video embed URLs)
        video_results = results.get("results", [])
        for result in video_results:
            if url := result.get("url"):
                urls.append(url)

    elif search_type == "images":
        # Image search - extract source page URLs
        image_results = results.get("results", [])
        for result in image_results:
            # Prefer the page URL over direct image URL for scraping
            if url := result.get("page_url", result.get("url")):
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


def display_search_results(
    results: SearchResults,
    search_type: str,
    urls: URLList,
) -> None:
    """Display search results in a formatted table."""
    table = Table(title=f"Search Results ({search_type.upper()})", show_lines=True)
    table.add_column("#", style="dim", width=4)
    table.add_column("Title", style="cyan", max_width=50)
    table.add_column("URL", style="green", max_width=60)
    table.add_column("Description", style="dim", max_width=40)

    if search_type == "web":
        items = results.get("web", {}).get("results", [])
    elif search_type == "news" or search_type == "videos" or search_type == "images":
        items = results.get("results", [])
    else:
        items = []

    for idx, item in enumerate(items[:20], 1):  # Limit display to 20
        title = item.get("title", "N/A")[:50]
        url = item.get("url", "N/A")
        description = item.get("description", item.get("snippet", ""))[:40]
        table.add_row(str(idx), title, url, description)

    console.print()
    console.print(table)
    console.print(f"\n[bold]Total URLs extracted:[/bold] {len(urls)}")


def main() -> None:
    """Main entry point for the Brave Search script."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Search using Brave Search API and optionally scrape results",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic web search
  %(prog)s "python frameworks 2024"

  # News search with freshness filter (past day)
  %(prog)s "artificial intelligence" --type news --freshness pd

  # Web search with custom Goggle
  %(prog)s "climate change" --goggle https://example.com/my.goggle

  # Video search with more results
  %(prog)s "machine learning tutorial" --type videos --count 30

  # Search only (no scraping)
  %(prog)s "best restaurants" --no-scrape

Freshness options:
  pd = past day, pw = past week, pm = past month, py = past year
  Or use date range: YYYY-MM-DDtoYYYY-MM-DD
        """,
    )

    parser.add_argument(
        "query",
        type=str,
        help="Search query string",
    )
    parser.add_argument(
        "-t",
        "--type",
        type=str,
        choices=["web", "news", "videos", "images"],
        default="web",
        help="Type of search (default: web)",
    )
    parser.add_argument(
        "-c",
        "--count",
        type=int,
        default=DEFAULT_COUNT,
        help=f"Number of results to fetch (max {MAX_COUNT}, default: {DEFAULT_COUNT})",
    )
    parser.add_argument(
        "-g",
        "--goggle",
        type=str,
        help="URL to a Goggle file for custom result ranking",
    )
    parser.add_argument(
        "-f",
        "--freshness",
        type=str,
        help="Freshness filter: pd (day), pw (week), pm (month), py (year), or date range",
    )
    parser.add_argument(
        "--country",
        type=str,
        default="us",
        help="Country code for localized results (default: us)",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory (default: output/research/web-search/brave/<sanitized_query>)",
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
        "--safe-search",
        type=str,
        choices=["off", "moderate", "strict"],
        default="moderate",
        help="Safe search level (default: moderate)",
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

    # Display header
    console.print()
    console.print(
        Panel(
            f"[bold cyan]Brave Search API Client[/bold cyan]\n"
            f"Query: [green]{args.query}[/green]\n"
            f"Type: {args.type.upper()}\n"
            f"Count: {args.count}",
            border_style="cyan",
        ),
    )

    # Load API key
    api_key = load_api_key()

    # Initialize rate limit tracker
    rate_tracker = RateLimitTracker()

    # Set up output directory
    if args.output_dir is None:
        console.print(
            "[red]Error: --output-dir / -o is required.[/red]\n"
            "[yellow]The aws-deep-research skill writes all intermediate artifacts "
            "under $WORK_DIR/<slug>/downloads/.[/yellow]\n"
            "[yellow]Pass:  -o $WORK_DIR/<slug>/downloads/brave[/yellow]"
        )
        sys.exit(EXIT_INVALID_ARGS)

    args.output_dir.mkdir(parents=True, exist_ok=True)

    # Build search URL
    try:
        search_url = build_search_url(
            search_type=args.type,
            query=args.query,
            count=args.count,
            country=args.country,
            freshness=args.freshness,
            goggle_url=args.goggle,
            safe_search=args.safe_search,
        )
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(EXIT_INVALID_ARGS)

    console.print(f"\n[dim]API URL: {search_url}[/dim]\n")

    # Perform the search
    results, rate_tracker = perform_search(api_key, search_url, rate_tracker)

    # Record this successful search against the persistent monthly budget.
    record_search("brave")
    budget = budget_status("brave")

    # Display rate limit status
    console.print()
    console.print(rate_tracker.display_summary())
    if budget["over_80"]:
        console.print(
            f"[yellow]⚠ Brave budget at {budget['pct_used']}% "
            f"({budget['used']}/{budget['cap']}) this month — prefer MCP-only.[/yellow]"
        )

    # Check for empty results
    if not results:
        console.print("[yellow]No results returned from API[/yellow]")
        sys.exit(0)

    # Save full response
    save_response(results, args.output_dir, args.query)

    # Extract URLs
    urls = extract_urls_from_response(results, args.type)

    # Display results
    display_search_results(results, args.type, urls)

    if not urls:
        console.print("[yellow]No URLs found in search results[/yellow]")
        sys.exit(0)

    # Save URLs to file
    save_urls_to_file(urls, args.output_dir)

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
            "search_type": args.type,
            "result_count": len(urls),
            "urls": urls,
            "output_dir": str(args.output_dir),
            "quota_remaining": rate_tracker.monthly_remaining,
            "quota_limit": rate_tracker.monthly_limit
            if rate_tracker.monthly_limit != float("inf")
            else None,
            "budget": budget,
        }
        print(json_mod.dumps(summary, indent=2))
    else:
        console.print()
        console.print(
            Panel(
                f"[green]Search completed successfully![/green]\n\n"
                f"Results saved to: {args.output_dir}\n"
                f"Monthly quota remaining: [bold]{rate_tracker.monthly_remaining}[/bold]",
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
