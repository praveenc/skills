#!/usr/bin/env bash
# Thin wrapper around run.py. Prefers python3; falls back to python.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if command -v python3 >/dev/null 2>&1; then
  exec python3 "$HERE/run.py" "$@"
elif command -v python >/dev/null 2>&1; then
  exec python "$HERE/run.py" "$@"
else
  echo "python3 (or python) is required to run the evals" >&2
  exit 2
fi
