#!/usr/bin/env bash
# Validates API keys and credentials needed for research subagents.
# Usage: bash scripts/check_api_keys.sh [SKILL_DIR]
# Output: one status line per service (parseable by the agent)

set -euo pipefail

SKILL_DIR="${1:-.}"

# Load keys from .env
eval "$(grep -E '^(TAVILY_API_KEY|BRAVE_SEARCH_API_KEY|GITHUB_TOKEN)=' "$SKILL_DIR/scripts/.env" 2>/dev/null)" || true

# --- AWS Credentials ---
if aws sts get-caller-identity --profile 001 >/dev/null 2>&1; then
  CALLER=$(aws sts get-caller-identity --profile 001 --output text --query 'Arn' 2>/dev/null)
  echo "AWS=VALID ($CALLER)"
else
  echo "AWS=INVALID"
fi

# --- Tavily ---
if [ -n "${TAVILY_API_KEY:-}" ] && ! echo "$TAVILY_API_KEY" | grep -q 'your_.*_here'; then
  echo "TAVILY=CONFIGURED"
else
  echo "TAVILY=MISSING"
fi

# --- Brave ---
if [ -n "${BRAVE_SEARCH_API_KEY:-}" ] && ! echo "$BRAVE_SEARCH_API_KEY" | grep -q 'your_.*_here'; then
  echo "BRAVE=CONFIGURED"
else
  echo "BRAVE=MISSING"
fi

# --- GitHub ---
if [ -n "${GITHUB_TOKEN:-}" ] && ! echo "$GITHUB_TOKEN" | grep -q 'your_.*_here'; then
  HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
    -H "Authorization: token $GITHUB_TOKEN" \
    -H "Accept: application/vnd.github.v3+json" \
    https://api.github.com/rate_limit 2>/dev/null || echo "000")
  echo "GITHUB=$HTTP_STATUS"
else
  echo "GITHUB=MISSING"
fi

# --- Kroki (optional) ---
if curl -s --max-time 2 http://localhost:8000/health >/dev/null 2>&1; then
  echo "KROKI=LOCAL"
elif curl -s --max-time 2 https://kroki.io/health >/dev/null 2>&1; then
  echo "KROKI=REMOTE"
else
  echo "KROKI=UNAVAILABLE"
fi
