#!/usr/bin/env python3
"""Eval runner for aws-deep-research.

Vendored from skill-audit/evals/run.py and adapted. It is a COPY on purpose:
skills install standalone (`npx skills add --skill aws-deep-research`), so a
cross-skill import would break on install.

Two phases, because an agent is needed to produce evidence but not to grade it:

  1. GENERATE (you, or a harness driver): run each case and drop its evidence
     into outputs/<case-id>/ - see README.md for the exact contract.
  2. VALIDATE (this script): grade the evidence against the machine `checks`
     in routing.json / behavior.json / faults.json, emit JSON and JUnit, and
     exit non-zero on any hard-gate failure.

Static mode grades what needs no agent at all: corpus shape, split
stratification, check-type validity, and reference integrity. That is the part
CI runs on every change.

Exit codes:
  0  all runnable checks passed
  1  a check FAILED, or evidence is missing (strict, the default)
  2  usage / config error

Usage:
  ./run.py --static             corpus structure only, no agent evidence needed
  ./run.py --selftest           validate the check engine against inline fixtures
  ./run.py                      grade every case that has evidence
  ./run.py --suite routing      grade one suite
  ./run.py --case route-014     grade one case
  ./run.py --lenient            missing evidence is PENDING, not FAIL
  ./run.py --json out.json      write a machine-readable summary
  ./run.py --junit out.xml      write JUnit XML for CI
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL_DIR = HERE.parent
OUTDIR = HERE / "outputs"
SUITES = {"routing": "routing.json", "behavior": "behavior.json", "faults": "faults.json"}
LINT = SKILL_DIR / "scripts" / "lint_report.py"

GREEN, YELLOW, RED, DIM, BOLD, RESET = (
    "\033[32m", "\033[33m", "\033[31m", "\033[2m", "\033[1m", "\033[0m"
)

# Slug rules from references/slug-guide.md - the runner must enforce the same
# bounds the skill claims at runtime.
SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
SLUG_MIN_TOKENS, SLUG_MAX_TOKENS = 4, 7
SLUG_MIN_CHARS, SLUG_MAX_CHARS = 30, 60

BEHAVIOR_CHECK_TYPES = {
    "slug_valid", "artifact_exists", "artifact_absent", "artifact_in_work_dir_only",
    "report_lint", "report_regex", "min_citations", "max_parallel", "trace_regex",
    "trace_absent_regex", "no_parent_findings_read", "no_parent_fetch",
    "subagent_return_budget", "native_activation", "no_fabricated_citations",
    "no_remote_kroki_fallback", "judge",
}
HARD_BY_DEFAULT = BEHAVIOR_CHECK_TYPES - {"judge"}


# --------------------------------------------------------------------------
# Evidence
# --------------------------------------------------------------------------

class Evidence:
    """What one generated run left behind. Any part may be absent."""

    def __init__(self, case_dir: Path) -> None:
        self.dir = case_dir
        self.trace = self._read("trace.txt")
        self.report = self._read("report.md")
        meta_raw = self._read("meta.json")
        self.meta = json.loads(meta_raw) if meta_raw else {}

    def _read(self, name: str) -> str | None:
        p = self.dir / name
        try:
            return p.read_text(encoding="utf-8")
        except OSError:
            return None

    @property
    def present(self) -> bool:
        return self.dir.is_dir() and (self.trace is not None or self.report is not None
                                      or bool(self.meta))

    @property
    def work_dir(self) -> Path | None:
        wd = self.meta.get("work_dir")
        return Path(wd) if wd else None

    def artifact(self, name: str) -> Path | None:
        """A findings file, from the recorded work dir or a copied artifacts/ dir."""
        for base in (self.work_dir, self.dir / "artifacts"):
            if base and (base / name).exists():
                return base / name
        return None


# --------------------------------------------------------------------------
# Check engine
# --------------------------------------------------------------------------

def _flags(spec: dict) -> int:
    f = 0
    if "i" in (spec.get("flags") or ""):
        f |= re.IGNORECASE
    if "s" in (spec.get("flags") or ""):
        f |= re.DOTALL
    return f


def validate_slug(slug: str) -> tuple[bool, str]:
    if not SLUG_RE.match(slug):
        return False, f"{slug!r} is not kebab-case"
    tokens = slug.split("-")
    if not SLUG_MIN_TOKENS <= len(tokens) <= SLUG_MAX_TOKENS:
        return False, f"{slug!r} has {len(tokens)} tokens (want {SLUG_MIN_TOKENS}-{SLUG_MAX_TOKENS})"
    if not SLUG_MIN_CHARS <= len(slug) <= SLUG_MAX_CHARS:
        return False, f"{slug!r} is {len(slug)} chars (want {SLUG_MIN_CHARS}-{SLUG_MAX_CHARS})"
    return True, f"{slug!r} valid"


def run_report_lint(report_path: Path, intents: str) -> tuple[bool, str]:
    cmd = ["python3", str(LINT), str(report_path), "--json"]
    if intents:
        cmd += ["--intents", intents]
    r = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if r.returncode == 2:
        return False, f"lint_report.py could not read {report_path}"
    try:
        payload = json.loads(r.stdout)
    except json.JSONDecodeError:
        return False, f"lint_report.py produced no JSON: {r.stderr[-200:]}"
    if payload["passed"]:
        return True, "report passes all hard checks"
    return False, f"hard failures: {', '.join(payload['hard_failed'])}"


def run_check(check: dict, ev: Evidence) -> tuple[str, str]:
    """Return (status, message). status in {PASS, FAIL, PENDING, INFO}."""
    t = check["type"]
    desc = check.get("desc", t)

    if t == "judge":
        return "INFO", desc
    if not ev.present:
        return "PENDING", f"{desc} (no evidence yet)"

    # --- trace-based ---
    if t in {"trace_regex", "trace_absent_regex"}:
        if ev.trace is None:
            return "PENDING", f"{desc} (no trace.txt)"
        hit = re.search(check["pattern"], ev.trace, _flags(check))
        ok = bool(hit) if t == "trace_regex" else not hit
        return ("PASS" if ok else "FAIL"), desc

    # --- artifact-based ---
    if t in {"artifact_exists", "artifact_absent"}:
        found = ev.artifact(check["path"])
        ok = (found is not None) if t == "artifact_exists" else (found is None)
        detail = desc if ok else f"{desc} ({check['path']} " \
                                 f"{'not found' if t == 'artifact_exists' else 'unexpectedly present'})"
        return ("PASS" if ok else "FAIL"), detail

    if t == "slug_valid":
        slug = ev.meta.get("slug")
        if not slug:
            return "PENDING", f"{desc} (meta.json has no slug)"
        ok, why = validate_slug(slug)
        return ("PASS" if ok else "FAIL"), f"{desc}: {why}"

    if t == "report_lint":
        if ev.report is None:
            return "PENDING", f"{desc} (no report.md)"
        ok, why = run_report_lint(ev.dir / "report.md", check.get("intents", ""))
        return ("PASS" if ok else "FAIL"), f"{desc}: {why}"

    if t == "report_regex":
        if ev.report is None:
            return "PENDING", f"{desc} (no report.md)"
        ok = bool(re.search(check["pattern"], ev.report, _flags(check)))
        return ("PASS" if ok else "FAIL"), desc

    if t == "min_citations":
        if ev.report is None:
            return "PENDING", f"{desc} (no report.md)"
        n = len(re.findall(r"^\[\d+\]\s+\[", ev.report, re.MULTILINE))
        ok = n >= check["count"]
        return ("PASS" if ok else "FAIL"), f"{desc} (found {n}, need >={check['count']})"

    # --- meta-recorded invariants ---
    if t == "max_parallel":
        n = ev.meta.get("max_parallel_subagents")
        if n is None:
            return "PENDING", f"{desc} (meta.json has no max_parallel_subagents)"
        return ("PASS" if n <= check["limit"] else "FAIL"), f"{desc} (peak {n}, limit {check['limit']})"

    if t == "subagent_return_budget":
        n = ev.meta.get("subagent_return_chars")
        if n is None:
            return "PENDING", f"{desc} (meta.json has no subagent_return_chars)"
        return ("PASS" if n <= check["max_chars"] else "FAIL"), \
               f"{desc} ({n} chars, max {check['max_chars']})"

    if t == "no_parent_findings_read":
        reads = ev.meta.get("parent_findings_reads")
        if reads is None:
            return "PENDING", f"{desc} (meta.json has no parent_findings_reads)"
        return ("PASS" if not reads else "FAIL"), \
               desc if not reads else f"{desc} (parent read: {reads})"

    if t == "no_parent_fetch":
        calls = ev.meta.get("parent_fetch_calls")
        if calls is None:
            return "PENDING", f"{desc} (meta.json has no parent_fetch_calls)"
        return ("PASS" if not calls else "FAIL"), \
               desc if not calls else f"{desc} (parent fetched: {calls})"

    if t == "artifact_in_work_dir_only":
        strays = ev.meta.get("artifacts_outside_work_dir")
        if strays is None:
            return "PENDING", f"{desc} (meta.json has no artifacts_outside_work_dir)"
        return ("PASS" if not strays else "FAIL"), \
               desc if not strays else f"{desc} (strays: {strays})"

    if t == "native_activation":
        loaded = ev.meta.get("skill_md_loaded")
        if loaded is None:
            return "PENDING", f"{desc} (meta.json has no skill_md_loaded)"
        return ("PASS" if loaded else "FAIL"), \
               desc if loaded else f"{desc} (harness did not load this SKILL.md)"

    if t == "no_remote_kroki_fallback":
        hosts = ev.meta.get("kroki_hosts_contacted", [])
        remote = [h for h in hosts if "localhost" not in h and "127.0.0.1" not in h]
        return ("PASS" if not remote else "FAIL"), \
               desc if not remote else f"{desc} (contacted {remote})"

    if t == "no_fabricated_citations":
        if ev.report is None:
            return "PENDING", f"{desc} (no report.md)"
        retrieved = ev.meta.get("retrieved_urls")
        if retrieved is None:
            return "PENDING", f"{desc} (meta.json has no retrieved_urls)"
        cited = set(re.findall(r"^\[\d+\]\s+\[[^\]]+\]\((https?://\S+?)\)\s*$",
                               ev.report, re.MULTILINE))
        fabricated = sorted(cited - set(retrieved))
        return ("PASS" if not fabricated else "FAIL"), \
               desc if not fabricated else f"{desc} ({len(fabricated)} unretrieved: {fabricated[:2]})"

    # --- routing ---
    if t == "should_trigger":
        actual = ev.meta.get("triggered")
        if actual is None:
            return "PENDING", f"{desc} (meta.json has no triggered)"
        return ("PASS" if actual == check["expected"] else "FAIL"), \
               f"{desc} (expected {check['expected']}, got {actual})"

    return "FAIL", f"unknown check type: {t}"


# --------------------------------------------------------------------------
# Corpus loading
# --------------------------------------------------------------------------

def load_suite(name: str) -> dict:
    path = HERE / SUITES[name]
    return json.loads(path.read_text(encoding="utf-8"))


def routing_cases_as_checks(suite: dict) -> list[dict]:
    """A routing case is one boolean assertion - express it as a normal check."""
    out = []
    for c in suite["cases"]:
        out.append({
            "id": c["id"],
            "kind": f"routing/{c['split']}",
            "prompt": c["query"],
            "checks": [{
                "type": "should_trigger",
                "expected": c["should_trigger"],
                "desc": f"should_trigger={c['should_trigger']} ({', '.join(c.get('tags', []))})",
            }],
        })
    return out


def all_cases(only_suite: str | None) -> list[dict]:
    cases: list[dict] = []
    for name in SUITES:
        if only_suite and name != only_suite:
            continue
        suite = load_suite(name)
        if name == "routing":
            cases += routing_cases_as_checks(suite)
        else:
            for c in suite["cases"]:
                cases.append({"id": c["id"], "kind": name,
                              "prompt": c.get("prompt", ""), "checks": c.get("checks", [])})
    return cases


# --------------------------------------------------------------------------
# Static gate - no agent evidence required
# --------------------------------------------------------------------------

def static_gate() -> int:
    problems: list[str] = []
    checks_run = 0

    def require(cond: bool, msg: str) -> None:
        nonlocal checks_run
        checks_run += 1
        if not cond:
            problems.append(msg)

    for name, filename in SUITES.items():
        path = HERE / filename
        require(path.exists(), f"{filename} is missing")
        if not path.exists():
            continue
        try:
            suite = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            problems.append(f"{filename} is not valid JSON: {exc}")
            continue

        cases = suite.get("cases", [])
        require(bool(cases), f"{filename} has no cases")
        ids = [c.get("id") for c in cases]
        require(all(ids), f"{filename} has a case with no id")
        require(len(ids) == len(set(ids)), f"{filename} has duplicate ids")
        require(bool(suite.get("mode")), f"{filename} does not declare a mode")
        require(bool(suite.get("isolation")), f"{filename} does not declare an isolation policy")
        require(bool(suite.get("trials")), f"{filename} does not declare a trial count")

        if name == "routing":
            pos = [c for c in cases if c.get("should_trigger") is True]
            neg = [c for c in cases if c.get("should_trigger") is False]
            require(len(cases) >= 20, f"routing has only {len(cases)} cases (want >=20)")
            require(len(pos) >= 8, f"routing has only {len(pos)} positives")
            require(len(neg) >= 8, f"routing has only {len(neg)} negatives")
            require({c.get("split") for c in cases} == {"train", "validation"},
                    "routing splits must be exactly train/validation")
            for split in ("train", "validation"):
                in_split = [c for c in cases if c.get("split") == split]
                require(any(c["should_trigger"] for c in in_split),
                        f"routing {split} split has no positive case")
                require(any(not c["should_trigger"] for c in in_split),
                        f"routing {split} split has no negative case")
            for c in cases:
                require(bool(c.get("rationale")),
                        f"routing case {c.get('id')} has no rationale (a label with no reason rots)")
        else:
            for c in cases:
                require(bool(c.get("checks")), f"{filename}:{c.get('id')} has no machine checks")
                for chk in c.get("checks", []):
                    require(chk.get("type") in BEHAVIOR_CHECK_TYPES,
                            f"{filename}:{c.get('id')} uses unknown check type {chk.get('type')!r}")
                    require(bool(chk.get("desc")),
                            f"{filename}:{c.get('id')} has a check with no desc")
                if name == "behavior":
                    require(bool(c.get("strategy")),
                            f"behavior:{c.get('id')} declares no strategy")

    behavior = load_suite("behavior") if (HERE / "behavior.json").exists() else {"cases": []}
    strategies = {c.get("strategy") for c in behavior["cases"]}
    require({"feed-only", "docs-only", "pricing-focused", "comprehensive"} <= strategies,
            f"behavior corpus misses strategies: "
            f"{ {'feed-only','docs-only','pricing-focused','comprehensive'} - strategies }")

    require(LINT.exists(), "scripts/lint_report.py is missing (report_lint checks need it)")

    print(f"{BOLD}static gate{RESET}  {checks_run} structural checks")
    for p in problems:
        print(f"  {RED}FAIL{RESET}  {p}")
    if not problems:
        print(f"  {GREEN}PASS{RESET}  corpus structure, splits, check types, and references are valid")
    return 1 if problems else 0


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------

def validate(cases: list[dict], only: str | None, lenient: bool,
             json_out: Path | None, junit_out: Path | None) -> int:
    totals = {"PASS": 0, "FAIL": 0, "PENDING": 0, "INFO": 0}
    results = []
    any_fail = False

    for case in cases:
        if only and case["id"] != only:
            continue
        ev = Evidence(OUTDIR / case["id"])
        print(f"\n{BOLD}{case['id']}{RESET} [{case['kind']}]  {DIM}{case['prompt'][:66]}{RESET}")
        case_result = {"id": case["id"], "kind": case["kind"], "checks": []}
        for check in case["checks"]:
            status, msg = run_check(check, ev)
            totals[status] += 1
            if status == "FAIL":
                any_fail = True
            icon = {"PASS": f"{GREEN}PASS{RESET}", "FAIL": f"{RED}FAIL{RESET}",
                    "PENDING": f"{YELLOW}PEND{RESET}", "INFO": f"{DIM}JUDGE{RESET}"}[status]
            print(f"  {icon}  {msg}")
            case_result["checks"].append({"type": check["type"], "status": status, "message": msg})
        case_result["status"] = ("FAIL" if any(c["status"] == "FAIL" for c in case_result["checks"])
                                 else "PENDING" if any(c["status"] == "PENDING"
                                                       for c in case_result["checks"])
                                 else "PASS")
        results.append(case_result)

    print(f"\n{BOLD}Summary:{RESET} {GREEN}{totals['PASS']} pass{RESET}, "
          f"{RED}{totals['FAIL']} fail{RESET}, {YELLOW}{totals['PENDING']} pending{RESET}, "
          f"{DIM}{totals['INFO']} judge{RESET}")

    if json_out:
        json_out.write_text(json.dumps(
            {"skill": "aws-deep-research", "totals": totals, "cases": results}, indent=2),
            encoding="utf-8")
        print(f"wrote {json_out}")

    if junit_out:
        suites = ET.Element("testsuites")
        ts = ET.SubElement(suites, "testsuite", name="aws-deep-research-evals",
                           tests=str(sum(len(c["checks"]) for c in results)),
                           failures=str(totals["FAIL"]), skipped=str(totals["PENDING"]))
        for c in results:
            for chk in c["checks"]:
                tc = ET.SubElement(ts, "testcase", classname=c["id"], name=chk["type"])
                if chk["status"] == "FAIL":
                    ET.SubElement(tc, "failure", message=chk["message"])
                elif chk["status"] == "PENDING":
                    ET.SubElement(tc, "skipped", message=chk["message"])
        ET.ElementTree(suites).write(junit_out, encoding="utf-8", xml_declaration=True)
        print(f"wrote {junit_out}")

    if any_fail:
        return 1
    if totals["PENDING"] and not lenient:
        print(f"{YELLOW}Pending evidence exists. Generate it (see README.md) or use --lenient.{RESET}")
        return 1
    return 0


# --------------------------------------------------------------------------
# Self-test - proves the check engine, no agent evidence needed
# --------------------------------------------------------------------------

class FakeEvidence(Evidence):
    def __init__(self, meta: dict, trace: str | None = None, report: str | None = None) -> None:
        self.dir = Path("/nonexistent")
        self.meta = meta
        self.trace = trace
        self.report = report

    @property
    def present(self) -> bool:
        return True

    def artifact(self, name: str) -> Path | None:
        return Path("/fake") / name if name in self.meta.get("_files", []) else None


def selftest() -> int:
    report = (
        "# Research Report: X\n\n## Executive Summary\nA claim [1].\n\n"
        "## References\n[1] [Src](https://docs.aws.amazon.com/a.html)\n"
    )
    cases = [
        ("slug_valid accepts a good slug",
         {"type": "slug_valid", "desc": "d"},
         FakeEvidence({"slug": "bedrock-llama3-70b-inference-pricing-analysis"}), "PASS"),
        ("slug_valid rejects a terse slug",
         {"type": "slug_valid", "desc": "d"}, FakeEvidence({"slug": "bedrock"}), "FAIL"),
        ("slug_valid rejects an over-long slug",
         {"type": "slug_valid", "desc": "d"},
         FakeEvidence({"slug": "a-very-long-slug-that-goes-well-past-the-sixty-character-ceiling-here"}),
         "FAIL"),
        ("artifact_exists finds a recorded file",
         {"type": "artifact_exists", "path": "aws-docs.md", "desc": "d"},
         FakeEvidence({"_files": ["aws-docs.md"]}), "PASS"),
        ("artifact_absent passes when absent",
         {"type": "artifact_absent", "path": "web-content.md", "desc": "d"},
         FakeEvidence({"_files": []}), "PASS"),
        ("artifact_absent fails when present",
         {"type": "artifact_absent", "path": "web-content.md", "desc": "d"},
         FakeEvidence({"_files": ["web-content.md"]}), "FAIL"),
        ("max_parallel enforces the 4-subagent cap",
         {"type": "max_parallel", "limit": 4, "desc": "d"},
         FakeEvidence({"max_parallel_subagents": 5}), "FAIL"),
        ("max_parallel passes at the cap",
         {"type": "max_parallel", "limit": 4, "desc": "d"},
         FakeEvidence({"max_parallel_subagents": 4}), "PASS"),
        ("no_parent_findings_read fails on a leak",
         {"type": "no_parent_findings_read", "desc": "d"},
         FakeEvidence({"parent_findings_reads": ["aws-docs.md"]}), "FAIL"),
        ("no_parent_findings_read passes when clean",
         {"type": "no_parent_findings_read", "desc": "d"},
         FakeEvidence({"parent_findings_reads": []}), "PASS"),
        ("subagent_return_budget enforces the char cap",
         {"type": "subagent_return_budget", "max_chars": 500, "desc": "d"},
         FakeEvidence({"subagent_return_chars": 900}), "FAIL"),
        ("native_activation fails when the harness never loaded the skill",
         {"type": "native_activation", "desc": "d"},
         FakeEvidence({"skill_md_loaded": False}), "FAIL"),
        ("no_remote_kroki_fallback allows localhost",
         {"type": "no_remote_kroki_fallback", "desc": "d"},
         FakeEvidence({"kroki_hosts_contacted": ["http://localhost:8000"]}), "PASS"),
        ("no_remote_kroki_fallback rejects a remote host",
         {"type": "no_remote_kroki_fallback", "desc": "d"},
         FakeEvidence({"kroki_hosts_contacted": ["https://kroki.io"]}), "FAIL"),
        ("no_fabricated_citations catches an unretrieved URL",
         {"type": "no_fabricated_citations", "desc": "d"},
         FakeEvidence({"retrieved_urls": []}, report=report), "FAIL"),
        ("no_fabricated_citations passes when every URL was retrieved",
         {"type": "no_fabricated_citations", "desc": "d"},
         FakeEvidence({"retrieved_urls": ["https://docs.aws.amazon.com/a.html"]}, report=report),
         "PASS"),
        ("should_trigger compares exactly",
         {"type": "should_trigger", "expected": False, "desc": "d"},
         FakeEvidence({"triggered": True}), "FAIL"),
        ("trace_regex finds the harness echo",
         {"type": "trace_regex", "pattern": "harness=", "desc": "d"},
         FakeEvidence({}, trace="harness=pi backend=pi"), "PASS"),
        ("trace_absent_regex catches a delegate tool",
         {"type": "trace_absent_regex", "pattern": "_Delegate", "desc": "d"},
         FakeEvidence({}, trace="called Foo_Delegate"), "FAIL"),
        ("min_citations counts reference lines",
         {"type": "min_citations", "count": 2, "desc": "d"},
         FakeEvidence({}, report=report), "FAIL"),
        ("missing meta yields PENDING not a false pass",
         {"type": "max_parallel", "limit": 4, "desc": "d"}, FakeEvidence({}), "PENDING"),
        ("judge is INFO", {"type": "judge", "desc": "d"}, FakeEvidence({}), "INFO"),
        ("unknown check type fails loudly",
         {"type": "bogus_check", "desc": "d"}, FakeEvidence({}), "FAIL"),
    ]
    ok = True
    for name, check, ev, expected in cases:
        status, _ = run_check(check, ev)
        good = status == expected
        ok = ok and good
        icon = f"{GREEN}ok{RESET}" if good else f"{RED}MISMATCH{RESET}"
        print(f"  {icon}  {name}: got {status}, expected {expected}")

    # Every check type used in the corpora must be handled by the engine.
    used = {chk["type"] for name in ("behavior", "faults")
            for c in load_suite(name)["cases"] for chk in c["checks"]}
    unhandled = used - BEHAVIOR_CHECK_TYPES
    if unhandled:
        ok = False
        print(f"  {RED}MISMATCH{RESET}  corpora use unhandled check types: {unhandled}")
    else:
        print(f"  {GREEN}ok{RESET}  every corpus check type is handled ({len(used)} in use)")

    print(f"\n{'PASS' if ok else 'FAIL'}: check engine self-test")
    return 0 if ok else 1


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="run.py", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--static", action="store_true", help="corpus structure only, no agent needed")
    ap.add_argument("--selftest", action="store_true", help="validate the check engine")
    ap.add_argument("--suite", choices=sorted(SUITES), help="grade one suite")
    ap.add_argument("--case", help="grade one case id")
    ap.add_argument("--lenient", action="store_true", help="missing evidence is PENDING, not FAIL")
    ap.add_argument("--json", dest="json_out", type=Path, help="write a JSON summary")
    ap.add_argument("--junit", dest="junit_out", type=Path, help="write JUnit XML")
    args = ap.parse_args(argv)

    missing = [f for f in SUITES.values() if not (HERE / f).exists()]
    if missing:
        print(f"missing corpora: {missing}", file=sys.stderr)
        return 2

    if args.selftest:
        return selftest()
    if args.static:
        return static_gate()
    return validate(all_cases(args.suite), args.case, args.lenient,
                    args.json_out, args.junit_out)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
