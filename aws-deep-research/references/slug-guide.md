# Slug Generation Guide

The slug identifies a research session on disk (`$WORK_DIR/<slug>/`) and names
the final report file (`<slug>-report.md`). A good slug is descriptive enough
to be meaningful a month from now when you grep `~/.aws-deep-research/`.

## Rules

- **4-7 words**, joined with hyphens (kebab-case)
- **30-60 characters total** (enforce both bounds - reject terse AND bloated)
- **Lowercase letters, digits, hyphens only**; no underscores, no dots
- Must encode: **primary service(s)** + **intent verb/dimension** + **scope qualifier**
- No generic stopwords alone (`aws`, `guide`, `info`, `research`, `report`)

## Examples

| Query | ❌ Too terse | ✅ Good slug |
|---|---|---|
| How does DynamoDB handle hot partitions? | `dynamodb` | `dynamodb-hot-partitions-troubleshooting-patterns` |
| Compare AWS Bedrock vs Azure OpenAI for enterprise RAG | `bedrock-azure` | `bedrock-vs-azure-openai-enterprise-rag-comparison` |
| What's the cost of running Llama-3-70B on Bedrock? | `bedrock-cost` | `bedrock-llama3-70b-inference-pricing-analysis` |
| Migrate self-hosted K8s to EKS Fargate | `eks-migration` | `self-hosted-k8s-to-eks-fargate-migration-plan` |
| Bedrock AgentCore overview | `agentcore` | `bedrock-agentcore-service-overview-capabilities` |
| Circuit breaker patterns (generic) | `circuit-breaker` | `circuit-breaker-pattern-distributed-systems-resilience` |

## Quick validator

Sanity-check token count:

```bash
echo "$slug" | tr '-' '\n' | wc -l
```

- < 4 tokens or < 30 chars → regenerate with more specificity
- > 7 tokens or > 60 chars → drop stopwords

Then **declare the slug explicitly in your plan** before dispatching, e.g.
`Slug: bedrock-llama3-70b-inference-pricing-analysis`.
