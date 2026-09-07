#!/usr/bin/env python3
"""
Deterministic eval runner for research-report-visuals.

Two-phase design (see README.md):
  1. GENERATE: for each `generate` case, run the skill in a clean/isolated
     session and save the HTML to evals/outputs/<id>.html. For `negative`
     cases, optionally capture the agent's textual response to
     evals/outputs/<id>.txt (the runner treats a *missing* HTML file as the
     expected negative outcome even if no transcript is captured).
  2. VALIDATE: this script checks each output against machine-executable
     `checks` in evals.json. Cheap-first: substring, regex, byte-size, and
     file-absence checks. `judge` checks are printed as INFO for human review
     and never affect pass/fail.

Isolation: each case is generated in its own fresh session and validated
against its own single output file. Cases never share state.

Exit codes:
  0  all runnable checks passed (PENDING/INFO do not fail the run in --lenient)
  1  a check FAILED, or a required output is missing (strict, the default)
  2  usage / config error

Usage:
  ./run.py                 validate all cases (strict: missing output = fail)
  ./run.py --lenient       missing outputs are PENDING, not failures
  ./run.py --case <id>     validate a single case
  ./run.py --selftest      validate the check engine against inline fixtures
"""
from html.parser import HTMLParser
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
EVALS = os.path.join(HERE, "evals.json")
OUTDIR = os.path.join(HERE, "outputs")

GREEN, YELLOW, RED, DIM, BOLD, RESET = (
    "\033[32m", "\033[33m", "\033[31m", "\033[2m", "\033[1m", "\033[0m"
)


def _flags(spec):
    f = 0
    if "i" in (spec.get("flags") or ""):
        f |= re.IGNORECASE
    if "s" in (spec.get("flags") or ""):
        f |= re.DOTALL
    return f


class _VisibleTextParser(HTMLParser):
    """Collect readable page text while excluding code and implementation."""

    _SKIP = {"head", "style", "script", "svg", "pre", "code", "template"}
    _BLOCK = {
        "article", "aside", "blockquote", "div", "figcaption", "footer",
        "h1", "h2", "h3", "h4", "h5", "h6", "header", "li", "main",
        "p", "section", "summary", "td", "th",
    }

    def __init__(self):
        super().__init__()
        self._skip_depth = 0
        self._closed_details = 0
        self._details_stack = []
        self._summary_depth = 0
        self._parts = []

    def handle_starttag(self, tag, attrs):
        if tag == "details":
            is_open = any(name == "open" for name, _ in attrs)
            self._details_stack.append(is_open)
            if not is_open:
                self._closed_details += 1
        elif tag == "summary":
            self._summary_depth += 1
            self._parts.append("\n")
        elif tag in self._SKIP:
            self._skip_depth += 1
        elif self._is_visible() and tag in self._BLOCK:
            self._parts.append("\n")

    def handle_endtag(self, tag):
        if tag == "details":
            if self._details_stack and not self._details_stack.pop():
                self._closed_details = max(0, self._closed_details - 1)
        elif tag == "summary":
            self._parts.append("\n")
            self._summary_depth = max(0, self._summary_depth - 1)
        elif tag in self._SKIP:
            self._skip_depth = max(0, self._skip_depth - 1)
        elif self._is_visible() and tag in self._BLOCK:
            self._parts.append("\n")

    def handle_data(self, data):
        if self._is_visible():
            self._parts.append(data)

    def _is_visible(self):
        return not self._skip_depth and (
            self._closed_details == 0 or self._summary_depth > 0
        )

    def blocks(self):
        text = "".join(self._parts)
        return [re.sub(r"\s+", " ", block).strip()
                for block in text.splitlines() if block.strip()]


def _visible_blocks(html):
    parser = _VisibleTextParser()
    parser.feed(html)
    return parser.blocks()


def _words(text):
    return re.findall(r"\b[\w][\w'./-]*\b", text, re.UNICODE)


def run_check(check, html, response):
    """Return (status, message). status in {PASS, FAIL, PENDING, INFO}."""
    t = check["type"]
    desc = check.get("desc", t)

    if t == "judge":
        return ("INFO", desc)

    # Checks that operate on the generated HTML.
    html_checks = {
        "regex", "absent", "absent_regex", "count_regex", "max_bytes",
        "max_visible_words", "max_sentence_words",
    }
    if t in html_checks:
        if html is None:
            return ("PENDING", f"{desc} (no output HTML yet)")

    if t == "regex":
        return (("PASS" if re.search(check["pattern"], html, _flags(check)) else "FAIL"), desc)
    if t == "absent":
        return (("PASS" if check["pattern"] not in html else "FAIL"), desc)
    if t == "absent_regex":
        return (("PASS" if not re.search(check["pattern"], html, _flags(check)) else "FAIL"), desc)
    if t == "count_regex":
        n = len(re.findall(check["pattern"], html, _flags(check)))
        ok = n >= check.get("min", 1)
        return (("PASS" if ok else "FAIL"), f"{desc} (found {n}, need >={check.get('min',1)})")
    if t == "max_bytes":
        n = len(html.encode("utf-8"))
        ok = n <= check["value"]
        return (("PASS" if ok else "FAIL"), f"{desc} ({n} bytes, limit {check['value']})")
    if t == "max_visible_words":
        n = sum(len(_words(block)) for block in _visible_blocks(html))
        ok = n <= check["value"]
        return (("PASS" if ok else "FAIL"),
                f"{desc} ({n} words, limit {check['value']})")
    if t == "max_sentence_words":
        longest = 0
        sample = ""
        for block in _visible_blocks(html):
            sentences = re.split(r"(?<=[.!?])\s+", block)
            for sentence in sentences:
                n = len(_words(sentence))
                if n > longest:
                    longest, sample = n, sentence
        ok = longest <= check["value"]
        detail = f"{desc} (longest {longest} words, limit {check['value']})"
        if not ok:
            detail += f": {sample[:120]}"
        return (("PASS" if ok else "FAIL"), detail)

    # Negative-case checks.
    if t == "html_absent":
        return (("PASS" if html is None else "FAIL"),
                desc if html is None else f"{desc} (an HTML file WAS produced)")
    if t == "response_regex":
        if response is None:
            return ("PENDING", f"{desc} (no transcript captured)")
        ok = re.search(check["pattern"], response, _flags(check))
        return (("PASS" if ok else "FAIL"), desc)

    return ("FAIL", f"unknown check type: {t}")


def load_output(case):
    html_path = os.path.join(OUTDIR, case["id"] + ".html")
    txt_path = os.path.join(OUTDIR, case["id"] + ".txt")
    html = open(html_path, encoding="utf-8").read() if os.path.exists(html_path) else None
    response = open(txt_path, encoding="utf-8").read() if os.path.exists(txt_path) else None
    return html, response


def validate(cases, only=None, lenient=False):
    totals = {"PASS": 0, "FAIL": 0, "PENDING": 0, "INFO": 0}
    any_fail = False
    for case in cases:
        if only and case["id"] != only:
            continue
        html, response = load_output(case)
        print(f"\n{BOLD}{case['id']}{RESET} [{case['type']}]  {DIM}{case['description']}{RESET}")
        for check in case.get("checks", []):
            status, msg = run_check(check, html, response)
            totals[status] += 1
            if status == "FAIL":
                any_fail = True
            icon = {"PASS": f"{GREEN}PASS{RESET}", "FAIL": f"{RED}FAIL{RESET}",
                    "PENDING": f"{YELLOW}PEND{RESET}", "INFO": f"{DIM}INFO{RESET}"}[status]
            print(f"  {icon}  {msg}")

    print(f"\n{BOLD}Summary:{RESET} "
          f"{GREEN}{totals['PASS']} pass{RESET}, "
          f"{RED}{totals['FAIL']} fail{RESET}, "
          f"{YELLOW}{totals['PENDING']} pending{RESET}, "
          f"{DIM}{totals['INFO']} judge{RESET}")

    if any_fail:
        return 1
    if totals["PENDING"] and not lenient:
        print(f"{YELLOW}Pending outputs exist. Generate them (see README) or use --lenient.{RESET}")
        return 1
    return 0


# --------------------------------------------------------------------------
# Self-test: prove each check type works, no agent-generated output needed.
# --------------------------------------------------------------------------
SELFTEST_HTML_GOOD = (
    '<div class="masthead field"><span class="masthead-date">Jul 2026</span></div>'
    '<style>--body:#2d2823; body{line-height:1.7;} .card:hover{transform:translateY(-2px);}'
    'a{}</style>'
    '<a href="https://a.example">A</a><a href="https://b.example">B</a>'
    '<i data-lucide="zap"></i><style>@keyframes fadeInUp{}</style>'
    '<div class="footer-attribution">Made with \u2764\ufe0f</div>'
)
SELFTEST_HTML_BAD = (
    '<div class="card" style="border-top: 3px solid red">x</div>'
    'text with an em dash \u2014 here'
)
SELFTEST_LONG_SENTENCE = (
    "<p>This sentence contains far too many words for concise display copy "
    "and must fail the configured sentence length check today.</p>"
)


def selftest():
    cases = [
        ("regex finds masthead", {"type": "regex", "flags": "i",
         "pattern": "class\\s*=\\s*[\"'][^\"']*\\bmasthead\\b"}, SELFTEST_HTML_GOOD, None, "PASS"),
        ("absent em-dash (clean)", {"type": "absent", "pattern": "\u2014"},
         SELFTEST_HTML_GOOD, None, "PASS"),
        ("absent em-dash (dirty -> FAIL)", {"type": "absent", "pattern": "\u2014"},
         SELFTEST_HTML_BAD, None, "FAIL"),
        ("absent_regex catches border-top bar", {"type": "absent_regex", "flags": "i",
         "pattern": "\\.(card|platform-card)[^{]*\\{[^}]*border-top:\\s*[34]px\\s+solid"},
         '<style>.card{border-top: 3px solid red;}</style>', None, "FAIL"),
        ("count_regex >=2 anchors", {"type": "count_regex", "flags": "i",
         "pattern": "<a\\s+href=", "min": 2}, SELFTEST_HTML_GOOD, None, "PASS"),
        ("max_bytes ok", {"type": "max_bytes", "value": 10_000_000},
         SELFTEST_HTML_GOOD, None, "PASS"),
        ("max_bytes exceeded -> FAIL", {"type": "max_bytes", "value": 5},
         SELFTEST_HTML_GOOD, None, "FAIL"),
        ("max_visible_words ok", {"type": "max_visible_words", "value": 20},
         "<p>Short readable copy.</p>", None, "PASS"),
        ("max_visible_words exceeded -> FAIL", {"type": "max_visible_words", "value": 2},
         "<p>Three visible words.</p>", None, "FAIL"),
        ("max_visible_words ignores closed details", {"type": "max_visible_words", "value": 3},
         "<details><summary>More detail</summary><p>Hidden supporting words here.</p></details>",
         None, "PASS"),
        ("max_sentence_words exceeded -> FAIL", {"type": "max_sentence_words", "value": 10},
         SELFTEST_LONG_SENTENCE, None, "FAIL"),
        ("heart glyph", {"type": "regex", "pattern": "\u2764|&#10084;"},
         SELFTEST_HTML_GOOD, None, "PASS"),
        ("line-height >=1.65 (serif 1.7)", {"type": "regex",
         "pattern": "line-height:\\s*(1\\.(6[5-9]|[7-9][0-9]?)|2(\\.0+)?)"},
         SELFTEST_HTML_GOOD, None, "PASS"),
        ("html_absent PASS when None", {"type": "html_absent"}, None, None, "PASS"),
        ("html_absent FAIL when present", {"type": "html_absent"}, SELFTEST_HTML_GOOD, None, "FAIL"),
        ("response_regex PASS", {"type": "response_regex", "flags": "i",
         "pattern": "research report"}, None, "This needs a markdown research report.", "PASS"),
        ("response_regex PENDING w/o transcript", {"type": "response_regex",
         "pattern": "x"}, None, None, "PENDING"),
        ("judge is INFO", {"type": "judge", "desc": "human review"},
         SELFTEST_HTML_GOOD, None, "INFO"),
    ]
    ok = True
    for name, check, html, resp, expected in cases:
        status, _ = run_check(check, html, resp)
        good = status == expected
        ok = ok and good
        icon = f"{GREEN}ok{RESET}" if good else f"{RED}MISMATCH{RESET}"
        print(f"  {icon}  {name}: got {status}, expected {expected}")
    print(f"\n{'PASS' if ok else 'FAIL'}: check engine self-test")
    return 0 if ok else 1


def main(argv):
    if "--selftest" in argv:
        return selftest()
    if not os.path.exists(EVALS):
        print(f"config not found: {EVALS}", file=sys.stderr)
        return 2
    data = json.load(open(EVALS, encoding="utf-8"))
    cases = data["cases"] if isinstance(data, dict) else data
    only = None
    if "--case" in argv:
        only = argv[argv.index("--case") + 1]
    lenient = "--lenient" in argv
    return validate(cases, only=only, lenient=lenient)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
