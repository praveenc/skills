---
name: aws-deep-research
description: >
  Performs multi-source, parallelized research on AWS topics and synthesizes
  the findings into a cited research report. Dispatches specialized subagents
  against AWS docs, AWS pricing, Bedrock AgentCore docs, AWS blog feeds, GitHub,
  and the open web. Activates when the user asks to "research", "do a deep
  dive", "compare", "analyze pricing of", "plan a migration to", or "review
  best practices for" an AWS service, architecture, or cross-cloud topic.
  Triggers include: "deep research", "research report", "Well-Architected
  review", cost/pricing comparison, service limits, troubleshooting a specific
  AWS error, or comparing AWS against a third-party/other-cloud alternative.
  Does NOT activate for: simple factual recalls the model already knows,
  writing AWS code without needing docs, operational AWS CLI commands, or
  questions that can be answered from the current conversation context.
compatibility: >
  Compatible with Kiro CLI, the pi coding-agent harness, and Claude Code (all
  need subagent dispatch; see references/platform-dispatch.md for the
  per-harness mechanism). Requires uv for Python scripts and the fetchv2 MCP
  server for batched web content extraction. Optional: Brave/Tavily API keys
  for web search, GITHUB_TOKEN for GitHub repo search, AWS credentials for docs
  and pricing, Docker-hosted Kroki for diagram rendering.
metadata:
  author: praveenc
  version: "6.12"
---

# AWS Deep Researcher

Multi-source research on AWS topics → structured report with citations.

```
Query → Intent → Strategy → [Decompose] → Dispatch subagents → Synthesize
```

## Architecture Rule

**ALL research runs in subagents. The parent agent only routes and dispatches.**

Raw documentation, pricing data, blog content, and search results NEVER enter
the parent's context. Each subagent writes findings to disk. The `synthesizer`
reads all findings and writes the final report. The parent only reads the
finished report to present to the user.

## Resolve Skill + Work Directories

Run once and reuse `SKILL_DIR` and `WORK_DIR` in all subsequent commands.

**Use the directory THIS `SKILL.md` was loaded from.** You just read this file
via an absolute path (e.g. `read /path/to/aws-deep-research/SKILL.md`). The
skill root is that file's parent directory. Run the resolver from **that same
directory** so the whole session stays pinned to the install you actually
loaded — do NOT substitute a `~/.kiro/...` or `~/.pi/...` path from memory:

```bash
# Replace <SKILL_MD_DIR> with the directory you just read this SKILL.md from.
eval "$(bash <SKILL_MD_DIR>/scripts/resolve_skill_dir.sh)"
echo "SKILL_DIR=$SKILL_DIR"   # sanity-check: must match <SKILL_MD_DIR>
```

The resolver derives `SKILL_DIR` from its own `BASH_SOURCE` location, so as
long as you invoke it by the path you loaded SKILL.md from, `SKILL_DIR` pins
to that exact copy — whether it is a `--skill` path, a git worktree, a
`~/.pi/...` install, or a `~/.kiro/...` install. **Verify the echo matches the
directory you loaded SKILL.md from before continuing.** If it does not,
re-run with the correct `<SKILL_MD_DIR>` — a mismatch means every downstream
script and reference will silently run a different install than the one you
loaded.

- `SKILL_DIR` — where this skill lives (scripts, agents, references).
- `WORK_DIR` — **global** research work root (default `~/.aws-deep-research/work`,
  override via `RESEARCH_WORK_DIR` in `$SKILL_DIR/scripts/.env`).

**All intermediate artifacts go under `$WORK_DIR/<slug>/`, never under the
invocation CWD.** This prevents stray `output/research/` folders from
accumulating in every project directory you run the skill from.

## Subagents

| Agent | Purpose | When |
|---|---|---|
| `aws-mcp-researcher` | AWS docs + pricing via MCP | Most queries |
| `web-content-researcher` | Web search + blog feeds | Comparisons, community, recent posts |
| `agentcore-researcher` | Bedrock AgentCore docs | AgentCore queries |
| `github-researcher` | GitHub repo search | Code examples |
| `diagram-generator` | D2 diagrams via Kroki | Architecture reports (optional) |
| `synthesizer` | Reads findings, writes report | Always last |

Agent definitions: `$SKILL_DIR/agents/`. Dispatch details: see
[references/platform-dispatch.md](references/platform-dispatch.md).

## Prerequisites

- `uv` installed. Prefer a package manager so the download is verifiable:
  - macOS: `brew install uv`
  - pipx: `pipx install uv`
  - pip: `pip install uv`
  - Other platforms: follow the official install docs at
    https://docs.astral.sh/uv/getting-started/installation/ and verify the
    installer before running it. Do not pipe a remote script straight into a
    shell.
- Python 3.13+ (managed by `uv`)
- Optional: API keys in `$SKILL_DIR/scripts/.env`
- Optional: AWS credentials (`AWS_PROFILE` or env vars)
- Optional: Docker for diagrams (`docker run -d -p 8000:8000 yuzutech/kroki`)

## Step 0 — First-Run Setup (one-time)

Check whether `.env` exists AND has been customized away from the example:
```bash
if [ ! -f "$SKILL_DIR/scripts/.env" ]; then
  echo "NEEDS_SETUP"          # .env doesn't exist yet
elif diff -q "$SKILL_DIR/scripts/.env" "$SKILL_DIR/scripts/.env.example" >/dev/null 2>&1; then
  echo "NEEDS_SETUP"          # .env is a verbatim copy of .env.example
else
  echo "CONFIGURED"
fi
```

If `NEEDS_SETUP` → read [references/setup-guide.md](references/setup-guide.md)
and follow the wizard. Otherwise skip to Step 1.

## Step 1 — Analyze Intent & Strategy

### 1a. Classify intent(s) — picks the **default subagent set**

For vague queries, read [references/intent-patterns.md](references/intent-patterns.md)
to decide whether to ask a clarifying question. **Never ask more than one.**

The intent determines **which subagents are candidates** for dispatch. The
strategy (Step 1d below) may then NARROW or KEEP that default set.

| Intent | Default subagents (candidates) |
|---|---|
| `service-overview` | aws-mcp-researcher, web-content-researcher |
| `architecture` | aws-mcp-researcher, web-content-researcher |
| `pricing` | aws-mcp-researcher (with pricing flag) |
| `comparison` | aws-mcp-researcher, web-content-researcher |
| `troubleshooting` | aws-mcp-researcher, web-content-researcher |
| `best-practices` | aws-mcp-researcher, web-content-researcher |
| `migration` | aws-mcp-researcher, web-content-researcher |
| `security-compliance` | aws-mcp-researcher, web-content-researcher |
| `cost-optimization` | aws-mcp-researcher (with pricing), web-content-researcher |
| `agentcore` | agentcore-researcher |
| `code-examples` | github-researcher, aws-mcp-researcher |
| `news-updates` | aws-mcp-researcher, web-content-researcher |

### 1b. Classify query type: AWS or Generic

Determine whether the query is **primarily about AWS services** or a
**generic/non-AWS topic**. This is a binary decision that changes everything:

| Query Type | Primary sources | Web search behavior |
|---|---|---|
| `aws` | MCP servers (docs, pricing) + blog feeds | Supplementary only, 1-2 searches max |
| `generic` | Web search (Brave/Tavily) | Primary source, use query expansion (3 searches) |

**Pass `query-type: aws` or `query-type: generic` to every subagent.**
The web-content-researcher uses this to decide search depth. The
aws-mcp-researcher skips entirely for `generic` queries.

Examples:
- "How does DynamoDB handle hot partitions?" → `aws`
- "Circuit breaker patterns in distributed systems" → `generic`
- "Compare AWS Bedrock vs Azure OpenAI" → `aws` (AWS is the anchor)
- "Best practices for gRPC load balancing" → `generic`

### 1c. Blog categories (only if web-content-researcher dispatched)

Read [references/blog-categories.md](references/blog-categories.md) to map
query to feed URLs. Max 3 feeds. Always include `whatsnew` for `news-updates`
or features launched in the last 30 days.

### 1d. Select strategy — **modifies** the intent default set

Strategy is a depth/scope modifier on top of intent. Intent says *which*
subagents are candidates; strategy says *which of those to keep* and
*how deep to go*. When strategy and intent conflict, **strategy wins**.

| Strategy | When | Effect on intent defaults | Decomposition per source |
|---|---|---|---|
| `feed-only` | "recent posts", "latest blogs" | **OVERRIDE** — use web-content-researcher only, ignore intent | Skip (no search queries) |
| `docs-only` | Single service question, API lookup | **NARROW** — keep only aws-mcp-researcher | 2–3 subqueries |
| `pricing-focused` | Cost, "how much", instance types | **NARROW** — keep only aws-mcp-researcher (with pricing) | 2–3 subqueries |
| `comprehensive` | Architecture, multi-service, comparisons | **KEEP** — dispatch all intent-default candidates | 2–3 per source, up to 3 facets for complex topics |

For `comprehensive` strategy, read [references/search-strategy.md](references/search-strategy.md)
for web search budget rules and the facet-pair catalog used during
decomposition.

### 1e. Direct URLs

If the user provides URLs or references a specific project, see
[references/direct-url-handling.md](references/direct-url-handling.md).

### 1f. Check API Keys

```bash
bash "$SKILL_DIR/scripts/check_api_keys.sh" "$SKILL_DIR"
```

Parse the output (one `KEY=STATUS` per line). Only prompt about services the
current strategy needs. If a needed service is INVALID/MISSING, inform the
user with the specific issue and ask whether to proceed without it. When all
needed keys are valid, proceed silently.

### 1g. Research Contract

Extract hard facts, entity constraints, and version requirements into
`$WORK_DIR/<slug>/research-contract.md`. See
[references/research-contract-guide.md](references/research-contract-guide.md)
for format and examples.

- **Complex** (3+ entities, version constraints) → show contract, ask user to validate
- **Simple** → proceed silently

## Step 2 — Generate Slug (MANDATORY before Step 3)

The slug identifies this research session on disk (`$WORK_DIR/<slug>/`) and
names the final report file (`<slug>-report.md`). A good slug is descriptive
enough to be meaningful a month from now when you grep `~/.aws-deep-research/`.

### Rules

- **4–7 words**, joined with hyphens (kebab-case)
- **30–60 characters total** (enforce both bounds — reject terse AND bloated)
- **Lowercase letters, digits, hyphens only**; no underscores, no dots
- Must encode: **primary service(s)** + **intent verb/dimension** + **scope qualifier**
- No generic stopwords alone (`aws`, `guide`, `info`, `research`, `report`)

### Examples

| Query | ❌ Too terse | ✅ Good slug |
|---|---|---|
| How does DynamoDB handle hot partitions? | `dynamodb` | `dynamodb-hot-partitions-troubleshooting-patterns` |
| Compare AWS Bedrock vs Azure OpenAI for enterprise RAG | `bedrock-azure` | `bedrock-vs-azure-openai-enterprise-rag-comparison` |
| What's the cost of running Llama-3-70B on Bedrock? | `bedrock-cost` | `bedrock-llama3-70b-inference-pricing-analysis` |
| Migrate self-hosted K8s to EKS Fargate | `eks-migration` | `self-hosted-k8s-to-eks-fargate-migration-plan` |
| Bedrock AgentCore overview | `agentcore` | `bedrock-agentcore-service-overview-capabilities` |
| Circuit breaker patterns (generic) | `circuit-breaker` | `circuit-breaker-pattern-distributed-systems-resilience` |

### Quick validator

Before proceeding, sanity-check: count hyphen-separated tokens (`echo "$slug" | tr '-' '\n' | wc -l`).
If < 4 tokens or total length < 30 chars → regenerate with more specificity.
If > 7 tokens or length > 60 chars → drop stopwords.

Once chosen, **declare the slug explicitly in your plan** before dispatching
subagents. Example: `Slug: bedrock-llama3-70b-inference-pricing-analysis`.

## Step 3 — Decompose (skip for `feed-only`)

Break query into subqueries using:
1. **Faceted** — split by dimensions (features, pricing, limits)
2. **Specificity** — broad + narrow variants
3. **Synonyms** — alternate terminology

List all subqueries with assigned subagents before proceeding.

## Step 4 — Dispatch Research

Create the work dir: `$WORK_DIR/<slug>/`

```bash
mkdir -p "$WORK_DIR/<slug>/downloads"
```

All **findings files** go into `$WORK_DIR/<slug>/`. Downloads go to
`$WORK_DIR/<slug>/downloads/`. **Never write under the invocation CWD.**

**Dispatch all applicable subagents, batching into rounds of ≤4** (all
supported harnesses cap parallel subagents per round).

**Determine the harness first, then dispatch accordingly** — there are two
dispatch worlds and picking the wrong one is the classic failure (a pi-hosted
model improvising into whatever delegate-shaped tool it finds):

- **Kiro** — dispatch **in-session** via the native subagent tool. Detect the
  engine first: on **v2** (current default) call `use_subagent` with
  `InvokeSubagents` and a `subagents[]` array; on **v3** name the agents in
  natural language. Prefer the **generic path** — hand each subagent the role
  from `$SKILL_DIR/agents/<name>.md` inline (omit `agent_name`), no
  registration needed. **Do NOT shell out** and **do NOT use any other
  delegate-shaped tool.**
- **pi / Claude Code** — dispatch as **headless child processes** via
  `scripts/dispatch.sh` (one call per subagent; background several + `wait`
  for a parallel round). **Do NOT reach for any environment delegate tool.**
- **Ambiguous or unknown harness** — ask the user one question; if they name
  an untested harness, offer the process-fan-out path as best effort.

Full procedure, detection fingerprints, the `dispatch.sh` contract, and round
batching: [references/platform-dispatch.md](references/platform-dispatch.md).

Before any process-fan-out round, print the bold disclaimer: **each subagent
launches a full, separate CLI process (its own model context + auth round-trip;
a 4-researcher round = 4 CLI cold starts).** `dispatch.sh` prints this for you.

| Subagent | Findings file | When |
|---|---|---|
| `aws-mcp-researcher` | `$WORK_DIR/<slug>/aws-docs.md` (+ `aws-pricing.md`) | Most strategies |
| `web-content-researcher` | `$WORK_DIR/<slug>/web-content.md` | Comparisons, blogs, community |
| `agentcore-researcher` | `$WORK_DIR/<slug>/agentcore.md` | AgentCore intent |
| `github-researcher` | `$WORK_DIR/<slug>/github-repos.md` | Code examples intent |

Include in each subagent's task string the fields defined in the **shared
subagent task-input contract**:
[references/subagent-task-contract.md](references/subagent-task-contract.md).
That file is the single source of truth for what every subagent needs.

**Transparency rule (MANDATORY): before dispatching any search subagent,
print the decomposed subqueries and their facet labels to the user.** This
lets the user correct a bad decomposition before any API credits are spent.
Format:

```
Dispatching web-content-researcher with:
  [1] "<subquery 1>"   (facet: <label>)
  [2] "<subquery 2>"   (facet: <label>)
```

Per-subagent reminders:

- **web-content-researcher**: include `feed-urls` and `query-type`. Remind it
  to **use `fetchv2:fetchv2_fetch_batch` (batched, up to 10 URLs per call)
  with `max_length_per_url: 8000`** and to **re-fetch at 15000–20000** for
  any primary source showing a `<!-- Truncated:` marker. Trafilatura is
  fallback only.
- **aws-mcp-researcher**: on Bedrock queries, tell it to consult
  `references/bedrock-llms-txt.md`. Decompose docs-search into 2 facet
  queries (reference · how-to-use-it is typical).

## Step 5 — Verify Findings (silent-failure detector)

Immediately after each round of subagents reports back, verify each expected
findings file exists and is non-trivial. Subagents occasionally report `✅`
while writing an empty/stub file (script crash mid-write, no API key, etc.).

```bash
for f in "$WORK_DIR/<slug>"/*.md; do
  [ "$(basename "$f")" = "research-contract.md" ] && continue
  sz=$(wc -c < "$f" 2>/dev/null || echo 0)
  if [ "$sz" -lt 500 ]; then
    echo "WEAK: $f ($sz bytes)"
  else
    echo "OK: $f ($sz bytes)"
  fi
done
```

- Any file `< 500 bytes` → treat the subagent as having failed silently.
- Record each `WEAK` entry in the synthesizer dispatch brief (Step 6) so it
  surfaces in the report's **Gaps & Limitations** section.
- Do NOT read the contents of any findings file in the parent — only check
  size and existence.

## Step 6 — Synthesize

After all researchers complete, dispatch `synthesizer` with:
- Original query and intents
- Work dir path (`$WORK_DIR/<slug>/`)
- List of expected findings files (with OK/WEAK/MISSING status from Step 5)
- Research contract file path

**Do NOT read findings files in the parent.** The synthesizer handles
everything in its own context.

## Step 7 — Optional Diagram

Read the report's Executive Summary only (~30 lines). Generate a diagram when
it describes architecture with 3+ components, a workflow/pipeline, data flow,
or tiered structure. Skip for pricing, feature overviews, or troubleshooting.

Check Kroki availability from the `check_api_keys.sh` output. If UNAVAILABLE,
skip silently. Otherwise dispatch `diagram-generator` with the report path
and a brief describing what to diagram.

## Step 8 — Present Results

Copy the final report to the global reports directory:

```bash
eval "$(grep '^REPORT_OUTPUT_DIR=' "$SKILL_DIR/scripts/.env" 2>/dev/null)"
REPORT_DIR="${REPORT_OUTPUT_DIR:-$HOME/.aws-deep-research/outputs}"
REPORT_DIR="${REPORT_DIR/#\~/$HOME}"
mkdir -p "$REPORT_DIR"
cp "$WORK_DIR/<slug>/<slug>-report.md" "$REPORT_DIR/"
echo "SAVED=$REPORT_DIR/<slug>-report.md"
```

Read ONLY `$WORK_DIR/<slug>/<slug>-report.md` and present:
- 3-5 key findings from the executive summary
- Any gaps noted
- Suggested follow-up directions

**Always display at the end:**
> 📄 **Report saved to**: `<REPORT_DIR>/<slug>-report.md`

Then ask: **"Would you like to open the report in your editor?"**

If yes:
```bash
${EDITOR:-${VISUAL:-code}} "$REPORT_DIR/<slug>-report.md"
```

## Gotchas

- **Kiro 4-subagent limit**: never dispatch more than 4 per round. Plan rounds.
- **Work dir is global**: `$WORK_DIR/<slug>/` (default `~/.aws-deep-research/work/<slug>/`),
  never `./output/research/<slug>/`. Override via `RESEARCH_WORK_DIR` in `.env`.
- **Slug discipline**: 4–7 words, 30–60 chars (see Step 2). Terse slugs
  make artifacts unrecoverable later.
- **Parallel fetch**: web-content-researcher MUST use `fetchv2:fetchv2_fetch_batch`
  (up to 10 URLs per call) for page extraction. Trafilatura is a fallback only.
- **`-o` flag is mandatory** for all search/scraper scripts — without it,
  output goes to wrong location outside the research directory. The `-o`
  target is always `$WORK_DIR/<slug>/downloads/<tool>`.
- **Domain blocklist**: `$SKILL_DIR/scripts/blocklist.txt` filters URLs
  from Brave/Tavily results automatically. When a subagent constructs a
  URL by hand (not from search), it must still check against the blocklist
  before calling `fetchv2:fetchv2_fetch_batch`. Add domains to the list as
  new SEC/DEAD/SPAM hits are observed.
- **Blog miscategorizations**: OpenSearch is `bigdata` not `databases`, Glue is
  `bigdata` not `databases`, Kendra is `machinelearning` not `bigdata`. Check
  `references/blog-categories.md` when unsure.
- **AWS credentials**: always pass `--profile 001` to `aws_doc_search.py`
  unless the user specifies otherwise.
- **Web search budget**: Brave 2K/month, Tavily 1K/month. Never use both for
  the same subquery. MCP servers are free — prefer them. Usage is persisted
  in `~/.aws-deep-research/budget.json`; when a search script's `--json`
  output shows `"budget": {"over_80": true}`, switch to MCP-only and note it
  in the report's Gaps section.
- **Evidence tags**: every finding carries a `{authority·date}` tag
  (`official` / `vendor-claim` / `third-party` / `community`). The synthesizer
  uses these to weight conflicting sources, so an untagged finding is treated
  as lowest-confidence. See `references/contract-compliance-rules.md`.

## Scripts Reference

All scripts: `$SKILL_DIR/scripts/`. Run via `uv run`.

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
