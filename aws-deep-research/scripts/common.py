"""
Shared utilities for web-search-scrape scripts.

Provides common functions used by brave_search.py and tavily_search.py.
Not intended to be run directly.
"""

import hashlib
import json
import os
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

from rich.console import Console
from rich.panel import Panel

# Type aliases
type URLList = list[str]

console = Console()


# ---------------------------------------------------------------------------
# Domain blocklist
# ---------------------------------------------------------------------------

_BLOCKLIST_PATH = Path(__file__).resolve().parent / "blocklist.txt"
_BLOCKLIST_CACHE: tuple[frozenset[str], float] | None = None


def load_blocked_domains(path: Path | None = None) -> frozenset[str]:
    """Read ``blocklist.txt`` and return the set of blocked domains (lowercase).

    Caches on mtime so repeated calls within a session don't re-read the file.
    Returns an empty frozenset if the file does not exist.
    """
    global _BLOCKLIST_CACHE
    p = path or _BLOCKLIST_PATH
    try:
        mtime = p.stat().st_mtime
    except FileNotFoundError:
        return frozenset()
    if _BLOCKLIST_CACHE is not None and _BLOCKLIST_CACHE[1] == mtime:
        return _BLOCKLIST_CACHE[0]
    domains: set[str] = set()
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip().lower()
        if line:
            # Entries are stored defanged (bad.example[.]com) so the file
            # carries no live, resolvable host. Un-defang to the real host
            # for matching.
            domains.add(line.replace("[.]", "."))
    blocked = frozenset(domains)
    _BLOCKLIST_CACHE = (blocked, mtime)
    return blocked


def is_blocked_url(url: str, blocked: frozenset[str] | None = None) -> bool:
    """True if the URL's host matches any blocked-domain suffix."""
    if blocked is None:
        blocked = load_blocked_domains()
    if not blocked:
        return False
    try:
        host = (urlparse(url).hostname or "").lower()
    except Exception:
        return False
    if not host:
        return False
    # Suffix match: block "example.com" also blocks "sub.example.com"
    for d in blocked:
        if host == d or host.endswith("." + d):
            return True
    return False


def filter_blocked_urls(urls: URLList, blocked: frozenset[str] | None = None) -> tuple[URLList, URLList]:
    """Return ``(kept, dropped)`` URL lists.

    ``dropped`` is surfaced so callers can log/report what was filtered.
    """
    if blocked is None:
        blocked = load_blocked_domains()
    if not blocked:
        return list(urls), []
    kept: URLList = []
    dropped: URLList = []
    for u in urls:
        if is_blocked_url(u, blocked):
            dropped.append(u)
        else:
            kept.append(u)
    return kept, dropped


# Max folder name length. Leaves headroom under the 255-char path limit
# enforced by OneDrive / iCloud / Windows NTFS / many sync clients, given
# that these folders sit several levels deep (e.g.
# output/research/web-search/brave/<this>/<domain>/<file>.md).
_MAX_FOLDER_NAME_LEN = 60


def sanitize_folder_name(query: str, max_len: int = _MAX_FOLDER_NAME_LEN) -> str:
    """Convert query string to a safe, length-bounded folder name.

    Strips non-alphanumerics and lowercases. If the result exceeds
    ``max_len`` chars, truncates and appends an 8-char SHA1 digest of
    the original query so near-duplicate queries don't collide.

    Returns ``search_results`` for empty/all-punctuation inputs.
    """
    sanitized = re.sub(r"[^a-zA-Z0-9]", "", query).lower()
    if not sanitized:
        return "search_results"
    if len(sanitized) <= max_len:
        return sanitized
    # Truncate and append short hash for uniqueness.
    # Reserve 9 chars at the end: "_" + 8 hex digits.
    digest = hashlib.sha1(query.encode("utf-8")).hexdigest()[:8]
    keep = max_len - 9
    return f"{sanitized[:keep]}_{digest}"


def save_urls_to_file(urls: URLList, output_dir: Path) -> Path:
    """Save extracted URLs to a text file."""
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    filepath = output_dir / f"urls_{timestamp}.txt"

    with open(filepath, "w", encoding="utf-8") as f:
        f.writelines(f"{url}\n" for url in urls)

    console.print(f"[green]✓ Saved {len(urls)} URLs to:[/green] {filepath}")
    return filepath


def run_scraper(
    urls: URLList,
    output_dir: Path,
    *,
    yes: bool = False,
    json_output: bool = False,
) -> None:
    """Invoke trafilatura_scraper.py with the extracted URLs."""
    if not urls:
        console.print("[yellow]No URLs to scrape[/yellow]")
        return

    script_dir = Path(__file__).parent
    scraper_path = script_dir / "trafilatura_scraper.py"

    if not scraper_path.exists():
        console.print(f"[red]Scraper not found at: {scraper_path}[/red]")
        return

    console.print()
    console.print(
        Panel(
            f"[bold]Starting content extraction[/bold]\n"
            f"URLs to process: {len(urls)}\n"
            f"Output directory: {output_dir}",
            title="Scraper Integration",
            border_style="cyan",
        ),
    )

    cmd = [
        "uv",
        "run",
        str(scraper_path),
        "--url",
        *urls,
        "--output-dir",
        str(output_dir),
    ]

    if yes:
        cmd.append("--yes")

    if json_output:
        cmd.append("--json")

    scraper_timeout = max(120, len(urls) * 120)

    try:
        result = subprocess.run(
            cmd,
            check=False,
            capture_output=False,
            timeout=scraper_timeout,
        )

        if result.returncode != 0:
            console.print(
                f"[yellow]Scraper exited with code {result.returncode}[/yellow]",
            )

    except subprocess.TimeoutExpired:
        console.print(
            f"[red]Scraper timed out after {scraper_timeout}s. "
            f"Some URLs may not have been processed.[/red]",
        )
    except subprocess.SubprocessError as e:
        console.print(f"[red]Failed to run scraper: {e}[/red]")
    except KeyboardInterrupt:
        console.print("\n[yellow]Scraping interrupted by user[/yellow]")


# ---------------------------------------------------------------------------
# Web-search budget tracking (persistent, per calendar month)
# ---------------------------------------------------------------------------
#
# The skill's search-strategy rules say usage "should be tracked" against
# monthly free-tier caps, but nothing persisted it - so the >80% "switch to
# MCP-only" rule relied on the model remembering. This module makes the count
# real: every successful search increments a counter in a small JSON file,
# keyed by engine and calendar month (UTC). Old months are pruned on write.

# Free-tier monthly caps (documented in SKILL.md / search-strategy.md).
BUDGET_CAPS: dict[str, int] = {"brave": 2000, "tavily": 1000}


def _budget_file() -> Path:
    """Location of the persisted budget counter.

    Sits next to the research work root so it survives across sessions.
    Honors RESEARCH_WORK_DIR (the work root); the budget file lives one
    level up from ``.../work`` at ``~/.aws-deep-research/budget.json`` by
    default, or ``$RESEARCH_WORK_DIR/../budget.json`` when overridden.
    """
    override = os.getenv("RESEARCH_WORK_DIR")
    if override:
        base = Path(override).expanduser().resolve().parent
    else:
        base = Path.home() / ".aws-deep-research"
    return base / "budget.json"


def _current_month() -> str:
    return datetime.now(UTC).strftime("%Y-%m")


def _load_budget(path: Path) -> dict[str, dict[str, int]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
    if not isinstance(data, dict):
        return {}
    return data


def record_search(engine: str, count: int = 1, path: Path | None = None) -> int:
    """Increment this month's counter for ``engine``; return the new total.

    Prunes counters for any month other than the current one so the file
    stays small. Best-effort: a write failure never breaks a search.
    """
    engine = engine.lower()
    p = path or _budget_file()
    month = _current_month()
    data = _load_budget(p)
    engine_counts = data.get(engine)
    prior = 0
    if isinstance(engine_counts, dict):
        prior = int(engine_counts.get(month, 0))
    # Prune stale months: keep only the current month per engine.
    new_engine_counts = {month: prior + count}
    data[engine] = new_engine_counts
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    except OSError:
        pass
    return new_engine_counts[month]


def get_usage(engine: str, path: Path | None = None) -> int:
    """Return this month's recorded search count for ``engine`` (0 if none)."""
    engine = engine.lower()
    data = _load_budget(path or _budget_file())
    engine_counts = data.get(engine, {})
    if not isinstance(engine_counts, dict):
        return 0
    return int(engine_counts.get(_current_month(), 0))


def budget_status(engine: str, cap: int | None = None, path: Path | None = None) -> dict:
    """Return usage summary for ``engine`` this month.

    Keys: ``engine``, ``month``, ``used``, ``cap``, ``remaining``,
    ``pct_used`` (0-100, rounded to 1 dp), ``over_80`` (bool - the trip-wire
    for the skill's "switch to MCP-only" rule).
    """
    engine = engine.lower()
    used = get_usage(engine, path)
    cap = cap if cap is not None else BUDGET_CAPS.get(engine, 0)
    remaining = max(cap - used, 0) if cap else None
    pct = round(100 * used / cap, 1) if cap else 0.0
    return {
        "engine": engine,
        "month": _current_month(),
        "used": used,
        "cap": cap or None,
        "remaining": remaining,
        "pct_used": pct,
        "over_80": bool(cap) and pct >= 80.0,
    }
