#!/usr/bin/env bash
# register.sh — install the aws-deep-research skill into Kiro CLI
#
# Copies:
#   1. This skill directory -> ~/.kiro/skills/aws-deep-research/
#   2. setup/kiro-agent.json -> ~/.kiro/agents/aws-deep-research.json
#   3. agents/*.json -> ~/.kiro/agents/<name>.json  (so kiro-cli can ListAgents them)
#
# After install, launch with:
#   kiro-cli chat --agent aws-deep-research
#
# Safe to re-run (idempotent). Backs up any existing install to
# ~/.kiro/skills/aws-deep-research.bak-<timestamp>/ before overwriting.

set -euo pipefail

# Resolve this script's directory -> the skill source
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_SRC="$(cd "$SCRIPT_DIR/.." && pwd)"
SKILL_NAME="aws-deep-research"

KIRO_SKILLS="$HOME/.kiro/skills"
KIRO_AGENTS="$HOME/.kiro/agents"
SKILL_DST="$KIRO_SKILLS/$SKILL_NAME"

mkdir -p "$KIRO_SKILLS" "$KIRO_AGENTS"

# --- 1. Skill directory ---
if [ -d "$SKILL_DST" ]; then
  TS=$(date +%Y%m%d-%H%M%S)
  BAK="$KIRO_SKILLS/${SKILL_NAME}.bak-$TS"
  echo "[register] existing install found; backing up to $BAK"
  mv "$SKILL_DST" "$BAK"
fi

echo "[register] installing skill: $SKILL_SRC -> $SKILL_DST"
rsync -a \
  --exclude='setup/' \
  --exclude='scripts/__pycache__/' \
  --exclude='.DS_Store' \
  "$SKILL_SRC/" "$SKILL_DST/"

# --- 2. Top-level agent registration ---
echo "[register] registering top-level agent: $KIRO_AGENTS/$SKILL_NAME.json"
cp "$SKILL_SRC/setup/kiro-agent.json" "$KIRO_AGENTS/$SKILL_NAME.json"

# --- 3. Subagent registration (so ListAgents finds them by name) ---
# Kiro resolves `file://agents/<name>.md` relative to the agent JSON's
# directory, so the .md prompt file must live next to the .json in
# ~/.kiro/agents/. Copy BOTH.
echo "[register] registering subagents from $SKILL_SRC/agents/"
for f in "$SKILL_SRC"/agents/*.json; do
  base=$(basename "$f" .json)
  echo "  -> $KIRO_AGENTS/$base.json + $base.md"
  cp "$SKILL_SRC/agents/$base.json" "$KIRO_AGENTS/$base.json"
  if [ -f "$SKILL_SRC/agents/$base.md" ]; then
    cp "$SKILL_SRC/agents/$base.md" "$KIRO_AGENTS/$base.md"
  else
    echo "     WARNING: no $base.md found next to $base.json"
  fi
done

# --- 4. .env check ---
if [ ! -f "$SKILL_DST/scripts/.env" ]; then
  echo "[register] WARNING: $SKILL_DST/scripts/.env not found."
  echo "           Copy scripts/.env.example -> scripts/.env and fill in keys."
  echo "           Required: BRAVE_API_KEY, TAVILY_API_KEY, GITHUB_TOKEN (optional)."
fi

echo
echo "[register] Done. Launch with:"
echo "    kiro-cli chat --agent $SKILL_NAME"
