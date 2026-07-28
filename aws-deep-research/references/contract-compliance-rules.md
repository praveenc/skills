# Research Contract Compliance Rules

These rules apply to ALL research subagents and the synthesizer.
**Read the research contract FIRST - before any searches or file reads.**

## Contents

- [For Researchers](#for-researchers)
- [Evidence Tagging (all researchers)](#evidence-tagging-all-researchers)
- [For Synthesizer](#for-synthesizer)

## For Researchers

1. **Read `research-contract.md` as your very first step** - before running
   any search scripts or reading any files
2. **Shape your search queries using the contract's constraints:**
   - Entity exclusions become NOT/exclude operators in queries
   - Entity inclusions become required terms
   - Temporal constraints become date filters or recency keywords
3. When writing output, tag any data that does NOT match the contract's
   entity or version constraints with "⚠️" and the actual version/entity
4. Never silently include version-mismatched data without a label
5. **Evidence tag every finding** (see "Evidence Tagging" below) so the
   synthesizer can weight sources and detect contradictions

## Evidence Tagging (all researchers)

Every discrete finding you write MUST carry a compact evidence tag of the
form `{authority·date}`. This is the single most important signal the
synthesizer uses to weight conflicting sources and assign confidence - an
untagged finding is treated as lowest-confidence.

### Authority levels (pick the most specific that applies)

| Tag | Meaning | Examples |
|---|---|---|
| `official` | First-party authoritative docs / specs | AWS docs, AWS What's New, service API reference, standards bodies, a project's own README |
| `vendor-claim` | First-party **marketing / performance claim**, not independently verified | press releases, launch blogs, "up to 10x faster", benchmarks self-reported by the vendor |
| `third-party` | Independent press, analysts, or neutral benchmarks | SemiAnalysis, Tom's Hardware, an independent benchmark repo |
| `community` | Practitioner-written, non-authoritative | dev.to, re:Post, community.aws, personal blogs, forum answers |

### Date component

- Use the publication/launch date when known: `{official·2026-03}` or
  `{vendor-claim·2025-09}`. Month precision is enough; year alone is fine.
- Use `undated` when no date is discoverable: `{community·undated}`.
- For pricing, the date is the **query date**, not a publication date.

### Format in findings files

Append the tag to the claim, before its citation marker. Examples:

```
- Rubin CPX delivers 30 PFLOPs FP4 {vendor-claim·2025-09} [3]
- Neuron 2.24 shipped disaggregated inference on 2025-07-02 {official·2025-07} [4]
- Practitioners report cold-start regressions on the Java runtime {community·2024} [9]
```

A single finding may legitimately carry two tags when a claim is corroborated
by an independent source - e.g. `{vendor-claim·2026-03}{third-party·2026-04}`.
That corroboration is itself high-value signal; keep both tags.

### Concrete Examples: Contract → Query Transformation

**Contract says**: Include: S3 Files, NFS | Exclude: EFS
```
# aws_doc_search.py
-q "S3 Files NFS support" -q "S3 file system access NOT EFS"

# brave_search.py
"Amazon S3 Files NFS -EFS -\"Elastic File System\""
```

**Contract says**: Include: Claude Opus 4.6, Sonnet 4.6 | Exclude: Claude 3.x
```
# aws_doc_search.py
-q "Bedrock Claude Opus 4.6 pricing" -q "Claude Sonnet 4.6 inference"

# tavily_search.py
"Claude Opus 4.6 vs Sonnet 4.6 benchmark -\"Claude 3\" -\"Claude 3.5\""
```

**Contract says**: Temporal: features launched after 2026-03-01
```
# brave_search.py (use freshness filter)
"<query>" --freshness pm   # past month

# sitemap_feed_extractor.py (filter by date in post-processing)
--top 50 --json  # then filter titles by date > 2026-03-01
```

## For Synthesizer

1. Read `research-contract.md` FIRST, before reading any research output files
2. Cross-validate every pricing table, benchmark score, and comparison
   against the contract's entity and temporal constraints
3. Data matching constraints → include as-is
4. Data for older/different versions → include with explicit ⚠️ label:
   "⚠️ This data is for Claude 3.5 - current 4.6 pricing may differ"
5. Derived claims (cost ratios, calculated savings, percentages) must
   cite a source or carry a ⚠️ label
6. If significant proxy data was used, add a "Data Accuracy Notes"
   subsection before References
7. **Weight evidence by its tag** when sources conflict (see below)
8. **Never silently drop a contradiction during deduplication.** If two
   sources make incompatible claims, surface both in the Consensus &
   Contradictions section rather than picking one and discarding the other

### Evidence Weighting Order

When two findings conflict, prefer them in this order and say so explicitly:

1. `official` and `third-party` (independent) - highest weight
2. `vendor-claim` **corroborated** by an `official`/`third-party` tag
3. `vendor-claim` uncorroborated - report as a claim, attribute it to the
   vendor, and label it "vendor-reported, not independently verified"
4. `community` - useful for real-world signal and reality-checks, but never
   overrides `official` on a factual point; treat as directional
5. `undated` / untagged - lowest; use only when nothing better exists

A newer date breaks ties within the same authority level (recency wins).
