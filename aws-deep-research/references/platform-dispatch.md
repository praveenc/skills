# Kiro CLI Subagent Dispatch

## How Kiro Dispatches Subagents

Agents are registered as JSON + MD pairs in `~/.kiro/agents/`. Dispatch by
agent name (e.g., `aws-mcp-researcher`). Kiro discovers agents via
`ListAgents` using the `.json` config's `name` and `description` fields.

## Critical Constraint: Max 4 Parallel Subagents

Kiro CLI supports **max 4 parallel subagents per round**. Plan dispatch
rounds to minimize total wall-clock time:

### Optimal Batching

**Simple queries (2-3 subagents)**: single round + synthesizer
```
Round 1: [aws-mcp-researcher, web-content-researcher]  → ~2 min
Round 2: [synthesizer]                                   → ~2 min
Total: ~4 min
```

**Comprehensive queries (4+ subagents)**: two rounds + synthesizer
```
Round 1: [aws-mcp-researcher, web-content-researcher, github-researcher, agentcore-researcher]  → ~3 min
Round 2: [synthesizer]                                                                            → ~2 min
Total: ~5 min
```

**With diagram (optional)**: add to synthesizer round if slot available
```
Round 2: [synthesizer, diagram-generator]  → ~2 min (parallel)
```

### Task Instructions Template

Include in each subagent's task string:
- The **resolved `SKILL_DIR` path**
- The **research contract file path** (`$WORK_DIR/<slug>/research-contract.md`)
- The original research query
- The specific subqueries assigned to that subagent
- The full output file path (e.g., `$WORK_DIR/<slug>/aws-docs.md`)
- The log directory: `$WORK_DIR/<slug>`
- For web-content-researcher: feed URLs from blog-categories.md (if blog research needed)
- For Bedrock queries: tell aws-mcp-researcher to consult `references/bedrock-llms-txt.md`
