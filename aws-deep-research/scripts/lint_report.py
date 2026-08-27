#!/usr/bin/env python3
"""lint_report.py - mechanical quality gate for a synthesized research report.

Grades the parts of report quality that code can observe: required sections,
citation/reference syntax, citation-to-reference consistency, size bounds, and
evidence-tag leakage. It does NOT judge insight, actionability, or narrative
quality - those stay with the rubric in evals/synthesis-rubric.json and a
calibrated judge.

Three callers:
  1. scripts/eval_synthesis.sh  - turns a synthesis regression into an exit code
  2. evals/run.py               - behavior-case assertions
  3. SKILL.md Step 6            - repair loop before the report reaches the user

Checks (hard = fails the gate, soft = reported, never fails):

  hard  title          H1 present
  hard  sections       required sections for the declared intents exist
  hard  refs_present   a References section with at least one [N] entry
  hard  ref_format     every reference is exactly `[N] [Title](url)`
  hard  ref_sequence   reference numbers start at 1 and increase by 1
  hard  no_dangling    every [N] cited in the body has a reference entry
  hard  size_max       report is under the size ceiling (default 50 KB)
  soft  no_orphans     every reference entry is cited somewhere in the body
  soft  size_min       report is above a floor that suggests a stub
  soft  no_bare_urls   body prose does not carry bare http(s) URLs
  soft  no_raw_tags    {authority-date} evidence tags did not leak into prose

Usage:
  lint_report.py <report.md> [--intents comparison,pricing] [--json]
                 [--max-bytes N] [--min-bytes N] [--strict]

  --intents   comma-separated intents from SKILL.md Step 1a. Drives which
              conditional sections are required. Omit to check only the
              universal sections.
  --strict    promote soft findings to hard (fails on any finding)
  --json      machine-readable result for a runner

Exit codes:
  0  every hard check passed
  1  a hard check failed (or any check, with --strict)
  2  usage error / report not readable
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# Sections every report must have, per agents/synthesizer.md Report Format.
UNIVERSAL_SECTIONS = [
    "Executive Summary",
    "Detailed Findings",
    "Recommendations",
    "Gaps & Limitations",
    "References",
]

# Intent -> extra sections that become mandatory. Mirrors the REQUIRED markers
# in agents/synthesizer.md.
CONDITIONAL_SECTIONS = {
    "comparison": ["Key Tensions & Decision Drivers"],
    "architecture": ["Key Tensions & Decision Drivers"],
    "migration": ["Key Tensions & Decision Drivers"],
    "cost-optimization": ["Key Tensions & Decision Drivers", "Pricing & Cost Analysis"],
    "pricing": ["Pricing & Cost Analysis"],
    "code-examples": ["Code Examples & Repositories"],
}

DEFAULT_MAX_BYTES = 50 * 1024
DEFAULT_MIN_BYTES = 2000

# `[N] [Title](url)` - the strict reference form. Title must be non-empty and
# the URL must be absolute. The URL is matched greedily to the final `)` on the
# line because real doc URLs legitimately contain balanced parens, e.g.
# https://github.com/.../docs/(agentic)/metrics-tool-correctness.mdx
REF_LINE = re.compile(r"^\[(\d+)\]\s+\[([^\]]+)\]\((https?://\S+)\)\s*$")
# Any line that opens with [N] - used to catch malformed reference lines.
REF_LINE_LOOSE = re.compile(r"^\[(\d+)\]\s*(.*)$")
CITATION = re.compile(r"\[(\d+)\]")
HEADING = re.compile(r"^#{1,4}\s+(.*?)\s*$", re.MULTILINE)
EVIDENCE_TAG = re.compile(r"\{(official|vendor-claim|third-party|community)[·|,.\-][^}]*\}")
FENCE = re.compile(r"^\s*```")
BARE_URL = re.compile(r"(?<![\(\[<])\bhttps?://[^\s)>\]]+")


def normalize_heading(h: str) -> str:
    """Fold case and `&`/`and` so section matching grades presence, not styling."""
    return re.sub(r"\s+", " ", h.lower().replace("&", "and")).strip()


def split_sections(text: str) -> tuple[list[str], str, str]:
    """Return (headings, body_before_references, references_block)."""
    headings = [h.strip() for h in HEADING.findall(text)]
    m = re.search(r"^##\s+References\s*$", text, re.MULTILINE | re.IGNORECASE)
    if not m:
        return headings, text, ""
    return headings, text[: m.start()], text[m.end() :]


def strip_code_fences(text: str) -> str:
    """Drop fenced code blocks - citations and URLs inside them are examples."""
    out, inside = [], False
    for line in text.splitlines():
        if FENCE.match(line):
            inside = not inside
            continue
        if not inside:
            out.append(line)
    return "\n".join(out)


def lint(text: str, intents: list[str], max_bytes: int, min_bytes: int) -> list[dict]:
    findings: list[dict] = []

    def add(severity: str, check: str, ok: bool, detail: str = "") -> None:
        findings.append({"check": check, "severity": severity, "ok": ok, "detail": detail})

    size = len(text.encode("utf-8"))
    headings, body_raw, refs_block = split_sections(text)
    body = strip_code_fences(body_raw)
    heading_set = {normalize_heading(h.lstrip("# ")) for h in headings}

    add("hard", "title", bool(re.match(r"^#\s+\S", text)), "H1 title on first line")

    required = list(UNIVERSAL_SECTIONS)
    for intent in intents:
        for section in CONDITIONAL_SECTIONS.get(intent, []):
            if section not in required:
                required.append(section)
    missing = [s for s in required
               if not any(normalize_heading(s) in h for h in heading_set)]
    add("hard", "sections", not missing, f"missing: {', '.join(missing)}" if missing else
        f"all {len(required)} required sections present")

    ref_lines = [ln for ln in refs_block.splitlines() if REF_LINE_LOOSE.match(ln.strip())]
    parsed = [REF_LINE.match(ln.strip()) for ln in ref_lines]
    add("hard", "refs_present", bool(ref_lines), f"{len(ref_lines)} reference entries")

    malformed = [ln.strip() for ln, p in zip(ref_lines, parsed) if p is None]
    add("hard", "ref_format", not malformed,
        f"{len(malformed)} malformed (want `[N] [Title](url)`): {malformed[:3]}"
        if malformed else "all references use [N] [Title](url)")

    # Sequence is graded over every reference line that carries a number, even a
    # malformed one - otherwise a malformed entry would silently create a hole.
    all_nums = [int(m.group(1)) for m in
                (REF_LINE_LOOSE.match(ln.strip()) for ln in ref_lines) if m]
    expected = list(range(1, len(all_nums) + 1))
    if all_nums == expected:
        seq_detail = f"1..{len(all_nums)} sequential"
    else:
        first_bad = next((i for i, (g, w) in enumerate(zip(all_nums, expected)) if g != w),
                         min(len(all_nums), len(expected)))
        seq_detail = (f"diverges at position {first_bad + 1}: "
                      f"got {all_nums[first_bad:first_bad + 4]}, "
                      f"want {expected[first_bad:first_bad + 4]}")
    add("hard", "ref_sequence", all_nums == expected, seq_detail)

    cited = {int(n) for n in CITATION.findall(body)}
    # Resolvability is graded against every numbered reference line, malformed or
    # not, so a formatting defect does not cascade into a false dangling report.
    ref_set = set(all_nums)
    dangling = sorted(cited - ref_set)
    add("hard", "no_dangling", not dangling,
        f"cited but not in References: {dangling}" if dangling else "every citation resolves")

    add("hard", "size_max", size <= max_bytes, f"{size} bytes (ceiling {max_bytes})")

    orphans = sorted(ref_set - cited)
    add("soft", "no_orphans", not orphans,
        f"in References but never cited: {orphans}" if orphans else "no orphan references")

    add("soft", "size_min", size >= min_bytes, f"{size} bytes (floor {min_bytes})")

    bare = BARE_URL.findall(body)
    add("soft", "no_bare_urls", not bare,
        f"{len(bare)} bare URL(s) in prose: {bare[:2]}" if bare else "no bare URLs in prose")

    leaked = EVIDENCE_TAG.findall(body)
    add("soft", "no_raw_tags", not leaked,
        f"{len(leaked)} raw evidence tag(s) leaked into prose" if leaked
        else "no raw evidence tags in prose")

    return findings


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        prog="lint_report.py",
        description="Mechanical quality gate for a synthesized research report.",
    )
    ap.add_argument("report", help="path to <slug>-report.md")
    ap.add_argument("--intents", default="", help="comma-separated intents (Step 1a)")
    ap.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES)
    ap.add_argument("--min-bytes", type=int, default=DEFAULT_MIN_BYTES)
    ap.add_argument("--strict", action="store_true", help="soft findings also fail")
    ap.add_argument("--json", action="store_true", dest="as_json")
    args = ap.parse_args(argv)

    path = Path(args.report)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"lint_report.py: cannot read {path}: {exc}", file=sys.stderr)
        return 2

    intents = [i.strip() for i in args.intents.split(",") if i.strip()]
    findings = lint(text, intents, args.max_bytes, args.min_bytes)

    failed_hard = [f for f in findings if not f["ok"] and f["severity"] == "hard"]
    failed_soft = [f for f in findings if not f["ok"] and f["severity"] == "soft"]
    passed = not failed_hard and (not args.strict or not failed_soft)

    if args.as_json:
        json.dump(
            {
                "report": str(path),
                "intents": intents,
                "bytes": len(text.encode("utf-8")),
                "passed": passed,
                "hard_failed": [f["check"] for f in failed_hard],
                "soft_failed": [f["check"] for f in failed_soft],
                "findings": findings,
            },
            sys.stdout,
            indent=2,
        )
        sys.stdout.write("\n")
    else:
        print(f"lint_report.py {path.name}  intents={intents or '(none)'}")
        for f in findings:
            icon = "PASS" if f["ok"] else ("FAIL" if f["severity"] == "hard" else "WARN")
            print(f"  {icon}  {f['check']:<14} {f['detail']}")
        print(f"\n{'PASS' if passed else 'FAIL'}: "
              f"{len(failed_hard)} hard, {len(failed_soft)} soft finding(s)")

    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
