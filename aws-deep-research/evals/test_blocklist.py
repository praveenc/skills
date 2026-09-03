"""test_blocklist.py - the domain blocklist gates every web fetch; cover it.

`scripts/common.py` filters Brave/Tavily results and manually-constructed URLs
against `blocklist.txt` before any fetchv2 batch call. A parsing or matching
defect here silently lets a SEC/SPAM/PAY/DEAD domain through, so the loader and
the suffix matcher get their own tests, not just incidental coverage.

Run via evals/run_tests.sh (puts scripts/ on PYTHONPATH so `import common` works).
"""

from __future__ import annotations

import os

import common


def _write(tmp_path, name, text):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


# --- parsing: comments, blanks, defang ------------------------------------

def test_comments_and_blank_lines_are_ignored(tmp_path):
    bl = _write(tmp_path, "bl.txt", "# a header comment\n\n  # indented comment\nbad.example.com\n")
    domains = common.load_blocked_domains(bl)
    assert domains == frozenset({"bad.example.com"})


def test_inline_comment_is_stripped(tmp_path):
    bl = _write(tmp_path, "bl.txt", "spam.example.net   # SPAM - scraped-content mill\n")
    assert common.load_blocked_domains(bl) == frozenset({"spam.example.net"})


def test_defanged_entries_are_undefanged(tmp_path):
    bl = _write(tmp_path, "bl.txt", "bad[.]example[.]com\n")
    domains = common.load_blocked_domains(bl)
    assert domains == frozenset({"bad.example.com"})  # [.] -> .


def test_entries_are_lowercased(tmp_path):
    bl = _write(tmp_path, "bl.txt", "Bad.EXAMPLE.Com\n")
    assert common.load_blocked_domains(bl) == frozenset({"bad.example.com"})


# --- missing file ----------------------------------------------------------

def test_missing_file_is_empty_not_error(tmp_path):
    missing = tmp_path / "does-not-exist.txt"
    assert common.load_blocked_domains(missing) == frozenset()
    # and an empty blocklist blocks nothing
    assert common.is_blocked_url("https://anything.example.com/x", frozenset()) is False


# --- suffix matching -------------------------------------------------------

def test_exact_host_is_blocked():
    blocked = frozenset({"example.com"})
    assert common.is_blocked_url("https://example.com/page", blocked) is True


def test_subdomain_is_blocked_by_suffix():
    blocked = frozenset({"example.com"})
    assert common.is_blocked_url("https://deep.sub.example.com/p", blocked) is True


def test_unrelated_domain_is_not_blocked():
    blocked = frozenset({"example.com"})
    assert common.is_blocked_url("https://example.org/p", blocked) is False


def test_suffix_match_respects_label_boundary():
    # "notexample.com" merely ends with the substring "example.com" but is a
    # different registrable domain - it must NOT be blocked.
    blocked = frozenset({"example.com"})
    assert common.is_blocked_url("https://notexample.com/p", blocked) is False


def test_non_http_or_hostless_url_is_not_blocked():
    blocked = frozenset({"example.com"})
    assert common.is_blocked_url("not a url", blocked) is False
    assert common.is_blocked_url("mailto:x@example.com", blocked) is False


# --- filter partitions kept vs dropped ------------------------------------

def test_filter_blocked_urls_partitions():
    blocked = frozenset({"example.com"})
    urls = ["https://ok.org/a", "https://x.example.com/b", "https://keep.net/c"]
    kept, dropped = common.filter_blocked_urls(urls, blocked)
    assert kept == ["https://ok.org/a", "https://keep.net/c"]
    assert dropped == ["https://x.example.com/b"]


# --- cache is keyed on (path, mtime), not mtime alone ----------------------

def test_cache_does_not_confuse_two_files_with_equal_mtime(tmp_path):
    # The blocklist gates fetches, so an mtime-only cache key could hand back a
    # different file's domains when two files share a modification time.
    a = _write(tmp_path, "a.txt", "aaa.example.com\n")
    b = _write(tmp_path, "b.txt", "bbb.example.com\n")
    same = 1_700_000_000
    os.utime(a, (same, same))
    os.utime(b, (same, same))
    assert common.load_blocked_domains(a) == frozenset({"aaa.example.com"})
    # Same mtime, different path: must reflect b's contents, not a's cached set.
    assert common.load_blocked_domains(b) == frozenset({"bbb.example.com"})
