# Bedrock llms.txt Documentation Index

An optimization for Bedrock-related queries that bypasses broad search in favor
of direct URL lookup from a structured table of contents.

## What is llms.txt?

The file at `https://docs.aws.amazon.com/bedrock/latest/userguide/llms.txt`
is a structured markdown index of all Amazon Bedrock documentation pages. It
follows the [llmstxt.org](https://llmstxt.org) convention - a machine-readable
TOC with titles, descriptions, and direct URLs for every doc page.

## Why Use It

- Covers ~170K chars of Bedrock documentation structure
- Contains direct URLs for all Bedrock topics: models, inference, agents,
  knowledge bases, guardrails, customization, evaluation, security, etc.
- Allows keyword matching against section titles to find the exact doc page
  without needing a search query
- Faster and more precise than `search_documentation` for Bedrock topics

## When to Use

Use this optimization when the research query involves any of these:

- Amazon Bedrock (general)
- Bedrock models, inference, converse API
- Bedrock Agents, action groups, agent collaboration
- Bedrock Knowledge Bases, RAG, chunking, data sources
- Bedrock Guardrails, content filtering
- Bedrock model customization, fine-tuning, continued pre-training
- Bedrock evaluation, model evaluation jobs
- Bedrock Flows, prompt management
- Bedrock security, IAM, encryption
- Bedrock pricing, quotas, limits

Do NOT use for:
- Non-Bedrock AWS services (use `search_documentation` instead)
- Bedrock AgentCore (use `bedrock-agentcore-mcp-server` instead)
- Pricing details (use `aws-pricing-mcp-server` instead)

## How to Use

### Step 1: Fetch the index

```
fetch_llms_txt(url="https://docs.aws.amazon.com/bedrock/latest/userguide/llms.txt")
```

### Step 2: Scan for matching sections

Look for section titles or descriptions that match your subquery keywords.
For example, if researching "Bedrock Knowledge Bases chunking strategies":
- Look for titles containing "knowledge base", "chunking", "data source"
- Extract the matching URLs

### Step 3: Read matched pages directly

```
read_documentation(url="https://docs.aws.amazon.com/bedrock/latest/userguide/<matched-page>.html")
```

This skips the search step entirely and gives you the exact page content.

### Step 4: Fall through for gaps

If the llms.txt doesn't cover a subquery (unlikely for Bedrock topics), fall
through to `search_documentation` as normal.

## Scope

This optimization applies to Amazon Bedrock documentation only. Other AWS
services do not yet have llms.txt files indexed in this skill. As more services
publish llms.txt files, this pattern can be extended.
