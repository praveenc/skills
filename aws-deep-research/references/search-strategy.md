# Search Strategy Rules Engine

Rules for determining which sources to query and how many API credits to spend
based on intent classification and query complexity.

## Core Principle

**MCP servers first, web search only when needed.**

MCP servers (aws-knowledge, aws-pricing, bedrock-agentcore, git-repo-research)
are free, authoritative, and fast. Web search APIs (Brave, Tavily) have monthly
limits and should be reserved for information MCP servers can't provide.

**Exception: non-AWS/generic topics.** When the query is not primarily about
AWS services, web search becomes the primary source. In this case, use
**query expansion** (up to 3 searches) to maximize coverage. See the
"Query Expansion" section below.

## Source Selection Matrix

| Intent | aws-knowledge | aws-pricing | agentcore | github | blog-feeds | web-search |
|---|---|---|---|---|---|---|
| service-overview | ✅ Required | — | If AgentCore | — | ✅ Recommended | — |
| architecture | ✅ Required | — | If AgentCore | Optional | ✅ Recommended | — |
| pricing | ✅ Supporting | ✅ Required | — | — | — | Optional |
| comparison | ✅ Required | Optional | — | — | Optional | ✅ Required |
| troubleshooting | ✅ Required | — | If AgentCore | — | Optional | ✅ Recommended |
| best-practices | ✅ Required | — | If AgentCore | — | ✅ Recommended | — |
| agentcore | Optional | — | ✅ Required | Optional | ✅ Recommended | — |
| code-examples | ✅ Supporting | — | — | ✅ Required | Optional | Optional |
| news-updates | ✅ Required | — | — | — | ✅ Required | ✅ Recommended |

Legend:
- ✅ Required — always query this source
- ✅ Recommended — query unless budget is exhausted
- Optional — query only if other sources are insufficient
- Supporting — query for context but not the primary source
- — — don't query

## Blog Feed Selection

Blog feeds are free (no API credits) and provide recent, in-depth technical
content. Always include them when the source selection matrix shows Recommended
or Required.

Use the category classification from Step 1b of the skill to determine which
feeds to search. Limit to max 3 feeds per research session. See
`references/blog-categories.md` for the full category-to-feed mapping.

## Query Complexity Tiers

### Tier 1: Simple (1-2 subqueries)
Single-service questions, straightforward lookups.

**Examples**: "What is Amazon Bedrock?", "How much does S3 cost?",
"What regions support Bedrock?"

**Budget**:
- MCP servers: unlimited (free)
- Blog feeds: 1 category feed (free)
- Web search: 0 credits (not needed)
- Total subagents: 0-1 (blog feed researcher only if applicable)

### Tier 2: Moderate (3-4 subqueries)
Multi-faceted questions, service comparisons within AWS, architecture guidance.

**Examples**: "Compare DynamoDB vs Aurora for a real-time analytics workload",
"Design a serverless RAG pipeline on Bedrock"

**Budget**:
- MCP servers: unlimited
- Blog feeds: 1-2 category feeds (free)
- Web search: 1-2 credits max (only if comparison involves non-AWS)
- Total subagents: 1-2

### Tier 3: Complex (5-7 subqueries)
Cross-service architectures, AWS vs third-party comparisons, deep dives
requiring multiple perspectives.

**Examples**: "Compare AWS Bedrock vs Azure OpenAI vs Google Vertex AI for
enterprise RAG", "Full cost analysis of migrating from self-hosted Kubernetes
to EKS with Fargate"

**Budget**:
- MCP servers: unlimited
- Blog feeds: 2-3 category feeds (free)
- Web search: 2-3 credits max
- Total subagents: 2-3

## Web Search Decision Rules

Only use web search when ALL of these are true:

1. **The information is unlikely to be in AWS docs** — third-party comparisons,
   community benchmarks, non-AWS service details, very recent announcements
   (< 1 week old)
2. **MCP server results are insufficient** — you searched aws-knowledge and
   didn't find what you need
3. **The query explicitly or implicitly requires external perspective** —
   "vs", "compared to", "alternatives", "community opinion", "benchmark"

### Skip web search when:
- The query is purely about AWS services and their features
- The query is about AWS pricing (use pricing MCP server)
- The query is about AWS best practices or Well-Architected guidance
- The query is about AgentCore (use agentcore MCP server)
- The query is about code examples in AWS repos (use GitHub MCP server)

## Brave vs Tavily Decision

When web search IS needed:

| Scenario | Use | Reason |
|---|---|---|
| Need a quick factual answer | Tavily basic + `--include-answer` | AI answer + sources in 1 credit |
| Need many diverse sources | Brave `--count 15` | More results per query |
| Need full page content | Tavily advanced + `--include-raw-content` | Pre-extracted markdown |
| Need recent news | Brave `--type news --freshness pw` | News-specific endpoint |
| Need domain-specific results | See site-scoped search below | |

**Never use both Brave and Tavily for the same subquery.**

## Site-Scoped Community Search

High-value AWS community sites contain practitioner-written content that
official docs and blogs often miss — tutorials, architecture comparisons,
real-world experience reports. Use **one** site-scoped search per research
session to tap into this content efficiently.

### Target sites

| Site | Content type |
|---|---|
| `builder.aws.com` | AWS Builder Center — practitioner articles, tutorials, architecture patterns |
| `repost.aws` | AWS re:Post — Q&A, knowledge articles, troubleshooting |
| `community.aws` | AWS Community — blog posts, events, builder content |
| `dev.to` | Developer articles (filter with AWS keywords) |

### How to search (single API call)

**Brave** — use `site:` and `OR` operators directly in the query string:

```bash
uv run $SKILL_DIR/scripts/brave_search.py \
  "<keywords> site:builder.aws.com OR site:repost.aws OR site:community.aws OR site:dev.to" \
  --count 10 --no-scrape --json -y \
  -o <output-dir>/downloads/brave
```

**Tavily** — use the `--include-domains` parameter:

```bash
uv run $SKILL_DIR/scripts/tavily_search.py \
  "<keywords>" \
  --include-domains builder.aws.com,repost.aws,community.aws,dev.to \
  --count 10 --json -y \
  -o <output-dir>/downloads/tavily
```

### When to use site-scoped search

- **Always** for `comprehensive` strategy — it's a cheap way to find
  practitioner perspectives alongside official docs
- **Recommended** for `architecture`, `best-practices`, `troubleshooting`
  intents — these benefit most from real-world experience
- **Skip** for `feed-only`, `docs-only`, and `pricing-focused` strategies

### Budget impact

One API call covers all community sites. This costs 1 Brave search or
1 Tavily credit — efficient because `OR`/`--include-domains` combines
multiple site scopes into a single request.

## GitHub Search Decision

Use GitHub search when:
- Intent includes `code-examples`
- User asks for "sample code", "reference implementation", "example project"
- User asks "how to implement X on AWS"

Skip GitHub search when:
- `GITHUB_TOKEN` is not set (check env first)
- The query is conceptual, not implementation-focused
- AWS docs already provide sufficient code examples

## Budget Tracking

The skill should track cumulative web search usage across a session:

- Brave: count searches against 2,000/month
- Tavily: count credits against 1,000/month

If approaching limits (>80% used), switch to MCP-only mode and note the
limitation in the report.

## Query Decomposition (default for all topics)

A single natural-language question typically hides 2–3 distinct facets (e.g.
*"what is X"* + *"how to use X"*, or *"docs"* + *"tutorial"*, or *"capabilities"*
+ *"pricing"*). Running one keyword-compressed string misses most of them.

**Rule: decompose every research topic into 2–3 facet-labeled subqueries
before dispatching to any search source** — web search, AWS docs MCP,
GitHub, or blog-feed search. Applies to AWS topics AND generic topics
equally; there is no "non-AWS only" exception.

### Facet pairs (pick 2–3 that fit the question)

| Facet pair | When it applies | Example for *"How does AWS Bedrock Guardrails compare to NVIDIA NeMo Guardrails?"* |
|---|---|---|
| **reference · tutorial** | Any "how do I X" question | `AWS Bedrock Guardrails documentation contextual grounding` + `NeMo Guardrails tutorial setup example` |
| **official · community** | Comparisons, reality-check on vendor claims | `AWS Bedrock Guardrails announcement features` + `Bedrock Guardrails review limitations production` |
| **what-it-is · how-to-use-it** | Service-overview / new-service learning | `what is Bedrock Guardrails capabilities` + `implement Bedrock Guardrails Python SDK example` |
| **capabilities · pricing** | Selection / build-vs-buy | `Bedrock Guardrails supported modalities features` + `Bedrock Guardrails pricing per 1000 requests` |
| **build · critique** | Pattern/architecture research | `circuit breaker pattern implementation microservices` + `circuit breaker anti-pattern failure modes` |
| **primary-source · third-party** | Research centered on one creator/paper/post | `Karpathy LLM knowledge base gist` + `LLM wiki Obsidian implementation community` |

Pick **the facet pair that genuinely splits the question**, not an arbitrary
one. If no pair fits, craft one that does — the facet is the value, not the
label.

### Transparency rule (MANDATORY)

Before each search-source dispatch, the parent MUST print the decomposed
subqueries in the chat so the user sees what will actually hit the API:

```
Dispatching web-content-researcher with:
  [1] "AWS Bedrock Guardrails documentation contextual grounding"   (facet: reference)
  [2] "Bedrock Guardrails review limitations production"            (facet: community)
```

This lets the user correct a bad decomposition before credits are spent.

### Budget impact

2 queries per source × up to 2 web sources (Brave + Tavily) = max 4
web-search credits per research session.

| Engine | Monthly cap | 4-query session cost |
|---|---:|---|
| Brave | 2,000 | 0.2% |
| Tavily | 1,000 | 0.4% |

Cheaper than running a single broad query and missing a facet — a missed
facet costs a second full research session.

### What about AWS topics specifically?

For AWS topics, the same 2-query decomposition applies to the `aws_doc_search`
and blog-feed calls inside `aws-mcp-researcher`. The parent still routes to
MCP first (per the Source Selection Matrix above) — decomposition governs
*what queries hit MCP*, not *whether to hit MCP*. Web search stays
"supplementary" for pure-AWS topics (Tier 2 budget: 0–2 web credits if any
comparison is involved).

### What about "Tier 3 complex" questions?

Complex questions may warrant 3 facets instead of 2 (e.g. build · critique ·
pricing, or reference · tutorial · community). Cap at 3 — beyond that,
diminishing returns and the facets start overlapping.
