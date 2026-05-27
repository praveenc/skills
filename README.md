# Praveen's Agent Skills

[![skills.sh](https://skills.sh/b/praveenc/skills)](https://skills.sh/praveenc/skills)
[![SKILL.md](https://img.shields.io/badge/format-SKILL.md-purple)](https://skills.sh/docs)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

> Production-grade skills for AI coding agents. Tested, documented, and versioned.

Built for [pi](https://github.com/mariozechner/pi-coding-agent),
[Claude Code](https://docs.claude.com/en/docs/claude-code), and
[Kiro CLI](https://kiro.dev) (with others likely compatible via the
industry-standard SKILL.md format).

## Skills

### :mag: Research & Analysis

- **[aws-deep-research](./aws-deep-research/)** - Multi-source, parallelized
  deep research with facet-based query decomposition, subagent dispatch, and
  synthesized citations. Optimized for AWS topics but works equally well on
  non-AWS / generic research queries. Enforces a contract-first research
  workflow with blind-evaluated synthesis quality.

  ```bash
  npx skills add https://github.com/praveenc/skills --skill aws-deep-research
  ```

  See [aws-deep-research/SKILL.md](./aws-deep-research/SKILL.md) for the
  full workflow documentation.

### :bar_chart: Visualization

- **[research-report-visuals](./research-report-visuals/)** - Transform
  markdown research reports into interactive, single-file HTML visual
  narratives. Analyzes report type, extracts narrative arc, chooses an
  appropriate visual mode (narrative-scroll, verdict-split, platform-cards,
  timeline, problem-solution), and produces a self-contained HTML file the
  reader can absorb in 60 seconds. Library-agnostic (Highcharts for
  quantitative data, SVG/CSS for architecture and narrative). Ships with
  opinionated typography, color systems, and a visual signature framework
  that prevents generic template output.

  ```bash
  npx skills add https://github.com/praveenc/skills --skill research-report-visuals
  ```

  See [research-report-visuals/SKILL.md](./research-report-visuals/SKILL.md)
  for the full workflow documentation.

### :shield: Coding Discipline

- **[agent-code-discipline](./agent-code-discipline/)** - Enforce four
  coding-agent principles distilled from Andrej Karpathy's observations:
  *think before coding*, *simplicity first*, *surgical changes*, and
  *goal-driven execution*. Reduces the most common LLM failure modes:
  silent assumptions, premature abstraction, scope creep, and unfocused
  execution. Ships with domain-specific reference examples (generic Python,
  AWS CDK, AWS Bedrock, multi-service compositions).

  ```bash
  npx skills add https://github.com/praveenc/skills --skill agent-code-discipline
  ```

  See [agent-code-discipline/SKILL.md](./agent-code-discipline/SKILL.md)
  for the full principles and usage.

### :clipboard: Quality & Compliance

- **[skill-audit](./skill-audit/)** - Audit an agent skill directory against
  published skill-authoring best practices. Produces a scorecard with
  prioritized findings report. Includes a scoring rubric reference and
  preflight validation script.

  ```bash
  npx skills add https://github.com/praveenc/skills --skill skill-audit
  ```

  See [skill-audit/SKILL.md](./skill-audit/SKILL.md) for usage.

## Installation

### Using the skills CLI (recommended)

```bash
# Interactive (auto-detects installed agents)
npx skills add https://github.com/praveenc/skills --skill aws-deep-research

# Target a specific agent globally
npx skills add https://github.com/praveenc/skills --skill aws-deep-research -a pi -g
npx skills add https://github.com/praveenc/skills --skill aws-deep-research -a claude-code -g
```

### Kiro CLI (requires the bundled `register.sh`)

Kiro CLI needs both the skill content AND an agent registration JSON.
The skill ships a one-shot installer that handles both:

```bash
git clone https://github.com/praveenc/skills.git /tmp/praveenc-skills
bash /tmp/praveenc-skills/aws-deep-research/setup/register.sh
```

This copies the skill to `~/.kiro/skills/aws-deep-research/` AND registers
the parent agent + all 6 subagents under `~/.kiro/agents/`. Launch with:

```bash
kiro-cli chat --agent aws-deep-research
```

## Configuration (required for full functionality)

After install, each skill that needs API keys ships a `scripts/.env.example`.
Copy it to `scripts/.env` and fill in the blanks:

```bash
cp ~/.claude/skills/aws-deep-research/scripts/.env.example \
   ~/.claude/skills/aws-deep-research/scripts/.env
$EDITOR ~/.claude/skills/aws-deep-research/scripts/.env
```

**aws-deep-research** uses these keys (all optional, but the skill
gracefully degrades, e.g. without `BRAVE_SEARCH_API_KEY` it falls back
to Tavily; without AWS credentials it skips the AWS docs/pricing
MCP calls):

| Variable | Purpose | Free tier |
|---|---|---|
| `BRAVE_SEARCH_API_KEY` | Web search | 2,000 queries/month |
| `TAVILY_API_KEY` | Alternate web search | 1,000 queries/month |
| `GITHUB_TOKEN` | Higher GitHub API rate limits | 5,000/hr with token vs 60/hr without |
| AWS credentials (via `~/.aws/config` or env) | AWS docs + pricing + Bedrock AgentCore MCP | - |

The skill writes research artifacts to `~/.aws-deep-research/work/<slug>/`
and final reports to `~/.aws-deep-research/outputs/`. Override either via
`RESEARCH_WORK_DIR` / `REPORT_OUTPUT_DIR` in `.env`.

## Compatibility matrix

| Skill | pi | Claude Code | Kiro CLI | Cursor | Notes |
|---|:-:|:-:|:-:|:-:|---|
| aws-deep-research | ✅ | ✅ | ✅ | ✅ | Kiro CLI needs `setup/register.sh` post-install |
| research-report-visuals | ✅ | ✅ | ✅ | ✅ | No API keys needed, pure prompt-driven |
| agent-code-discipline | ✅ | ✅ | ✅ | ✅ | Behavioral guidelines, no API keys needed |
| skill-audit | ✅ | ✅ | ✅ | ✅ | Includes preflight shell script |

## Versioning

Each skill ships with its own `SKILL.md` `metadata.version` field and a
`meta/CHANGELOG.md` in the source tree (excluded from deployed copies).
Breaking changes bump the minor (e.g. 6.x to 7.0); additive improvements
bump the patch (6.9 to 6.10); bug fixes bump the patch.

## Philosophy

These skills aim to be:

- **Contract-first**: every research task writes a research contract
  (scope, exclusions, factual anchors) before any search runs. No
  "just Google it and hope" flows.
- **Subagent-disciplined**: parent never reads raw content; researcher
  findings land on disk, synthesizer reads multiple files together.
- **Fail-loudly**: silent fallbacks to CWD-relative paths or placeholder
  API keys are treated as bugs. You should always know where artifacts
  are going and whether a needed credential is missing.
- **Facet-decomposed**: one natural-language question decomposes into
  2-3 focused keyword queries with labeled facets (reference/tutorial,
  official/community, capabilities/pricing, etc.), printed to the
  user before any API credit is spent.
- **Blind-evaluated where it matters**: synthesizer backend choice
  (Sonnet 4.6 vs Palmyra X5) was decided via two blind-read rounds
  with the evaluator unable to see the model label. Reproducible harness
  shipped alongside the skill.

## Contributing

PRs welcome. For a new skill, follow the
[industry-standard SKILL.md format](https://skills.sh/docs) and include:

- `SKILL.md` with YAML frontmatter (`name`, `description`, `metadata.version`)
- `agents/` for subagents (JSON + MD pairs) if the skill is multi-agent
- `references/` for on-demand knowledge loaded by the skill
- `scripts/` for executable tools, with a `.env.example` if keys are needed
- `setup/` for Kiro CLI or other platform-specific bootstrap (optional)
- `meta/CHANGELOG.md` - gitignored from shipped copies but retained in source

Don't commit: `.env`, `output/`, `work/`, `meta/`, `__pycache__/`.

## License

[MIT](./LICENSE) - Copyright (c) 2026 Praveen Chamarthi

---

<div align="center">
  <sub>Built for the AI community ❤️</sub>
</div>
