# First-Run Setup Guide

This guide runs once when the external machine-local config has not been
created or still matches the template.

Default path: `~/.config/aws-deep-research/config.env`.
Override it with `AWS_DEEP_RESEARCH_CONFIG`.
Never store credentials inside the skill directory.

This wizard runs only when SKILL.md **Step 0** determines the config is missing
or still matches the template. Step 0 owns that detection - do not re-detect
here (an inverted copy previously re-ran setup on already-configured machines).

## Setup Message

Show the user:

> 👋 **First-time setup for AWS Deep Research**
>
> This skill uses optional API keys for web search and GitHub search.
> AWS documentation, blog feeds, and MCP-based sources work without any keys.
>
> **Optional API keys** (add to `~/.config/aws-deep-research/config.env`):
>
> | Service | Free Tier | Credit Card? | Sign Up |
> |---------|-----------|-------------|---------|
> | Tavily Search | 1,000 credits/month | ❌ No | [Quickstart](https://docs.tavily.com/documentation/quickstart) |
> | Brave Search | 2,000 requests/month | ✅ Yes | [API signup](https://brave.com/search/api/) |
> | GitHub | Unlimited (public repos) | ❌ No | [Create token](https://github.com/settings/tokens) |
>
> Would you like to add any keys now, or proceed without them?

If the user provides keys, create the parent directory with mode `700`, write
`CONFIG_FILE` with mode `600`, and update it without echoing values.

Also ask:

> **Report output directory**: Final reports are saved to a global folder
> for safekeeping. Default: `~/.aws-deep-research/outputs`
>
> Would you like to use a different path?

If yes, update `REPORT_OUTPUT_DIR` in `CONFIG_FILE`. Otherwise keep the default.
Then proceed to Step 1.

## Data flow (for reviewers)

Every MCP server runs as a local child process (`uvx` or `npx`, versions
pinned in the launching script or agent JSON). This is where each one sends
data:

| Server | Launched by | Sends | To |
|---|---|---|---|
| `@praveenc/llmstxt-doc-search` | `llmstxt_doc_search.py` | requests for `llms.txt` indexes and doc pages; queries are ranked locally (BM25) | public doc sites (AWS docs, Strands, Kiro); sources cached in `~/.config/llmstxt-doc-search/` |
| `mcp-proxy-for-aws` | `aws_doc_search.py`, `setup/kiro-agent.json` | doc search queries, signed with SigV4 from local AWS credentials | AWS MCP Server, `aws-mcp.us-east-1.api.aws` |
| `awslabs.aws-pricing-mcp-server` | `aws_pricing_search.py` | service codes, filters and region, using local AWS credentials | AWS Price List API |
| `awslabs.amazon-bedrock-agentcore-mcp-server` | `agentcore_search.py`, `setup/kiro-agent.json` | AgentCore doc search and fetch requests | public AgentCore documentation |
| `fetchv2-mcp-server` | `agents/web-content-researcher.json`, `setup/kiro-agent.json` | an HTTP GET for each URL the web researcher fetches; 2.1.0+ refuses private and local addresses | the public site at that URL |

Non-MCP calls: `brave_search.py` and `tavily_search.py` send the query and
API key to Brave or Tavily; `github_search.py` sends the query and
`GITHUB_TOKEN` to `api.github.com`; `kroki_diagram.py` sends D2 source to
`KROKI_URL` (local Docker by default, never a public host automatically).
None of these calls carries findings files, reports, or the research
contract; Kroki receives only the D2 source.

**Accepted risk: fetchv2 auto-approve (updated 2026-11-16).**
`agents/web-content-researcher.json` auto-approves fetchv2's `fetch`,
`fetch_batch` and `discover_links`. This stays on by the user's decision. The
pin must be `fetchv2-mcp-server` 2.1.0 or newer.

- Socket flagged 2.0.0 with a `gptSecurity` alert (severity middle). Socket
  gave no reasoning.
- A code review of 2.0.0 found no private-address check, redirects followed
  to internal hosts, and no response size cap.
- 2.1.0 fixes these. It refuses private, loopback, link-local and reserved
  addresses on the first request and on every redirect. This applies to
  `fetch`, `fetch_batch`, `discover_links`, the robots.txt check and
  `fetch_llms_txt`. It caps each response at 5 MB.
- Keep `FETCHV2_ALLOW_PRIVATE_NETWORKS` unset. Setting it to `1` turns the
  address check off.

Known limits that remain:

- DNS rebinding can still get past the address check.
- Fetched page text is untrusted and can carry prompt injection. The
  existing gates stay: `public-web-approved: true` in SKILL.md Step 4, the
  untrusted-content rule in `contract-compliance-rules.md`, and
  `scripts/blocklist.txt`.
- `fetch_batch` and `fetch_llms_txt` do not check robots.txt.
- When extraction fails, the server returns the raw HTML.
