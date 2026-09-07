## GitHub Repository Findings

- **Claim:** The awslabs/agent-squad repository provides an open-source framework for orchestrating multiple AI agents using a supervisor/router pattern with pluggable intent classifiers.
  - Source: awslabs/agent-squad — <https://github.com/awslabs/agent-squad> ({official·2025-09-01})
  - facet: framework
  - Limitations: repo README describes design intent; no independent adoption metrics reviewed.

- **Claim:** The langchain-ai/langgraph repository implements graph-based agent orchestration with explicit state channels used to hand off data between nodes.
  - Source: langchain-ai/langgraph — <https://github.com/langchain-ai/langgraph> ({third-party·2025-08-15})
  - facet: framework
  - Limitations: description drawn from repo documentation, not a hands-on evaluation.

- **Claim:** strands-agents/sdk-python includes a "handoff_to_agent" tool primitive that lets one agent explicitly transfer control and context to another named agent.
  - Source: strands-agents/sdk-python — <https://github.com/strands-agents/sdk-python> ({official·2026-01-10})
  - facet: handoff-primitive
  - Limitations: primitive's behavior under partial-failure handoff not covered in the reviewed docs.

- **Claim:** microsoft/autogen documents a "GroupChat" orchestration pattern where a manager agent selects the next speaker/agent each turn based on conversation state.
  - Source: microsoft/autogen — <https://github.com/microsoft/autogen> ({third-party·2025-07-01})
  - facet: orchestration-pattern
  - Limitations: pattern description from project docs; scaling behavior at high agent counts not covered.

- **Claim:** The joaomdmoura/crewAI repository implements a "Crew" abstraction where tasks are handed off between role-based agents in a defined process order, either sequential or hierarchical.
  - Source: joaomdmoura/crewAI — <https://github.com/joaomdmoura/crewAI> ({community·2025-06-20})
  - facet: orchestration-pattern
  - Limitations: community-maintained project; process-order guarantees not independently verified.

## Source URLs
https://github.com/awslabs/agent-squad
https://github.com/langchain-ai/langgraph
https://github.com/strands-agents/sdk-python
https://github.com/microsoft/autogen
https://github.com/joaomdmoura/crewAI
