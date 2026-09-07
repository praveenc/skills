#!/usr/bin/env bash
# Thin wrapper around run.py. Prefers python3; falls back to python.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if command -v python3 >/dev/null 2>&1; then
  if [[ "${1:-}" == "--static" ]]; then
    python3 -m py_compile "$HERE/run.py" "$HERE/behavior_runner.py" \
      "$HERE/release_gate.py" "$HERE/../scripts/validate_output.py"
    python3 "$HERE/../scripts/validate_output.py" --selftest
  fi
  exec python3 "$HERE/run.py" "$@"
elif command -v python >/dev/null 2>&1; then
  if [[ "${1:-}" == "--static" ]]; then
    python -m py_compile "$HERE/run.py" "$HERE/behavior_runner.py" \
      "$HERE/release_gate.py" "$HERE/../scripts/validate_output.py"
    python "$HERE/../scripts/validate_output.py" --selftest
  fi
  exec python "$HERE/run.py" "$@"
else
  echo "python3 (or python) is required to run the evals" >&2
  exit 2
fi
