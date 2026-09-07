#!/usr/bin/env python3
"""Generate candidate behavior evidence with Pi and the bundled validator."""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUTPUTS = HERE / "outputs"
DEFAULT_MODEL = "amazon-bedrock/us.anthropic.claude-haiku-4-5-20251001-v1:0"
PERMISSIONS = (
    "tools=read,write; no network tools, sessions, extensions, context files, "
    "or prompt templates"
)
CATALOG_REVISION = "skills disabled except explicit candidate skill"
RUN_ID_RE = re.compile(r"\d{8}T\d{6}Z")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree_digest(root: Path) -> str:
    """Hash the full skill tree except generated and interpreter files."""
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        relative = path.relative_to(root)
        if (
            ".git" in relative.parts
            or "__pycache__" in relative.parts
            or relative.parts[:2] == ("evals", "outputs")
            or path.suffix == ".pyc"
        ):
            continue
        if path.is_symlink():
            payload = b"link\0" + os.readlink(path).encode("utf-8")
        elif path.is_file():
            payload = b"file\0" + path.read_bytes()
        else:
            continue
        digest.update(relative.as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(payload)
        digest.update(b"\0")
    return digest.hexdigest()


def snapshot_ignore(directory: str, names: list[str]) -> set[str]:
    ignored = {
        name
        for name in names
        if name in {".git", "__pycache__"} or name.endswith(".pyc")
    }
    if Path(directory).resolve() == (ROOT / "evals").resolve():
        ignored.add("outputs")
    return ignored


def snapshot_has_excluded_files(snapshot: Path) -> bool:
    return (
        any(snapshot.rglob(".git"))
        or (snapshot / "evals" / "outputs").exists()
        or any(path.name == "__pycache__" for path in snapshot.rglob("__pycache__"))
        or any(snapshot.rglob("*.pyc"))
    )


def freeze_snapshot(snapshot: Path) -> None:
    for path in sorted(snapshot.rglob("*"), key=lambda item: item.as_posix(), reverse=True):
        if not path.is_symlink():
            path.chmod(path.stat().st_mode & ~0o222)
    snapshot.chmod(snapshot.stat().st_mode & ~0o222)


def retain_candidate_snapshot(run_dir: Path) -> Path:
    snapshot = run_dir / "snapshots" / "candidate" / "research-report-visuals"
    source_digest = tree_digest(ROOT)
    if snapshot.exists():
        if (
            not snapshot.is_dir()
            or snapshot_has_excluded_files(snapshot)
            or tree_digest(snapshot) != source_digest
        ):
            raise SystemExit(f"existing candidate snapshot differs: {snapshot}")
    else:
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(
            ROOT,
            snapshot,
            symlinks=True,
            ignore=snapshot_ignore,
        )
        if snapshot_has_excluded_files(snapshot) or tree_digest(snapshot) != source_digest:
            raise SystemExit(f"candidate snapshot copy differs: {snapshot}")
    freeze_snapshot(snapshot)
    return snapshot


def behavior_digest(skill_root: Path, suite: dict) -> str:
    evals = skill_root / "evals"
    paths = [evals / "behavior.json"]
    paths.extend(evals / case["input"] for case in suite["cases"])
    digest = hashlib.sha256()
    for path in sorted(paths, key=lambda item: str(item)):
        digest.update(path.relative_to(evals).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def append_jsonl(path: Path, event: dict) -> None:
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event, sort_keys=True) + "\n")


def append_raw(path: Path, raw: str) -> None:
    if not raw:
        return
    with path.open("a", encoding="utf-8") as stream:
        stream.write(raw)
        if not raw.endswith("\n"):
            stream.write("\n")


def decode_timeout_value(value: str | bytes | None) -> str:
    if value is None:
        return ""
    return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value


def pi_version(pi: str) -> str:
    result = subprocess.run(
        [pi, "--version"], text=True, capture_output=True, timeout=30
    )
    if result.returncode:
        raise SystemExit(f"{pi} --version failed: {result.stderr.strip()}")
    return result.stdout.strip()


def pi_command(pi: str, model: str, prompt: str, skill_root: Path) -> list[str]:
    return [
        pi,
        "-p",
        "--no-session",
        "--mode",
        "json",
        "--thinking",
        "low",
        "--tools",
        "read,write",
        "--no-skills",
        "--skill",
        str(skill_root),
        "--no-extensions",
        "--no-context-files",
        "--no-prompt-templates",
        "--model",
        model,
        prompt,
    ]


def model_evidence(raw: str, trace_path: Path) -> dict:
    stats = {
        "model_calls": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "tool_calls": 0,
        "parse_errors": 0,
        "response": "",
    }
    for line in raw.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            stats["parse_errors"] += 1
            continue
        if event.get("type") != "message_end":
            continue
        message = event.get("message", {})
        if message.get("role") != "assistant":
            continue
        stats["model_calls"] += 1
        usage = message.get("usage", {})
        stats["input_tokens"] += usage.get("input", 0)
        stats["output_tokens"] += usage.get("output", 0)
        response_parts = []
        for content in message.get("content", []):
            if content.get("type") == "text":
                response_parts.append(content.get("text", ""))
                continue
            if content.get("type") != "toolCall":
                continue
            stats["tool_calls"] += 1
            name = content.get("name")
            arguments = content.get("arguments") or {}
            if name == "read":
                normalized = {"type": "file_read", "path": arguments.get("path")}
            elif name == "write":
                normalized = {"type": "file_write", "path": arguments.get("path")}
            else:
                normalized = {
                    "type": "tool_call",
                    "tool": name,
                    "arguments": {
                        key: value
                        for key, value in arguments.items()
                        if key != "content"
                    },
                }
            append_jsonl(trace_path, normalized)
        if response_parts:
            stats["response"] = "\n".join(response_parts)
    return stats


def run_pi(
    *,
    pi: str,
    model: str,
    prompt: str,
    phase: str,
    trial_dir: Path,
    skill_root: Path,
    timeout: int,
    pi_events: Path,
    harness_events: Path,
    trace_path: Path,
) -> tuple[int, dict]:
    started = time.monotonic()
    append_jsonl(
        harness_events,
        {
            "type": "pi_start",
            "phase": phase,
            "tools": ["read", "write"],
            "no_session": True,
            "model": model,
            "skill": str(skill_root),
        },
    )
    try:
        result = subprocess.run(
            pi_command(pi, model, prompt, skill_root),
            cwd=trial_dir,
            text=True,
            capture_output=True,
            timeout=timeout,
        )
        stdout, stderr, exit_code = result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired as exc:
        stdout = decode_timeout_value(exc.stdout)
        stderr = decode_timeout_value(exc.stderr)
        exit_code = 124
    append_raw(pi_events, stdout)
    stats = model_evidence(stdout, trace_path)
    append_jsonl(
        harness_events,
        {
            "type": "pi_end",
            "phase": phase,
            "exit_code": exit_code,
            "wall_time_seconds": round(time.monotonic() - started, 3),
            "stderr": stderr,
            "raw_event_parse_errors": stats["parse_errors"],
        },
    )
    return exit_code, stats


def run_validator(
    validator: Path,
    source: Path,
    output: Path,
    phase: str,
    trial_dir: Path,
    harness_events: Path,
    trace_path: Path,
) -> tuple[int, list[str]]:
    result = subprocess.run(
        [sys.executable, str(validator), str(source), str(output)],
        cwd=trial_dir,
        text=True,
        capture_output=True,
    )
    failures = [
        line.strip() for line in result.stdout.splitlines() if line.startswith("FAIL ")
    ]
    append_jsonl(
        harness_events,
        {
            "type": "validator",
            "phase": phase,
            "arguments": {
                "source": str(source.relative_to(trial_dir)),
                "html": str(output.relative_to(trial_dir)),
                "fix": False,
            },
            "exit_code": result.returncode,
            "failures": failures,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "mutating": False,
        },
    )
    append_jsonl(
        trace_path,
        {
            "type": "tool_call",
            "tool": "validate_output",
            "arguments": {
                **{
                    "source": str(source.relative_to(trial_dir)),
                    "html": str(output.relative_to(trial_dir)),
                    "fix": False,
                },
            },
            "exit_code": result.returncode,
        },
    )
    return result.returncode, failures


def repair_prompt(case: dict, failures: list[str]) -> str:
    return (
        f"Read evals/{case['input']} and output.html. Fix every reported occurrence "
        "across the complete file, then overwrite output.html. Preserve all other "
        "content and styling exactly. Do not introduce an em dash or en dash. Keep "
        "all border-top and border-left declarations at 1px or less. Preserve every "
        "protected literal and source URL. For a long report, keep 500-900 primary "
        "visible words and at least two closed details blocks with 25 words each.\n"
        + "\n".join(failures)
    )


def append_repair_diff(path: Path, before: str, after: str, repair: int) -> None:
    diff = difflib.unified_diff(
        before.splitlines(keepends=True),
        after.splitlines(keepends=True),
        fromfile=f"output.before-repair-{repair}.html",
        tofile=f"output.after-repair-{repair}.html",
    )
    with path.open("a", encoding="utf-8") as stream:
        stream.writelines(diff)


def selected_cases(suite: dict, requested: list[str]) -> list[dict]:
    by_id = {case["id"]: case for case in suite["cases"]}
    unknown = sorted(set(requested) - set(by_id))
    if unknown:
        raise SystemExit(f"unknown behavior case(s): {', '.join(unknown)}")
    return [case for case in suite["cases"] if not requested or case["id"] in requested]


def selected_trials(suite: dict, requested: list[int]) -> list[int]:
    trials = requested or list(range(1, suite["trials"] + 1))
    invalid = [trial for trial in trials if not 1 <= trial <= suite["trials"]]
    if invalid:
        raise SystemExit(f"trial numbers must be 1-{suite['trials']}: {invalid}")
    return sorted(set(trials))


def manifest_for(
    run_id: str,
    model: str,
    harness: str,
    corpus_digest: str,
    skill_revision: str,
    skill_tree_revision: str,
    component_digests: dict,
    skill_path: Path,
) -> dict:
    created_at = datetime.strptime(run_id, "%Y%m%dT%H%M%SZ").replace(
        tzinfo=timezone.utc
    ).isoformat()
    return {
        "run_id": run_id,
        "created_at": created_at,
        "corpus_revision": {"behavior": corpus_digest},
        "model": model,
        "harness": harness,
        "permissions": PERMISSIONS,
        "catalog_revision": CATALOG_REVISION,
        "catalog_skills": {},
        "evidence_digests": {},
        "arms": ["candidate"],
        "arm_definitions": {
            "candidate": {
                "target_skill_access": "available",
                "skill_revision": skill_revision,
                "skill_tree_digest": skill_tree_revision,
                "component_digests": component_digests,
                "skill_path": str(skill_path),
            }
        },
    }


def write_manifest(run_dir: Path, manifest: dict) -> None:
    path = run_dir / "manifest.json"
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        expected = {**manifest, "evidence_digests": existing.get("evidence_digests", {})}
        if existing != expected:
            raise SystemExit(f"existing manifest differs: {path}")
        manifest.clear()
        manifest.update(existing)
        return
    run_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def record_evidence_digests(run_dir: Path, prefix: Path) -> None:
    manifest_path = run_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    evidence = manifest.setdefault("evidence_digests", {})
    prefix_text = prefix.as_posix().rstrip("/") + "/"
    for relative in [key for key in evidence if key.startswith(prefix_text)]:
        del evidence[relative]
    for path in sorted((run_dir / prefix).rglob("*"), key=lambda item: item.as_posix()):
        if path.is_file():
            evidence[path.relative_to(run_dir).as_posix()] = sha256_file(path)
    manifest["evidence_digests"] = dict(sorted(evidence.items()))
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def run_trial(
    *,
    run_dir: Path,
    case: dict,
    trial_number: int,
    pi: str,
    model: str,
    timeout: int,
    manifest: dict,
    skill_root: Path,
    validator: Path,
) -> int:
    trial_dir = (
        run_dir
        / "candidate"
        / "behavior"
        / case["id"]
        / f"trial-{trial_number:02d}"
    )
    if trial_dir.exists():
        raise SystemExit(f"refusing to overwrite existing trial: {trial_dir}")

    evals = skill_root / "evals"
    source = (evals / case["input"]).resolve()
    if not source.is_file() or not source.is_relative_to(evals.resolve()):
        raise SystemExit(f"fixture is outside evals or missing: {source}")
    staged_source = trial_dir / "evals" / case["input"]
    staged_source.parent.mkdir(parents=True)
    shutil.copyfile(source, staged_source)

    pi_events = trial_dir / "pi-events.jsonl"
    harness_events = trial_dir / "harness-events.jsonl"
    trace_path = trial_dir / "trace.jsonl"
    repair_diff = trial_dir / "repair.diff"
    response_path = trial_dir / "response.txt"
    for path in (pi_events, harness_events, trace_path, repair_diff, response_path):
        path.touch()
    append_jsonl(
        harness_events,
        {
            "type": "fixture_staged",
            "source": str(source),
            "path": str(staged_source.relative_to(trial_dir)),
            "sha256": sha256_file(staged_source),
        },
    )

    prompt = (
        case["prompt"]
        + "\nThe requested trial directory is the current working directory."
        + "\nThe evaluation harness will validate output.html without modifying it."
    )
    started = time.monotonic()
    exit_codes: list[int] = []
    totals = {
        "model_calls": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "tool_calls": 0,
        "parse_errors": 0,
        "response": "",
    }

    def invoke(phase: str, invocation_prompt: str) -> None:
        exit_code, stats = run_pi(
            pi=pi,
            model=model,
            prompt=invocation_prompt,
            phase=phase,
            trial_dir=trial_dir,
            skill_root=skill_root,
            timeout=timeout,
            pi_events=pi_events,
            harness_events=harness_events,
            trace_path=trace_path,
        )
        exit_codes.append(exit_code)
        for key in ("model_calls", "input_tokens", "output_tokens", "tool_calls"):
            totals[key] += stats[key]
        totals["parse_errors"] += stats["parse_errors"]
        if stats["response"]:
            totals["response"] = stats["response"]

    invoke("initial", prompt)
    output = trial_dir / "output.html"
    if not output.exists():
        output.touch()
    shutil.copyfile(output, trial_dir / "output.initial.html")

    validator_exit, failures = run_validator(
        validator,
        staged_source,
        output,
        "initial",
        trial_dir,
        harness_events,
        trace_path,
    )
    repairs = 0
    while validator_exit and failures and repairs < 3:
        repairs += 1
        before = output.read_text(encoding="utf-8")
        invoke(f"repair-{repairs}", repair_prompt(case, failures))
        after = output.read_text(encoding="utf-8")
        append_repair_diff(repair_diff, before, after, repairs)
        validator_exit, failures = run_validator(
            validator,
            staged_source,
            output,
            f"repair-{repairs}",
            trial_dir,
            harness_events,
            trace_path,
        )

    response_path.write_text(totals["response"], encoding="utf-8")
    provenance = {
        "run_id": manifest["run_id"],
        "arm": "candidate",
        "suite": "behavior",
        "case_id": case["id"],
        "trial": trial_number,
        "model": manifest["model"],
        "harness": manifest["harness"],
        "permissions": manifest["permissions"],
        "catalog_revision": manifest["catalog_revision"],
        "corpus_digest": manifest["corpus_revision"]["behavior"],
        "skill_revision": manifest["arm_definitions"]["candidate"]["skill_revision"],
        "skill_tree_digest": manifest["arm_definitions"]["candidate"][
            "skill_tree_digest"
        ],
        "component_digests": manifest["arm_definitions"]["candidate"][
            "component_digests"
        ],
    }
    final_exit = max(exit_codes + [validator_exit])
    meta = {
        "provenance": provenance,
        "wall_time_seconds": round(time.monotonic() - started, 3),
        "model_calls": totals["model_calls"],
        "input_tokens": totals["input_tokens"],
        "output_tokens": totals["output_tokens"],
        "tool_calls": totals["tool_calls"],
        "raw_event_parse_errors": totals["parse_errors"],
        "repair_passes": repairs,
        "validator_passed": validator_exit == 0,
        "validator_failures": failures,
        "pi_exit_codes": exit_codes,
        "exit_code": final_exit,
    }
    (trial_dir / "meta.json").write_text(
        json.dumps(meta, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"{case['id']} trial-{trial_number:02d}: "
        f"exit={final_exit} repairs={repairs} validator={'pass' if not validator_exit else 'fail'}",
        flush=True,
    )
    return final_exit


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True, help="immutable UTC run ID")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--pi", default="pi", help="Pi executable")
    parser.add_argument("--timeout", type=int, default=300, help="seconds per Pi call")
    parser.add_argument("--case", action="append", default=[], help="case ID to run")
    parser.add_argument(
        "--trial", action="append", default=[], type=int, help="trial number to run"
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not RUN_ID_RE.fullmatch(args.run_id):
        raise SystemExit("--run-id must use YYYYMMDDTHHMMSSZ")
    if args.timeout < 1:
        raise SystemExit("--timeout must be positive")

    run_dir = OUTPUTS / args.run_id
    skill_root = retain_candidate_snapshot(run_dir)
    evals = skill_root / "evals"
    validator = skill_root / "scripts" / "validate_output.py"
    suite = json.loads((evals / "behavior.json").read_text(encoding="utf-8"))
    cases = selected_cases(suite, args.case)
    trials = selected_trials(suite, args.trial)
    component_digests = {
        "evals/run.py": sha256_file(evals / "run.py"),
        "scripts/validate_output.py": sha256_file(validator),
        "evals/behavior_runner.py": sha256_file(evals / "behavior_runner.py"),
    }
    manifest = manifest_for(
        args.run_id,
        args.model,
        f"pi {pi_version(args.pi)} + behavior_runner.py",
        behavior_digest(skill_root, suite),
        sha256_file(skill_root / "SKILL.md"),
        tree_digest(skill_root),
        component_digests,
        skill_root,
    )
    write_manifest(run_dir, manifest)

    failures = 0
    for trial_number in trials:
        for case in cases:
            failures += bool(
                run_trial(
                    run_dir=run_dir,
                    case=case,
                    trial_number=trial_number,
                    pi=args.pi,
                    model=args.model,
                    timeout=args.timeout,
                    manifest=manifest,
                    skill_root=skill_root,
                    validator=validator,
                )
            )
    record_evidence_digests(run_dir, Path("candidate") / "behavior")
    print(run_dir)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
