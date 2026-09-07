#!/usr/bin/env bash
# Validates API keys and credentials needed for research subagents.
# Output: one status line per service (parseable by the agent)

set -euo pipefail

usage() {
  cat <<'EOF'
check_api_keys.sh - validate credentials for the research subagents

USAGE:
  check_api_keys.sh [SKILL_DIR]

ARGUMENTS:
  SKILL_DIR   skill root containing scripts/read_env.py (default: ".")

ENVIRONMENT:
  AWS_DEEP_RESEARCH_CONFIG
              external config path (default: ~/.config/aws-deep-research/config.env)

OPTIONS:
  -h, --help  show this help and exit

OUTPUT:
  One "SERVICE=STATUS" line per service on stdout, e.g.:
    AWS=VALID|INVALID
    TAVILY=CONFIGURED|MISSING
    BRAVE=CONFIGURED|MISSING
    GITHUB=<http-status>|MISSING
    LLMSTXT=READY|UNAVAILABLE
    KROKI=LOCAL|CONFIGURED|UNAVAILABLE

EXAMPLES:
  check_api_keys.sh
  check_api_keys.sh "$SKILL_DIR"

EXIT CODES:
  0  always (per-service status is reported on stdout, not via exit code)
EOF
}

case "${1:-}" in
  -h|--help) usage; exit 0 ;;
esac

SKILL_DIR="${1:-.}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${AWS_DEEP_RESEARCH_CONFIG:-$HOME/.config/aws-deep-research/config.env}"

read_env() {
  python3 "$SCRIPT_DIR/read_env.py" "$ENV_FILE" "$1"
}

# Environment variables take precedence over literal values in .env.
TAVILY_API_KEY="${TAVILY_API_KEY:-$(read_env TAVILY_API_KEY)}"
BRAVE_SEARCH_API_KEY="${BRAVE_SEARCH_API_KEY:-$(read_env BRAVE_SEARCH_API_KEY)}"
GITHUB_TOKEN="${GITHUB_TOKEN:-$(read_env GITHUB_TOKEN)}"
KROKI_URL="${KROKI_URL:-$(read_env KROKI_URL)}"
# Optional AWS profile: env var, else config. No profile name is hardcoded -
# when unset, the AWS default credential chain (SSO/env/instance) is used.
AWS_PROFILE="${AWS_PROFILE:-$(read_env AWS_PROFILE)}"

# --- AWS Credentials ---
if aws sts get-caller-identity ${AWS_PROFILE:+--profile "$AWS_PROFILE"} >/dev/null 2>&1; then
  echo "AWS=VALID"
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
    -H "Authorization: Bearer $GITHUB_TOKEN" \
    -H "Accept: application/vnd.github+json" \
    -H "X-GitHub-Api-Version: 2022-11-28" \
    https://api.github.com/rate_limit 2>/dev/null || echo "000")
  echo "GITHUB=$HTTP_STATUS"
else
  echo "GITHUB=MISSING"
fi

# --- llmstxt-doc-search (primary AWS-docs source; needs Node for npx) ---
if command -v node >/dev/null 2>&1; then
  echo "LLMSTXT=READY"
else
  echo "LLMSTXT=UNAVAILABLE"
fi

# --- Kroki (optional) ---
case "$KROKI_URL" in
  [Dd][Ii][Ss][Aa][Bb][Ll][Ee][Dd])
    echo "KROKI=UNAVAILABLE"
    ;;
  "")
    if curl -s --max-time 2 http://localhost:8000/health >/dev/null 2>&1; then
      echo "KROKI=LOCAL"
    else
      echo "KROKI=UNAVAILABLE"
    fi
    ;;
  *)
    echo "KROKI=CONFIGURED"
    ;;
esac
