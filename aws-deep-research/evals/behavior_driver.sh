#!/usr/bin/env bash
# behavior_driver.sh - produce behavior-eval evidence by actually RUNNING a case.
#
# run.py grades evidence; it does not create it. This is the missing executor:
# it drives one behavior.json case end-to-end, isolates every artifact into a
# scratch tree, and leaves outputs/<case-id>/{trace.txt,report.md,meta.json} for
# `./run.py --suite behavior` to grade.
#
# Isolation (per behavior.json): a fresh work dir and a scratch config per run,
# wired through the skill's documented env surface (AWS_DEEP_RESEARCH_CONFIG,
# RESEARCH_WORK_DIR, REPORT_OUTPUT_DIR) - never by editing the skill tree. The
# case is FORCED-LOADED: SKILL.md is appended as the system prompt so discovery
# is bypassed and only behavior is measured (trigger quality is routing.json).
#
# Harnesses:
#   pi (default)   spawn `pi -p --append-system-prompt @SKILL.md "<prompt>"`,
#                  tee the transcript, copy the report, run the extractor.
#   claude-code    Claude Code is driven in-session via its native Agent tool,
#                  not as a subprocess this script can spawn. Run with
#                  --harness claude-code to print that procedure; then re-run
#                  with --session/--work-dir to assemble evidence from the
#                  transcript + work dir the Agent-tool run produced.
#
# Usage:
#   behavior_driver.sh <case-id> [--harness pi|claude-code] [--model M] [--keep]
#   behavior_driver.sh --all [--harness pi] [--model M] [--keep]
#   behavior_driver.sh <case-id> --harness claude-code \
#       --session <transcript.jsonl> --work-dir <slug-dir> [--report <report.md>]
#
# Env: PI_BIN (default pi). API keys are inherited from your real config
#      ($AWS_DEEP_RESEARCH_CONFIG or ~/.config/aws-deep-research/config.env) so
#      a live run can actually search; only the work/report dirs are redirected.
#
# Exit codes:
#   0  evidence written for every requested case
#   1  a run failed, produced no report, or the extractor failed
#   2  usage error
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$HERE/.." && pwd)"
CORPUS="$HERE/behavior.json"
OUTDIR="$HERE/outputs"
EXTRACT="$HERE/extract_behavior_meta.py"
PI_BIN="${PI_BIN:-pi}"
REAL_CONFIG="${AWS_DEEP_RESEARCH_CONFIG:-$HOME/.config/aws-deep-research/config.env}"

HARNESS="pi"
MODEL=""
KEEP=0
ALL=0
CASE_ID=""
SESSION=""
WORK_DIR_IN=""
REPORT_IN=""

err() { printf '%s\n' "$*" >&2; }

while [ $# -gt 0 ]; do
  case "$1" in
    -h|--help) sed -n '2,40p' "$0" | sed 's/^# \{0,1\}//;s/^#$//'; exit 0 ;;
    --all) ALL=1; shift ;;
    --harness) HARNESS="${2:?}"; shift 2 ;;
    --model) MODEL="${2:?}"; shift 2 ;;
    --keep) KEEP=1; shift ;;
    --session) SESSION="${2:?}"; shift 2 ;;
    --work-dir) WORK_DIR_IN="${2:?}"; shift 2 ;;
    --report) REPORT_IN="${2:?}"; shift 2 ;;
    -*) err "behavior_driver.sh: unknown flag: $1"; exit 2 ;;
    *) CASE_ID="$1"; shift ;;
  esac
done

[ -f "$CORPUS" ] || { err "behavior_driver.sh: no corpus at $CORPUS"; exit 2; }
[ "$ALL" = "1" ] || [ -n "$CASE_ID" ] || { err "behavior_driver.sh: give a case id or --all"; exit 2; }

# --- corpus lookup ---------------------------------------------------------
case_prompt() {  # id -> prompt (empty if not found)
  python3 - "$CORPUS" "$1" <<'PY'
import json, sys
corpus, cid = sys.argv[1], sys.argv[2]
for c in json.load(open(corpus, encoding="utf-8"))["cases"]:
    if c["id"] == cid:
        print(c.get("prompt", "")); break
PY
}

all_ids() { python3 -c 'import json,sys; [print(c["id"]) for c in json.load(open(sys.argv[1]))["cases"]]' "$CORPUS"; }

# --- assemble evidence from a completed run --------------------------------
# Copies the report and runs the extractor. Shared by every harness: once a run
# has produced a session transcript and a work dir, evidence assembly is
# identical.
assemble() {  # <case-id> <session-jsonl> <work-slug-dir> [<report.md>]
  local id="$1" session="$2" work="$3" report="${4:-}"
  local ev="$OUTDIR/$id"
  mkdir -p "$ev/artifacts"

  # Durable copy of the findings: the scratch work dir is ephemeral, but run.py
  # sources retrieved_urls and artifact checks from it at grade time.
  if [ -d "$work" ]; then
    cp -R "$work"/. "$ev/artifacts/" 2>/dev/null || true
  fi

  # Locate the report if not named explicitly: <slug>-report.md in the work dir.
  if [ -z "$report" ] && [ -d "$work" ]; then
    report="$(find "$work" -maxdepth 1 -name '*-report.md' ! -name '*.eval.md' 2>/dev/null | head -1)"
  fi
  if [ -n "$report" ] && [ -f "$report" ]; then
    cp "$report" "$ev/report.md"
  else
    err "  ! no <slug>-report.md found for $id (report checks will PEND/FAIL)"
  fi

  if [ ! -f "$session" ]; then
    err "  ! no session transcript at $session - cannot extract meta.json"
    return 1
  fi
  python3 "$EXTRACT" "$session" --work-dir "$ev/artifacts" --slug "$id" \
    -o "$ev/meta.json" || return 1
  echo "  evidence: $ev/{trace.txt,report.md,meta.json}"
}

# --- pi harness ------------------------------------------------------------
run_pi() {  # <case-id>
  local id="$1" prompt
  prompt="$(case_prompt "$id")"
  [ -n "$prompt" ] || { err "no such behavior case: $id"; return 2; }
  command -v "$PI_BIN" >/dev/null 2>&1 || { err "'$PI_BIN' not on PATH"; return 2; }

  local scratch work out cfg ev
  scratch="$(mktemp -d)"
  work="$scratch/work"; out="$scratch/out"; cfg="$scratch/config.env"
  mkdir -p "$work" "$out"
  ev="$OUTDIR/$id"; mkdir -p "$ev"

  {
    echo "RESEARCH_WORK_DIR=$work"
    echo "REPORT_OUTPUT_DIR=$out"
    # inherit real API keys so the run can actually search; keep only key lines
    if [ -f "$REAL_CONFIG" ]; then
      grep -E '^(BRAVE_SEARCH_API_KEY|TAVILY_API_KEY|GITHUB_TOKEN|KROKI_)' "$REAL_CONFIG" 2>/dev/null || true
    fi
  } >"$cfg"

  # Forced load: SKILL.md as system prompt, and tell the agent where the skill
  # lives (a forced-loaded agent cannot self-locate SKILL_DIR via BASH_SOURCE).
  local task="Your SKILL_DIR is $SKILL_DIR (use it directly; do not re-derive it).
This is a forced-load behavior run. Follow SKILL.md exactly for this request:

$prompt"

  echo ">> [$id] pi forced-load  work=$work"
  (
    cd "$scratch" &&
    AWS_DEEP_RESEARCH_CONFIG="$cfg" RESEARCH_WORK_DIR="$work" REPORT_OUTPUT_DIR="$out" \
      "$PI_BIN" -p ${MODEL:+--model "$MODEL"} \
      --append-system-prompt "$(cat "$SKILL_DIR/SKILL.md")" \
      "$task"
  ) </dev/null 2>&1 | tee "$ev/trace.txt"

  # newest slug dir the run created under $work
  local slug_dir session
  slug_dir="$(find "$work" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | head -1)"
  session="$(ls -t "$HOME/.pi/agent/sessions/"*"$(echo "$scratch" | tr '/' '-')"*/*.jsonl 2>/dev/null | head -1)"
  [ -n "$session" ] || session="$(find "$HOME/.pi/agent/sessions" -name '*.jsonl' -newer "$cfg" 2>/dev/null | head -1)"

  local rc=0
  assemble "$id" "$session" "$slug_dir" || rc=1

  [ "$KEEP" = "1" ] && echo "  kept scratch: $scratch" || rm -rf "$scratch"
  return $rc
}

# --- claude-code harness ---------------------------------------------------
run_claude_code() {  # <case-id>
  local id="$1" prompt
  prompt="$(case_prompt "$id")"
  [ -n "$prompt" ] || { err "no such behavior case: $id"; return 2; }

  # Evidence-assembly path: the Agent-tool run already happened.
  if [ -n "$SESSION" ] || [ -n "$WORK_DIR_IN" ]; then
    [ -n "$SESSION" ] && [ -n "$WORK_DIR_IN" ] || {
      err "claude-code assembly needs BOTH --session and --work-dir"; return 2; }
    mkdir -p "$OUTDIR/$id"
    [ -f "$SESSION" ] && cp "$SESSION" "$OUTDIR/$id/trace.txt" 2>/dev/null || true
    assemble "$id" "$SESSION" "$WORK_DIR_IN" "$REPORT_IN"
    return $?
  fi

  # Otherwise: print the procedure. Claude Code runs the skill natively via its
  # Agent tool in the current session - it is not a headless binary this script
  # spawns.
  cat <<EOF
[$id] Claude Code procedure (run these IN a Claude Code session):

  1. Set an isolated scratch and force-load the skill:
       export RESEARCH_WORK_DIR=\$(mktemp -d)/work
       export REPORT_OUTPUT_DIR=\$(mktemp -d)/out
     Load $SKILL_DIR/SKILL.md and follow it for the prompt below, dispatching
     researchers via the native Agent tool (Backend B, one round, backgrounded):

       $prompt

  2. Save the session transcript (the .jsonl under the Claude Code session dir)
     and note the \$RESEARCH_WORK_DIR/<slug>/ the run wrote.

  3. Assemble gradeable evidence:
       bash $HERE/behavior_driver.sh $id --harness claude-code \\
         --session <transcript.jsonl> --work-dir \$RESEARCH_WORK_DIR/<slug>

  4. Grade:  ./run.py --suite behavior --case $id
EOF
  return 0
}

# --- drive -----------------------------------------------------------------
drive_one() {
  case "$HARNESS" in
    pi) run_pi "$1" ;;
    claude-code) run_claude_code "$1" ;;
    *) err "unknown harness: $HARNESS (want pi|claude-code)"; return 2 ;;
  esac
}

fail=0
if [ "$ALL" = "1" ]; then
  while IFS= read -r id; do
    [ -n "$id" ] || continue
    drive_one "$id" || fail=1
  done < <(all_ids)
else
  drive_one "$CASE_ID" || fail=1
fi

echo
echo "grade it: (cd $HERE && ./run.py --suite behavior)"
exit "$fail"
