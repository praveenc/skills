## AWS Documentation Findings — g6 / g6e Instance Family

- **Claim:** g6 instances use NVIDIA L4 GPUs with 24 GiB of GPU memory per GPU, targeting mixed inference and graphics workloads.
  - Source: Amazon EC2 G6 Instances — <https://aws.amazon.com/ec2/instance-types/g6/> ({vendor-claim·2026-01-20})
  - facet: instance-specs
  - Limitations: vendor product page; per-size breakdown given in a separate spec table.

- **Claim:** g6e instances use NVIDIA L40S GPUs with 48 GiB of GPU memory per GPU, aimed at larger-model inference and fine-tuning.
  - Source: Amazon EC2 G6e Instances — <https://aws.amazon.com/ec2/instance-types/g6e/> ({vendor-claim·2026-01-20})
  - facet: instance-specs
  - Limitations: vendor product page; does not itself include third-party throughput numbers.

- **Claim:** g6.xlarge provides 1 GPU, 4 vCPUs, 16 GiB system memory, and a 10 Gbps baseline network allocation.
  - Source: Amazon EC2 Instance Types — <https://docs.aws.amazon.com/ec2/latest/instancetypes/ac.html> ({official·2026-01-20})
  - facet: instance-specs
  - Limitations: baseline bandwidth only; burstable ceiling documented separately per size.

- **Claim:** L4 and L40S GPUs use the Ada Lovelace architecture with 4th-generation Tensor Cores and FP8 support, unlike the Turing-based T4 in g4dn.
  - Source: Amazon EC2 Instance Types — <https://docs.aws.amazon.com/ec2/latest/instancetypes/ac.html> ({official·2026-01-20})
  - facet: gpu-architecture
  - Limitations: architecture family is documented; FP8 adoption in real workloads is not covered here.

- **Claim:** g6e.48xlarge supports up to 400 Gbps network bandwidth, versus a 100 Gbps ceiling on the largest g4dn size.
  - Source: Amazon EC2 G6e Instances — <https://aws.amazon.com/ec2/instance-types/g6e/> ({vendor-claim·2026-01-20})
  - facet: networking
  - Limitations: figure applies only to the largest g6e size, not the xlarge size used in most single-GPU inference comparisons.

## Source URLs
https://aws.amazon.com/ec2/instance-types/g6/
https://aws.amazon.com/ec2/instance-types/g6e/
https://docs.aws.amazon.com/ec2/latest/instancetypes/ac.html
