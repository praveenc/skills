# agent-code-discipline

Behavioral guidelines for LLM coding agents that reduce overcomplication, silent assumptions, scope creep, and unfocused execution. Distilled from Andrej Karpathy's observations on agent-assisted coding workflows.

## Usage

Drop `SKILL.md` into your agent's system prompt, CLAUDE.md, .cursorrules, or skill loader. The file is self-contained (~190 lines, ~2300 tokens).

Reference files in `references/` provide concrete before/after examples - load conditionally to keep base context lean:
- `examples-generic.md` - General coding examples (Python) for any code task
- `examples-aws-cdk.md` - CDK infrastructure examples (Lambda, DynamoDB, S3, Step Functions)
- `examples-aws-bedrock.md` - Bedrock/AgentCore examples (invoke, agents, guardrails, agent loop)
- `examples-aws-compositions.md` - Multi-service architecture patterns (RAG, orchestration, event-driven, streaming)

## Structure

```
karpathy-coding-discipline/
├── SKILL.md                      # Core principles (always loaded)
├── README.md                     # This file
├── references/
│   ├── examples-generic.md       # Generic coding contrast examples
│   ├── examples-aws-cdk.md       # 4 CDK contrast examples
│   ├── examples-aws-compositions.md  # 5 multi-service architecture patterns
│   └── examples-aws-bedrock.md   # 4 Bedrock/AgentCore contrast examples
├── evals/
│   └── evals.json                # 8 test cases to verify agent behavior
└── audit-report.md               # Best-practices audit
```

## Principles

1. **Think Before Coding** - Surface assumptions, ask before implementing ambiguous requests
2. **Simplicity First** - Minimum code that solves the problem, nothing speculative
3. **Surgical Changes** - Touch only what you must, match existing style
4. **Goal-Driven Execution** - Define success criteria, loop until verified

## Triggers

This skill activates on: coding discipline, simplicity, overengineering, scope creep, surgical changes, code review, think before coding, keep it simple, too complex, reduce complexity.

## Origin

Based on [Andrej Karpathy's observations](https://x.com/karpathy/status/1886192184808149383) on Claude Code (early 2026) and the [multica-ai/andrej-karpathy-skills](https://github.com/multica-ai/andrej-karpathy-skills) repo.
