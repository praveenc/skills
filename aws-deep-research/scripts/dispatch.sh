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
#     <outfile>     the findings/report path the child writes with its WRITE
#                   TOOL (the same path is given to the child in <task>). The
#                   child's stdout/stderr is captured to <dir>/logs/<agent>.stdout
#                   - it is NOT redirected onto <outfile> (see the execute block).
#
# Environment:
#   DISPATCH_HARNESS       override detection (same values as --harness)
#   DISPATCH_DRY_RUN=1     print the resolved command and exit 0; spawn nothing
#   DISPATCH_BANNER_SHOWN=1  suppress the per-call process disclaimer (set this
#                          once at round level after printing it yourself)
#   SKILL_DIR              skill root; auto-resolved if unset
#   DISPATCH_MODEL         optional model override passed to the child CLI
#                          (on pi, encode effort here too, e.g. sonnet:high)
#   DISPATCH_EFFORT        optional reasoning effort for claude (--effort);
#                          default medium for researchers, high for synthesizer
#   DISPATCH_TIMEOUT       seconds before the child is killed (default 900)
#
# Exit codes:
#   0  success (or dry-run)
#   2  usage error
#   3  harness could not be determined (caller must ask the user, pass --harness)
#   4  harness is known but not supported by this script (e.g. kiro, or an
#      untested harness), OR the child CLI is not on PATH
#   124 child exceeded DISPATCH_TIMEOUT (from `timeout`)
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
  <outfile>     findings/report path the child writes with its write tool;
                child stdout/stderr goes to <dir>/logs/<agent>.stdout, NOT here

OPTIONS:
  --harness H   force the harness (pi|claude); overrides env detection
  -h, --help    show this help and exit

ENVIRONMENT:
  DISPATCH_HARNESS        same as --harness
  DISPATCH_DRY_RUN=1      print the resolved command and exit 0; spawn nothing
  DISPATCH_BANNER_SHOWN=1 suppress the per-call process disclaimer
  DISPATCH_MODEL          optional model override (on pi, encode effort here)
  DISPATCH_EFFORT         optional reasoning effort for claude (--effort)
  DISPATCH_TIMEOUT        seconds before the child is killed (default 900)
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
  0   success (or dry-run)
  2   usage error
  3   harness could not be determined (ask the user, pass --harness)
  4   harness unsupported here (kiro is in-session; untested CLI); or child CLI not on PATH
  124 child exceeded DISPATCH_TIMEOUT
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
# Returns exactly one of pi|claude|kiro when a single fingerprint matches, or
# empty string when zero or more-than-one match (ambiguous → caller asks). On
# Claude Code the PREFERRED path is the native Agent tool (Backend C in
# references/platform-dispatch.md); this shim is the process-fan-out fallback.
detect_harness() {
  local matches="" n=0
  if [ "${PI_CODING_AGENT:-}" = "true" ] || [ -n "${PI_CODING_AGENT:-}" ]; then
    matches="$matches pi"; n=$((n+1))
  fi
  if [ -n "${CLAUDECODE:-}${CLAUDE_CODE_ENTRYPOINT:-}${CLAUDE_CODE_USE_BEDROCK:-}" ]; then
    matches="$matches claude"; n=$((n+1))
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
Ask the user which coding agent is running (pi, claude, kiro) and re-invoke with --harness."

# --- backend + per-harness command construction -----------------------------
# Tool names differ per CLI; the researchers need read + write + shell only
# (all network work goes through 'uv run scripts/*.py').
BACKEND=""
build_cmd() {
  # populates global arrays CMD (real argv) and CMD_DISPLAY (readable argv,
  # role prompt shown as @<file> instead of 8KB of text).
  # Children get read+write+bash+edit: bash runs `uv run scripts/*.py` (all
  # network work); edit lets the synthesizer/diagram step make targeted edits
  # instead of rewriting a whole file (Fable 5.1 leans toward full rewrites).
  local outdir; outdir="$(dirname "$OUTFILE")"
  case "$HARNESS" in
    pi)
      BACKEND="process-fanout"
      # pi encodes reasoning effort in the model spec (e.g. sonnet:high), so
      # pass effort via DISPATCH_MODEL rather than a separate flag.
      CMD=( pi -p --no-session --tools "read,write,bash,edit" )
      [ -n "${DISPATCH_MODEL:-}" ] && CMD+=( --model "$DISPATCH_MODEL" )
      CMD+=( --append-system-prompt "$ROLE" "$TASK" )
      CMD_DISPLAY=( pi -p --no-session --tools "read,write,bash,edit" )
      [ -n "${DISPATCH_MODEL:-}" ] && CMD_DISPLAY+=( --model "$DISPATCH_MODEL" )
      CMD_DISPLAY+=( --append-system-prompt "@${ROLE_FILE#"$SKILL_DIR"/}" "$TASK" )
      ;;
    claude|claude-code)
      HARNESS="claude"
      BACKEND="process-fanout"
      # --add-dir the findings dir so Write/Edit can reach $OUTFILE (outside cwd).
      CMD=( claude -p --append-system-prompt "$ROLE" --allowedTools "Read Write Bash Edit" --add-dir "$SKILL_DIR" --add-dir "$outdir" )
      [ -n "${DISPATCH_MODEL:-}" ]  && CMD+=( --model "$DISPATCH_MODEL" )
      [ -n "${DISPATCH_EFFORT:-}" ] && CMD+=( --effort "$DISPATCH_EFFORT" )
      CMD+=( "$TASK" )
      CMD_DISPLAY=( claude -p --append-system-prompt "@${ROLE_FILE#"$SKILL_DIR"/}" --allowedTools "Read Write Bash Edit" --add-dir "$SKILL_DIR" --add-dir "$outdir" )
      [ -n "${DISPATCH_MODEL:-}" ]  && CMD_DISPLAY+=( --model "$DISPATCH_MODEL" )
      [ -n "${DISPATCH_EFFORT:-}" ] && CMD_DISPLAY+=( --effort "$DISPATCH_EFFORT" )
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

# --- CLI existence check ----------------------------------------------------
# A missing child CLI must fail with guidance, not exit 127 and leave an empty
# findings file that reads as a silent failure downstream.
command -v "${CMD[0]}" >/dev/null 2>&1 || \
  die 4 "child CLI '${CMD[0]}' is not on PATH. Install it, or dispatch on a \
harness whose CLI is available (on Claude Code prefer the native Agent tool - \
Backend C in references/platform-dispatch.md - which needs no child CLI)."

# --- execute -----------------------------------------------------------------
# The child writes its findings/report to $OUTFILE with its *write tool* (the
# path is handed to it in <task>). dispatch.sh must NOT also redirect the
# child's stdout onto $OUTFILE: the shell holds that fd at offset 0, so the
# child's final status line ("✅ Wrote N chars ...") overwrites the head of the
# file the write tool just filled - two writers on one path, corrupting the H1
# and first record of every findings file. Capture stdout+stderr to a sibling
# log instead; the write tool owns $OUTFILE alone.
OUTDIR="$(dirname "$OUTFILE")"
LOGDIR="$OUTDIR/logs"
mkdir -p "$OUTDIR" "$LOGDIR"
LOGFILE="$LOGDIR/${AGENT}.stdout"

# Bound the child so a hung auth prompt or stuck fetch cannot block a round
# indefinitely (DISPATCH_TIMEOUT seconds, default 900; `timeout` exits 124).
# The child's exit code propagates via set -e so the caller sees failures.
if command -v timeout >/dev/null 2>&1; then
  timeout "${DISPATCH_TIMEOUT:-900}" "${CMD[@]}" > "$LOGFILE" 2>&1
else
  "${CMD[@]}" > "$LOGFILE" 2>&1
fi
