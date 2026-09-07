#!/usr/bin/env bash
# Generate metadata-only routing evidence with an isolated judge.
#
# The judge sees only the tested skill's name and description. It has no tools,
# no session history, and a scratch working directory outside the skill tree.
#
# Usage:
#   ./routing_judge.sh --skill-dir PATH --arm released|candidate [options]
#   ./routing_judge.sh --verify-isolation --skill-dir PATH
#
# Options:
#   --run-id ID
#   --trials N
#   --jobs N
#   --case ID
#   --split train|validation
#   --model MODEL
#   --dry-run
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CORPUS="$HERE/routing.json"
OUTROOT="$HERE/outputs"
PI_BIN="${PI_BIN:-pi}"

SKILL_DIR="$(cd "$HERE/.." && pwd)"
ARM="candidate"
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)"
TRIALS=3
JOBS=4
ONLY_CASE=""
ONLY_SPLIT=""
MODEL=""
DRY_RUN=0
VERIFY_ONLY=0

err() { printf '%s\n' "$*" >&2; }

while [ $# -gt 0 ]; do
  case "$1" in
    -h|--help) sed -n '2,22p' "$0" | sed 's/^# \{0,1\}//;s/^#$//'; exit 0 ;;
    --skill-dir) SKILL_DIR="${2:?}"; shift 2 ;;
    --arm) ARM="${2:?}"; shift 2 ;;
    --run-id) RUN_ID="${2:?}"; shift 2 ;;
    --trials) TRIALS="${2:?}"; shift 2 ;;
    --jobs) JOBS="${2:?}"; shift 2 ;;
    --case) ONLY_CASE="${2:?}"; shift 2 ;;
    --split) ONLY_SPLIT="${2:?}"; shift 2 ;;
    --model) MODEL="${2:?}"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    --verify-isolation) VERIFY_ONLY=1; shift ;;
    *) err "routing_judge.sh: unknown argument: $1"; exit 2 ;;
  esac
done

case "$ARM" in
  released|candidate) ;;
  *) err "routing_judge.sh: --arm must be released or candidate"; exit 2 ;;
esac
[ -f "$SKILL_DIR/SKILL.md" ] || { err "routing_judge.sh: no SKILL.md under $SKILL_DIR"; exit 2; }
[ -f "$CORPUS" ] || { err "routing_judge.sh: no routing.json at $CORPUS"; exit 2; }
if [ "$DRY_RUN" != "1" ]; then
  command -v "$PI_BIN" >/dev/null 2>&1 || {
    err "routing_judge.sh: '$PI_BIN' is not on PATH"
    exit 2
  }
  [ -n "$MODEL" ] || {
    err "routing_judge.sh: --model is required for reproducible evidence"
    exit 2
  }
  PI_VERSION="$("$PI_BIN" --version 2>/dev/null | tr -d '\r' | head -1)"
  [ -n "$PI_VERSION" ] || PI_VERSION="pi (version unavailable)"
else
  [ -n "$MODEL" ] || MODEL="<dry-run>"
  PI_VERSION="pi dry-run"
fi

SANDBOX="$(mktemp -d)"
trap 'rm -rf "$SANDBOX"' EXIT
RUN_DIR="$OUTROOT/$RUN_ID"

METADATA="$(python3 - "$SKILL_DIR/SKILL.md" <<'PY'
import sys

text = open(sys.argv[1], encoding="utf-8").read()
parts = text.split("---", 2)
if len(parts) < 3:
    raise SystemExit("SKILL.md has no YAML frontmatter")
lines = parts[1].splitlines()
name = ""
description = ""
for index, line in enumerate(lines):
    if line.startswith("name:"):
        name = line.split(":", 1)[1].strip().strip("\"'")
    if line.startswith("description:"):
        value = line.split(":", 1)[1].strip()
        if value in {">", "|"}:
            collected = []
            for following in lines[index + 1:]:
                if not following.startswith((" ", "\t")):
                    break
                collected.append(following.strip())
            description = " ".join(collected)
        else:
            description = value.strip("\"'")
if not name or not description:
    raise SystemExit("could not extract name and description")
print(f"name: {name}\ndescription: {description}")
PY
)" || { err "routing_judge.sh: metadata extraction failed"; exit 1; }

mkdir -p "$RUN_DIR"
python3 - "$RUN_DIR/manifest.json" "$RUN_ID" "$SKILL_DIR" "$ARM" \
  "$MODEL" "$PI_VERSION" "$CORPUS" <<'PY'
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

path, run_id, skill_dir, arm, model, harness, corpus = sys.argv[1:]
path = Path(path)
skill_file = Path(skill_dir) / "SKILL.md"

def digest(file):
    return hashlib.sha256(Path(file).read_bytes()).hexdigest()

if path.exists():
    manifest = json.loads(path.read_text(encoding="utf-8"))
    expected = {
        "run_id": run_id,
        "model": model,
        "harness": harness,
        "permissions": "no tools, skills, extensions, context files, prompt templates, or session; scratch cwd",
        "catalog_revision": "skills disabled; target metadata supplied inline",
    }
    mismatches = [
        f"{key}: existing={manifest.get(key)!r}, requested={value!r}"
        for key, value in expected.items()
        if manifest.get(key) != value
    ]
    if mismatches:
        raise SystemExit("manifest mismatch; use a new run ID:\n" + "\n".join(mismatches))
    recorded = manifest.get("corpus_revision", {}).get("routing")
    if recorded != digest(corpus):
        raise SystemExit("manifest routing corpus digest does not match routing.json")
else:
    manifest = {
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "corpus_revision": {"routing": digest(corpus)},
        "model": model,
        "harness": harness,
        "permissions": "no tools, skills, extensions, context files, prompt templates, or session; scratch cwd",
        "catalog_revision": "skills disabled; target metadata supplied inline",
        "catalog_skills": {},
        "arms": [],
        "arm_definitions": {},
    }
if arm not in manifest["arms"]:
    manifest["arms"].append(arm)
manifest["arm_definitions"][arm] = {
    "target_skill_access": "available",
    "skill_revision": digest(skill_file),
    "skill_path": str(Path(skill_dir).resolve()),
}
path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
PY
manifest_status=$?
if [ "$manifest_status" -ne 0 ]; then
  err "routing_judge.sh: manifest creation or validation failed"
  exit 1
fi

JUDGE_PROMPT_HEAD="You are a skill router. Below is the only metadata available
for one agent skill.

<skill>
$METADATA
</skill>

Decide whether this skill should activate for the user request below.
Answer with exactly one word: YES or NO.

User request: "

invoke_judge() {
  prompt="$1"
  if [ -n "$MODEL" ]; then
    (
      cd "$SANDBOX" &&
      "$PI_BIN" -p --no-session --no-tools --no-skills --no-extensions \
        --no-context-files --no-prompt-templates --thinking off --model "$MODEL" \
        "$prompt" </dev/null 2>/dev/null
    )
  else
    (
      cd "$SANDBOX" &&
      "$PI_BIN" -p --no-session --no-tools --no-skills --no-extensions \
        --no-context-files --no-prompt-templates --thinking off \
        "$prompt" </dev/null 2>/dev/null
    )
  fi
}

verify_isolation() {
  canary="$(python3 - "$SKILL_DIR/SKILL.md" <<'PY'
import re
import sys
text = open(sys.argv[1], encoding="utf-8").read()
match = re.search(r"^\s*version:\s*(.+)$", text, re.MULTILINE)
print(match.group(1).strip().strip("\"'") if match else "NO_VERSION")
PY
)"
  if ! out="$(invoke_judge "What is the exact metadata.version value in $SKILL_DIR/SKILL.md? Reply with only the version string.")"; then
    err "ISOLATION FAILURE: judge command failed"
    return 1
  fi
  [ -n "$(printf '%s' "$out" | tr -d '[:space:]')" ] || {
    err "ISOLATION FAILURE: judge returned no output"
    return 1
  }
  if printf '%s' "$out" | grep -qF "$canary"; then
    err "ISOLATION FAILURE: judge reported the real version ($canary)"
    err "response: $out"
    return 1
  fi
  echo "isolation OK: judge could not obtain the SKILL.md version canary"
}

if [ "$VERIFY_ONLY" = "1" ]; then
  [ "$DRY_RUN" = "1" ] && { echo "dry-run: isolation check skipped"; exit 0; }
  verify_isolation
  exit $?
fi
if [ "$DRY_RUN" != "1" ]; then
  verify_isolation || exit 1
fi

CASE_FILE="$SANDBOX/cases.tsv"
python3 - "$CORPUS" "$ONLY_CASE" "$ONLY_SPLIT" >"$CASE_FILE" <<'PY'
import json
import sys

corpus, only_case, only_split = sys.argv[1:]
for case in json.load(open(corpus, encoding="utf-8"))["cases"]:
    if only_case and case["id"] != only_case:
        continue
    if only_split and case["split"] != only_split:
        continue
    print("\t".join([case["id"], case["split"], case["query"]]))
PY

CASE_COUNT="$(wc -l <"$CASE_FILE" | tr -d ' ')"
[ "$CASE_COUNT" -gt 0 ] || { err "routing_judge.sh: no cases matched"; exit 2; }

echo "run=$RUN_ID arm=$ARM cases=$CASE_COUNT trials=$TRIALS jobs=$JOBS"
echo "skill=$SKILL_DIR"

run_trial() {
  query="$1"
  if [ "$DRY_RUN" = "1" ]; then
    printf 'YES'
    return
  fi
  if ! raw="$(invoke_judge "${JUDGE_PROMPT_HEAD}${query}")"; then
    printf 'ERROR'
    return
  fi
  out="$(printf '%s' "$raw" | tr -d '[:space:]' | tr '[:lower:]' '[:upper:]')"
  case "$out" in
    YES) printf 'YES' ;;
    NO) printf 'NO' ;;
    *) printf 'ERROR' ;;
  esac
}

run_case() {
  id="$1"
  split="$2"
  query="$3"
  trial=1
  case_failed=0
  while [ "$trial" -le "$TRIALS" ]; do
    vote="$(run_trial "$query")"
    trial_dir="$RUN_DIR/$ARM/routing/$id/$(printf 'trial-%02d' "$trial")"
    mkdir -p "$trial_dir"
    python3 - "$trial_dir/meta.json" "$vote" "$split" \
      "$RUN_DIR/manifest.json" "$ARM" "$id" "$trial" <<'PY'
import json
import sys

path, vote, split, manifest_path, arm, case_id, trial = sys.argv[1:]
manifest = json.load(open(manifest_path, encoding="utf-8"))
payload = {
    "mode": "metadata-only",
    "split": split,
    "raw_vote": vote,
    "provenance": {
        "run_id": manifest["run_id"],
        "arm": arm,
        "suite": "routing",
        "case_id": case_id,
        "trial": int(trial),
        "model": manifest["model"],
        "harness": manifest["harness"],
        "permissions": manifest["permissions"],
        "catalog_revision": manifest["catalog_revision"],
        "corpus_digest": manifest["corpus_revision"]["routing"],
        "skill_revision": manifest["arm_definitions"][arm]["skill_revision"],
    },
}
if vote == "YES":
    payload["triggered"] = True
elif vote == "NO":
    payload["triggered"] = False
else:
    payload["error"] = "judge returned no parseable vote"
json.dump(payload, open(path, "w"), indent=2)
PY
    printf '%-44s trial=%02d vote=%s\n' "$id" "$trial" "$vote"
    [ "$vote" = "ERROR" ] && case_failed=1
    trial=$((trial + 1))
  done
  return "$case_failed"
}

fail=0
running=0
while IFS=$'\t' read -r -u 3 id split query; do
  [ -n "$id" ] || continue
  run_case "$id" "$split" "$query" &
  running=$((running + 1))
  if [ "$running" -ge "$JOBS" ]; then
    wait || fail=1
    running=0
  fi
done 3<"$CASE_FILE"
wait || fail=1

echo "evidence: $RUN_DIR/$ARM/routing"
echo "grade: ./run.sh --run $RUN_DIR --suite routing --arm $ARM"
exit "$fail"
