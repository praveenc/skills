#!/usr/bin/env bash
# Resolves the skill's base directory AND the research work directory.
# Usage: eval "$(bash <path>/scripts/resolve_skill_dir.sh)"
# Exports:
#   SKILL_DIR  — absolute path to the skill folder (self-located; see below)
#   WORK_DIR   — absolute path to the research work root
#                (default ~/.aws-deep-research/work, override via RESEARCH_WORK_DIR in .env)
#
# Resolution strategy (in order):
#   1. SELF-LOCATE — derive SKILL_DIR from this script's own location via
#      BASH_SOURCE. Whichever copy you invoke (kiro, pi, project-local, custom)
#      is the copy that owns the session. This is the canonical path; it has
#      no preference bias.
#   2. FALLBACK — if BASH_SOURCE is unavailable (e.g. piped via stdin), search
#      a list of well-known install locations.
#
# The old preference-list behavior (kiro-before-pi) was a bug: invoking the
# script from ~/.pi/... would still return ~/.kiro/... when both existed.

set -euo pipefail

SKILL_DIR=""

# --- 1. Self-locate via BASH_SOURCE (preferred) ---
if [ -n "${BASH_SOURCE[0]:-}" ] && [ -f "${BASH_SOURCE[0]}" ]; then
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  CANDIDATE="$(dirname "$SCRIPT_DIR")"
  if [ -f "$CANDIDATE/SKILL.md" ]; then
    SKILL_DIR="$CANDIDATE"
  fi
fi

# --- 2. Fallback: search well-known install locations ---
if [ -z "$SKILL_DIR" ]; then
  for candidate in \
    "./.kiro/skills/aws-deep-research-v2" \
    "./.kiro/skills/aws-deep-research" \
    "./.pi/agent/skills/aws-deep-research" \
    "$HOME/.pi/agent/skills/aws-deep-research" \
    "$HOME/.kiro/skills/aws-deep-research-v2" \
    "$HOME/.kiro/skills/aws-deep-research"
  do
    if [ -f "$candidate/SKILL.md" ]; then
      if [ "${candidate#./}" != "$candidate" ]; then
        SKILL_DIR="$(cd "$candidate" && pwd)"
      else
        SKILL_DIR="$candidate"
      fi
      break
    fi
  done
fi

if [ -z "$SKILL_DIR" ]; then
  echo "ERROR: aws-deep-research skill not found" >&2
  exit 1
fi

CONFIG_FILE="${AWS_DEEP_RESEARCH_CONFIG:-$HOME/.config/aws-deep-research/config.env}"

# --- Resolve WORK_DIR from external machine-local config or default ---
WORK_DIR=""
if [ -f "$CONFIG_FILE" ]; then
  WORK_DIR="$(python3 "$SCRIPT_DIR/read_env.py" \
    "$CONFIG_FILE" RESEARCH_WORK_DIR)"
fi
if [ -z "$WORK_DIR" ]; then
  WORK_DIR="$HOME/.aws-deep-research/work"
fi
# Tilde expansion
WORK_DIR="${WORK_DIR/#\~/$HOME}"
mkdir -p "$WORK_DIR"

# This output is consumed by eval, so quote values as shell data.
printf 'SKILL_DIR=%q\n' "$SKILL_DIR"
printf 'CONFIG_FILE=%q\n' "$CONFIG_FILE"
printf 'WORK_DIR=%q\n' "$WORK_DIR"
