#!/usr/bin/env bash
# Generates evals/palmyra-vs-claude/COMPARISON.md — side-by-side metrics
# for each eval case (Claude synthesizer vs Palmyra X5).
#
# Does NOT re-run the synthesizers. It assumes:
#   - Claude reports live in ~/.aws-deep-research/work/<slug>/<slug>-report.md
#     (these were produced by the default synthesizer agent in prior runs)
#   - Palmyra reports live in evals/palmyra-vs-claude/<slug>-palmyra.md
#     (produced by scripts/synthesize_palmyra.py during the spike)

set -euo pipefail

EVAL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORK_ROOT="${RESEARCH_WORK_DIR:-$HOME/.aws-deep-research/work}"
OUT="$EVAL_DIR/COMPARISON.md"

SLUGS=(
  "aws-health-api-overview-sentiment-oss-alternatives"
  "bedrock-guardrails-contextual-grounding-enterprise-accuracy"
  "bedrock-automated-reasoning-checks-rag-oss-alternatives"
)

count_citations() { grep -oE '\[\^?[0-9]+\]' "$1" 2>/dev/null | wc -l | tr -d ' ' || echo 0; }
count_unique_cites() { grep -oE '\[\^?[0-9]+\]' "$1" 2>/dev/null | sort -u | wc -l | tr -d ' ' || echo 0; }
count_references() { awk '/^## References/{flag=1; next} flag && /^\[\^?[0-9]+\]/{c++} END{print c+0}' "$1" 2>/dev/null || echo 0; }
count_words() { wc -w < "$1" 2>/dev/null | tr -d ' ' || echo 0; }
count_bytes() { wc -c < "$1" 2>/dev/null | tr -d ' ' || echo 0; }
count_h2() { grep -cE '^## ' "$1" 2>/dev/null || echo 0; }
count_h3() { grep -cE '^### ' "$1" 2>/dev/null || echo 0; }

{
  echo "# Palmyra X5 vs Claude — synthesizer eval (3 cases)"
  echo
  echo "Generated: $(date +%Y-%m-%d\ %H:%M:%S)"
  echo
  echo "Both backends read the **identical** findings files from the shared"
  echo "\`\$WORK_DIR/<slug>/\` directories. Only the synthesizer model differs."
  echo
  echo "- **Claude reports**: \`\$WORK_DIR/<slug>/<slug>-report.md\` (produced by the default synthesizer agent in prior sessions)"
  echo "- **Palmyra reports**: \`evals/palmyra-vs-claude/<slug>-palmyra.md\` (produced by \`scripts/synthesize_palmyra.py\` during this spike)"
  echo
  echo "## Summary table"
  echo
  echo "| # | Slug | Input bytes | Claude report bytes | Palmyra report bytes | Claude words | Palmyra words | Claude cites | Palmyra cites | Claude refs | Palmyra refs |"
  echo "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"
  i=1
  for slug in "${SLUGS[@]}"; do
    work="$WORK_ROOT/$slug"
    claude="$work/$slug-report.md"
    palmyra="$EVAL_DIR/$slug-palmyra.md"
    # Sum input bytes from all findings files (excludes report files)
    in_bytes=0
    for f in "$work"/*.md; do
      name=$(basename "$f")
      case "$name" in *-report*.md) continue ;; esac
      [ -f "$f" ] || continue
      in_bytes=$(( in_bytes + $(count_bytes "$f") ))
    done
    cb=$(count_bytes "$claude"); pb=$(count_bytes "$palmyra")
    cw=$(count_words "$claude"); pw=$(count_words "$palmyra")
    cc=$(count_citations "$claude"); pc=$(count_citations "$palmyra")
    cr=$(count_references "$claude"); pr=$(count_references "$palmyra")
    echo "| $i | \`$slug\` | $in_bytes | $cb | $pb | $cw | $pw | $cc | $pc | $cr | $pr |"
    i=$((i+1))
  done
  echo

  echo "## Per-case structural diff"
  echo
  for slug in "${SLUGS[@]}"; do
    work="$WORK_ROOT/$slug"
    claude="$work/$slug-report.md"
    palmyra="$EVAL_DIR/$slug-palmyra.md"
    echo "### $slug"
    echo
    echo "\`\`\`"
    printf "%-30s %15s %15s\n" "metric" "Claude" "Palmyra"
    printf "%-30s %15s %15s\n" "------" "------" "-------"
    printf "%-30s %15s %15s\n" "bytes" "$(count_bytes "$claude")" "$(count_bytes "$palmyra")"
    printf "%-30s %15s %15s\n" "words" "$(count_words "$claude")" "$(count_words "$palmyra")"
    printf "%-30s %15s %15s\n" "H2 sections (##)" "$(count_h2 "$claude")" "$(count_h2 "$palmyra")"
    printf "%-30s %15s %15s\n" "H3 sections (###)" "$(count_h3 "$claude")" "$(count_h3 "$palmyra")"
    printf "%-30s %15s %15s\n" "citation markers [N]" "$(count_citations "$claude")" "$(count_citations "$palmyra")"
    printf "%-30s %15s %15s\n" "unique [N] markers" "$(count_unique_cites "$claude")" "$(count_unique_cites "$palmyra")"
    printf "%-30s %15s %15s\n" "references entries" "$(count_references "$claude")" "$(count_references "$palmyra")"
    echo "\`\`\`"
    echo
    echo "**Claude Executive Summary head:**"
    echo
    awk '/^## Executive Summary/{flag=1; next} /^## /{if(flag) exit} flag' "$claude" | head -20
    echo
    echo "**Palmyra Executive Summary head:**"
    echo
    awk '/^## Executive Summary/{flag=1; next} /^## /{if(flag) exit} flag' "$palmyra" | head -20
    echo
    echo "---"
    echo
  done

  echo "## Qualitative review checklist (fill in manually after eyeballing)"
  echo
  echo "For each case, score 1 (worse) / 0 (tie) / +1 (better) — Palmyra relative to Claude:"
  echo
  echo "| Case | Structure fidelity | Citation discipline | Prose tightness | Coverage | Actionability | Verdict |"
  echo "|---|---|---|---|---|---|---|"
  for slug in "${SLUGS[@]}"; do
    echo "| \`$slug\` | ? | ? | ? | ? | ? | ? |"
  done
  echo
  echo "## Cost & latency (from run)"
  echo
  echo "| Case | Input tokens | Output tokens | Latency | Cost (USD) |"
  echo "|---|---:|---:|---:|---:|"
  echo "| aws-health-api | 8,811 | 3,421 | 45.8 s | \$0.0258 |"
  echo "| bedrock-guardrails | 16,716 | 4,218 | 57.7 s | \$0.0353 |"
  echo "| bedrock-automated-reasoning | 25,721 | 3,882 | 55.3 s | \$0.0387 |"
  echo
  echo "Palmyra X5 pricing used: \$0.60/1M input, \$6.00/1M output."
} > "$OUT"

echo "Wrote $OUT"
wc -l "$OUT"
