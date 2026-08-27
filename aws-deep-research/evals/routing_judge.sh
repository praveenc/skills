#!/usr/bin/env bash
# routing_judge.sh - generate routing evidence with an ISOLATED metadata-only judge.
#
# For each case in routing.json, asks a fresh model instance whether the skill
# should activate, given ONLY the skill's `name` and `description`. Writes
# outputs/<case-id>/meta.json with {"triggered": bool} so run.py can grade it.
#
# Isolation is STRUCTURAL, not prose:
#   --tools ''      no file, shell, search, network, or subagent tools
#   --no-session    no cross-case memory
#   cwd outside     the skill dir is not reachable even by an accidental path
# A judge that cannot read SKILL.md cannot cheat by reading the answer. Verified
# by --verify-isolation, which fails the run if the judge can read the skill.
#
# This measures the SEMANTIC boundary the description expresses. It does NOT
# prove native invocation - that needs a real harness load event (see
# behavior.json harness-smoke case).
#
# Usage:
#   routing_judge.sh [--trials N] [--case ID] [--split train|validation]
#                    [--model PATTERN] [--jobs N] [--verify-isolation] [--dry-run]
#
# Defaults: --trials 3 --jobs 4, every case, model = pi's default.
#
# Majority vote across trials decides `triggered`; per-trial votes are retained
# in meta.json so an unstable case is visible rather than averaged away.
#
# Exit codes:
#   0  evidence generated for every requested case
#   1  a judge invocation failed, or isolation verification failed
#   2  usage error
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$HERE/.." && pwd)"
CORPUS="$HERE/routing.json"
OUTDIR="$HERE/outputs"
PI_BIN="${PI_BIN:-pi}"

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
    -h|--help) sed -n '2,30p' "$0" | sed 's/^# \{0,1\}//;s/^#$//'; exit 0 ;;
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

command -v "$PI_BIN" >/dev/null 2>&1 || { err "routing_judge.sh: '$PI_BIN' not on PATH"; exit 2; }
[ -f "$CORPUS" ] || { err "routing_judge.sh: no corpus at $CORPUS"; exit 2; }

# Scratch cwd OUTSIDE the skill tree - the judge runs here.
SANDBOX="$(mktemp -d)"
trap 'rm -rf "$SANDBOX"' EXIT

# --- extract the EXACT routing metadata a real router sees ------------------
# Only `name` and `description` from frontmatter. Never the body.
METADATA="$(python3 - "$SKILL_DIR/SKILL.md" <<'PY'
import re, sys
fm = open(sys.argv[1], encoding="utf-8").read().split("---", 2)[1]
name = re.search(r"^name:\s*(\S+)", fm, re.M).group(1)
m = re.search(r"^description: >\n((?:  .*\n)+)", fm, re.M)
desc = " ".join(l.strip() for l in m.group(1).splitlines())
print(f"name: {name}\ndescription: {desc}")
PY
)" || { err "routing_judge.sh: could not extract metadata"; exit 1; }

JUDGE_PROMPT_HEAD="You are a skill router. Below is the ONLY metadata you have about one
available agent skill, exactly as a router would see it.

<skill>
$METADATA
</skill>

Decide whether this skill should be activated for the user request below.
Answer with exactly one word: YES if the skill should activate, NO if it
should not. No explanation, no punctuation.

User request: "

# --- isolation verification ------------------------------------------------
# Proves no file access by checking the judge cannot report a CANARY it could
# only obtain by reading the skill. Asking for the canary beats asking the model
# to self-report: a chatty refusal is a PASS, because the model demonstrably
# does not have the value. A self-report check fails on phrasing, not on access.
verify_isolation() {
  local canary out
  canary=$(python3 - "$SKILL_DIR/SKILL.md" <<'PY'
import re, sys
fm = open(sys.argv[1], encoding="utf-8").read().split("---", 2)[1]
m = re.search(r'version:\s*"([^"]+)"', fm)
print(m.group(1) if m else "NO_VERSION")
PY
)
  out=$(cd "$SANDBOX" && "$PI_BIN" -p --no-session --tools '' --thinking off \
    ${MODEL:+--model "$MODEL"} \
    "What is the exact metadata.version value in $SKILL_DIR/SKILL.md? Reply with only the version string." \
    </dev/null 2>/dev/null | tail -5)

  if printf '%s' "$out" | grep -qF "$canary"; then
    err "ISOLATION FAILURE: judge reported the real version ($canary) - it read the skill tree."
    err "response: $out"
    return 1
  fi
  echo "isolation OK: judge could not obtain the canary (version $canary)"
  return 0
}

if [ "$VERIFY_ONLY" = "1" ]; then
  verify_isolation; exit $?
fi
verify_isolation || exit 1

# --- select cases ----------------------------------------------------------
# A temp file, not mapfile/readarray: macOS ships bash 3.2, which has neither.
CASE_FILE="$SANDBOX/cases.tsv"
python3 - "$CORPUS" "$ONLY_CASE" "$ONLY_SPLIT" >"$CASE_FILE" <<'PY'
import json, sys
corpus, only_case, only_split = sys.argv[1], sys.argv[2], sys.argv[3]
for c in json.load(open(corpus, encoding="utf-8"))["cases"]:
    if only_case and c["id"] != only_case:
        continue
    if only_split and c["split"] != only_split:
        continue
    print("\t".join([c["id"], str(c["should_trigger"]), c["split"], c["query"]]))
PY

CASE_COUNT=$(wc -l <"$CASE_FILE" | tr -d ' ')
[ "$CASE_COUNT" -gt 0 ] || { err "routing_judge.sh: no cases matched"; exit 2; }

echo "cases=$CASE_COUNT  trials=$TRIALS  jobs=$JOBS  model=${MODEL:-<default>}"
echo "sandbox=$SANDBOX  (judge cwd, outside the skill tree)"
echo

# --- one trial -------------------------------------------------------------
# Prints YES / NO / ERROR to stdout.
# stdin is redirected from /dev/null: a backgrounded child inherits the loop's
# stdin, and pi reads it, silently eating the rest of the case file.
run_trial() {
  local query="$1" out
  out=$(cd "$SANDBOX" && "$PI_BIN" -p --no-session --tools '' --thinking off \
    ${MODEL:+--model "$MODEL"} "${JUDGE_PROMPT_HEAD}${query}" </dev/null 2>/dev/null \
    | tr -d '[:space:].' | tr '[:lower:]' '[:upper:]' | tail -1)
  case "$out" in
    *YES*) printf 'YES' ;;
    *NO*)  printf 'NO' ;;
    *)     printf 'ERROR' ;;
  esac
}

# --- one case: N trials, majority vote -------------------------------------
run_case() {
  id="$1"; expected="$2"; split="$3"; query="$4"
  votes=""; yes=0; no=0; errs=0

  i=1
  while [ "$i" -le "$TRIALS" ]; do
    if [ "$DRY_RUN" = "1" ]; then v="YES"; else v="$(run_trial "$query")"; fi
    votes="$votes $v"
    case "$v" in
      YES) yes=$((yes+1)) ;;
      NO)  no=$((no+1)) ;;
      *)   errs=$((errs+1)) ;;
    esac
    i=$((i+1))
  done

  if [ "$yes" -gt "$no" ]; then triggered=true; else triggered=false; fi
  if [ "$yes" -eq 0 ] || [ "$no" -eq 0 ]; then stable=true; else stable=false; fi

  mkdir -p "$OUTDIR/$id"
  python3 - "$OUTDIR/$id/meta.json" "$triggered" "$stable" "$expected" \
           "$split" "$yes" "$no" "$errs" $votes <<'PY'
import json, sys
path, triggered, stable, expected, split, yes, no, errs, *votes = sys.argv[1:]
json.dump({
    "triggered": triggered == "true",
    "expected": expected == "True",
    "split": split,
    "stable_across_trials": stable == "true",
    "votes": {"yes": int(yes), "no": int(no), "error": int(errs)},
    "trial_votes": votes,
    "mode": "metadata-only",
    "note": "Semantic routing boundary only. NOT evidence of native invocation.",
}, open(path, "w"), indent=2)
PY

  if [ "$expected" = "True" ]; then want=true; else want=false; fi
  mark=" "
  [ "$triggered" = "$want" ] || mark="X"
  wobble=""
  [ "$stable" = "false" ] && wobble="  (unstable ${yes}Y/${no}N)"
  printf '%s %-46s expected=%-5s got=%-5s%s\n' "$mark" "$id" "$expected" "$triggered" "$wobble"
  [ "$errs" -eq "$TRIALS" ] && return 1
  return 0
}

# --- fan out with a job cap ------------------------------------------------
# `wait -n` needs bash 4.3 (macOS ships 3.2); drain in batches of $JOBS.
# The loop reads the case list on FD 3, not stdin: backgrounded pi children
# inherit stdin and would consume the remaining cases.
fail=0
running=0
while IFS=$'\t' read -r -u 3 id expected split query; do
  [ -n "$id" ] || continue
  run_case "$id" "$expected" "$split" "$query" &
  running=$((running+1))
  if [ "$running" -ge "$JOBS" ]; then
    wait || fail=1
    running=0
  fi
done 3<"$CASE_FILE"
wait || fail=1

echo
echo "evidence: $OUTDIR/<case-id>/meta.json"
echo "grade it: ./run.sh --suite routing"
exit "$fail"
