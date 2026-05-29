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

```bash
# Interactive (auto-detects installed agents)
npx skills add https://github.com/praveenc/skills --skill <skill-name>

# Target a specific agent globally
npx skills add https://github.com/praveenc/skills --skill <skill-name> -a pi -g
npx skills add https://github.com/praveenc/skills --skill <skill-name> -a claude-code -g

# List available skills
npx skills add https://github.com/praveenc/skills --list
```

See each skill's own README for skill-specific setup (API keys, Kiro CLI registration, etc.).

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

- **Production-grade**: every skill is tested, documented, versioned, and ships with an eval harness
- **Contract-first**: research skills write a research contract (scope, exclusions, factual anchors) before any search runs
- **Fail-loudly**: silent fallbacks to placeholder API keys or CWD-relative paths are treated as bugs
- **Context-lean**: heavy references load conditionally so base context stays small
- **Cross-agent**: all skills target the industry-standard SKILL.md format (55+ agents supported via the skills CLI)

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
