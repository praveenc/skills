# Direct URL & llms.txt Handling

When the user's query includes direct URLs or references a specific
domain/project, check for an `llms.txt` file first - it provides
structured, LLM-optimized documentation far more efficient than scraping.

## Architecture rule (non-negotiable)

**The parent NEVER fetches.** A direct URL is a research source like any
other, so it goes through a subagent: `web-content-researcher` fetches it and
writes `$WORK_DIR/<slug>/direct-fetch.md`. The parent passes only that
**path** to the synthesizer - never fetched content, and never page text
inside a task string.

This is the same context-isolation guarantee as every other source (see
SKILL.md **Architecture Rule**). Fetching in the parent would put raw page
content into the one context the whole design keeps clean.

## Detection

- User provides a URL → extract the domain
- User mentions a specific project/tool/library → infer the likely docs URL

## Dispatch

Add `direct-urls` to the `web-content-researcher` brief (per
[subagent-task-contract.md](subagent-task-contract.md)) and tell it to write
`direct-fetch.md` in addition to its normal `web-content.md`. The blocklist
and the public-web approval gate apply to direct URLs exactly as they do to
search results.

## Subagent workflow (inside web-content-researcher)

1. Check each URL's domain against `$SKILL_DIR/scripts/blocklist.txt`. Skip
   blocked domains and record the skip.
2. Try `fetchv2:fetchv2_fetch_llms_txt` on `https://<domain>/llms.txt`.
3. If found → parse the structured index, then
   `fetchv2:fetchv2_fetch_batch` the most relevant linked pages (max 5).
4. If 404 → `fetchv2:fetchv2_fetch` the direct URL(s), or
   `fetchv2:fetchv2_discover_links` then `fetch_batch` the top results.
5. Re-fetch at `max_length_per_url` 15000-20000 for any primary source whose
   response carries a `<!-- Truncated:` marker.
6. Write paraphrased evidence records (never raw page prose) to
   `direct-fetch.md`, each with its `{authority·date}` tag.

## When to Use fetchv2 Tools

| Scenario | Tool |
|---|---|
| User provides a doc URL | `fetch` |
| Specific library/framework | try `llms.txt` first |
| Explore a docs site | `discover_links` then `fetch_batch` |
| Multiple doc pages | `fetch_batch` (up to 10 URLs per call) |

## Synthesis

Include `direct-fetch.md` in the synthesizer's `expected-findings-files` list
with its OK/WEAK/MISSING status from the Step 5 size gate. It is a findings
file like any other.
