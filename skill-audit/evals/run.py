#!/usr/bin/env python3
"""
Deterministic eval runner for skill-audit.

Two-phase design (see README.md):
  1. GENERATE: for each case, run the skill-audit skill in a clean/isolated
     agent session against the case's fixture, and save the written audit
     report to evals/outputs/<id>.md. For `negative` cases (the target is not
     a skill, or the skill should not trigger), no report should be produced;
     the runner treats a MISSING report file as the expected outcome.
  2. VALIDATE: this script checks each report against machine-executable
     `checks` in evals.json. The fixtures are deterministic, so the defects
     the auditor must cite are fixed strings - checkable with plain regex,
     no LLM-as-judge. `judge` checks are printed as INFO for human review
     and never affect pass/fail.

Why this is deterministic despite auditing being a judgment task: the VERDICT
(a per-dimension score) is a judgment, but the EVIDENCE the auditor must cite
against a fixed fixture is not. A correct audit of flawed-skill MUST contain
the string "helper" (the planted name mismatch), a backslash Windows path, the
no-op phrases, and the voodoo constants. Those are what we grade here.

Isolation: each case is generated in its own fresh agent session and validated
against its own single output file. Cases never share state.

Exit codes:
  0  all runnable checks passed (PENDING/INFO do not fail in --lenient)
  1  a check FAILED, or a required report is missing (strict, the default)
  2  usage / config error

Usage:
  ./run.py                 validate all cases (strict: missing report = fail)
  ./run.py --lenient       missing reports are PENDING, not failures
  ./run.py --case <id>     validate a single case
  ./run.py --selftest      validate the check engine against inline fixtures
"""
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


def run_check(check, report):
    """Return (status, message). status in {PASS, FAIL, PENDING, INFO}.

    `report` is the audit report text, or None if no report was produced.
    """
    t = check["type"]
    desc = check.get("desc", t)

    if t == "judge":
        return ("INFO", desc)

    # Negative-case check: the auditor should NOT have produced a report.
    if t == "report_absent":
        return (("PASS" if report is None else "FAIL"),
                desc if report is None else f"{desc} (a report WAS produced)")

    # All remaining checks operate on the produced report text.
    if report is None:
        return ("PENDING", f"{desc} (no audit report yet)")

    if t == "regex":
        return (("PASS" if re.search(check["pattern"], report, _flags(check)) else "FAIL"), desc)
    if t == "any_regex":
        # PASS if ANY of the patterns matches (OR-group).
        ok = any(re.search(p, report, _flags(check)) for p in check["patterns"])
        return (("PASS" if ok else "FAIL"), desc)
    if t == "absent":
        return (("PASS" if check["pattern"] not in report else "FAIL"), desc)
    if t == "absent_regex":
        return (("PASS" if not re.search(check["pattern"], report, _flags(check)) else "FAIL"), desc)
    if t == "count_regex":
        n = len(re.findall(check["pattern"], report, _flags(check)))
        ok = n >= check.get("min", 1)
        return (("PASS" if ok else "FAIL"), f"{desc} (found {n}, need >={check.get('min',1)})")

    return ("FAIL", f"unknown check type: {t}")


def load_report(case):
    path = os.path.join(OUTDIR, case["id"] + ".md")
    return open(path, encoding="utf-8").read() if os.path.exists(path) else None


def validate(cases, only=None, lenient=False):
    totals = {"PASS": 0, "FAIL": 0, "PENDING": 0, "INFO": 0}
    any_fail = False
    for case in cases:
        if only and case["id"] != only:
            continue
        report = load_report(case)
        print(f"\n{BOLD}{case['id']}{RESET} [{case['kind']}]  {DIM}{case.get('prompt','')[:70]}{RESET}")
        for check in case.get("checks", []):
            status, msg = run_check(check, report)
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
        print(f"{YELLOW}Pending reports exist. Generate them (see README) or use --lenient.{RESET}")
        return 1
    return 0


# --------------------------------------------------------------------------
# Self-test: prove each check type works, no agent-generated report needed.
# --------------------------------------------------------------------------
SELFTEST_REPORT = (
    "# Skill Best-Practices Audit - flawed-skill\n\n"
    "| 1 | Frontmatter spec | 00.spec | \U0001f534 | name 'helper' does not match dir |\n"
    "| 10 | Anti-patterns | 01a.claude | \U0001f534 | Windows path C:\\data\\input; "
    "voodoo constants --threshold 0.7 --window 42 --mode 3; no-ops present |\n"
    "F1 - the 'write clean code' line is a no-op that restates default behavior.\n"
    "**Overall:** \U0001f534\n"
)
SELFTEST_CLEAN = (
    "# Skill Best-Practices Audit - clean-skill\n\n"
    "| 4 | Description & triggers | 02.desc | \U0001f7e2 | credits the 'Do NOT use for' clause |\n"
    "| 9 | Eval scaffolding | 03.eval | \U0001f534 | no evals/ directory |\n"
    "**Overall:** \U0001f534\n"
)


def selftest():
    cases = [
        ("regex finds name mismatch", {"type": "regex", "pattern": "helper"},
         SELFTEST_REPORT, "PASS"),
        ("regex miss -> FAIL", {"type": "regex", "pattern": "nonexistent-token"},
         SELFTEST_REPORT, "FAIL"),
        ("any_regex windows path (OR-group)", {"type": "any_regex", "flags": "i",
         "patterns": ["backslash", "C:\\\\data"]}, SELFTEST_REPORT, "PASS"),
        ("any_regex voodoo constants", {"type": "any_regex",
         "patterns": ["0\\.7", "window 42", "mode 3"]}, SELFTEST_REPORT, "PASS"),
        ("regex no-op flagged", {"type": "regex", "flags": "i", "pattern": "no-op"},
         SELFTEST_REPORT, "PASS"),
        ("count_regex >=1 red badge", {"type": "count_regex",
         "pattern": "\U0001f534", "min": 1}, SELFTEST_REPORT, "PASS"),
        ("absent: report must not invent a green frontmatter", {"type": "absent",
         "pattern": "no such string"}, SELFTEST_REPORT, "PASS"),
        ("clean: credits Do NOT clause", {"type": "regex", "flags": "i",
         "pattern": "do not use"}, SELFTEST_CLEAN, "PASS"),
        ("clean: dim 9 red for missing evals", {"type": "regex", "flags": "i",
         "pattern": "no evals/? directory"}, SELFTEST_CLEAN, "PASS"),
        ("report_absent PASS when None", {"type": "report_absent"}, None, "PASS"),
        ("report_absent FAIL when present", {"type": "report_absent"},
         SELFTEST_REPORT, "FAIL"),
        ("regex PENDING when no report", {"type": "regex", "pattern": "x"},
         None, "PENDING"),
        ("judge is INFO", {"type": "judge", "desc": "human review"},
         SELFTEST_REPORT, "INFO"),
    ]
    ok = True
    for name, check, report, expected in cases:
        status, _ = run_check(check, report)
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
