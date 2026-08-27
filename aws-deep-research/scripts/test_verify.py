"""Tests for the Step 5 findings size-gate and the report linter.

These are the deterministic half of the fault-injection surface: MISSING /
WEAK / boundary-size / unreadable findings files, and reports that are
malformed in ways a mechanical grader must catch. The model-facing faults
(invalid API key, denied web approval, exhausted budget) live in
evals/faults.json instead.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent
VERIFY = SCRIPTS_DIR / "verify_findings.sh"
LINT = SCRIPTS_DIR / "lint_report.py"

MIN_BYTES = 500


def run_verify(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(VERIFY), *args], capture_output=True, text=True, check=False
    )


def run_lint(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", str(LINT), *args], capture_output=True, text=True, check=False
    )


def write_bytes(path: Path, n: int) -> Path:
    path.write_text("x" * n, encoding="utf-8")
    return path


# --------------------------------------------------------------------------
# verify_findings.sh
# --------------------------------------------------------------------------


def test_ok_and_weak_are_classified_by_size(tmp_path: Path) -> None:
    write_bytes(tmp_path / "aws-docs.md", MIN_BYTES + 1)
    write_bytes(tmp_path / "web-content.md", 10)
    r = run_verify(str(tmp_path))
    assert r.returncode == 0
    assert "aws-docs.md=OK" in r.stdout
    assert "web-content.md=WEAK" in r.stdout


@pytest.mark.parametrize(
    ("size", "status"),
    [(MIN_BYTES - 1, "WEAK"), (MIN_BYTES, "OK"), (MIN_BYTES + 1, "OK")],
)
def test_threshold_boundary_is_inclusive_at_min(tmp_path: Path, size: int, status: str) -> None:
    """<500 is WEAK; exactly 500 is OK. Guards an off-by-one in the gate."""
    write_bytes(tmp_path / "aws-docs.md", size)
    r = run_verify(str(tmp_path))
    assert f"aws-docs.md={status}" in r.stdout, r.stdout


def test_expected_but_absent_file_is_missing(tmp_path: Path) -> None:
    write_bytes(tmp_path / "aws-docs.md", MIN_BYTES)
    r = run_verify(str(tmp_path), "--expect", "github-repos.md")
    assert r.returncode == 0
    assert "github-repos.md=MISSING" in r.stdout


def test_undeclared_file_on_disk_is_still_reported(tmp_path: Path) -> None:
    """An undeclared findings file is real evidence - never silently dropped."""
    write_bytes(tmp_path / "aws-docs.md", MIN_BYTES)
    write_bytes(tmp_path / "surprise.md", MIN_BYTES)
    r = run_verify(str(tmp_path), "--expect", "aws-docs.md")
    assert "surprise.md=OK" in r.stdout


def test_contract_report_and_log_files_are_not_findings(tmp_path: Path) -> None:
    write_bytes(tmp_path / "research-contract.md", 100)
    write_bytes(tmp_path / "slug-report.md", 100)
    write_bytes(tmp_path / "slug-report.eval.md", 100)
    write_bytes(tmp_path / "research.log", 100)
    write_bytes(tmp_path / "aws-docs.md", MIN_BYTES)
    r = run_verify(str(tmp_path))
    assert "aws-docs.md=OK" in r.stdout
    for skipped in ("research-contract", "slug-report", "research.log"):
        assert skipped not in r.stdout


def test_unreadable_file_is_flagged_not_crashed(tmp_path: Path) -> None:
    f = write_bytes(tmp_path / "aws-docs.md", MIN_BYTES)
    write_bytes(tmp_path / "web-content.md", MIN_BYTES)
    f.chmod(0o000)
    try:
        r = run_verify(str(tmp_path))
        assert "aws-docs.md=UNREADABLE" in r.stdout, r.stdout
        assert r.returncode == 0  # web-content.md is still OK
    finally:
        f.chmod(0o644)


def test_all_weak_exits_nonzero(tmp_path: Path) -> None:
    """Nothing worth synthesizing must not look like success."""
    write_bytes(tmp_path / "aws-docs.md", 10)
    r = run_verify(str(tmp_path))
    assert r.returncode == 1
    assert "do not synthesize" in r.stderr


def test_empty_work_dir_exits_nonzero(tmp_path: Path) -> None:
    r = run_verify(str(tmp_path))
    assert r.returncode == 1
    assert "no findings files" in r.stderr


def test_missing_work_dir_is_usage_error() -> None:
    r = run_verify("/nonexistent/work/dir")
    assert r.returncode == 2


def test_no_args_is_usage_error() -> None:
    assert run_verify().returncode == 2


def test_unknown_flag_is_usage_error(tmp_path: Path) -> None:
    assert run_verify(str(tmp_path), "--bogus").returncode == 2


def test_help_exits_zero_with_usage() -> None:
    r = run_verify("--help")
    assert r.returncode == 0
    assert "Usage:" in r.stdout


def test_json_output_is_parseable(tmp_path: Path) -> None:
    write_bytes(tmp_path / "aws-docs.md", MIN_BYTES + 5)
    write_bytes(tmp_path / "web-content.md", 3)
    r = run_verify(str(tmp_path), "--json", "--expect", "github-repos.md")
    payload = json.loads(r.stdout)
    assert payload["ok"] == 1
    assert payload["files"]["aws-docs.md"]["status"] == "OK"
    assert payload["files"]["web-content.md"]["status"] == "WEAK"
    assert payload["files"]["github-repos.md"]["status"] == "MISSING"


def test_custom_min_bytes_is_honoured(tmp_path: Path) -> None:
    write_bytes(tmp_path / "aws-docs.md", 200)
    assert "WEAK" in run_verify(str(tmp_path)).stdout
    assert "OK" in run_verify(str(tmp_path), "--min-bytes", "100").stdout


def test_never_prints_findings_content(tmp_path: Path) -> None:
    """The gate is size-only - content must not cross into the parent context."""
    secret = "SENTINEL_FINDINGS_CONTENT_" + "y" * MIN_BYTES
    (tmp_path / "aws-docs.md").write_text(secret, encoding="utf-8")
    r = run_verify(str(tmp_path))
    assert "SENTINEL_FINDINGS_CONTENT" not in r.stdout + r.stderr


# --------------------------------------------------------------------------
# lint_report.py
# --------------------------------------------------------------------------

GOOD_REPORT = """# Research Report: Example

**Date**: 2026-08-27

## Executive Summary

A claim with a citation [1] and another [2].

## Key Tensions & Decision Drivers

- Trade-off one [1].

## Detailed Findings

### Topic

More detail [2].

## Recommendations

Do the thing [1].

## Gaps & Limitations

Nothing found about X.

## References

[1] [First source](https://docs.aws.amazon.com/a.html)
[2] [Second source](https://aws.amazon.com/blogs/b/)
"""


def lint_text(tmp_path: Path, text: str, *args: str) -> dict:
    p = tmp_path / "slug-report.md"
    p.write_text(text, encoding="utf-8")
    r = run_lint(str(p), "--json", *args)
    return json.loads(r.stdout)


def test_good_report_passes(tmp_path: Path) -> None:
    out = lint_text(tmp_path, GOOD_REPORT, "--intents", "comparison", "--min-bytes", "100")
    assert out["passed"], out["hard_failed"]


def test_missing_required_section_fails(tmp_path: Path) -> None:
    text = GOOD_REPORT.replace("## Gaps & Limitations", "## Something Else")
    out = lint_text(tmp_path, text, "--min-bytes", "100")
    assert "sections" in out["hard_failed"]


def test_conditional_section_required_only_for_matching_intent(tmp_path: Path) -> None:
    text = GOOD_REPORT.replace("## Key Tensions & Decision Drivers\n\n- Trade-off one [1].\n\n", "")
    assert "sections" in lint_text(
        tmp_path, text, "--intents", "comparison", "--min-bytes", "100"
    )["hard_failed"]
    assert lint_text(
        tmp_path, text, "--intents", "service-overview", "--min-bytes", "100"
    )["passed"]


def test_pricing_intent_requires_pricing_section(tmp_path: Path) -> None:
    out = lint_text(tmp_path, GOOD_REPORT, "--intents", "pricing", "--min-bytes", "100")
    assert "sections" in out["hard_failed"]


def test_section_match_tolerates_case_and_ampersand(tmp_path: Path) -> None:
    text = GOOD_REPORT.replace("## Gaps & Limitations", "## Gaps and limitations")
    assert lint_text(tmp_path, text, "--min-bytes", "100")["passed"]


def test_bare_url_reference_is_malformed(tmp_path: Path) -> None:
    """The `[N] Title — https://url` form the older synthesizer emitted."""
    text = GOOD_REPORT.replace(
        "[1] [First source](https://docs.aws.amazon.com/a.html)",
        "[1] First source - https://docs.aws.amazon.com/a.html",
    )
    out = lint_text(tmp_path, text, "--min-bytes", "100")
    assert "ref_format" in out["hard_failed"]


def test_reference_url_with_balanced_parens_is_valid(tmp_path: Path) -> None:
    """Real doc URLs contain parens - the strict form must not reject them."""
    text = GOOD_REPORT.replace(
        "https://docs.aws.amazon.com/a.html",
        "https://github.com/o/r/blob/main/docs/(agentic)/metrics.mdx",
    )
    assert lint_text(tmp_path, text, "--min-bytes", "100")["passed"]


def test_non_sequential_references_fail(tmp_path: Path) -> None:
    text = GOOD_REPORT.replace("[2] [Second source]", "[5] [Second source]")
    out = lint_text(tmp_path, text, "--min-bytes", "100")
    assert "ref_sequence" in out["hard_failed"]


def test_dangling_citation_fails(tmp_path: Path) -> None:
    text = GOOD_REPORT.replace("More detail [2].", "More detail [9].")
    out = lint_text(tmp_path, text, "--min-bytes", "100")
    assert "no_dangling" in out["hard_failed"]


def test_malformed_reference_does_not_cascade_into_dangling(tmp_path: Path) -> None:
    """A formatting defect must be reported once, not as a phantom dangling ref."""
    text = GOOD_REPORT.replace(
        "[1] [First source](https://docs.aws.amazon.com/a.html)",
        "[1] First source - https://docs.aws.amazon.com/a.html",
    )
    out = lint_text(tmp_path, text, "--min-bytes", "100")
    assert "ref_format" in out["hard_failed"]
    assert "no_dangling" not in out["hard_failed"]


def test_no_references_section_fails(tmp_path: Path) -> None:
    text = GOOD_REPORT.split("## References")[0]
    out = lint_text(tmp_path, text, "--min-bytes", "100")
    assert "refs_present" in out["hard_failed"]


def test_leaked_subagent_preamble_fails_title(tmp_path: Path) -> None:
    """A `✅ Wrote report to ...` first line means the H1 is not the H1."""
    text = "✅ **Wrote report to /path/x-report.md**\n\n" + GOOD_REPORT
    out = lint_text(tmp_path, text, "--min-bytes", "100")
    assert "title" in out["hard_failed"]


def test_oversize_report_fails(tmp_path: Path) -> None:
    text = GOOD_REPORT + ("\nfiller line\n" * 200)
    out = lint_text(tmp_path, text, "--max-bytes", "500", "--min-bytes", "100")
    assert "size_max" in out["hard_failed"]


def test_citations_inside_code_fences_are_ignored(tmp_path: Path) -> None:
    text = GOOD_REPORT.replace(
        "## Recommendations",
        "## Extra\n\n```\nexample citation [99] in a code block\n```\n\n## Recommendations",
    )
    out = lint_text(tmp_path, text, "--min-bytes", "100")
    assert "no_dangling" not in out["hard_failed"]


def test_orphan_reference_is_soft_but_strict_promotes_it(tmp_path: Path) -> None:
    text = GOOD_REPORT.replace(
        "## References\n",
        "## References\n",
    ).replace(
        "[2] [Second source](https://aws.amazon.com/blogs/b/)",
        "[2] [Second source](https://aws.amazon.com/blogs/b/)\n"
        "[3] [Never cited](https://example.com/c)",
    )
    lenient = lint_text(tmp_path, text, "--min-bytes", "100")
    assert lenient["passed"]
    assert "no_orphans" in lenient["soft_failed"]
    strict = lint_text(tmp_path, text, "--min-bytes", "100", "--strict")
    assert not strict["passed"]


def test_leaked_evidence_tag_is_soft(tmp_path: Path) -> None:
    text = GOOD_REPORT.replace("A claim with", "A claim {official·2026-03} with")
    out = lint_text(tmp_path, text, "--min-bytes", "100")
    assert out["passed"]
    assert "no_raw_tags" in out["soft_failed"]


def test_stub_report_trips_size_floor(tmp_path: Path) -> None:
    out = lint_text(tmp_path, GOOD_REPORT)  # default floor 2000 > this fixture
    assert "size_min" in out["soft_failed"]


def test_unreadable_report_is_usage_error() -> None:
    assert run_lint("/nonexistent/report.md").returncode == 2


def test_help_exits_zero() -> None:
    r = run_lint("--help")
    assert r.returncode == 0
    assert "usage" in r.stdout.lower()
