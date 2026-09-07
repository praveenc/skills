#!/usr/bin/env python3
"""Require complete routing, native, behavior, and judge evidence for release."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path


HERE = Path(__file__).resolve().parent
RUNNER = HERE / "run.py"
SUITES = {
    "routing": {"released", "candidate"},
    "native": {"no-skill", "released", "candidate"},
    "behavior": {"no-skill", "released", "candidate"},
}


def load_manifest(run_dir: Path) -> dict:
    return json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))


def grade(suite: str, run_dir: Path) -> dict:
    with tempfile.TemporaryDirectory() as directory:
        result_path = Path(directory) / "result.json"
        command = [
            sys.executable,
            str(RUNNER),
            "--run",
            str(run_dir),
            "--suite",
            suite,
            "--json",
            str(result_path),
        ]
        for arm in sorted(SUITES[suite]):
            command.extend(["--arm", arm])
        completed = subprocess.run(command)
        if completed.returncode:
            raise SystemExit(f"{suite} evaluation failed")
        return json.loads(result_path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for suite in SUITES:
        parser.add_argument(f"--{suite}-run", required=True, type=Path)
    args = parser.parse_args()
    runs = {suite: getattr(args, f"{suite}_run") for suite in SUITES}

    manifests = {suite: load_manifest(run_dir) for suite, run_dir in runs.items()}
    for suite, required in SUITES.items():
        missing = required - set(manifests[suite].get("arms", []))
        if missing:
            raise SystemExit(f"{suite} run is missing arms: {sorted(missing)}")

    candidate_trees = {
        manifest["arm_definitions"]["candidate"]["skill_tree_digest"]
        for manifest in manifests.values()
    }
    released_trees = {
        manifest["arm_definitions"]["released"]["skill_tree_digest"]
        for manifest in manifests.values()
    }
    if len(candidate_trees) != 1 or len(released_trees) != 1:
        raise SystemExit("suite runs do not use identical candidate and released trees")

    results = {suite: grade(suite, runs[suite]) for suite in SUITES}
    behavior_cases = {
        case["id"]
        for case in json.loads((HERE / "behavior.json").read_text(encoding="utf-8"))[
            "cases"
        ]
    }
    judges = results["behavior"]["judges"]
    reviewed = {
        result["case_id"]
        for result in judges["results"]
        if result["valid"]
    }
    if judges["invalid"] or reviewed != behavior_cases:
        missing = sorted(behavior_cases - reviewed)
        raise SystemExit(
            f"behavior judges are incomplete or invalid; missing={missing}, "
            f"invalid={judges['invalid']}"
        )

    print("RELEASE PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
