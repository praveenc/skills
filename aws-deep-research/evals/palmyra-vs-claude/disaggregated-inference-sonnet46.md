# Research Report: Disaggregated Inference and Next-Generation LLM Inference Platforms

**Date**: 2026-04-26
**Query**: Disaggregated inference and next-generation LLM inference platforms — NVIDIA Vera Rubin (Rubin CPX), Groq LPU, AWS Trainium + Cerebras partnership, AWS native disaggregated inference (Neuron SDK, llm-d, SageMaker LMI)
**Intents**: architecture, comparison, news-updates
**Sources consulted**: AWS official documentation, AWS What's New announcements, AWS ML Blog, NVIDIA Developer Blog, NVIDIA Newsroom, Groq official site, Cerebras blog, AWS press release, SemiAnalysis newsletter, Tom's Hardware, GitHub repositories
**Synthesizer backend**: Writer Palmyra X5 (Bedrock)

---

## Executive Summary

The LLM inference landscape is undergoing a structural shift driven by a single architectural insight: the two phases of inference — **prefill** (compute-bound) and **decode** (memory-bandwidth-bound) — have fundamentally different hardware requirements, and co-locating them on identical hardware wastes both [1]. Disaggregated inference separates these phases onto purpose-built hardware, enabling higher throughput, lower latency, and better cost efficiency at scale. In the agentic era, where models generate 10× more tokens through complex reasoning chains compared to single-shot replies, this architectural separation is becoming the gating factor for production deployments [5].

Every major platform vendor has converged on disaggregation as the organizing principle for next-generation inference. NVIDIA unveiled the Rubin CPX GPU in September 2025 as a purpose-built context-phase accelerator, pairing it with the standard Rubin GPU for decode in a rack-scale disaggregated system [3]. Groq's LPU architecture — built around deterministic execution and on-chip SRAM — has been integrated into NVIDIA's platform as the "NVIDIA Groq 3 LPX," targeting decode-phase latency at near-1,000 tokens per second per user [7]. AWS has simultaneously pursued disaggregation on two fronts: natively through the Neuron SDK (disaggregated inference shipped in Neuron 2.24, July 2025) [4] and via open-source orchestration through a March 2026 collaboration with the llm-d project [5]; and through a landmark partnership with Cerebras announced March 13, 2026, which pairs Trainium-powered prefill nodes with Cerebras CS-3 wafer-scale decode nodes connected over EFA [8].

The competitive picture as of April 2026 is one of rapid convergence: the same disaggregation concept is being implemented at the chip level (Rubin CPX), the rack level (Vera Rubin NVL144 CPX), the software orchestration level (llm-d + NIXL on AWS), and the hybrid-hardware level (Trainium + Cerebras CS-3). Organizations evaluating inference infrastructure must now choose not just a chip, but an entire disaggregated stack.

---

## Detailed Findings

### The Disaggregated Inference Concept

LLM inference divides into two computationally distinct phases. The **prefill phase** processes the entire input prompt in parallel to generate the initial set of key-value (KV) cache entries; it is compute-bound and benefits from high FLOP/s throughput [5]. The **decode phase** autoregressively generates one token at a time, requiring the model weights and the ever-growing KV cache to be read from memory on every step; it is memory-bandwidth-bound and benefits from high memory bandwidth and low-latency interconnects [5].

Traditional deployments co-locate both phases on the same GPU fleet, leading to resource contention: prefill-heavy batches starve decode operations of memory bandwidth, while decode-heavy workloads underutilize the compute available for prefill [5]. Disaggregated inference solves this by routing prefill requests to a compute-optimized pool and decode requests to a memory-bandwidth-optimized pool, with KV-cache tensors transferred between pools over a high-speed fabric [1][5]. The critical enabling technology for this transfer is a low-latency, high-throughput KV-cache transport layer — implemented variously as NVLink (NVIDIA), EFA + NIXL (AWS), or on-chip SRAM (Cerebras/Groq).

---

### NVIDIA Vera Rubin Platform and Rubin CPX

NVIDIA unveiled the Rubin CPX GPU at the AI Infra Summit in September 2025, positioning it as the first CUDA GPU purpose-built for the context (prefill) phase of disaggregated inference [3]. Jensen Huang described it as "the first CUDA GPU purpose-built for massive-context AI, where models reason across millions of tokens of knowledge at once" [3].

**Hardware specifications** (vendor-reported, not independently verified):

| Attribute | Rubin CPX | Standard Rubin GPU |
|---|---|---|
| AI Compute (FP4/NVFP4) | 30 petaFLOPs | 50 petaFLOPs |
| Memory | 128 GB GDDR7 | 288 GB HBM4 |
| Die design | Single-die | Dual-die chiplet |
| Primary use | Context/prefill phase | Generation/decode phase |

The choice of GDDR7 over HBM4 for the CPX is a deliberate cost-optimization: the context phase does not require the extreme memory bandwidth of HBM, but does require high compute density [2]. Tom's Hardware noted that the CPX's 30 PFLOPs figure is close to what a single die of the dual-die standard Rubin would deliver (~25 PFLOPs per half), suggesting the CPX may be a single optimized die from the standard Rubin design [2].

At the rack scale, the **Vera Rubin NVL144 CPX platform** is claimed to deliver 8 exaflops of AI compute, 100 TB of fast memory, and 1.7 PB/s of memory bandwidth in a single rack — representing a claimed 7.5× more AI performance than the GB300 NVL72 [3]. NVIDIA's monetization claim is $5B in token revenue for every $100M invested in the platform (vendor-reported, no third-party verification) [3]. Early customers exploring Rubin CPX include Cursor, Runway, and Magic [3].

NVIDIA's full-stack disaggregated framework is branded **SMART** (System for Massive AI Reasoning and Throughput), combining Blackwell/Rubin hardware, NVFP4 low-precision inference, TensorRT-LLM, and NVIDIA Dynamo as the orchestration layer [1]. At CES 2026, NVIDIA detailed all six Rubin platform products: Rubin GPU, Vera CPU, NVLink 6 Switch, ConnectX-9, BlueField-4, and Spectrum-6 — framing the rack as a single distributed accelerator [4 — SemiAnalysis].

---

### Groq LPU Architecture and NVIDIA Integration

Groq's Language Processing Unit (LPU) was designed from first principles for LLM inference rather than adapted from graphics workloads. Four core design principles differentiate it from GPUs [6]:

1. **Software-first**: the compiler, not runtime heuristics, determines execution schedules.
2. **Programmable assembly-line architecture**: operations are pipelined deterministically rather than dispatched dynamically.
3. **Deterministic execution**: the compiler produces fixed schedules, eliminating the runtime variance inherent in GPU kernel execution.
4. **On-chip SRAM as primary weight storage**: hundreds of MB of SRAM store model weights directly on-chip, feeding compute units at full speed without DRAM round-trips [5][6].

The rationale is architectural: GPUs were designed for independent parallel operations (graphics rendering). LLM inference is dominated by a limited set of linear algebra operations — primarily matrix multiplications — that do not benefit from GPU generality and pay a significant overhead penalty for it [6]. Groq claims LPUs run LLMs up to 10× more energy-efficiently than GPUs at the architectural level (vendor claim, no third-party benchmark cited) [6].

**The NVIDIA-Groq integration** represents the most significant development in this space. NVIDIA announced the **"NVIDIA Groq 3 LPX"** as a rack-scale inference accelerator co-designed with the Vera Rubin NVL72 platform [7]. The LPX integrates 256 NVIDIA Groq 3 LPU accelerators and targets generation speeds approaching **1,000 tokens per second per user** — described as "speed of thought computing" [7]. In the disaggregated architecture, the LPX handles the latency-sensitive portions of the decode loop (FFN-attention and scale-up communication) while the Vera Rubin NVL72 handles prefill and long-context processing [7]. NVIDIA claims the combined Vera Rubin + LPX platform delivers up to **35× higher inference throughput per megawatt** and **10× more revenue opportunity** for trillion-parameter models versus prior-generation platforms (vendor-reported, no third-party verification) [7].

This integration effectively means Groq's LPU technology is now embedded within NVIDIA's platform naming and go-to-market — a significant strategic development for both companies.

---

### AWS Native Disaggregated Inference Stack

AWS has built disaggregated inference support across multiple layers of its stack, from silicon to orchestration.

#### Trainium2 and EC2 UltraServers

AWS Trainium2 (Trn2) instances were introduced with Neuron SDK 2.21 in December 2024, including the `trn2.48xlarge` instance type and the Trn2 UltraServer configuration [2 — AWS]. The **Trn2 UltraServer** scales up to 64 Trainium2 chips connected via NeuronLink, AWS's dedicated high-bandwidth, low-latency accelerator interconnect [9]. UltraServers connect multiple EC2 instances using this dedicated interconnect, enabling access to significantly more compute and memory than standalone instances — targeting trillion-parameter-scale inference [9].

EC2 UltraServers are built on the AWS Nitro System and support EFA networking for scale-out across tens of thousands of accelerators on a petabit-scale non-blocking network [9]. Two UltraServer configurations are currently available: Trn2 UltraServers (Trainium2) and P6e-GB200 UltraServers (NVIDIA GB200 NVL72, up to 72 Blackwell GPUs in one NVLink domain) [9].

#### Neuron SDK Disaggregated Inference (2.24, July 2025)

AWS Neuron 2.24, released July 2, 2025, introduced native disaggregated inference support in the NxD Inference (NxDI) library [4]. Key features in this release:

- **Disaggregated inference**: reduces prefill-decode interference by separating the two phases [4]
- **Prefix caching**: accelerates Time-To-First-Token (TTFT) for repeated prompt prefixes [4]
- **Context parallelism**: improves performance on long sequences [4]
- **PyTorch 2.7 support** and expanded Qwen 2.5 model compatibility [4]

The NxD Inference library, introduced in Neuron 2.21, is a PyTorch-based library integrated with vLLM that simplifies deployment of large language and multimodal models with minimal code changes [2 — AWS]. Neuron 2.26 (September 2025) further extended capabilities with expert parallelism support (beta) for Mixture-of-Experts models, Llama 4 Scout and Maverick support (beta), and PyTorch 2.8 / JAX 0.6.2 compatibility [1 — AWS].

#### llm-d Integration and NIXL/EFA (March 2026)

On March 16, 2026, AWS published a joint announcement with the llm-d open-source project, introducing disaggregated inference orchestration for Kubernetes-based deployments [5]. The collaboration produced a dedicated container — `ghcr.io/llm-d/llm-d-aws` — that bundles AWS-specific libraries (EFA, libfabric) and integrates llm-d with the **NIXL (NVIDIA Inference Xfer Library)** for KV-cache transfer between prefill and decode nodes [5].

**llm-d** is an open-source inference orchestration framework that provides four key capabilities beyond what vLLM alone offers [5]:

1. **Intelligent inference scheduling**: routes requests to the optimal node based on KV-cache state, load, and request characteristics.
2. **Prefill/decode disaggregation**: physically separates prefill and decode pods, with KV-cache tensors transferred via NIXL over EFA.
3. **Wide expert parallelism**: distributes MoE expert layers across nodes for efficient trillion-parameter serving.
4. **Tiered prefix caching**: multi-level caching to maximize KV-cache reuse and minimize TTFT.

The AWS deployment targets **Amazon SageMaker HyperPod EKS** and **Amazon EKS** as the primary Kubernetes substrates [5]. AWS conducted extensive benchmarking across multiple iterations before the stable release.

Separately, on March 19, 2026, AWS announced native support for **NIXL with EFA** across all EFA-enabled EC2 instance types [10]. NIXL 1.0.0+ with EFA installer 1.47.0+ delivers increased KV-cache throughput, reduced inter-token latency, and optimized KV-cache memory utilization [10]. NIXL is interoperable with all EFA-enabled instances and integrates natively with NVIDIA Dynamo, SGLang, and vLLM [10]. This support is available at no additional cost in all AWS regions [10].

#### SageMaker LMI Containers

The SageMaker Large Model Inference (LMI) container provides a managed path for deploying LLMs on SageMaker AI, supporting quantization, tensor parallelism, and continuous batching [11]. LMI documentation is hosted on the Deep Java Library (DJL) site and covers backend selection, instance type guidance, and performance tuning. The LMI container is the managed-service complement to the self-managed llm-d/EKS path for customers who prefer SageMaker's operational abstraction.

---

### AWS + Cerebras Partnership (March 2026)

The most architecturally novel development in the AWS ecosystem is the multiyear partnership with Cerebras announced March 13, 2026 [8]. This is a primary-source announcement from the AWS press office.

**Architecture**: The integrated system pairs **Trainium-powered servers for prefill** with **Cerebras CS-3 systems for decode**, connected via Elastic Fabric Adapter (EFA) networking [8]. This is a hardware-level instantiation of the disaggregated inference concept: Trainium's dense compute cores handle the compute-bound prefill phase, while the CS-3's wafer-scale SRAM stores all model weights on-chip, delivering what Cerebras describes as "thousands of times greater memory bandwidth than the fastest GPU" for the memory-bandwidth-bound decode phase [9 — Cerebras].

**Key claims** (vendor-reported):
- AWS is the **first cloud provider** to offer Cerebras's disaggregated inference solution [8]
- Service will be available exclusively through **Amazon Bedrock**, launching "in the next couple of months" from the March 2026 announcement (i.e., approximately May–June 2026) [8]
- Later in 2026, AWS will offer leading open-source LLMs and Amazon Nova on Cerebras hardware [8]
- Cerebras CS-3 provides **5× more high-speed token capacity** in the same hardware footprint vs alternatives (vendor claim, no third-party benchmark) [9 — Cerebras]
- Cerebras systems have powered models from OpenAI, Cognition, and Meta at up to **3,000 tokens per second** (vendor claim) [9 — Cerebras]
- David Brown (VP Compute & ML Services, AWS): "splitting inference across Trainium and CS-3, connecting with EFA, each system does what it's best at. The result will be inference an order of magnitude faster and higher performance than what's available today" [8]

The Cerebras CS-3 is built around the **WSE-3 (Wafer Scale Engine 3)**, a single-die chip the size of an entire silicon wafer. The wafer-scale design enables on-chip SRAM storage of entire model weight sets, eliminating the DRAM bandwidth bottleneck that limits GPU decode performance. This is architecturally analogous to Groq's LPU SRAM approach but at a dramatically larger scale.

The partnership is significant for AWS's competitive positioning: it gives AWS a decode-phase accelerator that is architecturally differentiated from NVIDIA's GPU stack, while Trainium handles the prefill phase where AWS silicon is already competitive.

---

### Competitive Architecture Comparison

| Platform | Prefill Hardware | Decode Hardware | KV-Cache Transport | Orchestration |
|---|---|---|---|---|
| NVIDIA Vera Rubin + LPX | Rubin CPX (GDDR7, 30 PFLOPs) | Rubin GPU + Groq 3 LPX | NVLink 6 | NVIDIA Dynamo |
| AWS Trainium + Cerebras | Trainium2/3 (NeuronLink) | Cerebras CS-3 (WSE-3 SRAM) | EFA | Amazon Bedrock |
| AWS Native (llm-d) | Any EFA-enabled EC2 | Any EFA-enabled EC2 | EFA + NIXL | llm-d on EKS/HyperPod |
| AWS Neuron SDK (NxDI) | Trn2 NeuronCores | Trn2 NeuronCores | NeuronLink | vLLM + NxDI |

All four approaches implement the same prefill/decode separation concept but differ in whether the hardware specialization is at the chip level (Rubin CPX vs Rubin GPU; Trainium vs CS-3) or the software/scheduling level (llm-d routing homogeneous GPU/Trainium pods).

---

## Pricing & Cost Analysis

Specific pricing data for the new platforms was not available in the findings. The following is known:

- **NIXL with EFA on AWS**: available at no additional cost on all EFA-enabled EC2 instance types [10]
- **Rubin CPX / Vera Rubin NVL144 CPX**: NVIDIA's monetization claim is $5B in token revenue per $100M platform investment (vendor-reported, no independent verification) [3]
- **AWS + Cerebras on Bedrock**: pricing not announced as of the March 2026 press release; service described as launching "in the next couple of months" [8]
- **Trn2 UltraServer**: available as On-Demand, Reserved, Spot, or Savings Plan instances [2 — AWS]; specific pricing not retrieved

A full pricing comparison was not possible with available data. See Gaps & Limitations.

---

## Code Examples & Repositories

The GitHub findings returned several relevant AWS repositories, though none are specifically dedicated to disaggregated inference or llm-d integration. The most relevant repositories identified:

**[aws-samples/foundation-model-benchmarking-tool](https://github.com/aws-samples/foundation-model-benchmarking-tool)** (255 stars, last updated Feb 2026) — Benchmarks any model on any AWS platform across instance types and serving stacks. Useful for evaluating disaggregated vs. co-located inference performance on Trainium and GPU instances.

**[aws-samples/sample-genai-on-eks-starter-kit](https://github.com/aws-samples/sample-genai-on-eks-starter-kit)** (53 stars, last updated Apr 2026) — Production-ready GenAI infrastructure on Amazon EKS including vLLM, SGLang, and Ollama serving. Relevant as a substrate for llm-d disaggregated deployments.

**[aws-samples/deepseek-using-vllm-on-eks](https://github.com/aws-samples/deepseek-using-vllm-on-eks)** (69 stars, last updated Feb 2026) — vLLM deployment on EKS, directly applicable to the llm-d/NIXL disaggregated inference pattern.

**[aws-samples/easy-model-deployer](https://github.com/aws-samples/easy-model-deployer)** (74 stars, last updated Jan 2026) — Deploy open-source LLMs on AWS with OpenAI-compatible APIs; useful for rapid prototyping before moving to disaggregated production deployments.

The primary llm-d codebase lives at `llm-d.ai` and the AWS-specific container is published at `ghcr.io/llm-d/llm-d-aws` [5]. The NIXL library is at `github.com/ai-dynamo/nixl` [6 — EC2 docs]. Neither was returned by the GitHub search queries, likely because they are not under the `aws` or `aws-samples` GitHub organizations.

---

## Recommendations

1. **Adopt NIXL + EFA for existing GPU-based disaggregated inference immediately.** AWS supports NIXL 1.0.0+ with EFA at no additional cost on all EFA-enabled instances [10]. For teams already running vLLM, SGLang, or NVIDIA Dynamo on EC2, enabling NIXL for KV-cache transfer between prefill and decode nodes is the lowest-friction path to disaggregated inference gains. Start with the official EFA + NIXL getting-started guide [6].

2. **Evaluate llm-d on SageMaker HyperPod EKS for production-scale disaggregated serving.** The `ghcr.io/llm-d/llm-d-aws` container is the most complete AWS-native disaggregated inference stack available today, combining intelligent scheduling, prefill/decode separation, expert parallelism, and tiered prefix caching [5]. Teams running large MoE models (e.g., Llama 4 Maverick, DeepSeek) at scale should prioritize this path over manual vLLM multi-node configurations.

3. **Plan for the AWS + Cerebras Bedrock service as a managed decode-acceleration option.** The Trainium + CS-3 disaggregated architecture targets an order-of-magnitude inference speed improvement for decode-heavy workloads [8]. For agentic and coding assistant use cases — where Cerebras reports ~15× more tokens per query than chat [9 — Cerebras] — the Bedrock-managed service (expected ~May–June 2026) warrants a proof-of-concept evaluation as soon as it becomes available.

4. **Use the Foundation Model Benchmarking Tool to quantify disaggregation gains before committing to infrastructure.** The `aws-samples/foundation-model-benchmarking-tool` supports cross-instance and cross-serving-stack benchmarking. Run it to measure TTFT, inter-token latency, and throughput under your specific workload mix (input/output length distribution, concurrency) before choosing between Trn2 UltraServer + NxDI, llm-d on GPU, or the Cerebras Bedrock service.

5. **Track the NVIDIA Vera Rubin + Groq 3 LPX platform for 2026–2027 planning.** The Rubin CPX + LPX disaggregated rack represents the most aggressive hardware-level specialization for inference [3][7]. AWS already offers P6e-GB200 UltraServers [9], and Rubin-based instances are likely to follow. Organizations with long-context workloads (coding assistants, video, deep research) should include Rubin CPX availability in their 18-month infrastructure roadmap.

---

## Gaps & Limitations

**Pricing data absent for key platforms.** No pricing was retrieved for Rubin CPX/NVL144 CPX, Cerebras CS-3 on Bedrock, or Trn2 UltraServer on-demand rates. A follow-up query to AWS pricing pages and NVIDIA partner pricing would be needed for TCO analysis.

**Cerebras CS-3 / WSE-3 technical specifications not retrieved.** The findings include Cerebras's architectural claims (on-chip SRAM, 3,000 tokens/second, 5× token capacity) from the Cerebras blog [9 — Cerebras] and AWS press release [8], but no independent technical datasheet or third-party benchmark for the CS-3 was found. All CS-3 performance claims should be treated as vendor-reported until independently verified.

**Rubin CPX availability timeline unclear.** The September 2025 announcement [3] and January 2026 CES details [4 — SemiAnalysis] do not include a GA date or AWS instance availability timeline for Rubin CPX-based instances. The P6e-GB200 (Blackwell) is currently available on AWS [9]; Rubin CPX instances have not been announced.

**llm-d benchmarking results not fully retrieved.** The AWS ML Blog post [5] references "extensive benchmarking" with specific results, but the full content was truncated in the findings. The actual throughput and latency improvement numbers from the llm-d disaggregated inference benchmarks were not captured. Reviewing the full blog post directly is recommended.

**SageMaker LMI v15 specifics not confirmed.** The research contract referenced "SageMaker LMI v15" but the findings only confirm the existence of LMI containers and their documentation location [11]; no version-specific changelog for v15 was retrieved. The DJL documentation site (`docs.djl.ai`) should be consulted directly for LMI release notes.

**Groq's independent commercial status post-NVIDIA integration is unclear.** The web findings describe "NVIDIA Groq 3 LPX" as a co-designed product [7], but it is not clear whether Groq Systems operates independently, has been acquired, or is a technology licensee. This has implications for customers evaluating standalone Groq Cloud inference vs. NVIDIA-integrated LPX deployments.

**GitHub search did not surface llm-d or NIXL repositories.** The GitHub queries returned general AWS inference samples rather than the specific llm-d or neuronx-distributed-inference repositories. The canonical llm-d repository and the `aws-neuron/neuronx-distributed-inference` GitHub repository should be consulted directly for implementation details.

**Azure and GCP excluded per scope.** No cross-cloud comparison data was gathered. For organizations evaluating multi-cloud inference strategies, a follow-up research pass covering Google TPU v6 (Trillium) and Azure ND H200 v5 disaggregated inference would provide a complete competitive picture.

---

## References

[1] [NVIDIA Rubin CPX Accelerates Inference Performance and Efficiency for 1M-Token Context Workloads — NVIDIA Developer Blog (September 2025)](https://developer.nvidia.com/blog/nvidia-rubin-cpx-accelerates-inference-performance-and-efficiency-for-1m-token-context-workloads/)

[2] [Nvidia Rubin CPX forms one half of new 'disaggregated' AI inference architecture — Tom's Hardware (September 2025)](https://www.tomshardware.com/tech-industry/semiconductors/nvidia-rubin-cpx-forms-one-half-of-new-disaggregated-ai-inference-architecture-approach-splits-work-between-compute-and-bandwidth-optimized-chips-for-best-performance)

[3] [NVIDIA Unveils Rubin CPX: A New Class of GPU Designed for Massive-Context Inference — NVIDIA Newsroom (September 2025)](https://nvidianews.nvidia.com/news/nvidia-unveils-rubin-cpx-a-new-class-of-gpu-designed-for-massive-context-inference)

[4] [Vera Rubin – Extreme Co-Design: An Evolution from Grace Blackwell Oberon — SemiAnalysis Newsletter (January 2026)](https://newsletter.semianalysis.com/p/vera-rubin-extreme-co-design-an-evolution)

[5] [Introducing Disaggregated Inference on AWS powered by llm-d — AWS ML Blog (March 16, 2026)](https://aws.amazon.com/blogs/machine-learning/introducing-disaggregated-inference-on-aws-powered-by-llm-d/)

[6] [Get started with EFA and NIXL for inference workloads on Amazon EC2 — AWS EC2 Documentation](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/efa-start-nixl.html)

[7] [Inside NVIDIA Groq 3 LPX: The Low-Latency Inference Accelerator for the NVIDIA Vera Rubin Platform — NVIDIA Developer Blog](https://developer.nvidia.com/blog/inside-nvidia-groq-3-lpx-the-low-latency-inference-accelerator-for-the-nvidia-vera-rubin-platform/)

[8] [AWS and Cerebras Collaboration Aims to Set a New Standard for AI Inference Speed and Performance in the Cloud — AWS Press Release (March 13, 2026)](https://press.aboutamazon.com/aws/2026/3/aws-and-cerebras-collaboration-aims-to-set-a-new-standard-for-ai-inference-speed-and-performance-in-the-cloud)

[9] [Amazon EC2 UltraServers — AWS](https://aws.amazon.com/ec2/ultraservers/)

[10] [AWS adds support for NIXL with EFA to accelerate LLM inference at scale — AWS What's New (March 19, 2026)](https://aws.amazon.com/about-aws/whats-new/2026/03/aws-support-nixl-with-efa/)

[11] [The large model inference (LMI) container documentation — Amazon SageMaker AI](https://docs.aws.amazon.com/sagemaker/latest/dg/large-model-inference-container-docs.html)

[12] [New features for AWS Neuron 2.24 include PyTorch 2.7 and inference enhancements — AWS What's New (July 2, 2025)](https://aws.amazon.com/about-aws/whats-new/2025/07/aws-neuron-2-24-pytorch-2-7-inference-enhancements/)

[13] [AWS Neuron introduces support for Trainium2 and NxD Inference — AWS What's New (December 23, 2024)](https://aws.amazon.com/about-aws/whats-new/2024/12/aws-neuron-trainium2-nxd-inference/)

[14] [Announcing AWS Neuron SDK 2.26.0 — AWS What's New (September 19, 2025)](https://aws.amazon.com/about-aws/whats-new/2025/09/aws-neuron-2-26-announce/)

[15] [Groq LPU Architecture — Groq](https://groq.com/lpu-architecture)

[16] [What is a Language Processing Unit? — Groq Blog](https://groq.com/blog/the-groq-lpu-explained)

[17] [Cerebras is Coming to AWS — Cerebras Blog (March 2026)](https://www.cerebras.ai/blog/cerebras-is-coming-to-aws)