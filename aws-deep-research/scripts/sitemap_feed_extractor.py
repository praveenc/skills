# /// script
# requires-python = ">=3.13"
# dependencies = [
#   "requests>=2.31.0",
#   "rich>=13.7.0",
#   "defusedxml>=0.7.1",
# ]
# ///
"""
Sitemap & Feed Extractor — Smart date-filtered URL extraction from sitemaps, RSS, and Atom feeds

Fetches a sitemap.xml (or discovers it from a homepage), extracts <url> entries
with <lastmod> dates, and returns the most relevant URLs filtered by count or
date range. Designed for LLM/agent workflows where full sitemaps are too large
for context windows.

Supports:
  - Standard XML sitemaps and sitemap indexes (recursive, up to 10 levels)
  - RSS 2.0 feeds (<item> with <pubDate>)
  - Atom feeds (<entry> with <updated>)
  - Google News sitemaps (<news:publication_date> as date source)
  - Gzip-compressed sitemaps (.xml.gz)
  - Auto-discovery from homepage URL (robots.txt + common paths)
  - Graceful handling of malformed/truncated XML

Smart filtering strategy (--top N mode):
  1. Determine the current date (or use --start-date)
  2. Start filtering from the current month
  3. If fewer than N results, expand backward one month at a time
  4. Stop once N results are collected or the sitemap is exhausted

Date range mode (--from / --to):
  Return all URLs with lastmod within the specified date range.

Route filtering (--route):
  Pre-filter entries by URL path before applying date/top-N logic.
  Only entries whose URL path contains the route substring are kept.
  Can be used standalone (without --top or --from) to return ALL matching entries.
  Useful when sitemaps lack dates and you want a specific section (e.g. /blog/).

Usage:
    uv run sitemap/sitemap_feed_extractor.py https://example.com/sitemap.xml --top 10
    uv run sitemap/sitemap_feed_extractor.py https://example.com/sitemap.xml --top 10 --route blog
    uv run sitemap/sitemap_feed_extractor.py https://example.com --top 10 --discover
    uv run sitemap/sitemap_feed_extractor.py https://example.com/sitemap.xml --from 2026-01-01 --to 2026-03-07
    uv run sitemap/sitemap_feed_extractor.py https://example.com/sitemap.xml --top 20 --start-date 2026-02-15
    uv run sitemap/sitemap_feed_extractor.py https://example.com/sitemap.xml --top 10 --output urls.txt
    uv run sitemap/sitemap_feed_extractor.py https://example.com/sitemap.xml --top 10 --json
    uv run sitemap/sitemap_feed_extractor.py https://aws.amazon.com/blogs/aws/feed/ --top 5
"""

from __future__ import annotations

import argparse
import gzip
import json
import re
import sys
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date, datetime
from io import BytesIO
from urllib.parse import urljoin, urlparse

import requests
from defusedxml import ElementTree as ET
from rich.console import Console
from rich.table import Table

# ── Constants ────────────────────────────────────────────────────────────────

SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"
NEWS_NS = "http://www.google.com/schemas/sitemap-news/0.9"
ATOM_NS = "http://www.w3.org/2005/Atom"

SITEMAPINDEX_TAG = f"{{{SITEMAP_NS}}}sitemapindex"
SITEMAP_TAG = f"{{{SITEMAP_NS}}}sitemap"
URL_TAG = f"{{{SITEMAP_NS}}}url"
LOC_TAG = f"{{{SITEMAP_NS}}}loc"
LASTMOD_TAG = f"{{{SITEMAP_NS}}}lastmod"
PRIORITY_TAG = f"{{{SITEMAP_NS}}}priority"
CHANGEFREQ_TAG = f"{{{SITEMAP_NS}}}changefreq"

# Google News sitemap tags
NEWS_TAG = f"{{{NEWS_NS}}}news"
NEWS_PUB_DATE_TAG = f"{{{NEWS_NS}}}publication_date"
NEWS_TITLE_TAG = f"{{{NEWS_NS}}}title"
NEWS_PUB_TAG = f"{{{NEWS_NS}}}publication"
NEWS_PUB_NAME_TAG = f"{{{NEWS_NS}}}name"

USER_AGENT = "Mozilla/5.0 (compatible; SitemapExtractor/1.0; +https://github.com/llm-utility-scripts)"
REQUEST_TIMEOUT = 30
MAX_EXPAND_MONTHS = 120  # go back up to 10 years
MAX_RECURSION_DEPTH = 10  # max sitemap index nesting

# Common sitemap paths to probe when using --discover
_COMMON_SITEMAP_PATHS = [
    "sitemap.xml",
    "sitemap.xml.gz",
    "sitemap_index.xml",
    "sitemap-index.xml",
    "sitemap_index.xml.gz",
    "sitemap-index.xml.gz",
    ".sitemap.xml",
    "sitemap",
    "sitemap/sitemap-index.xml",
]

console = Console()


# ── Data types ───────────────────────────────────────────────────────────────


@dataclass(slots=True, frozen=True)
class SitemapEntry:
    """A single <url> entry from a sitemap."""

    loc: str
    lastmod: date | None
    priority: float | None
    changefreq: str | None = None
    news_title: str | None = None
    news_publication: str | None = None


@dataclass
class FetchStats:
    """Track fetch statistics for the summary panel."""

    sitemaps_fetched: int = 0
    total_bytes: int = 0
    total_time: float = 0.0
    errors: list[str] = field(default_factory=list)


# ── Parsing helpers ──────────────────────────────────────────────────────────


def parse_lastmod(raw: str) -> date | None:
    """Parse a lastmod string — handles ISO-8601 datetime, date-only, and common variants."""
    if not raw:
        return None
    raw = raw.strip()
    # Try date-only first (most common in sitemaps)
    for fmt in (
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S.%fZ",
    ):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    # Last resort: take first 10 chars as YYYY-MM-DD
    try:
        return datetime.strptime(raw[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def parse_rfc2822_date(raw: str) -> date | None:
    """Parse RSS pubDate (RFC 2822 format): 'Wed, 04 Mar 2026 20:04:16 +0000'."""
    if not raw:
        return None
    from email.utils import parsedate_to_datetime

    try:
        return parsedate_to_datetime(raw.strip()).date()
    except (ValueError, TypeError):
        # Fall back to ISO parsing in case feed uses ISO dates
        return parse_lastmod(raw)


def parse_priority(raw: str | None) -> float | None:
    if raw is None:
        return None
    try:
        return float(raw.strip())
    except ValueError:
        return None


def _get_el_text(parent: ET.Element, tag: str) -> str | None:  # type: ignore[name-defined]
    """Safely get text from a child element."""
    el = parent.find(tag)
    if el is not None and el.text:
        return el.text.strip()
    return None


# ── Fetching ─────────────────────────────────────────────────────────────────


def fetch_sitemap_bytes(url: str, stats: FetchStats) -> bytes | None:
    """
    Download sitemap content. Handles:
      - Transport-level gzip (Accept-Encoding)
      - .xml.gz files (content-level gzip decompression)
      - Returns None on failure (non-fatal)
    """
    t0 = time.monotonic()
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": USER_AGENT, "Accept-Encoding": "gzip, deflate"},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        stats.errors.append(f"{url}: {exc}")
        console.print(f"[red]✗ {url}: {exc}[/red]", highlight=False)
        return None

    elapsed = time.monotonic() - t0
    content = resp.content
    stats.sitemaps_fetched += 1
    stats.total_bytes += len(content)
    stats.total_time += elapsed

    # Decompress .xml.gz if needed (content-level gzip, not transport-level)
    if url.endswith(".gz") or _is_gzipped(content):
        try:
            content = gzip.decompress(content)
        except gzip.BadGzipFile:
            pass  # Not actually gzipped — use raw content

    console.print(
        f"[green]✓[/green] {url} ({len(content) / 1024:,.1f} KB, {elapsed:.1f}s)",
        highlight=False,
    )
    return content


def _is_gzipped(data: bytes) -> bool:
    """Check if data starts with gzip magic bytes."""
    return len(data) >= 2 and data[0:2] == b"\x1f\x8b"


# ── XML Parsing (error-tolerant) ─────────────────────────────────────────────


def _safe_parse_xml(xml_bytes: bytes, source_url: str) -> ET.Element | None:  # type: ignore[name-defined]
    """
    Parse XML with error tolerance. If the XML is truncated or malformed,
    try to salvage what we can by closing unclosed tags.
    """
    try:
        tree = ET.parse(BytesIO(xml_bytes))
        return tree.getroot()
    except ET.ParseError:
        # Try to recover truncated XML by brute-force closing the root tag
        for close_tag in (b"</urlset>", b"</sitemapindex>"):
            try:
                patched = xml_bytes + close_tag
                tree = ET.parse(BytesIO(patched))
                return tree.getroot()
            except ET.ParseError:
                continue
        console.print(f"[red]✗ Unparseable XML: {source_url}[/red]", highlight=False)
        return None


def iter_entries_from_xml(xml_bytes: bytes, source_url: str) -> Iterator[SitemapEntry]:
    """Parse sitemap XML and yield SitemapEntry objects. Error-tolerant."""
    root = _safe_parse_xml(xml_bytes, source_url)
    if root is None:
        return

    for url_el in root.iter(URL_TAG):
        loc_text = _get_el_text(url_el, LOC_TAG)
        if not loc_text:
            continue

        # Standard lastmod
        lastmod = parse_lastmod(_get_el_text(url_el, LASTMOD_TAG) or "")

        # Google News: use publication_date as fallback date source
        news_title: str | None = None
        news_pub_name: str | None = None
        news_el = url_el.find(NEWS_TAG)
        if news_el is not None:
            news_title = _get_el_text(news_el, NEWS_TITLE_TAG)
            pub_el = news_el.find(NEWS_PUB_TAG)
            if pub_el is not None:
                news_pub_name = _get_el_text(pub_el, NEWS_PUB_NAME_TAG)
            # Use news publication_date if no lastmod
            if lastmod is None:
                news_date_str = _get_el_text(news_el, NEWS_PUB_DATE_TAG)
                if news_date_str:
                    lastmod = parse_lastmod(news_date_str)

        yield SitemapEntry(
            loc=loc_text,
            lastmod=lastmod,
            priority=parse_priority(_get_el_text(url_el, PRIORITY_TAG)),
            changefreq=_get_el_text(url_el, CHANGEFREQ_TAG),
            news_title=news_title,
            news_publication=news_pub_name,
        )


# ── RSS / Atom Parsing ──────────────────────────────────────────────────────

DC_NS = "http://purl.org/dc/elements/1.1/"


def _parse_rss_entries(root: ET.Element) -> list[SitemapEntry]:  # type: ignore[name-defined]
    """Parse RSS 2.0 <channel><item> elements into SitemapEntry objects."""
    entries: list[SitemapEntry] = []
    channel = root.find("channel")
    if channel is None:
        return entries

    for item in channel.findall("item"):
        link = _get_el_text(item, "link")
        if not link:
            continue
        entries.append(
            SitemapEntry(
                loc=link,
                lastmod=parse_rfc2822_date(_get_el_text(item, "pubDate") or ""),
                priority=None,
                news_title=_get_el_text(item, "title"),
                news_publication=_get_el_text(item, f"{{{DC_NS}}}creator"),
            ),
        )
    return entries


def _parse_atom_entries(root: ET.Element) -> list[SitemapEntry]:  # type: ignore[name-defined]
    """Parse Atom <feed><entry> elements into SitemapEntry objects."""
    ns = f"{{{ATOM_NS}}}"
    entries: list[SitemapEntry] = []

    for entry_el in root.findall(f"{ns}entry"):
        # Atom links are in <link href="..."/> attributes
        link_el = entry_el.find(f"{ns}link")
        href = link_el.get("href") if link_el is not None else None
        if not href:
            continue

        # Prefer <updated>, fall back to <published>
        date_str = _get_el_text(entry_el, f"{ns}updated") or _get_el_text(
            entry_el,
            f"{ns}published",
        )
        # Author
        author_el = entry_el.find(f"{ns}author")
        author_name = (
            _get_el_text(author_el, f"{ns}name") if author_el is not None else None
        )

        entries.append(
            SitemapEntry(
                loc=href,
                lastmod=parse_lastmod(date_str or ""),
                priority=None,
                news_title=_get_el_text(entry_el, f"{ns}title"),
                news_publication=author_name,
            ),
        )
    return entries


def _detect_format(root: ET.Element) -> str:  # type: ignore[name-defined]
    """Detect XML format from root tag. Returns 'sitemap-index', 'sitemap', 'rss', 'atom', or 'unknown'."""
    tag = root.tag
    if tag == SITEMAPINDEX_TAG:
        return "sitemap-index"
    if tag == f"{{{SITEMAP_NS}}}urlset":
        return "sitemap"
    if tag == "rss":
        return "rss"
    if tag == f"{{{ATOM_NS}}}feed":
        return "atom"
    return "unknown"


# ── Sitemap Index Handling (recursive) ───────────────────────────────────────


def _get_child_sitemap_urls(root: ET.Element) -> list[str]:  # type: ignore[name-defined]
    """Extract child sitemap URLs from a sitemap index root element."""
    urls: list[str] = []
    for sitemap_el in root.iter(SITEMAP_TAG):
        loc_text = _get_el_text(sitemap_el, LOC_TAG)
        if loc_text:
            urls.append(loc_text)
    return urls


def collect_entries_recursive(
    url: str,
    stats: FetchStats,
    *,
    depth: int = 0,
) -> list[SitemapEntry]:
    """
    Fetch a sitemap URL and collect entries. If it's a sitemap index,
    recurse into children (up to MAX_RECURSION_DEPTH).
    """
    if depth > MAX_RECURSION_DEPTH:
        console.print(
            f"[yellow]⚠ Max depth reached, skipping {url}[/yellow]",
            highlight=False,
        )
        return []

    xml_bytes = fetch_sitemap_bytes(url, stats)
    if xml_bytes is None:
        return []

    root = _safe_parse_xml(xml_bytes, url)
    if root is None:
        return []

    fmt = _detect_format(root)

    # RSS feed
    if fmt == "rss":
        console.print("  ↳ RSS feed detected")
        return _parse_rss_entries(root)

    # Atom feed
    if fmt == "atom":
        console.print("  ↳ Atom feed detected")
        return _parse_atom_entries(root)

    # Sitemap index — recurse into children
    if fmt == "sitemap-index":
        child_urls = _get_child_sitemap_urls(root)
        console.print(f"  ↳ Sitemap index with {len(child_urls)} child sitemap(s)")
        entries: list[SitemapEntry] = []
        for child_url in child_urls:
            entries.extend(collect_entries_recursive(child_url, stats, depth=depth + 1))
        return entries

    # It's a urlset — parse entries directly from already-parsed root
    entries = []
    for url_el in root.iter(URL_TAG):
        loc_text = _get_el_text(url_el, LOC_TAG)
        if not loc_text:
            continue

        lastmod = parse_lastmod(_get_el_text(url_el, LASTMOD_TAG) or "")

        news_title: str | None = None
        news_pub_name: str | None = None
        news_el = url_el.find(NEWS_TAG)
        if news_el is not None:
            news_title = _get_el_text(news_el, NEWS_TITLE_TAG)
            pub_el = news_el.find(NEWS_PUB_TAG)
            if pub_el is not None:
                news_pub_name = _get_el_text(pub_el, NEWS_PUB_NAME_TAG)
            if lastmod is None:
                news_date_str = _get_el_text(news_el, NEWS_PUB_DATE_TAG)
                if news_date_str:
                    lastmod = parse_lastmod(news_date_str)

        entries.append(
            SitemapEntry(
                loc=loc_text,
                lastmod=lastmod,
                priority=parse_priority(_get_el_text(url_el, PRIORITY_TAG)),
                changefreq=_get_el_text(url_el, CHANGEFREQ_TAG),
                news_title=news_title,
                news_publication=news_pub_name,
            ),
        )
    return entries


# ── Sitemap Discovery ────────────────────────────────────────────────────────


def discover_sitemaps_from_homepage(homepage_url: str, stats: FetchStats) -> list[str]:
    """
    Given a homepage URL, discover sitemap URLs by:
      1. Parsing robots.txt for Sitemap: directives
      2. Probing common sitemap paths
    Returns deduplicated list of valid sitemap URLs.
    """
    parsed = urlparse(homepage_url)
    base = f"{parsed.scheme}://{parsed.netloc}/"

    console.print(f"Discovering sitemaps for {base}")

    found_urls: dict[str, bool] = {}  # ordered set

    # 1. Check robots.txt
    robots_url = urljoin(base, "robots.txt")
    try:
        resp = requests.get(
            robots_url,
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT,
        )
        if resp.ok:
            for line in resp.text.splitlines():
                match = re.match(r"^sitemap:\s*(.+)$", line.strip(), re.IGNORECASE)
                if match:
                    sitemap_url = match.group(1).strip()
                    if sitemap_url.startswith("http"):
                        found_urls[sitemap_url] = True
    except requests.RequestException:
        pass

    # 2. Probe common paths
    for path in _COMMON_SITEMAP_PATHS:
        probe_url = urljoin(base, path)
        if probe_url in found_urls:
            continue
        try:
            resp = requests.head(
                probe_url,
                headers={"User-Agent": USER_AGENT},
                timeout=10,
                allow_redirects=True,
            )
            if resp.ok:
                found_urls[probe_url] = True
        except requests.RequestException:
            pass

    if found_urls:
        console.print(f"  Found {len(found_urls)} sitemap(s)")
    else:
        console.print("[yellow]No sitemaps discovered[/yellow]")

    return list(found_urls.keys())


# ── Main Collection Entry Point ──────────────────────────────────────────────


def collect_all_entries(
    url: str,
    stats: FetchStats,
    *,
    discover: bool = False,
) -> list[SitemapEntry]:
    """
    Fetch sitemap(s) and return all SitemapEntry objects.

    If discover=True, treat `url` as a homepage and discover sitemaps first.
    Otherwise, treat `url` as a direct sitemap URL.
    """
    if discover:
        sitemap_urls = discover_sitemaps_from_homepage(url, stats)
        if not sitemap_urls:
            return []
        console.print()
        entries: list[SitemapEntry] = []
        for sm_url in sitemap_urls:
            entries.extend(collect_entries_recursive(sm_url, stats))
        # Deduplicate by URL (keep first occurrence, which preserves ordering)
        seen: set[str] = set()
        deduped: list[SitemapEntry] = []
        for e in entries:
            if e.loc not in seen:
                seen.add(e.loc)
                deduped.append(e)
        return deduped
    return collect_entries_recursive(url, stats)


# ── Filtering ────────────────────────────────────────────────────────────────


def filter_by_route(entries: list[SitemapEntry], route: str) -> list[SitemapEntry]:
    """
    Pre-filter entries whose URL path contains the route substring.
    Excludes the bare section index (e.g. /blog itself when route="blog").

    The match is case-insensitive and checks the path portion of the URL.

    Examples:
      route="blog"      matches /blog/my-post, /en/blog/post  (NOT /blog or /blog/)
      route="blog/2026" matches /blog/2026/my-post
      route="docs"      matches /docs/api/reference  (NOT /docs or /docs/)

    """
    # Normalize: strip leading/trailing slashes for consistent matching
    route_lower = route.strip("/").lower()

    filtered: list[SitemapEntry] = []
    for entry in entries:
        parsed_path = urlparse(entry.loc).path.strip("/").lower()
        # Must contain the route AND have additional path segments after it
        if route_lower not in parsed_path:
            continue
        # Find where the route ends in the path
        idx = parsed_path.find(route_lower)
        remainder = parsed_path[idx + len(route_lower) :]
        # Exclude bare section index: remainder must have real content after the route
        # e.g. "/blog" → remainder="" (excluded), "/blog/my-post" → remainder="/my-post" (kept)
        remainder = remainder.strip("/")
        if remainder:
            filtered.append(entry)

    return filtered


def month_start(y: int, m: int) -> date:
    return date(y, m, 1)


def prev_month(y: int, m: int) -> tuple[int, int]:
    if m == 1:
        return y - 1, 12
    return y, m - 1


def filter_top_n(
    entries: list[SitemapEntry],
    n: int,
    start: date,
) -> list[SitemapEntry]:
    """
    Grab top N entries by expanding backward from `start` month-by-month.

    Strategy:
      - Entries WITH lastmod are sorted descending by date and taken greedily.
      - Entries WITHOUT lastmod are appended at the end if still needed.
    """
    # Split entries with and without dates
    dated = sorted(
        [e for e in entries if e.lastmod is not None],
        key=lambda e: e.lastmod,  # type: ignore[arg-type]
        reverse=True,
    )
    undated = [e for e in entries if e.lastmod is None]

    if not dated:
        # No dates at all — just return first N entries (or all undated)
        console.print(
            "[yellow]No <lastmod> dates found — returning first N entries[/yellow]",
        )
        return undated[:n]

    # Expand month-by-month from start
    results: list[SitemapEntry] = []
    y, m = start.year, start.month

    for _ in range(MAX_EXPAND_MONTHS):
        ms = month_start(y, m)
        # Entries in this month: lastmod year-month matches
        month_entries = [
            e
            for e in dated
            if e.lastmod is not None and e.lastmod.year == y and e.lastmod.month == m
        ]
        # Sort by date descending, then by priority descending within same date
        month_entries.sort(
            key=lambda e: (e.lastmod, e.priority if e.priority is not None else 0.0),  # type: ignore[arg-type]
            reverse=True,
        )
        results.extend(month_entries)

        if len(results) >= n:
            results = results[:n]
            break

        y, m = prev_month(y, m)
        # If we've gone past the oldest entry, stop
        oldest = dated[-1].lastmod
        if oldest is not None and ms < date(oldest.year, oldest.month, 1):
            break
    else:
        # Exhausted months — pad with undated if needed
        if len(results) < n:
            results.extend(undated[: n - len(results)])

    return results[:n]


def filter_date_range(
    entries: list[SitemapEntry],
    from_date: date,
    to_date: date,
) -> list[SitemapEntry]:
    """Return entries with lastmod between from_date and to_date (inclusive), sorted descending."""
    filtered = [
        e
        for e in entries
        if e.lastmod is not None and from_date <= e.lastmod <= to_date
    ]
    filtered.sort(key=lambda e: e.lastmod, reverse=True)  # type: ignore[arg-type]
    return filtered


# ── Output ───────────────────────────────────────────────────────────────────


def display_results(entries: list[SitemapEntry]) -> None:
    """Print a Rich table of the extracted entries."""
    # Detect if any entries have news data
    has_news = any(e.news_title for e in entries)

    table = Table(show_lines=False, padding=(0, 1), show_edge=False)
    table.add_column("#", style="dim", width=4, justify="right")
    table.add_column("Date", style="cyan", width=12)
    if has_news:
        table.add_column("Title", style="magenta", max_width=40, no_wrap=True)
    table.add_column("URL", style="green", no_wrap=False)

    for i, entry in enumerate(entries, 1):
        row = [
            str(i),
            str(entry.lastmod) if entry.lastmod else "—",
        ]
        if has_news:
            row.append(entry.news_title or "—")
        row.append(entry.loc)
        table.add_row(*row)

    console.print()
    console.print(table)
    console.print()


def output_json(entries: list[SitemapEntry]) -> str:
    """Return JSON representation of entries."""
    data = []
    for e in entries:
        item: dict = {
            "url": e.loc,
            "lastmod": str(e.lastmod) if e.lastmod else None,
            "priority": e.priority,
        }
        if e.changefreq:
            item["changefreq"] = e.changefreq
        if e.news_title:
            item["news_title"] = e.news_title
        if e.news_publication:
            item["news_publication"] = e.news_publication
        data.append(item)
    return json.dumps(data, indent=2)


def output_urls_only(entries: list[SitemapEntry]) -> str:
    """Return one URL per line."""
    return "\n".join(e.loc for e in entries)


# ── CLI ──────────────────────────────────────────────────────────────────────


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Extract URLs from sitemaps with smart date filtering",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  # Get top 10 most recent posts
  uv run sitemap/sitemap_feed_extractor.py https://example.com/sitemap.xml --top 10

  # Filter by route — only URLs containing /blog/ in their path
  uv run sitemap/sitemap_feed_extractor.py https://windsurf.com/sitemap.xml --top 10 --route blog

  # Get ALL URLs matching a route (no --top needed)
  uv run sitemap/sitemap_feed_extractor.py https://example.com/sitemap.xml --route docs/api

  # Auto-discover sitemaps from a homepage
  uv run sitemap/sitemap_feed_extractor.py https://example.com --top 10 --discover

  # Get posts from a date range
  uv run sitemap/sitemap_feed_extractor.py https://example.com/sitemap.xml --from 2026-01-01 --to 2026-03-07

  # Top 20 starting from a specific date (instead of today)
  uv run sitemap/sitemap_feed_extractor.py https://example.com/sitemap.xml --top 20 --start-date 2026-02-15

  # Output as JSON
  uv run sitemap/sitemap_feed_extractor.py https://example.com/sitemap.xml --top 10 --json

  # Save URLs to a file
  uv run sitemap/sitemap_feed_extractor.py https://example.com/sitemap.xml --top 10 --output urls.txt

  # URLs only (no table), useful for piping
  uv run sitemap/sitemap_feed_extractor.py https://example.com/sitemap.xml --top 10 --urls-only
""",
    )
    parser.add_argument(
        "sitemap_url",
        help="URL of sitemap.xml, RSS feed, or Atom feed (or homepage with --discover)",
    )

    mode = parser.add_argument_group("Filter mode (choose one)")
    mode.add_argument(
        "--top",
        "-n",
        type=int,
        metavar="N",
        help="Get the N most recent URLs (expands backward month-by-month)",
    )
    mode.add_argument(
        "--from",
        dest="from_date",
        type=str,
        metavar="YYYY-MM-DD",
        help="Start of date range (inclusive)",
    )
    mode.add_argument(
        "--to",
        dest="to_date",
        type=str,
        metavar="YYYY-MM-DD",
        help="End of date range (inclusive, defaults to today)",
    )

    opts = parser.add_argument_group("Options")
    opts.add_argument(
        "--route",
        "-r",
        type=str,
        metavar="PATH",
        help="Filter URLs by path substring (e.g. 'blog', 'docs/api', 'news')",
    )
    opts.add_argument(
        "--discover",
        action="store_true",
        help="Treat URL as homepage — discover sitemaps via robots.txt + common paths",
    )
    opts.add_argument(
        "--start-date",
        type=str,
        metavar="YYYY-MM-DD",
        help="Reference date for --top mode (defaults to today)",
    )
    opts.add_argument(
        "--json",
        dest="json_output",
        action="store_true",
        help="Output results as JSON",
    )
    opts.add_argument(
        "--urls-only",
        action="store_true",
        help="Output only URLs, one per line (no table)",
    )
    opts.add_argument(
        "--output",
        "-o",
        type=str,
        metavar="FILE",
        help="Save URLs to a file (one per line)",
    )

    return parser


def parse_date_arg(value: str, label: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        console.print(
            f"[red]Invalid date for {label}: {value!r} (expected YYYY-MM-DD)[/red]",
        )
        sys.exit(1)


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    # Validate mode
    has_top = args.top is not None
    has_from = args.from_date is not None
    has_to = args.to_date is not None
    has_route = args.route is not None

    if not has_top and not has_from and not has_route:
        console.print(
            "[red]Specify either --top N, --from YYYY-MM-DD, or --route PATH[/red]",
        )
        parser.print_help()
        sys.exit(1)

    if has_top and has_from:
        console.print("[red]Cannot use --top and --from together. Pick one mode.[/red]")
        sys.exit(1)

    # Parse dates
    today = date.today()

    if has_top:
        start = (
            parse_date_arg(args.start_date, "--start-date")
            if args.start_date
            else today
        )
    elif has_from:
        from_date = parse_date_arg(args.from_date, "--from")
        to_date = parse_date_arg(args.to_date, "--to") if has_to else today

    # Banner — one compact line
    console.print()
    parts = ["[bold]Sitemap & Feed Extractor[/bold]"]
    if has_top:
        parts.append(f"top {args.top} from {start}")
    elif has_from:
        parts.append(f"{from_date} → {to_date}")
    else:
        parts.append("all matching entries")
    if args.route:
        parts.append(f"route='{args.route}'")
    if args.discover:
        parts.append("discover=on")
    console.print(" · ".join(parts))
    console.print(f"  {args.sitemap_url}", highlight=False)

    # Fetch & parse
    stats = FetchStats()
    try:
        all_entries = collect_all_entries(
            args.sitemap_url,
            stats,
            discover=args.discover,
        )
    except requests.RequestException as exc:
        console.print(f"[red]Failed to fetch sitemap: {exc}[/red]")
        sys.exit(1)

    # Compact stats
    dated_count = sum(1 for e in all_entries if e.lastmod is not None)
    news_count = sum(1 for e in all_entries if e.news_title is not None)
    stat_parts = [f"{len(all_entries)} entries"]
    if dated_count:
        stat_parts.append(f"{dated_count} dated")
    if news_count:
        stat_parts.append(f"{news_count} news")
    console.print(f"Parsed: {', '.join(stat_parts)}")

    if not all_entries:
        console.print("[yellow]No entries found.[/yellow]")
        sys.exit(0)

    # Apply route filter (before date/top-N filtering)
    if args.route:
        pre_count = len(all_entries)
        all_entries = filter_by_route(all_entries, args.route)
        console.print(f"Route '{args.route}': {pre_count} → {len(all_entries)}")
        if not all_entries:
            console.print(f"[yellow]No URLs match route '{args.route}'[/yellow]")
            sys.exit(0)

    # Filter by date or top-N (or return all if route-only mode)
    if has_top:
        results = filter_top_n(all_entries, args.top, start)
    elif has_from:
        results = filter_date_range(all_entries, from_date, to_date)
    else:
        # Route-only mode: return all route-matched entries, sorted by date descending
        dated = sorted(
            [e for e in all_entries if e.lastmod is not None],
            key=lambda e: e.lastmod,  # type: ignore[arg-type]
            reverse=True,
        )
        undated = [e for e in all_entries if e.lastmod is None]
        results = dated + undated

    if not results:
        console.print("[yellow]No URLs matched the filter criteria.[/yellow]")
        sys.exit(0)

    # Output
    if args.json_output:
        print(output_json(results))
    elif args.urls_only:
        print(output_urls_only(results))
    else:
        display_results(results)

        # Compact summary line
        summary = f"[green]{len(results)} URL(s)[/green]"
        if results[0].lastmod:
            summary += f" | {results[-1].lastmod} → {results[0].lastmod}"
        if stats.errors:
            summary += f" | {len(stats.errors)} error(s)"
        console.print(summary)

    # Save to file
    if args.output:
        from pathlib import Path

        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output_urls_only(results) + "\n", encoding="utf-8")
        console.print(f"[green]✓[/green] Saved to {out_path}")


if __name__ == "__main__":
    main()
