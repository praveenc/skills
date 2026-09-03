## AWS Documentation Findings

- **Claim:** Claude Sonnet 5 is available in Amazon Bedrock via the model ID anthropic.claude-sonnet-5-20260115-v1:0, accessible through the Converse API.
  - Source: Amazon Bedrock — Supported foundation models — <https://docs.aws.amazon.com/bedrock/latest/userguide/models-supported.html> ({official·2026-02-01})
  - facet: availability
  - Limitations: model ID/version string is illustrative of Bedrock's naming convention.

- **Claim:** Claude Sonnet 5 supports a 200K token context window and an extended "thinking" mode configurable via the Converse API's reasoning parameters.
  - Source: Amazon Bedrock — Anthropic Claude models — <https://docs.aws.amazon.com/bedrock/latest/userguide/model-parameters-anthropic-claude-messages.html> ({official·2026-02-01})
  - facet: model-capabilities
  - Limitations: parameter documentation; does not independently benchmark reasoning quality.

- **Claim:** Claude Sonnet 5 is available through cross-region inference profiles in US and EU regions, alongside prior Claude 4.x profiles.
  - Source: Amazon Bedrock — Cross-region inference — <https://docs.aws.amazon.com/bedrock/latest/userguide/cross-region-inference-support.html> ({official·2026-01-20})
  - facet: availability
  - Limitations: regional profile coverage can change over time; snapshot at query date.

- **Claim:** Prompt caching is documented as supported for Claude Sonnet 5 on Bedrock, reducing repeated input token costs for multi-turn or tool-heavy workloads.
  - Source: Amazon Bedrock — Prompt caching — <https://docs.aws.amazon.com/bedrock/latest/userguide/prompt-caching.html> ({official·2026-01-25})
  - facet: model-capabilities
  - Limitations: describes the mechanism; actual savings depend on workload cache-hit rate.

- **Claim:** AgentCore documentation lists Claude Sonnet 5 as a supported model for the AgentCore Runtime managed agent loop.
  - Source: Amazon Bedrock AgentCore — Supported models — <https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/supported-models.html> ({official·2026-02-05})
  - facet: availability
  - Limitations: supported-model list is maintained separately from the main Bedrock model catalog and may lag it.

## Source URLs
https://docs.aws.amazon.com/bedrock/latest/userguide/models-supported.html
https://docs.aws.amazon.com/bedrock/latest/userguide/model-parameters-anthropic-claude-messages.html
https://docs.aws.amazon.com/bedrock/latest/userguide/cross-region-inference-support.html
https://docs.aws.amazon.com/bedrock/latest/userguide/prompt-caching.html
https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/supported-models.html
