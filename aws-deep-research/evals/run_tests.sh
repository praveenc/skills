#!/usr/bin/env bash
# run_tests.sh - run the whole aws-deep-research test suite, correctly.
#
# Lives in evals/ because it measures the skill rather than running it. The
# suite needs `rich` on the path because scripts/common.py imports it at module
# level and test_budget.py imports common. Running plain `pytest evals/` without
# it fails at COLLECTION, which looks like a broken suite rather than a missing
# dependency. This script is the one supported invocation - use it instead of
# assembling uv flags by hand.
#
# Usage:
#   run_tests.sh                 # every test file
#   run_tests.sh --fast          # skip the slow --help subprocess sweep
#   run_tests.sh <pytest args>   # e.g. run_tests.sh evals/test_dispatch.py -v
#
# Exit codes: pytest's own (0 pass, 1 test failure, 2+ usage/collection error).
set -euo pipefail

EVALS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$EVALS_DIR/.." && pwd)"

case "${1:-}" in
  -h|--help) sed -n '2,17p' "$0" | sed 's/^# \{0,1\}//;s/^#$//'; exit 0 ;;
esac

if ! command -v uv >/dev/null 2>&1; then
  echo "run_tests.sh: uv is required (brew install uv)" >&2
  exit 2
fi

args=()
if [ "${1:-}" = "--fast" ]; then
  shift
  args+=(-k "not test_python_clis_support_help")
fi
if [ $# -gt 0 ]; then
  args+=("$@")
else
  args+=(evals/)
fi

cd "$SKILL_DIR"
# scripts/ on PYTHONPATH so test_budget.py can `import common` from evals/.
export PYTHONPATH="$SKILL_DIR/scripts${PYTHONPATH:+:$PYTHONPATH}"
exec uv run --python 3.13 --with pytest --with rich pytest "${args[@]}"
