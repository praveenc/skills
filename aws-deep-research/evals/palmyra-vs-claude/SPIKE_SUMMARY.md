# Palmyra X5 Synthesizer Spike — Archived Findings

**Status**: spike complete, shelved for now. `scripts/synthesize_palmyra.py` retained in-tree as an opt-in escape hatch. Not wired into `SKILL.md` as default or auto-switching mode.

**Date**: 2026-04-26
**Skill version at time of spike**: v6.2 → v6.4
**Bedrock model evaluated**: `us.writer.palmyra-x5-v1:0` (Writer Palmyra X5, 1.04 M input / 8,192 output)
**Baseline**: `us.anthropic.claude-sonnet-4-6` (Claude Sonnet 4.6, 200 K / 64 K)

---

## Hypothesis

Palmyra X5's 1 M context window + ~5× cheaper input tokens could make it a superior synthesizer for the aws-deep-research skill, especially in a future "raw-ingest" mode where researcher subagents stop compressing their findings files to 15 KB and hand over raw content instead.

## Methodology

Single script (`scripts/synthesize_palmyra.py`) that accepts `--model-id`, so both candidates:

- Read the **identical** set of findings files from the same `$WORK_DIR/<slug>/`
- Received the **identical** system prompt + user template + temperature (0.3)
- Differed only in `--model-id` and `--max-output-tokens` (Palmyra 8,192; Sonnet 16,384)
- Had their `**Synthesizer backend**` line stripped from the output before presentation
- Were labeled A/B via `$RANDOM` coin flip with the mapping locked in a `.blind-mapping` file the evaluator (user) did not see until after voting

## Blind read 1 — cross-vendor hardware comparison

**Topic**: *"Disaggregated inference and next-generation LLM inference platforms — NVIDIA Vera Rubin (Rubin CPX), Groq LPU, AWS Trainium + Cerebras partnership, AWS native disaggregated inference"*

**Query type**: `aws` (AWS is one of several anchors; cross-vendor)
**Findings payload**: `aws-docs.md` (46 KB) + `web-content.md` (10 KB) + `github-repos.md` (6 KB) = ~63 KB total input

**Results**:

| Backend | Bytes | Words | Cites | Refs | Latency | Cost |
|---|---:|---:|---:|---:|---:|---:|
| Claude Sonnet 4.6 | 27,263 | 3,580 | 87 | 17 | 141 s | $0.058 |
| Palmyra X5 | 20,441 | 2,585 | 81 | 16 | 69 s | $0.039 |

**User verdict**: Sonnet 4.6 wins on **coverage**, **accuracy** (clarity), **structure**, and **actionability**; tie on **citation discipline** and **tightness**.

## Blind read 2 — personal workflow / methodology (non-AWS)

**Topic**: *"What is the LLM knowledge base pattern Andrej Karpathy describes? How is it useful, what problem does it solve? How to adapt an existing Obsidian vault, and what operational discipline is required?"*

**Query type**: `generic` (web search was the primary source via Brave query expansion; no AWS docs)
**Findings payload**: `web-content.md` only (24 KB, post-truncation-fix fetchv2 batch with `max_length_per_url: 20000`)

**Results**:

| Backend | Bytes | Words | Cites | Refs | Latency | Cost |
|---|---:|---:|---:|---:|---:|---:|
| Claude Sonnet 4.6 | 24,527 | 3,598 | 89 | 8 | 132 s | $0.041 |
| Palmyra X5 | 16,939 | 2,289 | 68 | 8 | 51 s | $0.027 |

**User verdict**: Sonnet 4.6 wins on **coverage** and **actionability**; tie on **accuracy**, **structure**, **citation discipline**, and **tightness**. User called out Sonnet's use of dividers and fleshed-out details as a positive, and noted "I like the way A presented it" on accuracy.

## Aggregate verdict

Two blind reads across two very different topic classes, inputs controlled byte-for-byte, neither read revealed the backend label until after scoring:

- **Sonnet 4.6 preferred in both rounds.** Never lost on any criterion across either round.
- **Palmyra X5 was consistently ~33–37% tighter and ~1.5× faster** but that brevity did not carry synthesis value — Sonnet's extra words were load-bearing, not padding.
- **Cost savings** of $0.02–$0.03 per report for Palmyra were real but too small to offset the coverage gap.
- **Output token ceiling** (8,192 ≈ 6 K words) was never hit in practice, so that ceiling didn't *directly* harm Palmyra in these tests; the quality gap came from the model, not from truncation-at-generation.

## Decision

- **Default synthesizer remains** the pi/kiro-dispatched `synthesizer` agent (Claude family).
- **`scripts/synthesize_palmyra.py` is retained** as opt-in tooling. No `SKILL.md` step dispatches it.
- **Do NOT auto-switch** to Palmyra based on input size, strategy, or intent — the evidence doesn't support it.

## What we did NOT test — deliberately shelved

The spike did NOT disprove value in these scenarios, only set them aside:

1. **Massive-input raw-ingest** (300 KB+ of uncompressed researcher output). Palmyra's 1 M context would matter; Sonnet would stress its 200 K. Never tested because the spike used the standard 15 KB-per-file compressed flow.
2. **High-volume batch synthesis**, e.g. a nightly job that produces 50+ reports. Palmyra's $0.02–$0.03/report edge compounds to a real $/month delta. Never tested at volume.
3. **Long-document domains Writer explicitly trained for**: *"Regulatory & compliance intelligence"* (10-K filings, contract analysis), *"Revenue & reporting automation"* (full RFPs ingested), *"Customer & research insights"* (thousands of survey responses). These are the stated use-cases Writer markets Palmyra X5 for. Our research-synthesis benchmark is adjacent but not identical.
4. **Tuned Palmyra prompt**: we used the same system prompt for both models. A Palmyra-specific prompt (mandating exhaustive citation coverage, forcing explicit section-per-vendor) might narrow the coverage gap.

**If any of these become real needs** (especially #3 — 10-K / compliance-style ingestion — or #2 — batch volume), re-open the spike rather than assume the verdict above transfers. The verdict is specific to **research-report synthesis from mixed AWS-docs + web-content + github-repos findings at ~50–150 KB input**.

## Artifacts preserved in this directory

```
evals/palmyra-vs-claude/
├── SPIKE_SUMMARY.md                                    ← this file
├── compare.sh                                          ← metrics harness (round 1)
├── COMPARISON.md                                       ← round 1 side-by-side (3 existing-report cases)
│
├── # Round 1 — 3 existing reports re-synthesized via Palmyra
├── aws-health-api-overview-sentiment-oss-alternatives-palmyra.md
├── bedrock-guardrails-contextual-grounding-enterprise-accuracy-palmyra.md
├── bedrock-automated-reasoning-checks-rag-oss-alternatives-palmyra.md
│
├── # Round 1b — cross-vendor hardware blind read (fresh research)
├── disaggregated-inference-palmyra.md
├── disaggregated-inference-sonnet46.md
├── disaggregated-inference-ReportA.md                  ← was Sonnet 4.6
├── disaggregated-inference-ReportB.md                  ← was Palmyra X5
│
├── # Round 2 — Karpathy KB blind read (non-AWS / generic)
├── karpathy-kb-palmyra.md
├── karpathy-kb-sonnet46.md
├── karpathy-kb-ReportA.md                              ← was Sonnet 4.6
└── karpathy-kb-ReportB.md                              ← was Palmyra X5
```

Work-dir artifacts (findings files + contracts + blind mappings) are under `~/.aws-deep-research/work/{disaggregated-inference-llm-platforms-apr26,karpathy-llm-knowledge-basis-obsidian-workflow}/`.

## Reopening criteria

Reopen the spike if any of the following is true:

- The default `comprehensive` strategy starts regularly producing >300 KB findings payloads
- You want to synthesize a single 10-K, 8-K, or similarly long regulatory filing as part of a research session
- You plan to run batched / automated synthesis that produces >50 reports/month
- A new Palmyra release ships a higher output-token ceiling (>16 K out) or a structured-output mode that improves citation discipline
- The user (or another evaluator) wants to A/B test a Palmyra-tuned prompt variant

Until then, the script is here but untouched.
