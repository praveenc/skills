## AWS Pricing Findings

- **Claim:** On-Demand pricing for g4dn.xlarge in us-east-1 is $0.526/hour, priced as of 2026-02-14.
  - Source: Amazon EC2 On-Demand Pricing — <https://aws.amazon.com/ec2/pricing/on-demand/> ({official·2026-02-14})
  - facet: pricing-g4dn
  - Limitations: On-Demand list price only; excludes EBS and data transfer.

- **Claim:** On-Demand pricing for g6.xlarge in us-east-1 is $0.8048/hour, priced as of 2026-02-14.
  - Source: Amazon EC2 On-Demand Pricing — <https://aws.amazon.com/ec2/pricing/on-demand/> ({official·2026-02-14})
  - facet: pricing-g6
  - Limitations: On-Demand list price only; region-specific, other regions vary.

- **Claim:** On-Demand pricing for g6e.xlarge in us-east-1 is $1.861/hour, priced as of 2026-02-14.
  - Source: Amazon EC2 On-Demand Pricing — <https://aws.amazon.com/ec2/pricing/on-demand/> ({official·2026-02-14})
  - facet: pricing-g6e
  - Limitations: On-Demand list price only; larger sizes scale roughly linearly but were not individually verified.

- **Claim:** A 1-year No Upfront Savings Plan brings g6.xlarge's effective hourly cost to roughly $0.523/hour, about a 35% discount off On-Demand, priced as of 2026-02-14.
  - Source: AWS Savings Plans Pricing — <https://aws.amazon.com/savingsplans/compute-pricing/> ({official·2026-02-14})
  - facet: pricing-savings-plan
  - Limitations: discount rate depends on term/commitment chosen; figure shown is for 1-year No Upfront.

- **Claim:** g6e.xlarge Spot pricing was observed at approximately $0.62/hour in us-east-1, roughly a 67% discount off On-Demand, priced as of 2026-02-14.
  - Source: EC2 Spot Instance Advisor — <https://aws.amazon.com/ec2/spot/instance-advisor/> ({official·2026-02-14})
  - facet: pricing-spot
  - Limitations: Spot prices fluctuate continuously; snapshot at query time, not a guaranteed rate.

- **Claim:** A cost-per-inference analysis estimates g6.xlarge is roughly 22% cheaper per 1,000 BERT-base inferences than g4dn.xlarge once the measured throughput uplift is factored in, despite the higher hourly rate.
  - Source: "Benchmarking NVIDIA L4 vs T4 for Transformer Inference" — <https://www.databricks.com/blog/benchmarking-l4-vs-t4-transformer-inference> ({third-party·2026-02-01})
  - facet: cost-per-inference
  - Limitations: derived metric combining official pricing with a third-party throughput measurement, not an AWS-published figure.

## Source URLs
https://aws.amazon.com/ec2/pricing/on-demand/
https://aws.amazon.com/savingsplans/compute-pricing/
https://aws.amazon.com/ec2/spot/instance-advisor/
https://www.databricks.com/blog/benchmarking-l4-vs-t4-transformer-inference
