## AWS Documentation Findings — g4dn Instance Family

- **Claim:** g4dn instances use NVIDIA T4 GPUs with 16 GiB of GPU memory per GPU, aimed at ML inference and graphics workloads.
  - Source: Amazon EC2 G4 Instances — <https://aws.amazon.com/ec2/instance-types/g4/> ({vendor-claim·2026-01-15})
  - facet: instance-specs
  - Limitations: page covers both g4dn (NVIDIA) and g4ad (AMD) variants; only g4dn is in scope.

- **Claim:** g4dn.xlarge provides 1 GPU, 4 vCPUs, 16 GiB system memory, and up to 25 Gbps network bandwidth on larger sizes.
  - Source: Amazon EC2 Instance Types — <https://docs.aws.amazon.com/ec2/latest/instancetypes/ac.html> ({official·2026-01-15})
  - facet: instance-specs
  - Limitations: spec table spans the whole accelerated-computing family; only g4dn rows used.

- **Claim:** T4 GPUs support FP16 and INT8 Tensor Core inference, with INT8 commonly used for transformer inference benchmarking.
  - Source: Amazon EC2 User Guide — <https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/instance-types.html> ({official·2026-01-10})
  - facet: gpu-architecture
  - Limitations: summarized from the instance guide, not a dedicated GPU whitepaper.

- **Claim:** Only the largest g4dn size (g4dn.metal / g4dn.12xlarge) reaches the family's 100 Gbps network ceiling; smaller sizes are capped much lower.
  - Source: Amazon EC2 G4 Instances — <https://aws.amazon.com/ec2/instance-types/g4/> ({vendor-claim·2026-01-15})
  - facet: networking
  - Limitations: ceiling figure applies to the largest size only, not the xlarge/2xlarge sizes typically used for single-model inference.

## Source URLs
https://aws.amazon.com/ec2/instance-types/g4/
https://docs.aws.amazon.com/ec2/latest/instancetypes/ac.html
https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/instance-types.html
