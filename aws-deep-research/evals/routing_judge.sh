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
# Two modes:
#   default (metadata-only)  the judge sees ONLY this skill's name+description
#                            and answers YES/NO. Measures the boundary in
#                            isolation.
#   --catalog <skills-dir>   the judge sees the name+description of EVERY skill
#                            in <skills-dir> (plus this one) and must CHOOSE one.
#                            `triggered` = it chose aws-deep-research. This is
#                            the realistic router setting: a description that
#                            wins alone can still lose to a sibling like
#                            amazon-bedrock or aws-billing on a contested query.
#
# Usage:
#   routing_judge.sh [--trials N] [--case ID] [--split train|validation]
#                    [--model PATTERN] [--jobs N] [--catalog DIR]
#                    [--verify-isolation] [--dry-run]
#
# Defaults: --trials 3 --jobs 4, every case, model = pi's default.
#
# Majority vote across trials decides `triggered`; per-trial votes are retained
# in meta.json so an unstable case is visible rather than averaged away.
# The vote parse is first-token exact ("No, but ... Yes" is a NO, not a YES).
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
CATALOG=""
MODE_LABEL="metadata-only"

err() { printf '%s\n' "$*" >&2; }

while [ $# -gt 0 ]; do
  case "$1" in
    -h|--help) sed -n '2,45p' "$0" | sed 's/^# \{0,1\}//;s/^#$//'; exit 0 ;;
    --trials) TRIALS="${2:?}"; shift 2 ;;
    --jobs) JOBS="${2:?}"; shift 2 ;;
    --case) ONLY_CASE="${2:?}"; shift 2 ;;
    --split) ONLY_SPLIT="${2:?}"; shift 2 ;;
    --model) MODEL="${2:?}"; shift 2 ;;
    --catalog) CATALOG="${2:?}"; MODE_LABEL="catalog"; shift 2 ;;
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

# --- catalog mode: present EVERY skill, grade which one the judge picks ------
CATALOG_PROMPT_HEAD=""
if [ -n "$CATALOG" ]; then
  [ -d "$CATALOG" ] || { err "routing_judge.sh: catalog dir not found: $CATALOG"; exit 2; }
  CATALOG_LIST="$(python3 - "$CATALOG" "$SKILL_DIR" <<'PY'
import re, sys, pathlib
catalog_dir, skill_dir = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])

def extract(md):
    try:
        parts = md.read_text(encoding="utf-8").split("---", 2)
    except OSError:
        return None
    if len(parts) < 3:
        return None
    fm = parts[1]
    nm = re.search(r"^name:\s*(\S+)", fm, re.M)
    # description as a `>` folded block, or a single-line scalar
    block = re.search(r"^description:\s*>\s*\n((?:[ \t].*\n?)+)", fm, re.M)
    line = re.search(r"^description:\s*(\S.*)$", fm, re.M)
    if not nm or not (block or line):
        return None
    desc = (" ".join(l.strip() for l in block.group(1).splitlines())
            if block else line.group(1).strip())
    return nm.group(1), re.sub(r"\s+", " ", desc).strip()

seen = {}
for md in sorted(catalog_dir.glob("*/SKILL.md")):
    r = extract(md)
    if r:
        seen[r[0]] = r[1]
# the skill under test must be in the catalog even if CATALOG omits it
r = extract(skill_dir / "SKILL.md")
if r:
    seen.setdefault(r[0], r[1])
for name in sorted(seen):
    print(f"- {name}: {seen[name]}")
PY
)" || { err "routing_judge.sh: could not build catalog from $CATALOG"; exit 1; }

  case "$CATALOG_LIST" in
    *aws-deep-research*) : ;;
    *) err "routing_judge.sh: catalog has no readable aws-deep-research SKILL.md"; exit 1 ;;
  esac

  CATALOG_PROMPT_HEAD="You are a skill router. Below is the full catalog of available agent
skills, each with the name and description a router sees.

<skills>
$CATALOG_LIST
</skills>

Choose the ONE skill that should handle the user request below. Answer with
exactly that skill's name and nothing else. If no skill fits, answer NONE.

User request: \""
fi

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

echo "mode=$MODE_LABEL  cases=$CASE_COUNT  trials=$TRIALS  jobs=$JOBS  model=${MODEL:-<default>}"
echo "sandbox=$SANDBOX  (judge cwd, outside the skill tree)"
echo

# --- one trial -------------------------------------------------------------
# Prints YES / NO / ERROR to stdout.
# stdin is redirected from /dev/null: a backgrounded child inherits the loop's
# stdin, and pi reads it, silently eating the rest of the case file.
#
# Vote parse is FIRST-TOKEN EXACT: the first standalone YES/NO word wins, so a
# hedged "No, but ... Yes" scores NO (its leading answer). The old substring
# scan collapsed whitespace and matched *YES* anywhere, flipping that to YES.
run_trial() {
  local query="$1" out first
  out=$(cd "$SANDBOX" && "$PI_BIN" -p --no-session --tools '' --thinking off \
    ${MODEL:+--model "$MODEL"} "${JUDGE_PROMPT_HEAD}${query}" </dev/null 2>/dev/null \
    | tr '[:lower:]' '[:upper:]')
  first=$(printf '%s\n' "$out" | grep -oE '\b(YES|NO)\b' | head -1)
  case "$first" in
    YES) printf 'YES' ;;
    NO)  printf 'NO' ;;
    *)   printf 'ERROR' ;;
  esac
}

# Catalog trial: the judge names a skill (or NONE). Reuse the YES/NO pipeline -
# YES = it chose aws-deep-research; NO = it chose another skill or NONE.
#
# Parse only the LAST non-empty line (the answer; the prompt asks for the name
# and nothing else), not the whole response - the same first-token rigor as the
# YES/NO parser above. Prefer a standalone aws-deep-research token so hedging
# prose ("the user-request is best suited to...") on the answer line cannot be
# misread as the chosen skill via its stray hyphen.
run_trial_catalog() {
  local query="$1" out last chosen
  out=$(cd "$SANDBOX" && "$PI_BIN" -p --no-session --tools '' --thinking off \
    ${MODEL:+--model "$MODEL"} "${CATALOG_PROMPT_HEAD}${query}" </dev/null 2>/dev/null \
    | tr '[:upper:]' '[:lower:]')
  last=$(printf '%s\n' "$out" | grep -vE '^[[:space:]]*$' | tail -1)
  if printf '%s' "$last" | grep -qE '(^|[^a-z0-9-])aws-deep-research([^a-z0-9-]|$)'; then
    printf 'YES'; return
  fi
  chosen=$(printf '%s' "$last" | grep -oE 'none|[a-z0-9]+(-[a-z0-9]+)+' | head -1)
  case "$chosen" in
    "") printf 'ERROR' ;;
    *)  printf 'NO' ;;
  esac
}

# Dispatch to the active mode.
emit_vote() {
  if [ -n "$CATALOG" ]; then run_trial_catalog "$1"; else run_trial "$1"; fi
}

# --- one case: N trials, majority vote -------------------------------------
run_case() {
  id="$1"; expected="$2"; split="$3"; query="$4"
  votes=""; yes=0; no=0; errs=0

  i=1
  while [ "$i" -le "$TRIALS" ]; do
    if [ "$DRY_RUN" = "1" ]; then v="YES"; else v="$(emit_vote "$query")"; fi
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
  MODE_LABEL="$MODE_LABEL" python3 - "$OUTDIR/$id/meta.json" "$triggered" "$stable" "$expected" \
           "$split" "$yes" "$no" "$errs" $votes <<'PY'
import json, os, sys
path, triggered, stable, expected, split, yes, no, errs, *votes = sys.argv[1:]
mode = os.environ.get("MODE_LABEL", "metadata-only")
note = ("Router chose among ALL catalog skills; triggered = it chose aws-deep-research."
        if mode == "catalog" else
        "Semantic routing boundary only. NOT evidence of native invocation.")
json.dump({
    "triggered": triggered == "true",
    "expected": expected == "True",
    "split": split,
    "stable_across_trials": stable == "true",
    "votes": {"yes": int(yes), "no": int(no), "error": int(errs)},
    "trial_votes": votes,
    "mode": mode,
    "note": note,
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
# `wait -n` needs bash 4.3 (macOS ships 3.2); drain a batch of $JOBS by waiting
# each PID individually. A bare `wait` returns only the LAST job's status, so a
# failing case among passing ones is masked - collect PIDs and OR their codes.
# The loop reads the case list on FD 3, not stdin: backgrounded pi children
# inherit stdin and would consume the remaining cases.
fail=0
pids=""
running=0
drain() {
  for p in $pids; do wait "$p" || fail=1; done
  pids=""
  running=0
}
while IFS=$'\t' read -r -u 3 id expected split query; do
  [ -n "$id" ] || continue
  run_case "$id" "$expected" "$split" "$query" &
  pids="$pids $!"
  running=$((running+1))
  [ "$running" -ge "$JOBS" ] && drain
done 3<"$CASE_FILE"
drain

echo
echo "evidence: $OUTDIR/<case-id>/meta.json"
echo "grade it: ./run.sh --suite routing"
exit "$fail"
