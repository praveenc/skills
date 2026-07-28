#!/usr/bin/env bash
# dispatch.sh - portable subagent dispatch for the aws-deep-research skill.
#
# Dispatches ONE subagent as a headless child process on a process-fan-out
# harness (pi or Claude Code). The CALLER is responsible for backgrounding
# multiple invocations with `&` and `wait`-ing on them to get a parallel round.
#
# This script does NOT handle Kiro. Kiro dispatches subagents in-session via
# its native `subagent` tool (see references/platform-dispatch.md); there is no
# subprocess to spawn, so a shell shim cannot express it. If --harness kiro is
# requested this script exits with guidance rather than guessing.
#
# Usage:
#   dispatch.sh [--harness pi|claude] <agent-name> <task> <outfile>
#     <agent-name>  base name under $SKILL_DIR/agents/ (e.g. synthesizer)
#     <task>        literal task string, OR "@/path/to/taskfile" to read a file
#     <outfile>     where the child's stdout (the findings/report) is written
#
# Environment:
#   DISPATCH_HARNESS       override detection (same values as --harness)
#   DISPATCH_DRY_RUN=1     print the resolved command and exit 0; spawn nothing
#   DISPATCH_BANNER_SHOWN=1  suppress the per-call process disclaimer (set this
#                          once at round level after printing it yourself)
#   SKILL_DIR              skill root; auto-resolved if unset
#   DISPATCH_MODEL         optional model override passed to the child CLI
#
# Exit codes:
#   0  success (or dry-run)
#   2  usage error
#   3  harness could not be determined (caller must ask the user, pass --harness)
#   4  harness is known but not supported by this script (e.g. kiro, or an
#      untested harness) - caller must handle per SKILL.md
set -euo pipefail

# --- tiny helpers -----------------------------------------------------------
err()  { printf '%s\n' "$*" >&2; }
die()  { local code="$1"; shift; err "dispatch.sh: $*"; exit "$code"; }

# --- parse args -------------------------------------------------------------
HARNESS_OVERRIDE="${DISPATCH_HARNESS:-}"

usage() {
  cat <<'EOF'
dispatch.sh - portable subagent dispatch (pi / Claude Code)

USAGE:
  dispatch.sh [--harness pi|claude] <agent-name> <task> <outfile>

ARGUMENTS:
  <agent-name>  base name under $SKILL_DIR/agents/ (e.g. synthesizer)
  <task>        literal task string, OR "@/path/to/taskfile" to read a file
  <outfile>     where the child's stdout (findings/report) is written

OPTIONS:
  --harness H   force the harness (pi|claude); overrides env detection
  -h, --help    show this help and exit

ENVIRONMENT:
  DISPATCH_HARNESS        same as --harness
  DISPATCH_DRY_RUN=1      print the resolved command and exit 0; spawn nothing
  DISPATCH_BANNER_SHOWN=1 suppress the per-call process disclaimer
  DISPATCH_MODEL          optional model override passed to the child CLI
  SKILL_DIR               skill root; auto-resolved from this script if unset

EXAMPLES:
  # dry-run: preview the exact pi command
  DISPATCH_DRY_RUN=1 dispatch.sh --harness pi synthesizer "synthesize" out.md

  # real dispatch of one researcher (task read from a brief file)
  dispatch.sh --harness claude web-content-researcher @brief.md web-content.md

  # parallel round: background several, then wait
  dispatch.sh aws-mcp-researcher     @brief-aws.md    aws-docs.md    &
  dispatch.sh web-content-researcher @brief-web.md    web-content.md &
  wait

EXIT CODES:
  0  success (or dry-run)
  2  usage error
  3  harness could not be determined (ask the user, pass --harness)
  4  harness known but unsupported here (kiro is in-session; or untested CLI)
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    -h|--help) usage; exit 0 ;;
    --harness) HARNESS_OVERRIDE="${2:-}"; shift 2 ;;
    --harness=*) HARNESS_OVERRIDE="${1#*=}"; shift ;;
    --) shift; break ;;
    -*) usage >&2; die 2 "unknown flag: $1" ;;
    *) break ;;
  esac
done

AGENT="${1:-}"
TASK_RAW="${2:-}"
OUTFILE="${3:-}"
[ -n "$AGENT" ]   || die 2 "missing <agent-name> (usage: dispatch.sh [--harness H] <agent> <task> <outfile>)"
[ -n "$TASK_RAW" ] || die 2 "missing <task>"
[ -n "$OUTFILE" ] || die 2 "missing <outfile>"

# --- resolve SKILL_DIR ------------------------------------------------------
if [ -z "${SKILL_DIR:-}" ]; then
  _self="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  SKILL_DIR="$(dirname "$_self")"
fi
[ -f "$SKILL_DIR/SKILL.md" ] || die 2 "SKILL_DIR does not look like the skill root: $SKILL_DIR"

ROLE_FILE="$SKILL_DIR/agents/${AGENT}.md"
[ -f "$ROLE_FILE" ] || die 2 "no role prompt for agent '$AGENT' at $ROLE_FILE"

# --- resolve the task (literal string or @file) -----------------------------
case "$TASK_RAW" in
  @*)
    TASK_FILE="${TASK_RAW#@}"
    [ -f "$TASK_FILE" ] || die 2 "task file not found: $TASK_FILE"
    TASK="$(cat "$TASK_FILE")"
    ;;
  *) TASK="$TASK_RAW" ;;
esac

# --- harness detection ------------------------------------------------------
# Returns exactly one of pi|claude|codex|kiro when a single fingerprint matches,
# or empty string when zero or more-than-one match (ambiguous → caller asks).
detect_harness() {
  local matches="" n=0
  if [ "${PI_CODING_AGENT:-}" = "true" ] || [ -n "${PI_CODING_AGENT:-}" ]; then
    matches="$matches pi"; n=$((n+1))
  fi
  if [ -n "${CLAUDECODE:-}${CLAUDE_CODE_ENTRYPOINT:-}${CLAUDE_CODE_USE_BEDROCK:-}" ]; then
    matches="$matches claude"; n=$((n+1))
  fi
  if [ -n "${CODEX_SANDBOX:-}${CODEX_HOME:-}" ]; then
    matches="$matches codex"; n=$((n+1))
  fi
  if [ -n "${KIRO_AGENT:-}${KIRO_CLI:-}${KIRO_VERSION:-}" ]; then
    matches="$matches kiro"; n=$((n+1))
  fi
  if [ "$n" -eq 1 ]; then
    printf '%s' "${matches# }"
  else
    printf ''
  fi
}

if [ -n "$HARNESS_OVERRIDE" ]; then
  HARNESS="$HARNESS_OVERRIDE"
else
  HARNESS="$(detect_harness)"
fi

[ -n "$HARNESS" ] || die 3 "could not determine the harness from the environment. \
Ask the user which coding agent is running (pi, claude, codex, kiro) and re-invoke with --harness."

# --- backend + per-harness command construction -----------------------------
# Tool names differ per CLI; the researchers need read + write + shell only
# (all network work goes through 'uv run scripts/*.py').
BACKEND=""
build_cmd() {
  # populates global arrays CMD (real argv) and CMD_DISPLAY (readable argv,
  # role prompt shown as @<file> instead of 8KB of text).
  case "$HARNESS" in
    pi)
      BACKEND="process-fanout"
      CMD=( pi -p --no-session --tools "read,write,bash" )
      [ -n "${DISPATCH_MODEL:-}" ] && CMD+=( --model "$DISPATCH_MODEL" )
      CMD+=( --append-system-prompt "$ROLE" "$TASK" )
      CMD_DISPLAY=( pi -p --no-session --tools "read,write,bash" )
      [ -n "${DISPATCH_MODEL:-}" ] && CMD_DISPLAY+=( --model "$DISPATCH_MODEL" )
      CMD_DISPLAY+=( --append-system-prompt "@${ROLE_FILE#"$SKILL_DIR"/}" "$TASK" )
      ;;
    claude|claude-code)
      HARNESS="claude"
      BACKEND="process-fanout"
      CMD=( claude -p --append-system-prompt "$ROLE" --allowedTools "Read Write Bash" --add-dir "$SKILL_DIR" )
      [ -n "${DISPATCH_MODEL:-}" ] && CMD+=( --model "$DISPATCH_MODEL" )
      CMD+=( "$TASK" )
      CMD_DISPLAY=( claude -p --append-system-prompt "@${ROLE_FILE#"$SKILL_DIR"/}" --allowedTools "Read Write Bash" --add-dir "$SKILL_DIR" )
      [ -n "${DISPATCH_MODEL:-}" ] && CMD_DISPLAY+=( --model "$DISPATCH_MODEL" )
      CMD_DISPLAY+=( "$TASK" )
      ;;
    kiro)
      die 4 "kiro dispatches subagents in-session via its native 'subagent' tool, \
not via a subprocess. Do NOT shell out. See references/platform-dispatch.md."
      ;;
    *)
      die 4 "harness '$HARNESS' is not one of the tested process-fan-out CLIs \
(pi, claude). This script cannot build a command for it. Ask the user to \
confirm and, if they want to proceed, supply the CLI's headless invocation."
      ;;
  esac
}

# ROLE holds the full prompt text; only read it when we actually need it.
ROLE="$(cat "$ROLE_FILE")"
build_cmd

# --- echo the decision (mismatch must never be silent) ----------------------
render_display() {
  local out="" tok
  for tok in "${CMD_DISPLAY[@]}"; do
    case "$tok" in
      *[[:space:]]*|"") out="$out \"$tok\"" ;;
      *) out="$out $tok" ;;
    esac
  done
  printf '%s' "${out# }"
}
DISPLAY_CMD="$(render_display)"

err "harness=$HARNESS  backend=$BACKEND  agent=$AGENT  ->  $OUTFILE"
err "\$ $DISPLAY_CMD  > $OUTFILE"

# --- bold process disclaimer (once per call unless already shown) -----------
if [ "${DISPATCH_BANNER_SHOWN:-}" != "1" ]; then
  # bold only when stderr is a TTY; plain otherwise (logs, pipes, tests).
  if [ -t 2 ]; then B=$'\033[1m'; R=$'\033[0m'; else B=""; R=""; fi
  err ""
  err "⚠️  ${B}Each subagent launches a full, separate CLI process - its own model"
  err "    context and its own auth round-trip. A 4-researcher round = 4 CLI cold starts.${R}"
  err ""
fi

# --- dry-run: print resolved command, spawn nothing -------------------------
if [ "${DISPATCH_DRY_RUN:-}" = "1" ]; then
  printf '%s\n' "$DISPLAY_CMD > $OUTFILE"
  exit 0
fi

# --- execute: child writes findings to $OUTFILE -----------------------------
mkdir -p "$(dirname "$OUTFILE")"
"${CMD[@]}" > "$OUTFILE"
