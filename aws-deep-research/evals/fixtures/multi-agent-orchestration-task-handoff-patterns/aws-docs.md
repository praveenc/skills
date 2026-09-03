## AWS Documentation Findings

- **Claim:** Amazon Bedrock multi-agent collaboration lets a supervisor agent delegate sub-tasks to specialized collaborator agents and consolidate their responses.
  - Source: Amazon Bedrock Agents — Multi-agent collaboration — <https://docs.aws.amazon.com/bedrock/latest/userguide/agents-multi-agent-collaboration.html> ({official·2025-12-01})
  - facet: orchestration-pattern
  - Limitations: describes the managed feature's design; does not benchmark handoff latency.

- **Claim:** Supervisor agents can run in "supervisor" mode, which always routes to collaborators, or "supervisor with routing," which can answer simple requests directly.
  - Source: Amazon Bedrock Agents — Multi-agent collaboration — <https://docs.aws.amazon.com/bedrock/latest/userguide/agents-multi-agent-collaboration.html> ({official·2025-12-01})
  - facet: orchestration-pattern
  - Limitations: mode selection guidance is qualitative, not tied to specific fan-out thresholds.

- **Claim:** AWS Step Functions is documented as a common backbone for durable task handoff between agents, using state machines to track task status and retries.
  - Source: AWS Step Functions Developer Guide — <https://docs.aws.amazon.com/step-functions/latest/dg/welcome.html> ({official·2025-11-15})
  - facet: durable-handoff
  - Limitations: general workflow-orchestration guide, not agent-specific.

- **Claim:** Bedrock AgentCore Runtime documentation describes per-invocation session isolation so handoffs between agents do not leak state across unrelated sessions.
  - Source: Amazon Bedrock AgentCore Runtime — <https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime.html> ({official·2026-01-05})
  - facet: session-isolation
  - Limitations: describes the isolation mechanism, not measured overhead.

- **Claim:** Amazon EventBridge is documented as a pattern for asynchronous agent-to-agent task handoff when a receiving agent may not be immediately available.
  - Source: Amazon EventBridge User Guide — <https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-what-is.html> ({official·2025-10-20})
  - facet: async-handoff
  - Limitations: general event-bus documentation; agent orchestration is one of many documented use cases.

## Source URLs
https://docs.aws.amazon.com/bedrock/latest/userguide/agents-multi-agent-collaboration.html
https://docs.aws.amazon.com/step-functions/latest/dg/welcome.html
https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime.html
https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-what-is.html
