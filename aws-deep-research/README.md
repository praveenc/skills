# :mag: aws-deep-research

[![skills.sh](https://skills.sh/b/praveenc/skills)](https://skills.sh/praveenc/skills)

Multi-source, parallelized deep research with facet-based query decomposition,
subagent dispatch, and synthesized citations.

**AWS-first** (dispatches specialist subagents against AWS Knowledge MCP,
AWS Pricing MCP, Bedrock AgentCore docs, AWS blog feeds, GitHub, and the open
web), and also handles **generic / non-AWS research** the model cannot answer
from memory - library internals, software architecture patterns, methodology
deep-dives, cross-vendor comparisons, and primary-source research (papers,
gists, blog posts).

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

<p align="center">
  <img src="./docs/workflow.png"
       alt="aws-deep-research workflow: query, research contract, facet decomposition, parallel subagent dispatch, findings files, size-gate, synthesis, report"
       width="720">
</p>

<p align="center"><sub>
  <a href="./docs/workflow.png">Open full-size PNG</a> &middot;
  <a href="./docs/workflow.d2">View D2 source</a>
</sub></p>

The eight-step flow enforced by `SKILL.md`:

1. **Research contract** grounds every claim (scope, exclusions, factual anchors)
2. **Facet-labeled decomposition** (2-3 subqueries per source, printed to the user before any API credit is spent)
3. **Domain blocklist** filters URLs pre-fetch
4. Up to **4 subagents dispatch in parallel** writing findings to disk (never into the parent's context)
5. **Size gate** (`scripts/verify_findings.sh`) catches silent failures
6. **Synthesizer** re-reads the contract to ground all citations in the final report
7. **Report gate** (`scripts/lint_report.py`) checks sections, citation integrity, and size, with one repair attempt

## Testing

```bash
bash scripts/run_tests.sh          # 147 model-free tests
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
| `GITHUB_TOKEN` | Higher GitHub API rate limits | 5,000/hr with token vs 60/hr without |
| AWS credentials (via `~/.aws/config` or env) | AWS docs + pricing + Bedrock AgentCore MCP | - |

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
