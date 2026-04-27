# /// script
# requires-python = ">=3.13"
# dependencies = [
#   "trafilatura[all]==2.0.0",
#   "rich",
#   "requests",
#   "defusedxml",
#   "tenacity>=8.2.0",
# ]
# ///
import hashlib
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from urllib.parse import urlparse

import defusedxml.ElementTree as DefusedET
import requests
from common import save_urls_to_file
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
)
from rich.prompt import Confirm
from rich.table import Table
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)
from trafilatura import extract
from trafilatura.settings import DEFAULT_CONFIG

# Python 3.12 type aliases for better readability
type ProcessResult = tuple[str, bool, str]  # (url, success, message)
type URLList = list[str]

# Exit codes
EXIT_SUCCESS = 0
EXIT_GENERAL_ERROR = 1
EXIT_INVALID_ARGS = 2
EXIT_AUTH_ERROR = 3
EXIT_RATE_LIMIT = 4
EXIT_NETWORK_ERROR = 5

# URL patterns that serve raw markdown content (no extraction needed)
MARKDOWN_URL_SUFFIXES = (".md", ".markdown")

# Constants for time formatting
SECONDS_PER_MINUTE = 60
SECONDS_PER_HOUR = 3600

# Preview limit for URL display
URL_PREVIEW_LIMIT = 10

# Concurrency settings
DEFAULT_WORKERS = 4
MAX_WORKERS = 8

# Content quality filtering
DEFAULT_MIN_WORDS = 50

# Scrape index for cross-run deduplication (resolved relative to output dir at runtime)
SCRAPE_INDEX_FILE = None

console = Console()


def _load_scrape_index() -> dict[str, str]:
    """Load the URL-to-filepath scrape index."""
    if SCRAPE_INDEX_FILE and SCRAPE_INDEX_FILE.exists():
        try:
            return json.loads(SCRAPE_INDEX_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save_scrape_index(index: dict[str, str]) -> None:
    """Save the URL-to-filepath scrape index."""
    if SCRAPE_INDEX_FILE is None:
        return
    SCRAPE_INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
    SCRAPE_INDEX_FILE.write_text(
        json.dumps(index, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def get_crawler_config():
    """
    Configure trafilatura settings for optimal extraction.

    Returns a modified copy of the default trafilatura config with
    custom timeout, sleep, and language settings.
    """
    config = deepcopy(DEFAULT_CONFIG)
    config["DEFAULT"]["DOWNLOAD_TIMEOUT"] = "30"
    config["DEFAULT"]["SLEEP_TIME"] = "5"
    config["DEFAULT"]["MIN_FILE_SIZE"] = "10"
    config["DEFAULT"]["EXTRACTION_TIMEOUT"] = "30"
    config["DEFAULT"]["EXTENSIVE_DATE_SEARCH"] = "off"
    # Force English language extraction
    config["DEFAULT"]["TARGET_LANGUAGE"] = "en"
    return config


class SitemapError(Exception):
    """Custom exception for sitemap parsing errors."""


class DownloadError(Exception):
    """Custom exception for download failures."""


class ExtractionError(Exception):
    """Custom exception for content extraction failures."""


def _raise_sitemap_error(message: str, url: str, hint: str) -> None:
    """Raise a SitemapError with notes."""
    error = SitemapError(message)
    error.add_note(f"URL: {url}")
    error.add_note(hint)
    raise error


def _raise_download_error(url: str) -> None:
    """Raise a DownloadError with notes."""
    error = DownloadError("Failed to download URL")
    error.add_note(f"URL: {url}")
    error.add_note("Check if the URL is accessible and valid")
    raise error


def _raise_extraction_error(url: str) -> None:
    """Raise an ExtractionError with notes."""
    error = ExtractionError("Failed to extract content")
    error.add_note(f"URL: {url}")
    error.add_note("The page may not contain extractable text content")
    raise error


# Sitemap parsing limits
MAX_SITEMAP_DEPTH = 3
MAX_SITEMAP_URLS = 5000


def parse_sitemap(
    sitemap_url: str,
    *,
    _depth: int = 0,
    _accumulated: int = 0,
) -> URLList:
    """
    Download and parse sitemap XML to extract all <loc> URLs.

    Args:
        sitemap_url: The sitemap URL to parse.
        _depth: Internal recursion depth counter (do not set manually).
        _accumulated: Internal URL counter (do not set manually).

    """
    if _depth >= MAX_SITEMAP_DEPTH:
        console.print(
            f"[yellow]Sitemap recursion limit ({MAX_SITEMAP_DEPTH}) reached. "
            f"Skipping deeper sitemaps.[/yellow]",
        )
        return []

    console.print(f"[cyan]Fetching sitemap from: {sitemap_url}[/cyan]")

    # Download sitemap with proper compression handling
    response = requests.get(sitemap_url, timeout=30)
    response.raise_for_status()
    content = response.text

    if not content:
        _raise_sitemap_error(
            "Failed to download sitemap",
            sitemap_url,
            "Check if the sitemap URL is accessible",
        )

    try:
        root = DefusedET.fromstring(content)
    except DefusedET.ParseError as e:
        _raise_sitemap_error(
            f"Failed to parse sitemap XML: {e}",
            sitemap_url,
            "Ensure the sitemap is valid XML format",
        )

    # Handle both sitemap and sitemap index
    # Namespace for sitemap.org schema
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

    urls: URLList = []

    # Check if it's a sitemap index
    sitemaps = root.findall(".//sm:sitemap/sm:loc", ns)
    if sitemaps:
        console.print(
            f"[yellow]Found sitemap index with {len(sitemaps)} sitemaps[/yellow]",
        )
        # Recursively parse each sitemap with depth and count limits
        for sitemap_loc in sitemaps:
            if _accumulated + len(urls) >= MAX_SITEMAP_URLS:
                console.print(
                    f"[yellow]URL limit ({MAX_SITEMAP_URLS}) reached. "
                    f"Truncating sitemap results.[/yellow]",
                )
                break
            sitemap_url_nested = sitemap_loc.text
            console.print(
                f"[dim]  Parsing nested sitemap: {sitemap_url_nested}[/dim]",
            )
            nested_urls = parse_sitemap(
                sitemap_url_nested,
                _depth=_depth + 1,
                _accumulated=_accumulated + len(urls),
            )
            urls.extend(nested_urls)
    # Regular sitemap with URLs (using walrus operator for efficiency)
    elif (url_elements := root.findall(".//sm:url/sm:loc", ns)) or (
        url_elements := root.findall(".//loc")
    ):
        urls = [loc.text for loc in url_elements if loc.text]

    # Enforce global URL limit
    urls = urls[:MAX_SITEMAP_URLS]

    console.print(f"[green]✓ Extracted {len(urls)} URLs from sitemap[/green]")
    return urls


def sanitize_filename(url: str) -> str:
    """Generate a safe, meaningful filename from URL."""
    parsed_url = urlparse(url)

    # Get domain without www, preserve TLD
    domain = parsed_url.netloc.replace("www.", "").replace(".", "_")

    # Handle trailing slash
    path = parsed_url.path
    path = path.removesuffix("/")

    # Extract path segments
    segments = [seg for seg in path.split("/") if seg]

    if segments:
        # Use the last path segment as the base filename
        file_name = segments[-1]

        # Remove common extensions
        if "." in file_name:
            file_name = re.sub(
                r"\.(html?|php|aspx?)$",
                "",
                file_name,
                flags=re.IGNORECASE,
            )

        # Clean the filename
        file_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in file_name)

        # Add path hash for uniqueness (md5 is fine for non-security use)
        path_hash = hashlib.md5(  # noqa: S324
            parsed_url.path.encode(),
        ).hexdigest()[:8]
        return f"{domain}_{file_name}_{path_hash}.md"
    # For root URLs, use domain with hash
    path_hash = hashlib.md5(url.encode()).hexdigest()[:8]  # noqa: S324
    return f"{domain}_{path_hash}.md"


def is_markdown_url(url: str) -> bool:
    """Check if URL points to a raw markdown file."""
    parsed = urlparse(url)
    return parsed.path.lower().endswith(MARKDOWN_URL_SUFFIXES)


# Retry configuration for transient HTTP errors
MAX_RETRIES = 3
RETRY_WAIT_MIN = 2  # seconds
RETRY_WAIT_MAX = 10  # seconds


@retry(
    stop=stop_after_attempt(MAX_RETRIES),
    wait=wait_exponential(multiplier=1, min=RETRY_WAIT_MIN, max=RETRY_WAIT_MAX),
    retry=retry_if_exception_type(
        (
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
            requests.exceptions.HTTPError,
        ),
    ),
    reraise=True,
)
def _fetch_url_content(url: str) -> str:
    """
    Fetch URL content with automatic retry on transient errors.

    Uses requests.get() instead of trafilatura.fetch_url() to:
    1. Control User-Agent header for better scraping compatibility
    2. Integrate with tenacity retry logic for transient error handling
    3. Support the is_markdown_url() bypass for raw .md files
    """
    response = requests.get(
        url,
        timeout=30,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    # Retry on 5xx server errors, don't retry 4xx (won't help)
    if response.status_code >= 500:
        response.raise_for_status()
    response.raise_for_status()
    return response.text


def process_url(
    url: str,
    output_dir: Path,
    crawler_config,
    *,
    min_words: int = 0,
) -> ProcessResult:
    """Process a single URL and save markdown."""
    try:
        # Create per-domain subdirectory
        parsed_domain = urlparse(url)
        domain_dir = parsed_domain.netloc.replace("www.", "").replace(".", "_")
        domain_output_dir = output_dir / domain_dir
        domain_output_dir.mkdir(parents=True, exist_ok=True)

        filename = sanitize_filename(url)
        filepath = domain_output_dir / filename

        # Skip if file already exists
        if filepath.exists():
            return url, True, f"SKIPPED (already exists): {filepath}"

        # Fetch content with retry logic
        downloaded = _fetch_url_content(url)

        if not downloaded:
            _raise_download_error(url)

        # Check if URL serves raw markdown - save directly without extraction
        if is_markdown_url(url):
            result = downloaded
        else:
            # Use trafilatura for HTML content extraction
            result = extract(
                downloaded,
                include_comments=False,
                include_tables=True,
                output_format="markdown",
                with_metadata=True,
                config=crawler_config,
                include_links=True,
            )

            if not result:
                _raise_extraction_error(url)

        # Filter by minimum word count
        if min_words > 0:
            word_count = len(result.split())
            if word_count < min_words:
                return (
                    url,
                    True,
                    f"SKIPPED (only {word_count} words, minimum {min_words})",
                )

        # Save to file
        filepath.write_text(result, encoding="utf-8")
        return url, True, str(filepath)

    except requests.exceptions.SSLError as e:
        return url, False, f"SSL certificate error for {url}: {e}"
    except (
        DownloadError,
        ExtractionError,
        requests.RequestException,
    ) as e:
        # Preserve enhanced error messages
        error_msg = str(e)
        if hasattr(e, "__notes__"):
            error_msg += "\n" + "\n".join(f"  Note: {note}" for note in e.__notes__)
        return url, False, error_msg


def _process_sitemap_urls(
    sitemap_url: str,
    *,
    save_urls_flag: bool,
    yes: bool = False,
) -> URLList:
    """Process sitemap and return URLs."""
    try:
        sitemap_urls = parse_sitemap(sitemap_url)
    except (SitemapError, requests.RequestException) as e:
        console.print(f"[red]Error processing sitemap: {e}[/red]")
        if hasattr(e, "__notes__"):
            for note in e.__notes__:
                console.print(f"[dim]  {note}[/dim]")
        sys.exit(EXIT_NETWORK_ERROR)

    # Show preview of URLs
    console.print(
        f"\n[cyan]Preview of URLs from sitemap (first {URL_PREVIEW_LIMIT}):[/cyan]",
    )
    for url in sitemap_urls[:URL_PREVIEW_LIMIT]:
        console.print(f"  • {url}")
    if len(sitemap_urls) > URL_PREVIEW_LIMIT:
        console.print(
            f"  [dim]... and {len(sitemap_urls) - URL_PREVIEW_LIMIT} more[/dim]",
        )

    # Option to save URLs
    if save_urls_flag:
        save_urls_to_file(sitemap_urls, Path())

    # Ask for confirmation
    console.print()
    if not yes and not Confirm.ask(
        f"[yellow]Proceed with downloading {len(sitemap_urls)} URLs?[/yellow]",
    ):
        console.print("[yellow]Aborted by user[/yellow]")
        sys.exit(0)

    return sitemap_urls


def _load_urls_from_file(input_file: Path) -> URLList:
    """Load URLs from input file."""
    try:
        file_urls = [
            stripped
            for line in input_file.read_text(encoding="utf-8").splitlines()
            if (stripped := line.strip()) and not stripped.startswith("#")
        ]
    except OSError as e:
        console.print(f"[red]Error reading input file: {e}[/red]")
        console.print(f"[dim]  File path: {input_file}[/dim]")
        console.print("[dim]  Ensure the file exists and is readable[/dim]")
        sys.exit(EXIT_GENERAL_ERROR)

    console.print(f"[green]✓ Loaded {len(file_urls)} URLs from file[/green]")
    return file_urls


def _format_elapsed_time(elapsed_time: float) -> str:
    """Format elapsed time into human-readable string."""
    if elapsed_time < SECONDS_PER_MINUTE:
        return f"{elapsed_time:.1f}s"
    if elapsed_time < SECONDS_PER_HOUR:
        minutes = int(elapsed_time // SECONDS_PER_MINUTE)
        seconds = elapsed_time % SECONDS_PER_MINUTE
        return f"{minutes}m {seconds:.0f}s"
    hours = int(elapsed_time // SECONDS_PER_HOUR)
    minutes = int((elapsed_time % SECONDS_PER_HOUR) // SECONDS_PER_MINUTE)
    return f"{hours}h {minutes}m"


def _merge_results(results: list[ProcessResult], output_dir: Path) -> Path | None:
    """Combine all successfully scraped files into a single markdown document."""
    successful = [
        (url, filepath)
        for url, success, filepath in results
        if success and "SKIPPED" not in filepath
    ]

    if not successful:
        console.print("[yellow]No successful results to merge[/yellow]")
        return None

    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    merged_path = output_dir / f"merged_{timestamp}.md"

    with open(merged_path, "w", encoding="utf-8") as merged:
        merged.write(f"# Merged Content ({len(successful)} pages)\n\n")
        merged.write(f"Generated: {datetime.now(UTC).isoformat()}\n\n")
        merged.write("---\n\n")

        for url, filepath in successful:
            content = Path(filepath).read_text(encoding="utf-8")
            merged.write(f"## Source: {url}\n\n")
            merged.write(content)
            merged.write("\n\n---\n\n")

    console.print(f"[green]✓ Merged output saved to:[/green] {merged_path}")
    return merged_path


def _display_results(results: list[ProcessResult], elapsed_time: float) -> None:
    """Display processing results summary."""
    console.print()
    successful = sum(1 for _, success, _ in results if success)
    failed = len(results) - successful
    skipped = sum(1 for _, success, msg in results if success and "SKIPPED" in msg)

    time_str = _format_elapsed_time(elapsed_time)
    processed = successful - skipped
    rate = processed / elapsed_time if elapsed_time > 0 and processed > 0 else 0

    summary_panel = Panel(
        f"[green]✓ Successful: {processed}[/green]\n"
        f"[yellow]⊙ Skipped: {skipped}[/yellow]\n"
        f"[red]✗ Failed: {failed}[/red]\n"
        f"[cyan]Total: {len(results)}[/cyan]\n"
        f"[dim]Time: {time_str} ({rate:.1f} pages/sec)[/dim]",
        title="Summary",
        border_style="blue",
    )
    console.print(summary_panel)

    # Show failed URLs if any
    if failed > 0:
        console.print("\n[red]Failed URLs:[/red]")
        for url, success, error in results:
            if not success:
                console.print(f"  • {url}")
                console.print(f"    [dim]{error}[/dim]")


def main(
    sitemap_url: str | None,
    input_file: Path | None,
    output_dir: Path,
    *,
    direct_urls: list[str] | None = None,
    save_urls_flag: bool,
    workers: int = DEFAULT_WORKERS,
    min_words: int = DEFAULT_MIN_WORDS,
    merge: bool = False,
    force: bool = False,
    yes: bool = False,
    json_output: bool = False,
) -> None:
    """Main processing function."""
    urls: URLList = []

    # Gather URLs passed directly via --url
    if direct_urls:
        urls.extend(direct_urls)

    # Gather URLs from sitemap
    if sitemap_url:
        urls.extend(
            _process_sitemap_urls(sitemap_url, save_urls_flag=save_urls_flag, yes=yes),
        )

    # Gather URLs from input file
    if input_file:
        urls.extend(_load_urls_from_file(input_file))

    if not urls:
        console.print("[yellow]No URLs to process[/yellow]")
        sys.exit(0)

    # Remove duplicates while preserving order
    seen: set[str] = set()
    unique_urls = [url for url in urls if url not in seen and not seen.add(url)]

    if len(urls) != len(unique_urls):
        console.print(
            f"[yellow]Removed {len(urls) - len(unique_urls)} duplicate URLs[/yellow]",
        )

    # Cross-run deduplication via scrape index
    scrape_index = _load_scrape_index()
    if not force and scrape_index:
        already_scraped = [url for url in unique_urls if url in scrape_index]
        if already_scraped:
            unique_urls = [url for url in unique_urls if url not in scrape_index]
            console.print(
                f"[yellow]Skipping {len(already_scraped)} URLs already scraped "
                f"in previous runs (use --force to re-scrape)[/yellow]",
            )
            if not unique_urls:
                console.print(
                    "[yellow]All URLs already scraped. Nothing to do.[/yellow]",
                )
                sys.exit(0)

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Get crawler configuration
    crawler_config = get_crawler_config()

    # Display configuration
    config_table = Table(title="Configuration", show_header=False)
    config_table.add_column("Setting", style="cyan")
    config_table.add_column("Value", style="green")
    if sitemap_url:
        config_table.add_row("Sitemap URL", sitemap_url)
    if input_file:
        config_table.add_row("Input File", str(input_file))
    config_table.add_row("Output Directory", str(output_dir))
    config_table.add_row("Total URLs", str(len(unique_urls)))
    config_table.add_row("Extractor", "Trafilatura")
    config_table.add_row("Workers", str(min(workers, len(unique_urls))))
    console.print()
    console.print(config_table)
    console.print()

    # Process URLs concurrently with progress bar and timing
    results: list[ProcessResult] = []
    start_time = perf_counter()
    num_workers = min(workers, MAX_WORKERS, len(unique_urls))

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Processing URLs", total=len(unique_urls))

        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            future_to_url = {
                executor.submit(
                    process_url,
                    url,
                    output_dir,
                    crawler_config,
                    min_words=min_words,
                ): url
                for url in unique_urls
            }

            for future in as_completed(future_to_url):
                result = future.result()
                results.append(result)
                url_display = result[0][:50]
                status = "[green]✓" if result[1] else "[red]✗"
                progress.update(
                    task,
                    advance=1,
                    description=f"{status}[/] {url_display}...",
                )

    elapsed_time = perf_counter() - start_time
    _display_results(results, elapsed_time)

    # Update scrape index with newly scraped URLs
    for url, success, filepath_or_msg in results:
        if success and "SKIPPED" not in filepath_or_msg:
            scrape_index[url] = filepath_or_msg
    _save_scrape_index(scrape_index)

    if merge:
        _merge_results(results, output_dir)

    if json_output:
        import json as json_mod

        successful = sum(1 for _, success, _ in results if success)
        skipped = sum(1 for _, success, msg in results if success and "SKIPPED" in msg)
        failed = len(results) - successful
        processed = successful - skipped
        files = [msg for _, success, msg in results if success and "SKIPPED" not in msg]
        summary = {
            "status": "success",
            "total": len(results),
            "successful": processed,
            "skipped": skipped,
            "failed": failed,
            "output_dir": str(output_dir),
            "elapsed_seconds": round(elapsed_time, 2),
            "files": files,
        }
        print(json_mod.dumps(summary, indent=2))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Batch download URLs from sitemap.xml or text file using Trafilatura",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Download a single URL directly
  %(prog)s -u https://example.com/article

  # Download multiple URLs directly
  %(prog)s -u https://example.com/page1 https://example.com/page2

  # From sitemap only
  %(prog)s --sitemap https://example.com/sitemap.xml

  # From sitemap with URL export
  %(prog)s --sitemap https://example.com/sitemap.xml --save-urls

  # From text file only
  %(prog)s --input urls.txt

  # From both sitemap and text file
  %(prog)s --sitemap https://example.com/sitemap.xml --input urls.txt

  # Custom output directory
  %(prog)s --sitemap https://example.com/sitemap.xml -o custom/folder
        """,
    )
    parser.add_argument(
        "-s",
        "--sitemap",
        type=str,
        help="Sitemap XML URL to parse and download",
    )
    parser.add_argument(
        "-u",
        "--url",
        type=str,
        nargs="+",  # Allow one or more URLs
        help="Direct URL(s) to download and extract content from",
    )
    parser.add_argument(
        "-i",
        "--input",
        type=Path,
        help="Input file containing URLs (one per line)",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory for markdown files (default: output/research/scrapes/YYYY-MM-DD)",
    )
    parser.add_argument(
        "--save-urls",
        action="store_true",
        help="Save extracted sitemap URLs to a text file before processing",
    )
    parser.add_argument(
        "-w",
        "--workers",
        type=int,
        default=DEFAULT_WORKERS,
        help=f"Number of concurrent download workers (default: {DEFAULT_WORKERS}, max: {MAX_WORKERS})",
    )
    parser.add_argument(
        "--min-words",
        type=int,
        default=DEFAULT_MIN_WORDS,
        help=f"Minimum word count to save content (default: {DEFAULT_MIN_WORDS}, 0 to disable)",
    )
    parser.add_argument(
        "--merge",
        action="store_true",
        help="Also produce a single merged markdown file with all results",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-scrape URLs even if they exist in the scrape index",
    )
    parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Auto-confirm prompts (non-interactive mode for automation)",
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
        console = Console(quiet=True)

    # Validate that at least one input source is provided
    if not args.sitemap and not args.input and not args.url:
        parser.error("At least one of --sitemap, --input, or --url must be provided")

    # Set default output directory with today's date
    if args.output_dir is None:
        console.print(
            "[red]Error: --output-dir / -o is required.[/red]\n"
            "[yellow]The aws-deep-research skill writes all intermediate artifacts "
            "under $WORK_DIR/<slug>/downloads/.[/yellow]\n"
            "[yellow]Pass:  -o $WORK_DIR/<slug>/downloads/blogs[/yellow]"
        )
        sys.exit(EXIT_INVALID_ARGS)

    # Resolve scrape index relative to output directory
    globals()['SCRAPE_INDEX_FILE'] = args.output_dir / ".scrape_index.json"

    try:
        main(
            args.sitemap,
            args.input,
            args.output_dir,
            direct_urls=args.url,
            save_urls_flag=args.save_urls,
            workers=args.workers,
            min_words=args.min_words,
            merge=args.merge,
            force=args.force,
            yes=args.yes,
            json_output=args.json_output,
        )
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
        sys.exit(130)
