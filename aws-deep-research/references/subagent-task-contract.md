# Subagent Task-Input Contract

Every subagent dispatched by the parent MUST receive these fields in its
task brief. This reference is the single source of truth - subagent-specific
`.md` files reference this file rather than restating the contract.

## Mandatory fields (all subagents)

| Field | Purpose | Example |
|---|---|---|
| `SKILL_DIR` | Absolute path to the skill root - lets the subagent find `scripts/`, `references/`, and `.env` | `/Users/alice/.kiro/skills/aws-deep-research` |
| `work-dir` | Absolute path to `$WORK_DIR/<slug>/` - where downloads and findings files live | `/Users/alice/.aws-deep-research/work/bedrock-agent-deployment/` |
| `research-contract` | Absolute path to the contract file - **first thing each subagent reads** | `$work-dir/research-contract.md` |
| `original-query` | Verbatim user question - for context and fallback reasoning | "Building autonomous agents on Bedrock..." |
| `query-type` | `aws` or `generic` - shapes search depth and source selection | `aws` |
| `subqueries` | **2-3 facet-labeled strings per Query Decomposition rule** (see `references/search-strategy.md`). Each labeled with its facet name. | `[("AWS Bedrock Agents deployment options", "reference"), ("multi-agent collaboration supervisor patterns", "architecture")]` |
| `findings-file` | Absolute path where the subagent writes its structured findings. Always inside `work-dir/`. | `$work-dir/aws-docs.md` |

## Optional fields (subagent-specific)

| Subagent | Extra fields |
|---|---|
| `web-content-researcher` | `feed-urls` (list of user-approved blog feed URLs), `direct-urls` (user-supplied URLs to fetch into `direct-fetch.md`; see `references/direct-url-handling.md`), `fetchv2-max-length` (default 8000; bump to 15000-20000 for known primary sources), `public-web-approved: true` (mandatory explicit consent gate) |
| `aws-mcp-researcher` | `pricing-flag` (true if pricing intent), `region` (default `us-east-1`) |
| `github-researcher` | `top-n` (default 5) |
| `agentcore-researcher` | `top-n` (default 3) |
| `synthesizer` | `intents` (list), `expected-findings-files` (list of `{name, status: OK|WEAK|MISSING}`) |
| `diagram-generator` | `report-path`, `diagram-brief` (what to diagram, from Executive Summary scan) |

## Subagent responsibility on receipt

Every subagent, before doing anything else:

1. Read `research-contract` - this is the hard filter for all findings.
2. Read `references/contract-compliance-rules.md` for the per-subagent
   "stay-within-contract" rules.
3. Confirm `findings-file` path is inside `work-dir/` - never write elsewhere.
4. For each subquery, tag all results with its facet label so the synthesizer
   can see which facet yielded which evidence.
5. `web-content-researcher` MUST stop unless `public-web-approved: true` is
   present in the brief.

## What NOT to include in subagent task briefs

- **Raw content from previous subagents** - the parent must not read findings
  files. Only file paths and size-gate status propagate between subagents.
- **Speculative context** - if a fact isn't in the contract, it doesn't
  belong in the task brief. Subagents must earn their context by reading
  the contract.
- **Findings files from sibling subagents** - only the synthesizer reads
  multiple findings files together.

## Transparency rule reminder

Before dispatching, the parent prints the decomposed subqueries to the user
(per `SKILL.md` Step 4). That printout IS the user-facing confirmation of
what will hit each API - it is not logged separately.
