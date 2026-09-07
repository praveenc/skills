# :mag: aws-deep-research

[![skills.sh](https://skills.sh/b/praveenc/skills)](https://skills.sh/praveenc/skills)

Multi-source, parallelized deep research with facet-based query decomposition,
subagent dispatch, and synthesized citations.

**AWS-first** (dispatches specialist subagents against AWS docs via `llms.txt`
indexes - Bedrock, AgentCore, Well-Architected - plus AWS Pricing, GitHub, AWS
blog feeds, and the open web), and also handles **generic / non-AWS research**
the model cannot answer from memory - library internals, software architecture
patterns, methodology deep-dives, cross-vendor comparisons, and primary-source
research (papers, gists, blog posts).

The skill auto-classifies each query as `aws` or `generic` in Step 1b and
routes to appropriate sources; generic queries skip the AWS MCP researcher and
fall through to web search + GitHub with the same facet-decomposition and
contract-first discipline. It deliberately does **not** activate for code
authoring, local debugging, AWS CLI operations, or anything answerable from the
current conversation - see `evals/routing.json` for the frozen boundary.

## Install

```bash
npx skills add https://github.com/praveenc/skills --skill aws-deep-research
```

## How it works

```
Query → Contract → Slug → Decompose → Dispatch → Verify → Synthesize → Gate → Present
```

<sub><a href="./docs/workflow.d2">D2 source for the workflow diagram</a></sub>

The flow enforced by `SKILL.md`:

1. **Research contract** grounds every claim (scope, exclusions, factual anchors)
2. **Facet-labeled decomposition** (2-3 subqueries per source, printed to the user before any API credit is spent)
3. **Subagents dispatch in one round**, writing findings to disk, never into the parent's context - native `Agent` tool on Claude Code / SDK, `subagent` on Kiro, headless process fan-out on pi (parallel cap is per-harness)
4. **Size gate** (`scripts/verify_findings.sh`) catches silent failures and failure/skip notes
5. **Synthesizer** re-reads the contract to ground all citations, translating internal evidence tags to reader confidence labels
6. **Report gate** (`scripts/lint_report.py`) checks sections, citation integrity, size, and tag leakage - one repair attempt - and writes a `.lint.json` audit sidecar
7. **Present**: copy to `~/.aws-deep-research/outputs/`, summarize key findings and gaps

## Testing

```bash
bash evals/run_tests.sh           # model-free unit tests (pytest)
bash evals/run.sh --static         # eval-corpus structure gate
bash evals/run.sh --selftest       # eval check-engine self-test
```

Trigger, behavior, and fault corpora live in `evals/` - see
[evals/README.md](./evals/README.md) for the run protocol, isolation rules,
splits, and release gates.

## Example queries

```
# AWS-centric
> How does Bedrock AgentCore compare to Strands Agents SDK?
> Cost-optimize a serverless RAG pipeline on Bedrock + OpenSearch
> Review best practices for Bedrock Guardrails in production

# Cross-vendor / comparative
> Disaggregated inference: NVIDIA Rubin CPX vs Groq LPU vs AWS Trainium
> Compare AWS Bedrock vs Azure OpenAI vs Vertex AI for enterprise RAG

# Non-AWS / generic
> What is Karpathy's LLM knowledge-base pattern and how do I adapt
  an Obsidian vault?
> Circuit breaker pattern in distributed systems - production lessons
> Context engineering for agents: write, select, compress, isolate
```

## Configuration

The skill uses these keys (all optional; it gracefully degrades):

| Variable | Purpose | Free tier |
|---|---|---|
| `BRAVE_SEARCH_API_KEY` | Web search | 2,000 queries/month |
| `TAVILY_API_KEY` | Alternate web search | 1,000 queries/month |
| `GITHUB_TOKEN` | GitHub repo search (REST) | 5,000/hr with token vs 60/hr without |
| AWS credentials (via `~/.aws/config` or env) | AWS Pricing + docs fallback (llms.txt is the primary docs source and needs none) | - |

Create `~/.config/aws-deep-research/config.env` from
`scripts/.env.example`, populate only the keys you need, and set mode `600`.
The config stays outside the installed skill tree so scanners and package
publishers cannot ingest credentials.

## Artifacts

Research artifacts write to `~/.aws-deep-research/work/<slug>/` and final
reports to `~/.aws-deep-research/outputs/`. Override via `RESEARCH_WORK_DIR` /
`REPORT_OUTPUT_DIR` in the external config file.

## Full documentation

See [SKILL.md](./SKILL.md) for the complete workflow specification.
