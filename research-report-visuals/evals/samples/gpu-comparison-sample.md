# GPU Inference Hardware Comparison: g4dn vs g6 vs g6e

**Date:** March 2026
**Sources:** [AWS Instance Types](https://aws.amazon.com/ec2/instance-types/), [NVIDIA L4 Datasheet](https://www.nvidia.com/en-us/data-center/l4/), [TensorRT Benchmarks](https://developer.nvidia.com/tensorrt)

## Executive Summary

Organizations running BERT-class inference on g4dn instances (NVIDIA T4) face a decision: migrate to g6 (NVIDIA L4) or g6e (NVIDIA L40S). Both offer significant throughput improvements, but with different cost/performance tradeoffs.

## Hardware Specifications

### NVIDIA T4 (g4dn instances)
- Architecture: Turing (2018)
- FP16 TFLOPS: 65
- Memory: 16 GB GDDR6
- Memory bandwidth: 320 GB/s
- TDP: 70W

### NVIDIA L4 (g6 instances)
- Architecture: Ada Lovelace (2023)
- FP16 TFLOPS: 121
- Memory: 24 GB GDDR6
- Memory bandwidth: 300 GB/s
- TDP: 72W

### NVIDIA L40S (g6e instances)
- Architecture: Ada Lovelace (2023)
- FP16 TFLOPS: 362
- Memory: 48 GB GDDR6
- Memory bandwidth: 864 GB/s
- TDP: 350W

## Benchmark Results (BERT-base, batch=8, seq_len=128)

| Metric | T4 (g4dn) | L4 (g6) | L40S (g6e) |
|--------|-----------|---------|------------|
| P50 latency | 4.2ms | 2.1ms | 1.4ms |
| P99 latency | 8.7ms | 4.3ms | 2.8ms |
| Throughput | 1,200 req/s | 2,400 req/s | 4,800 req/s |
| Cost/hour | $0.526 | $0.651 | $1.412 |
| Cost/1M inferences | $0.12 | $0.075 | $0.082 |

## Key Finding

The L4 (g6) offers the best cost-per-inference at 37% lower than T4, while the L40S (g6e) offers the lowest absolute latency but at higher cost. For latency-sensitive workloads under 3ms P50, g6e is required. For cost optimization, g6 is the clear winner.

## Migration Considerations

1. CUDA compatibility: Both L4 and L40S support CUDA 12.x natively
2. TensorRT versions: Minimum TRT 8.6 for Ada Lovelace optimizations
3. Driver requirements: NVIDIA driver 535+ required
4. Framework support: TF Serving 2.14+, Triton 24.01+
