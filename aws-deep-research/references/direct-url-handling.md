# Direct URL & llms.txt Handling

When the user's query includes direct URLs or references a specific
domain/project, check for an `llms.txt` file first — it provides
structured, LLM-optimized documentation far more efficient than scraping.

## Detection

- User provides a URL → extract the domain
- User mentions a specific project/tool/library → infer the likely docs URL

## Workflow

1. Try `fetch_llms_txt` on `https://<domain>/llms.txt`
2. If found → parse the structured content, use `fetch_batch` to pull
   the most relevant linked pages (max 5). Add findings directly to the
   research output — no subagent needed.
3. If not found (404) → fall back to `fetch` on the direct URL(s), or
   use `discover_links` to find relevant pages, then `fetch_batch` top results.

## When to Use fetchv2 Tools

| Scenario | Tool |
|---|---|
| User provides a doc URL | `fetch` |
| Specific library/framework | try `llms.txt` first |
| Explore a docs site | `discover_links` then `fetch_batch` |
| Multiple doc pages | `fetch_batch` (up to 10 URLs per call) |

## Integration

Pass fetched content to subagents by including it in the task string as
additional context, or write to `$WORK_DIR/<slug>/direct-fetch.md`
and tell the synthesizer to include it.
