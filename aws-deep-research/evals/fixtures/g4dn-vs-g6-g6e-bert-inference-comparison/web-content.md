## Web Content Findings

- **Claim:** An independent benchmark reports BERT-base inference throughput of ~950 sequences/sec on g6.xlarge (L4) versus ~410 sequences/sec on g4dn.xlarge (T4) at batch size 32, roughly a 2.3x uplift.
  - Source: "Benchmarking NVIDIA L4 vs T4 for Transformer Inference" — <https://www.databricks.com/blog/benchmarking-l4-vs-t4-transformer-inference> ({third-party·2026-02-01})
  - facet: benchmark-throughput
  - Limitations: single-run benchmark; batch size and sequence length not exhaustively varied.

- **Claim:** A separate community post independently measured BERT-large throughput on g6e.xlarge (L40S) at ~1,800 sequences/sec, a large uplift consistent in direction with the vendor's inference-performance claim for larger models.
  - Source: "g6e first impressions for NLP inference" — <https://dev.to/mlops-corner/g6e-first-impressions-for-nlp-inference> ({community·2026-02-10})
  - facet: benchmark-throughput
  - Limitations: informal community benchmark; exact software stack/versions not fully disclosed.

- **Claim:** AWS's launch blog claims g6e delivers "up to 4x higher inference performance" than g4dn for large language model workloads.
  - Source: "Announcing new Amazon EC2 G6e instances" — <https://aws.amazon.com/blogs/aws/announcing-new-amazon-ec2-g6e-instances/> ({vendor-claim·2025-12-05})
  - facet: benchmark-throughput
  - Limitations: no benchmark methodology published; the specific 4x figure for BERT workloads is not independently corroborated.

- **Claim:** Practitioners on a re:Post thread report choosing g4dn over g6 for lower-priority batch inference specifically because of g4dn's lower Spot price volatility, despite its older GPU architecture.
  - Source: re:Post community thread — <https://repost.aws/questions/g4dn-vs-g6-batch-inference-cost> ({community·2026-01-25})
  - facet: cost-tradeoff
  - Limitations: anecdotal reports from a small number of practitioners, not a controlled study.

- **Claim:** A GitHub-hosted benchmark suite shows g6.2xlarge sustaining p99 latency of ~18ms for BERT-base at batch size 8, versus ~34ms on g4dn.2xlarge.
  - Source: "optimum-benchmark" GitHub repository — <https://github.com/huggingface/optimum-benchmark> ({third-party·2026-01-30})
  - facet: inference-latency
  - Limitations: results depend on the specific optimization backend configured; not all backends were tested.

- **Claim:** The same independent analysis notes that FP8 quantization support on L4/L40S is not yet widely adopted in production BERT deployments, so real-world gains today skew closer to ~2x rather than peak theoretical throughput.
  - Source: "Benchmarking NVIDIA L4 vs T4 for Transformer Inference" — <https://www.databricks.com/blog/benchmarking-l4-vs-t4-transformer-inference> ({third-party·2026-02-01})
  - facet: benchmark-throughput
  - Limitations: adoption estimate is qualitative, not measured across a representative sample of deployments.

## Source URLs
https://www.databricks.com/blog/benchmarking-l4-vs-t4-transformer-inference
https://dev.to/mlops-corner/g6e-first-impressions-for-nlp-inference
https://aws.amazon.com/blogs/aws/announcing-new-amazon-ec2-g6e-instances/
https://repost.aws/questions/g4dn-vs-g6-batch-inference-cost
https://github.com/huggingface/optimum-benchmark
