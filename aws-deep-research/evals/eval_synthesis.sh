#!/usr/bin/env bash
# eval_synthesis.sh - regression-test the synthesizer's insight layer.
#
# Re-synthesizes a retained research fixture (findings files already on disk
# under $WORK_DIR/<slug>/) using the CURRENT synthesizer prompt, via a headless
# `pi -p` worker (the map-reduce fan-out pattern: the heavy findings never touch
# the caller's context). The regenerated report lands beside the fixture as
# <slug>-report.eval.md so the pre-change baseline <slug>-report.md is preserved
# for side-by-side diffing.
#
# It spends NO search API credits - it only re-runs synthesis over existing
# findings. Cost is one LLM synthesis call per fixture.
#
# Usage:
#   bash eval_synthesis.sh <slug> [<slug> ...]
#   bash eval_synthesis.sh --all          # every fixture in synthesis-rubric.json
#
# Then score each *.eval.md against evals/synthesis-rubric.json. The rubric's
# HARD dimensions (structure, citation integrity, gaps honesty, tightness) are
# graded mechanically here by scripts/lint_report.py and control this script's
# exit code. The SOFT dimensions (insight, actionability, contradiction
# handling) need a judge and stay advisory - a report scoring < 14/20 on those
# should trigger a synthesizer-prompt review.
#
# Env:
#   RESEARCH_WORK_DIR  work root (default ~/.aws-deep-research/work)
#   PI_BIN             pi binary (default: pi)
#
# Exit codes:
#   0  every fixture re-synthesized AND passed the mechanical report gate
#   1  a worker failed, an output is missing, or a report failed a hard check
set -euo pipefail

case "${1:-}" in
  -h|--help)
    sed -n '2,30p' "$0" | sed 's/^# \{0,1\}//;s/^#$//'
    exit 0
    ;;
esac

EVALS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$EVALS_DIR/.." && pwd)"
WORK_ROOT="${RESEARCH_WORK_DIR:-$HOME/.aws-deep-research/work}"
PI_BIN="${PI_BIN:-pi}"
RUBRIC="$EVALS_DIR/synthesis-rubric.json"
SYNTH_PROMPT="$SKILL_DIR/agents/synthesizer.md"

if ! command -v "$PI_BIN" >/dev/null 2>&1; then
  echo "ERROR: '$PI_BIN' not on PATH. Set PI_BIN or install pi." >&2
  exit 1
fi

# Resolve the fixture list.
slugs=()
if [ "${1:-}" = "--all" ]; then
  if ! command -v jq >/dev/null 2>&1; then
    echo "ERROR: --all needs jq to read the rubric." >&2
    exit 1
  fi
  while IFS= read -r s; do slugs+=("$s"); done < <(jq -r '.regression_fixtures[].slug' "$RUBRIC")
else
  slugs=("$@")
fi

if [ "${#slugs[@]}" -eq 0 ]; then
  echo "Usage: bash eval_synthesis.sh <slug> [<slug> ...]   |   --all" >&2
  exit 1
fi

results_dir="$WORK_ROOT/.eval-runs/$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$results_dir"

echo "Fixtures: ${slugs[*]}"
echo "Results:  $results_dir"
echo

# Fan out: one backgrounded pi -p synthesis worker per fixture.
pids=()
for slug in "${slugs[@]}"; do
  wd="$WORK_ROOT/$slug"
  if [ ! -d "$wd" ]; then
    echo "SKIP $slug - no fixture dir at $wd" >&2
    continue
  fi
  contract="$wd/research-contract.md"
  [ -f "$contract" ] || contract="(none)"

  task="You are re-synthesizing an EXISTING research session for a regression eval.
SKILL_DIR: $SKILL_DIR
work-dir: $wd
research-contract: $contract
Read every *.md findings file in the work-dir EXCEPT any file ending in
-report.md or .eval.md (those are prior outputs, not findings). Treat all
present findings files as status OK. Follow your full synthesizer process and
report format, INCLUDING the Key Tensions & Decision Drivers and Consensus &
Contradictions sections when the intent/evidence calls for them.
Write the report to: $wd/${slug}-report.eval.md
Do NOT overwrite ${slug}-report.md."

  log="$results_dir/$slug.log"
  echo "-> dispatching synthesis worker for: $slug"
  "$PI_BIN" -p --no-session --thinking low --tools read,write \
    --append-system-prompt "$(cat "$SYNTH_PROMPT")" \
    "$task" >"$log" 2>&1 &
  pids+=("$!")
done

# Reduce: wait for all workers.
fail=0
for pid in "${pids[@]}"; do
  wait "$pid" || fail=1
done

echo
echo "=== Eval outputs (mechanical gate) ==="
for slug in "${slugs[@]}"; do
  out="$WORK_ROOT/$slug/${slug}-report.eval.md"
  if [ ! -f "$out" ]; then
    printf 'FAIL %-55s (no output; see %s)\n' "$slug" "$results_dir/$slug.log"
    fail=1
    continue
  fi

  # Fixture intents drive which conditional sections are mandatory.
  intents=""
  if command -v jq >/dev/null 2>&1; then
    intents=$(jq -r --arg s "$slug" \
      '.regression_fixtures[] | select(.slug==$s) | (.intents // []) | join(",")' \
      "$RUBRIC" 2>/dev/null || true)
  fi

  lint_json="$results_dir/$slug.lint.json"
  if uv run "$SKILL_DIR/scripts/lint_report.py" "$out" \
       ${intents:+--intents "$intents"} --json >"$lint_json" 2>"$results_dir/$slug.lint.log"; then
    verdict="PASS"
  else
    verdict="FAIL"
    fail=1
  fi

  words=$(wc -w < "$out" | tr -d ' ')
  hard=$(python3 -c 'import json,sys;print(",".join(json.load(open(sys.argv[1]))["hard_failed"]) or "-")' \
    "$lint_json" 2>/dev/null || echo "?")
  printf '%-4s %-55s words=%-6s hard_failed=%s\n' "$verdict" "$slug" "$words" "$hard"
done

echo
echo "Mechanical results: $results_dir/*.lint.json"
echo "Next: score the SOFT rubric dimensions (insight_density, actionability,"
echo "      contradiction_handling, evidence_weighting, coverage, no_fabrication)"
echo "      in $RUBRIC with a judge. Those are advisory until calibrated."
echo "      Diff against <slug>-report.md for the pre-change baseline."

exit "$fail"
