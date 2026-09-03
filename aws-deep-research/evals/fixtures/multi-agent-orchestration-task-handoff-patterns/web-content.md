## Web Content Findings

- **Claim:** An AWS blog post describes a "blackboard" pattern where agents write intermediate results to a shared memory store rather than passing full context directly between agents.
  - Source: "Design patterns for multi-agent systems on AWS" — <https://aws.amazon.com/blogs/machine-learning/design-patterns-for-multi-agent-systems-on-aws/> ({vendor-claim·2025-11-10})
  - facet: orchestration-pattern
  - Limitations: pattern is presented as guidance, not backed by a published case study in the same post.

- **Claim:** An independent engineering blog reports that explicit handoff contracts (a JSON schema per handoff) reduced downstream parsing errors by roughly 40% in a production multi-agent pipeline.
  - Source: "What we learned building a 12-agent pipeline" — <https://www.anyscale.com/blog/what-we-learned-building-a-12-agent-pipeline> ({third-party·2026-01-18})
  - facet: handoff-contract
  - Limitations: single production case study; the 40% figure is self-reported by the pipeline's own team.

- **Claim:** A community post independently arrives at the same "typed handoff schema" recommendation, citing fewer silent failures when one agent hands work to another.
  - Source: "Stop passing raw strings between your agents" — <https://dev.to/aiplatform/stop-passing-raw-strings-between-your-agents> ({community·2026-01-22})
  - facet: handoff-contract
  - Limitations: practitioner opinion piece; no quantitative failure-rate data given.

- **Claim:** AWS's blog claims supervisor-based orchestration "scales to dozens of collaborator agents with no architectural changes," without publishing a specific tested agent count.
  - Source: "Design patterns for multi-agent systems on AWS" — <https://aws.amazon.com/blogs/machine-learning/design-patterns-for-multi-agent-systems-on-aws/> ({vendor-claim·2025-11-10})
  - facet: scalability
  - Limitations: no benchmark or tested agent count is published to support the scaling claim.

- **Claim:** A re:Post thread notes that supervisor agents can become a bottleneck at high fan-out, recommending a hierarchical "supervisor-of-supervisors" pattern past roughly 10-15 collaborators.
  - Source: re:Post community thread — <https://repost.aws/questions/bedrock-multi-agent-supervisor-bottleneck> ({community·2026-01-28})
  - facet: scalability
  - Limitations: anecdotal threshold from one practitioner's workload, not a controlled benchmark; tension with the AWS scaling claim above.

## Source URLs
https://aws.amazon.com/blogs/machine-learning/design-patterns-for-multi-agent-systems-on-aws/
https://www.anyscale.com/blog/what-we-learned-building-a-12-agent-pipeline
https://dev.to/aiplatform/stop-passing-raw-strings-between-your-agents
https://repost.aws/questions/bedrock-multi-agent-supervisor-bottleneck
