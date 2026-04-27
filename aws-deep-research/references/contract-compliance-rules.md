# Research Contract Compliance Rules

These rules apply to ALL research subagents and the synthesizer.
**Read the research contract FIRST — before any searches or file reads.**

## For Researchers

1. **Read `research-contract.md` as your very first step** — before running
   any search scripts or reading any files
2. **Shape your search queries using the contract's constraints:**
   - Entity exclusions become NOT/exclude operators in queries
   - Entity inclusions become required terms
   - Temporal constraints become date filters or recency keywords
3. When writing output, tag any data that does NOT match the contract's
   entity or version constraints with "⚠️" and the actual version/entity
4. Never silently include version-mismatched data without a label

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
   "⚠️ This data is for Claude 3.5 — current 4.6 pricing may differ"
5. Derived claims (cost ratios, calculated savings, percentages) must
   cite a source or carry a ⚠️ label
6. If significant proxy data was used, add a "Data Accuracy Notes"
   subsection before References
