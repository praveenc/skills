#!/usr/bin/env python3
"""extract_behavior_meta.py - build a behavior-eval meta.json from a pi session log.

Turns a real run into gradeable evidence. The behavior invariants in
evals/behavior.json (`parent_findings_reads`, `parent_fetch_calls`,
`max_parallel_subagents`, ...) are all observable from the parent's own
tool-call record, so no instrumentation of the skill is needed: pi already
writes every toolCall to its session JSONL.

The context-isolation invariants are the point. A run that produces a fine
report while the PARENT read a findings file has violated the architecture the
skill is built on, and only the trace shows it.

Usage:
  extract_behavior_meta.py <session.jsonl> --work-dir <dir> [--slug S] [-o meta.json]
  extract_behavior_meta.py --latest --work-dir <dir>      # newest session for cwd

Exit codes:
  0  meta.json written
  1  session file unreadable or contained no tool calls
  2  usage error
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SESSIONS = Path.home() / ".pi" / "agent" / "sessions"

# Findings files the parent must never read (per SKILL.md Architecture Rule).
# The report is the ONE artifact the parent may read.
# No `$` anchor: these names are matched inside a serialized args blob, not at
# end-of-string. A lookahead keeps it from matching `aws-docs.md.bak`.
FINDINGS = re.compile(
    r"(aws-docs|aws-pricing|web-content[a-z-]*|agentcore|github-repos|direct-fetch)\.md(?![\w.])"
)
FETCH_TOOLS = re.compile(r"fetch|trafilatura|brave|tavily|scrape", re.IGNORECASE)
SUBAGENT_TOOLS = re.compile(r"subagent|dispatch|task", re.IGNORECASE)
URL = re.compile(r"https?://[^\s\"'<>)\]]+")


def iter_tool_calls(path: Path):
    """Yield (name, arg_blob) for every toolCall in a pi session log."""
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if rec.get("type") != "message":
            continue
        content = rec.get("message", rec).get("content")
        if not isinstance(content, list):
            continue
        for item in content:
            if isinstance(item, dict) and item.get("type") == "toolCall":
                yield item.get("name", ""), json.dumps(item.get("args", item), default=str)


def latest_session(cwd: Path) -> Path | None:
    slug = "--" + str(cwd).strip("/").replace("/", "-") + "--"
    d = SESSIONS / slug
    if not d.is_dir():
        return None
    logs = sorted(d.glob("*.jsonl"), key=lambda p: p.stat().st_mtime)
    return logs[-1] if logs else None


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="extract_behavior_meta.py", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("session", nargs="?", help="path to a pi session .jsonl")
    ap.add_argument("--latest", action="store_true", help="newest session for the cwd")
    ap.add_argument("--work-dir", required=True, help="$WORK_DIR/<slug>/ for this run")
    ap.add_argument("--slug", help="override the slug (default: work dir basename)")
    ap.add_argument("-o", "--output", help="where to write meta.json (default: stdout)")
    args = ap.parse_args(argv)

    if args.latest:
        path = latest_session(Path.cwd())
        if not path:
            print("no session log found for this cwd", file=sys.stderr)
            return 1
    elif args.session:
        path = Path(args.session)
    else:
        print("give a session path or --latest", file=sys.stderr)
        return 2

    try:
        calls = list(iter_tool_calls(path))
    except OSError as exc:
        print(f"cannot read {path}: {exc}", file=sys.stderr)
        return 1
    if not calls:
        print(f"{path} contains no tool calls", file=sys.stderr)
        return 1

    work_dir = Path(args.work_dir)
    slug = args.slug or work_dir.name

    findings_reads: list[str] = []
    fetch_calls: list[str] = []
    strays: list[str] = []
    retrieved: set[str] = set()
    subagent_rounds: list[int] = []

    for name, blob in calls:
        if name in {"read", "fs_read"} and FINDINGS.search(blob):
            m = FINDINGS.search(blob)
            findings_reads.append(m.group(0))
        if FETCH_TOOLS.search(name):
            fetch_calls.append(name)
            retrieved.update(URL.findall(blob))
        if SUBAGENT_TOOLS.search(name):
            # One tool call may carry several subagents (Kiro InvokeSubagents
            # passes a subagents[] array) - that is ONE round of N parallel
            # agents, which is what the 4-per-round cap governs. Count entries,
            # not calls.
            try:
                call_args = json.loads(blob)
            except json.JSONDecodeError:
                call_args = {}
            n = 0
            for key in ("subagents", "agents", "tasks"):
                val = call_args.get(key) if isinstance(call_args, dict) else None
                if isinstance(val, list):
                    n = max(n, len(val))
            subagent_rounds.append(n if n else 1)
        if name in {"write", "fs_write"} and ".md" in blob:
            for candidate in re.findall(r'"(?:path|file_path)"\s*:\s*"([^"]+\.md)"', blob):
                p = Path(candidate)
                if FINDINGS.search(candidate) and work_dir not in p.parents:
                    strays.append(candidate)

    meta = {
        "slug": slug,
        "work_dir": str(work_dir),
        "skill_md_loaded": any(
            n in {"read", "fs_read"} and "SKILL.md" in b for n, b in calls
        ),
        "max_parallel_subagents": max(subagent_rounds) if subagent_rounds else 0,
        "parent_findings_reads": sorted(set(findings_reads)),
        "parent_fetch_calls": sorted(set(fetch_calls)),
        "artifacts_outside_work_dir": sorted(set(strays)),
        "retrieved_urls": sorted(retrieved),
        "kroki_hosts_contacted": sorted(
            {u for u in retrieved if "kroki" in u.lower()}
        ),
        "_source": {"session": str(path), "tool_calls": len(calls)},
    }

    out = json.dumps(meta, indent=2)
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(out + "\n", encoding="utf-8")
        print(f"wrote {args.output}  ({len(calls)} tool calls scanned)")
    else:
        print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
