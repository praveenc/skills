#!/usr/bin/env bash
# preflight.sh - Validate a skill directory and resolve the audit output path.
#
# Usage: preflight.sh <skill-dir> [output-file]
#
# Validates the skill directory, creates meta/ if needed, resolves the
# output path, and prints structured JSON to stdout.
#
# Exit codes:
#   0  Success - JSON printed to stdout
#   1  Skill directory invalid or missing SKILL.md
#   2  Usage / argument error
#
# stdout: JSON object with skill_dir, output_file, skill_name
# stderr: Diagnostic messages on error

set -uo pipefail

print_help() {
  cat <<'HELP'
Usage: preflight.sh [OPTIONS] <skill-dir> [output-file]

Validate a skill directory and resolve the audit report output path.
Creates <skill-dir>/meta/ if it does not exist.

ARGUMENTS
  <skill-dir>      Path to the skill directory (must contain SKILL.md).
  [output-file]    Optional. Defaults to <skill-dir>/meta/AUDIT-<YYYY-MM-DD>.md.

OPTIONS
  -h, --help       Show this help and exit.

OUTPUT (stdout)
  JSON: {"skill_dir": "...", "output_file": "...", "skill_name": "..."}

EXIT CODES
  0  Success
  1  Invalid skill directory or missing SKILL.md
  2  Usage / argument error

EXAMPLES
  preflight.sh /path/to/my-skill
  preflight.sh /path/to/my-skill /tmp/custom-audit.md
HELP
}

err() { printf '%s\n' "$*" >&2; }

# json_escape - escape a string for safe inclusion in a JSON string literal.
# Escapes backslash and double-quote (the two characters that would otherwise
# produce invalid JSON for a filesystem path). Prints the escaped value.
json_escape() {
  local s=$1
  s=${s//\\/\\\\}   # backslash -> \\  (must run first)
  s=${s//\"/\\\"}   # double-quote -> \"
  printf '%s' "$s"
}

# ── Parse args ─────────────────────────────────────────────────────────────

POSITIONAL=()

while [ $# -gt 0 ]; do
  case "$1" in
    -h|--help) print_help; exit 0 ;;
    --) shift; while [ $# -gt 0 ]; do POSITIONAL+=("$1"); shift; done ;;
    -*) err "error: unknown option: $1"; err "run with --help for usage"; exit 2 ;;
    *)  POSITIONAL+=("$1"); shift ;;
  esac
done

if [ "${#POSITIONAL[@]}" -lt 1 ]; then
  err "error: <skill-dir> is required"
  err "usage: preflight.sh <skill-dir> [output-file]"
  exit 2
fi
if [ "${#POSITIONAL[@]}" -gt 2 ]; then
  err "error: too many arguments (expected 1-2, got ${#POSITIONAL[@]})"
  exit 2
fi

SKILL_DIR="${POSITIONAL[0]}"
OUTPUT_FILE="${POSITIONAL[1]:-}"

# ── Validate skill directory ───────────────────────────────────────────────

if [ ! -d "$SKILL_DIR" ]; then
  err "error: not a directory: $SKILL_DIR"
  exit 1
fi
SKILL_DIR="$(cd "$SKILL_DIR" && pwd)"

if [ ! -r "$SKILL_DIR/SKILL.md" ]; then
  err "error: no readable SKILL.md in: $SKILL_DIR"
  err "expected: $SKILL_DIR/SKILL.md"
  exit 1
fi

# ── Resolve output path ───────────────────────────────────────────────────

if [ -z "$OUTPUT_FILE" ]; then
  META_DIR="$SKILL_DIR/meta"
  if [ ! -d "$META_DIR" ]; then
    mkdir -p "$META_DIR" || { err "error: failed to create $META_DIR"; exit 1; }
  fi
  STAMP="$(date +%Y-%m-%d)"
  OUTPUT_FILE="$META_DIR/AUDIT-$STAMP.md"
else
  # Ensure parent directory exists for custom output
  OUTPUT_PARENT="$(dirname "$OUTPUT_FILE")"
  if [ ! -d "$OUTPUT_PARENT" ]; then
    mkdir -p "$OUTPUT_PARENT" || { err "error: failed to create $OUTPUT_PARENT"; exit 1; }
  fi
  OUTPUT_FILE="$(cd "$OUTPUT_PARENT" && pwd)/$(basename "$OUTPUT_FILE")"
fi

# ── Extract skill name from directory ──────────────────────────────────────

SKILL_NAME="$(basename "$SKILL_DIR")"

# ── Output structured JSON ─────────────────────────────────────────────────

printf '{"skill_dir": "%s", "output_file": "%s", "skill_name": "%s"}\n' \
  "$(json_escape "$SKILL_DIR")" "$(json_escape "$OUTPUT_FILE")" "$(json_escape "$SKILL_NAME")"
