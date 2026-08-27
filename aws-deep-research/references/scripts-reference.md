# Scripts Reference

All scripts live in `$SKILL_DIR/scripts/` and run via `uv run`. Each supports
`--help` (except `resolve_skill_dir.sh`, which is `eval`-sourced). The `-o`
flag is mandatory on all search/scraper scripts - it targets
`$WORK_DIR/<slug>/downloads/<tool>`; without it, output lands outside the
research directory.

| Script | Used By | Cost |
|---|---|---|
| `aws_doc_search.py` | aws-mcp-researcher | Free (AWS creds) |
| `aws_pricing_search.py` | aws-mcp-researcher | Free (AWS creds) |
| `agentcore_search.py` | agentcore-researcher | Free |
| `github_search.py` | github-researcher | Free |
| `brave_search.py` | web-content-researcher | 2K/month free |
| `tavily_search.py` | web-content-researcher | 1K/month free |
| `trafilatura_scraper.py` | web-content-researcher | Free |
| `sitemap_feed_extractor.py` | web-content-researcher | Free |
| `kroki_diagram.py` | diagram-generator | Free |

## Support scripts (not research tools)

| Script | Purpose |
|---|---|
| `resolve_skill_dir.sh` | `eval`-sourced; exports `SKILL_DIR` / `WORK_DIR` pinned to the loaded install |
| `check_api_keys.sh` | Validates AWS/Brave/Tavily/GitHub/Kroki availability; prints `KEY=STATUS` lines |
| `dispatch.sh` | Headless subagent dispatch for pi / Claude Code (one process per subagent) |
| `verify_findings.sh` | Step 5 size gate; prints `<file>=OK\|WEAK\|MISSING\|UNREADABLE`, never contents |
| `lint_report.py` | Step 6 report gate; sections, citation/reference integrity, size. `--json` for runners |
| `common.py` | Shared helpers (blocklist matching, output paths) imported by the Python tools |

Test and eval tooling lives in `$SKILL_DIR/evals/`, not here - see
`evals/README.md`. `verify_findings.sh` and `lint_report.py` are the exception:
SKILL.md calls them at runtime, so they are skill tools the eval layer reuses.
