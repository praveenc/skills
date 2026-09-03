## AWS Pricing Findings

- **Claim:** On-Demand Bedrock pricing for Claude Sonnet 5 is $3.00 per million input tokens and $15.00 per million output tokens in us-east-1, priced as of 2026-02-14.
  - Source: Amazon Bedrock Pricing — <https://aws.amazon.com/bedrock/pricing/> ({official·2026-02-14})
  - facet: token-pricing
  - Limitations: list price only; excludes any negotiated enterprise discount.

- **Claim:** Prompt-cache read tokens for Claude Sonnet 5 are priced at $0.30 per million tokens, a 90% discount off the base input price, priced as of 2026-02-14.
  - Source: Amazon Bedrock Pricing — <https://aws.amazon.com/bedrock/pricing/> ({official·2026-02-14})
  - facet: token-pricing
  - Limitations: discount applies to cache-hit tokens only; cache-write tokens are billed separately.

- **Claim:** Batch inference for Claude Sonnet 5 on Bedrock is priced at roughly half of On-Demand token rates, priced as of 2026-02-14.
  - Source: Amazon Bedrock Pricing — <https://aws.amazon.com/bedrock/pricing/> ({official·2026-02-14})
  - facet: batch-pricing
  - Limitations: batch throughput/turnaround time is not covered by the pricing page itself.

- **Claim:** A third-party cost-tracking site estimates a typical 10K-token coding-agent session on Claude Sonnet 5 costs approximately $0.09-$0.14, depending on cache-hit rate, as sampled 2026-02-10.
  - Source: "LLM API pricing tracker" — <https://llmpricecheck.com/anthropic/claude-sonnet-5> ({third-party·2026-02-10})
  - facet: session-cost
  - Limitations: modeled estimate from a third-party tracker, not an AWS-published figure; depends on an assumed cache-hit rate.

- **Claim:** Provisioned Throughput pricing for Claude Sonnet 5 is quoted as a fixed hourly rate per model unit rather than per-token, priced as of 2026-02-14.
  - Source: Amazon Bedrock Pricing — <https://aws.amazon.com/bedrock/pricing/> ({official·2026-02-14})
  - facet: provisioned-throughput
  - Limitations: exact per-model-unit rate varies by commitment term and is not fully enumerated on the public pricing page.

## Source URLs
https://aws.amazon.com/bedrock/pricing/
https://llmpricecheck.com/anthropic/claude-sonnet-5
