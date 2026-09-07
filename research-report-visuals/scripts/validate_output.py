#!/usr/bin/env python3
"""Validate and safely normalize a generated research-report visual."""

import argparse
import re
import sys
import tempfile
from html.parser import HTMLParser
from pathlib import Path


WORD_RE = re.compile(r"\b[\w][\w'./+-]*\b", re.UNICODE)
URL_RE = re.compile(r"https?://[^\s)\]>\"']+")
SOURCE_LINK_RE = re.compile(r"\[[^\]]+\]\((https?://[^)]+)\)")
PROTECTED_PATTERNS = [
    r"\b[a-z]{2}-[a-z]+-\d\b",
    r"\b(?:Python|Java|Node(?:\.js)?)\s+\d+(?:\.\d+)*(?:\+)?",
    r"\$[\d,]+(?:\.\d+)?",
    r"\b\d+(?:\.\d+)?%",
    r"\b\d[\d,]*(?:\.\d+)?-\d[\d,]*(?:\.\d+)?\s*(?:ms|milliseconds?|seconds?|minutes?|hours?|days?|points?|SD)?\b",
    r"\b(?:under|over|below|above|up to|at least|more than|less than)\s+\d[\d,]*(?:\.\d+)?\s*(?:ms|milliseconds?|seconds?|minutes?|hours?|days?|points?|SD)?\b",
    r"\b\d[\d,]*(?:\.\d+)?\s+(?:ms|milliseconds?|seconds?|minutes?|hours?|days?|points?|SD|percentage points?|requests? per second|input tokens?|output tokens?|members?)\b",
    r"\b(?:anthropic|amazon)\.[A-Za-z0-9_.]*[-:][A-Za-z0-9_.:-]+\b",
    r"\b[A-Z][A-Za-z0-9]+(?:[A-Z][A-Za-z0-9]+)+\b",
]


class TextParser(HTMLParser):
    def __init__(self, omit_closed_details=False):
        super().__init__(convert_charrefs=True)
        self.omit_closed_details = omit_closed_details
        self.skip = 0
        self.closed_details = 0
        self.hidden = 0
        self.hidden_stack = []
        self.text = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        is_hidden = (
            "hidden" in attrs
            or (attrs.get("aria-hidden") or "").lower() == "true"
            or re.search(r"(?:display\s*:\s*none|visibility\s*:\s*hidden)",
                         attrs.get("style") or "", re.I)
        )
        self.hidden_stack.append(is_hidden)
        if is_hidden:
            self.hidden += 1
        if tag in {"script", "style", "template"}:
            self.skip += 1
        if tag == "details" and self.omit_closed_details:
            is_open = any(name == "open" for name, _ in attrs)
            if not is_open:
                self.closed_details += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style", "template"} and self.skip:
            self.skip -= 1
        if tag == "details" and self.omit_closed_details and self.closed_details:
            self.closed_details -= 1
        if self.hidden_stack and self.hidden_stack.pop():
            self.hidden -= 1

    def handle_data(self, data):
        if not self.skip and not self.closed_details and not self.hidden:
            self.text.append(data)


class DetailsParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.summary = 0
        self.current = []
        self.counts = []
        self.open_stack = []

    def handle_starttag(self, tag, attrs):
        if tag == "details":
            self.open_stack.append(any(name == "open" for name, _ in attrs))
            self.depth += 1
            if self.depth == 1:
                self.current = []
        elif tag == "summary" and self.depth:
            self.summary += 1

    def handle_endtag(self, tag):
        if tag == "summary" and self.summary:
            self.summary -= 1
        elif tag == "details" and self.depth:
            if self.depth == 1:
                is_open = self.open_stack.pop() if self.open_stack else False
                if not is_open:
                    self.counts.append(len(WORD_RE.findall(" ".join(self.current))))
            self.depth -= 1

    def handle_data(self, data):
        if self.depth and not self.summary:
            self.current.append(data)


def parsed_text(html, omit_closed_details=False):
    parser = TextParser(omit_closed_details)
    parser.feed(html)
    return " ".join(parser.text)


def protected_literals(source):
    url_spans = [match.span() for match in URL_RE.finditer(source)]
    matches = []
    for pattern in PROTECTED_PATTERNS:
        for match in re.finditer(pattern, source):
            if any(start <= match.start() < end for start, end in url_spans):
                continue
            matches.append((match.start(), match.end(), match.group(0).rstrip(".,;:")))
    matches.sort(key=lambda item: (item[0], -(item[1] - item[0])))
    non_overlapping = []
    for match in matches:
        if non_overlapping and match[0] < non_overlapping[-1][1]:
            continue
        non_overlapping.append(match)
    seen = set()
    values = []
    for _, _, value in non_overlapping:
        if value and value not in seen:
            seen.add(value)
            values.append(value)
    return values


class StructureParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = set()
        self.title_text = []
        self.in_title = False
        self.html_lang = False
        self.viewport = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.tags.add(tag)
        if tag == "html" and attrs.get("lang"):
            self.html_lang = True
        if tag == "meta" and (attrs.get("name") or "").lower() == "viewport":
            self.viewport = True
        if tag == "title":
            self.in_title = True

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False

    def handle_data(self, data):
        if self.in_title:
            self.title_text.append(data)


def validate(source, html):
    errors = []
    structure = StructureParser()
    structure.feed(html)
    if not re.match(r"(?is)^\s*<!doctype\s+html", html):
        errors.append("missing doctype")
    if not structure.html_lang:
        errors.append("missing html lang")
    if not "".join(structure.title_text).strip():
        errors.append("missing title")
    if not structure.viewport:
        errors.append("missing viewport")
    for tag in ("header", "main", "h1", "footer"):
        if tag not in structure.tags:
            errors.append(f"missing {tag} landmark" if tag != "h1" else "missing h1")
    if "\u2014" in html or "\u2013" in html:
        errors.append("contains em dash or en dash")
    thick_borders = re.findall(
        r"border-(?:top|left)\s*:\s*(?:[3-9]|\d{2,})px\s+solid[^;}\n]*",
        html,
        re.I,
    )
    if thick_borders:
        errors.append(
            "contains prohibited thick borders: " + ", ".join(thick_borders[:5])
        )

    content = parsed_text(html)
    missing = [value for value in protected_literals(source) if value not in content]
    if missing:
        errors.append("missing protected literals: " + ", ".join(repr(v) for v in missing[:20]))

    source_urls = SOURCE_LINK_RE.findall(source)
    hrefs = set(re.findall(r"(?is)<a\b[^>]*href\s*=\s*[\"']([^\"']+)", html))
    missing_urls = [url.rstrip(".,;:") for url in source_urls if url.rstrip(".,;:") not in hrefs]
    if missing_urls:
        errors.append("missing source links: " + ", ".join(missing_urls[:10]))

    source_words = len(WORD_RE.findall(source))
    visible_words = len(WORD_RE.findall(parsed_text(html, omit_closed_details=True)))
    section_count = len(re.findall(r"(?m)^##\s+", source))
    if source_words <= 100 and visible_words > 300:
        errors.append(f"short report has {visible_words} visible words; limit is 300")
    if source_words >= 1000 or section_count >= 7:
        if not 500 <= visible_words <= 900:
            errors.append(f"long report has {visible_words} visible words; required 500-900")
        details = DetailsParser()
        details.feed(html)
        qualifying = sum(count >= 25 for count in details.counts)
        if qualifying < 2:
            errors.append(
                f"long report has {qualifying} substantive details blocks; required 2"
            )
    return errors


def run(source_path, html_path):
    source = source_path.read_text(encoding="utf-8")
    html = html_path.read_text(encoding="utf-8")
    errors = validate(source, html)
    if errors:
        for error in errors:
            print(f"FAIL {error}")
        return 1
    print("PASS output validation")
    return 0


def selftest():
    source = (
        "# Report\n\nPython 3.12+ reduces latency to under 200ms for 14 days.\n"
        "[Source](https://example.com/report)\n"
    )
    good = """<!doctype html><html lang="en"><head><title>R</title>
<meta name="viewport" content="width=device-width"></head><body><header>H</header>
<main><h1>R</h1><p>Python 3.12+ reduces latency to under 200ms for 14 days.</p>
<a href="https://example.com/report">Source</a></main><footer>F</footer></body></html>"""
    bad = good.replace("14 days", "two weeks").replace("</style>", "")
    bad = bad.replace("<head>", "<head><style>.card{border-top:4px solid red}</style>")
    bad = bad.replace("latency", "latency\u2014")
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source_path = root / "source.md"
        html_path = root / "output.html"
        source_path.write_text(source, encoding="utf-8")
        html_path.write_text(bad, encoding="utf-8")
        assert run(source_path, html_path) == 1
        assert "\u2014" in html_path.read_text(encoding="utf-8")
        html_path.write_text(good, encoding="utf-8")
        assert run(source_path, html_path) == 0
    print("PASS validator self-test")
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", nargs="?", type=Path)
    parser.add_argument("html", nargs="?", type=Path)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    if args.selftest:
        return selftest()
    if not args.source or not args.html:
        parser.error("source and html are required")
    return run(args.source, args.html)


if __name__ == "__main__":
    sys.exit(main())
