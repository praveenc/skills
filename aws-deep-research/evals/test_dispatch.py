"""Tests for scripts/dispatch.sh - portable subagent dispatch.

These tests never spawn a real model. They drive dispatch.sh in DISPATCH_DRY_RUN
mode (prints the resolved command, exits 0) and assert on:
  - per-harness command construction (pi, claude)
  - harness detection from env fingerprints, including the ambiguous case
  - guard exits for kiro (in-session, not a subprocess) and untested harnesses

Run:
  uv run --python 3.13 --with pytest pytest evals/test_dispatch.py -q
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "dispatch.sh"
SKILL_DIR = Path(__file__).resolve().parent.parent  # evals/ -> skill root


def run(
    args: list[str],
    env: dict[str, str] | None = None,
    *,
    clean_env: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Invoke dispatch.sh. By default inherits os.environ; clean_env starts bare."""
    base = {} if clean_env else dict(os.environ)
    # a bare env still needs HOME/PATH for bash to run
    base.setdefault("HOME", os.environ.get("HOME", "/tmp"))
    base.setdefault("PATH", os.environ.get("PATH", "/usr/bin:/bin"))
    base["SKILL_DIR"] = str(SKILL_DIR)
    if env:
        base.update(env)
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        capture_output=True,
        text=True,
        env=base,
    )


# --- command construction ---------------------------------------------------


def test_pi_command_construction():
    r = run(
        ["--harness", "pi", "synthesizer", "Synthesize findings", "/tmp/report.md"],
        env={"DISPATCH_DRY_RUN": "1"},
    )
    assert r.returncode == 0, r.stderr
    out = r.stdout
    assert out.startswith("pi -p")
    assert "--no-session" in out
    assert "--tools read,write,bash" in out
    assert "--append-system-prompt @agents/synthesizer.md" in out
    assert '"Synthesize findings"' in out
    assert "> /tmp/report.md" in out
    # pi must NOT carry claude-only flags
    assert "--allowedTools" not in out
    assert "--add-dir" not in out


def test_claude_command_construction():
    r = run(
        ["--harness", "claude", "synthesizer", "Synthesize findings", "/tmp/report.md"],
        env={"DISPATCH_DRY_RUN": "1"},
    )
    assert r.returncode == 0, r.stderr
    out = r.stdout
    assert out.startswith("claude -p")
    assert "--append-system-prompt @agents/synthesizer.md" in out
    assert '--allowedTools "Read Write Bash"' in out
    assert f"--add-dir {SKILL_DIR}" in out
    assert "> /tmp/report.md" in out
    # claude must NOT carry pi-only flags
    assert "--no-session" not in out
    assert "--tools read,write,bash" not in out


def test_claude_code_alias_normalizes_to_claude():
    r = run(
        ["--harness", "claude-code", "synthesizer", "t", "/tmp/r.md"],
        env={"DISPATCH_DRY_RUN": "1"},
    )
    assert r.returncode == 0, r.stderr
    assert r.stdout.startswith("claude -p")
    assert "harness=claude " in r.stderr


def test_model_override_threads_through():
    r = run(
        ["--harness", "pi", "synthesizer", "t", "/tmp/r.md"],
        env={"DISPATCH_DRY_RUN": "1", "DISPATCH_MODEL": "sonnet:high"},
    )
    assert r.returncode == 0, r.stderr
    assert "--model sonnet:high" in r.stdout


def test_task_from_file_is_read(tmp_path: Path):
    tf = tmp_path / "task.txt"
    tf.write_text("do the research work")
    r = run(
        ["--harness", "pi", "synthesizer", f"@{tf}", "/tmp/r.md"],
        env={"DISPATCH_DRY_RUN": "1"},
    )
    assert r.returncode == 0, r.stderr
    assert '"do the research work"' in r.stdout


# --- disclaimer -------------------------------------------------------------


def test_disclaimer_shown_by_default():
    r = run(
        ["--harness", "pi", "synthesizer", "t", "/tmp/r.md"],
        env={"DISPATCH_DRY_RUN": "1"},
    )
    assert "separate CLI process" in r.stderr
    # non-TTY: no literal escape codes leaking
    assert "\\033" not in r.stderr
    assert "033[1m" not in r.stderr


def test_disclaimer_suppressed_when_flagged():
    r = run(
        ["--harness", "pi", "synthesizer", "t", "/tmp/r.md"],
        env={"DISPATCH_DRY_RUN": "1", "DISPATCH_BANNER_SHOWN": "1"},
    )
    assert "separate CLI process" not in r.stderr


def test_decision_line_always_echoed():
    r = run(
        ["--harness", "pi", "synthesizer", "t", "/tmp/out.md"],
        env={"DISPATCH_DRY_RUN": "1"},
    )
    # mismatch must never be silent: harness+backend+outfile on stderr
    assert "harness=pi" in r.stderr
    assert "backend=process-fanout" in r.stderr
    assert "/tmp/out.md" in r.stderr


# --- harness detection ------------------------------------------------------


def test_detect_pi_from_env():
    r = run(
        ["synthesizer", "t", "/tmp/r.md"],
        env={"DISPATCH_DRY_RUN": "1", "PI_CODING_AGENT": "true"},
        clean_env=True,
    )
    assert r.returncode == 0, r.stderr
    assert r.stdout.startswith("pi -p")


def test_detect_claude_from_env():
    r = run(
        ["synthesizer", "t", "/tmp/r.md"],
        env={"DISPATCH_DRY_RUN": "1", "CLAUDECODE": "1"},
        clean_env=True,
    )
    assert r.returncode == 0, r.stderr
    assert r.stdout.startswith("claude -p")


def test_ambiguous_env_falls_through_to_ask():
    # pi + kiro fingerprints both present → cannot decide → exit 3 (ask user).
    r = run(
        ["synthesizer", "t", "/tmp/r.md"],
        env={"DISPATCH_DRY_RUN": "1", "PI_CODING_AGENT": "true", "KIRO_AGENT": "1"},
        clean_env=True,
    )
    assert r.returncode == 3
    assert "could not determine the harness" in r.stderr


def test_no_env_asks_user():
    r = run(
        ["synthesizer", "t", "/tmp/r.md"],
        env={"DISPATCH_DRY_RUN": "1"},
        clean_env=True,
    )
    assert r.returncode == 3
    assert "Ask the user" in r.stderr


def test_override_beats_ambiguous_env():
    r = run(
        ["--harness", "claude", "synthesizer", "t", "/tmp/r.md"],
        env={"DISPATCH_DRY_RUN": "1", "PI_CODING_AGENT": "true", "KIRO_AGENT": "1"},
        clean_env=True,
    )
    assert r.returncode == 0, r.stderr
    assert r.stdout.startswith("claude -p")


# --- guard exits ------------------------------------------------------------


def test_kiro_refuses_with_guidance():
    r = run(
        ["--harness", "kiro", "synthesizer", "t", "/tmp/r.md"],
        env={"DISPATCH_DRY_RUN": "1"},
    )
    assert r.returncode == 4
    assert "in-session" in r.stderr
    assert "subagent" in r.stderr


def test_untested_harness_refuses():
    r = run(
        ["--harness", "gemini", "synthesizer", "t", "/tmp/r.md"],
        env={"DISPATCH_DRY_RUN": "1"},
    )
    assert r.returncode == 4
    assert "not one of the tested" in r.stderr


# --- usage errors -----------------------------------------------------------


def test_missing_args_is_usage_error():
    r = run(["--harness", "pi", "synthesizer"], env={"DISPATCH_DRY_RUN": "1"})
    assert r.returncode == 2


def test_unknown_agent_is_usage_error():
    r = run(
        ["--harness", "pi", "no-such-agent", "t", "/tmp/r.md"],
        env={"DISPATCH_DRY_RUN": "1"},
    )
    assert r.returncode == 2
    assert "no role prompt" in r.stderr


def test_help_flag_exits_zero_with_usage():
    r = run(["--help"])
    assert r.returncode == 0
    assert "USAGE:" in r.stdout
    assert "EXIT CODES:" in r.stdout
    assert "--harness" in r.stdout


def test_unknown_flag_is_usage_error():
    r = run(["--bogus"])
    assert r.returncode == 2
    assert "unknown flag" in r.stderr


@pytest.mark.parametrize("agent", [
    "aws-mcp-researcher",
    "web-content-researcher",
    "github-researcher",
    "agentcore-researcher",
    "synthesizer",
    "diagram-generator",
])
def test_every_registered_agent_dispatches(agent: str):
    r = run(
        ["--harness", "pi", agent, "t", "/tmp/r.md"],
        env={"DISPATCH_DRY_RUN": "1"},
    )
    assert r.returncode == 0, r.stderr
    assert f"@agents/{agent}.md" in r.stdout


# --- F1 regression: child stdout must not clobber the findings file ---------


def test_child_stdout_goes_to_log_not_findings(tmp_path: Path):
    """F1: the child writes findings with its write tool; dispatch.sh sends the
    child's stdout to <dir>/logs/<agent>.stdout, NOT onto the findings file.

    Reproduction with a fake `claude` on PATH that (a) writes real findings to
    the outfile and (b) prints a status line to stdout - exactly the two writers
    that used to corrupt the head of every findings file.
    """
    bindir = tmp_path / "bin"
    bindir.mkdir()
    fake = bindir / "claude"
    fake.write_text(
        "#!/usr/bin/env bash\n"
        "set -eu\n"
        '# emulate the write tool filling the findings file\n'
        'printf "# Findings\\n\\n- record one\\n" > "$FAKE_FINDINGS_PATH"\n'
        'head -c 600 /dev/zero | tr "\\0" x >> "$FAKE_FINDINGS_PATH"\n'
        'printf "\\n" >> "$FAKE_FINDINGS_PATH"\n'
        '# the final status line the model prints to stdout (used to clobber)\n'
        'printf "STATUS wrote 640 chars to %s\\n" "$FAKE_FINDINGS_PATH"\n'
    )
    fake.chmod(0o755)

    work = tmp_path / "work"
    work.mkdir()
    outfile = work / "aws-docs.md"
    r = run(
        ["--harness", "claude", "aws-mcp-researcher", "write findings", str(outfile)],
        env={
            "PATH": f"{bindir}:{os.environ.get('PATH', '')}",
            "FAKE_FINDINGS_PATH": str(outfile),
            "DISPATCH_BANNER_SHOWN": "1",
        },
    )
    assert r.returncode == 0, r.stderr

    content = outfile.read_text(encoding="utf-8")
    assert content.startswith("# Findings"), content[:80]
    assert "STATUS wrote" not in content  # stdout did NOT leak into findings

    log = work / "logs" / "aws-mcp-researcher.stdout"
    assert log.exists(), "child stdout log was not created"
    assert "STATUS wrote 640 chars" in log.read_text(encoding="utf-8")
