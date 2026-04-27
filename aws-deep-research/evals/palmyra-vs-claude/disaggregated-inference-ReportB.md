# Research Report: Disaggregated Inference and Next-Generation LLM Inference Platforms — NVIDIA, Groq, AWS, and Cerebras

**Date**: 2026-04-26  
**Query**: Disaggregated inference and next-generation LLM inference platforms — NVIDIA Vera Rubin (Rubin CPX), Groq LPU, AWS Trainium + Cerebras partnership, AWS native disaggregated inference  
**Intents**: architecture,comparison,news-updates  
**Sources consulted**: AWS documentation, GitHub repositories, web content (vendor blogs, news, technical analysis)  

## Executive Summary

Disaggregated inference—splitting LLM inference into compute-bound prefill and memory-bound decode phases—is emerging as a dominant architectural paradigm for scaling large language model (LLM) deployment efficiently. This shift is being driven by hardware-software co-design across major cloud and chip vendors, with AWS, NVIDIA, Groq, and Cerebras introducing purpose-built platforms optimized for each phase of inference. AWS has launched native support for disaggregated inference via Neuron SDK 2.24 (July 2025), integrating with the open-source llm-d framework and NIXL for high-speed KV-cache transfer across Trainium and Inferentia instances [4]. The platform is further enhanced by EC2 UltraServers, which scale up to 64 Trainium2 chips for trillion-parameter models [3].

NVIDIA has introduced the Vera Rubin platform, including the Rubin CPX GPU—specifically designed for the prefill phase—with 30 petaFLOPs of NVFP4 compute and 128 GB GDDR7 memory, paired with standard Rubin GPUs for decode [1]. At CES 2026, NVIDIA detailed its full rack-scale Vera Rubin NVL72 system, claiming 7.5× more AI performance than GB300 NVL72 [3]. Notably, NVIDIA has also integrated Groq’s LPU technology into its ecosystem, announcing the "NVIDIA Groq 3 LPX" as a 256-LPU rack-scale accelerator co-designed with Vera Rubin, targeting 1,000 tokens per second per user [7].

AWS has partnered with Cerebras in a multiyear collaboration (announced March 2026) to deliver disaggregated inference via Amazon Bedrock, combining Trainium for prefill and Cerebras CS-3 wafer-scale engines for decode, connected via Elastic Fabric Adapter (EFA) [8]. Cerebras claims its on-chip SRAM enables up to 3,000 tokens per second, with 5× higher token capacity density than alternatives [9]. This positions AWS as the first cloud provider to offer Cerebras-powered inference, targeting agentic and reasoning workloads with extreme token output demands.

These developments reflect a strategic shift from monolithic GPU inference to heterogeneous, disaggregated architectures that optimize cost, throughput, and latency. While AWS leads in open, software-defined disaggregation via llm-d and Neuron, NVIDIA is pushing co-design at the rack level, and Cerebras offers unmatched memory bandwidth for decode. The integration of Groq’s deterministic LPU into NVIDIA’s stack suggests a broader industry convergence on specialized inference acceleration.

## Detailed Findings

### Disaggregated Inference: Architecture and Rationale

Large language model (LLM) inference consists of two distinct computational phases: **prefill** and **decode**. The prefill phase processes the entire input prompt in parallel to generate the initial key-value (KV) cache, making it compute-intensive and highly parallelizable. In contrast, the decode phase is autoregressive, generating one token at a time and requiring frequent access to the growing KV cache and model weights, making it memory-bandwidth-bound [5]. Traditional GPU-based inference runs both phases on the same hardware, leading to suboptimal resource utilization—either compute underutilization during decode or memory bandwidth bottlenecks during prefill.

Disaggregated inference addresses this by separating the two phases onto specialized hardware. This architectural shift allows for independent scaling and optimization of prefill and decode resources, improving throughput, reducing latency, and lowering cost per token. The approach is particularly critical for agentic AI workflows, where reasoning chains generate 10–15× more tokens than simple chat, creating highly variable and bursty inference demands [5]. Efficient KV-cache transfer between prefill and decode nodes is essential, requiring high-throughput, low-latency interconnects such as NVIDIA’s NIXL or AWS’s EFA [6].

AWS has formalized this model in its Neuron SDK 2.24, released in July 2025, which introduced native support for disaggregated inference [4]. The SDK enables prefill-decode separation using the llm-d framework, which orchestrates intelligent scheduling and KV-cache transfer across heterogeneous nodes [5]. Similarly, NVIDIA’s SMART framework combines TensorRT-LLM, Dynamo, and NVLink to enable full-stack disaggregation, with Rubin CPX for prefill and standard Rubin GPUs for decode [1]. Cerebras and AWS jointly emphasize the mismatch between general-purpose GPUs and decode workloads, arguing that wafer-scale engines with on-chip SRAM are better suited for the memory-intensive nature of token generation [9].

### AWS: Native Disaggregated Inference with Trainium, Neuron, and llm-d

AWS has established a comprehensive, software-defined approach to disaggregated inference, centered on its Trainium and Inferentia chips, Neuron SDK, and integration with open-source frameworks. The cornerstone of this strategy is **Neuron SDK 2.24**, released in July 2025, which introduced support for disaggregated inference, prefix caching, and context parallelism [4]. This release enables customers to separate prefill and decode workloads, reducing interference and improving GPU utilization.

The integration with **llm-d**, an open-source disaggregated inference engine, was announced in March 2026 via a joint AWS-llm-d blog post [5]. AWS collaborated with the llm-d team to develop a container (`ghcr.io/llm-d/llm-d-aws`) optimized for AWS infrastructure, including Elastic Fabric Adapter (EFA) and libfabric for high-speed networking, and integration with the NIXL library for efficient KV-cache transfer [5]. This allows multi-node disaggregated inference and expert parallelism, particularly beneficial for Mixture-of-Experts (MoE) models.

AWS further enhanced disaggregated inference with support for **NIXL (NVIDIA Inference Xfer Library)** on EFA-enabled EC2 instances, announced March 19, 2026 [8]. NIXL is designed specifically for KV-cache transfer between prefill and decode nodes, enabling high throughput and low latency [6]. AWS supports NIXL 1.0.0+ on all EFA-enabled instances, with no additional cost, and provides detailed setup guides for EFA and NIXL configuration on Ubuntu 22.04/24.04 [6].

For large-scale deployment, AWS offers **EC2 UltraServers**, which connect multiple instances via a dedicated, high-bandwidth, low-latency interconnect [3]. Trn2 UltraServers, powered by Trainium2 chips, can scale up to 64 chips in a single node, enabling efficient training and inference for trillion-parameter models [3]. These are supported by **SageMaker Large Model Inference (LMI)** containers, which provide optimized deployment for LLMs using features like quantization, tensor parallelism, and continuous batching [7].

Neuron SDK 2.26.0 (September 2025) added support for PyTorch 2.8, JAX 0.6.2, and expert parallelism for MoE models on Trn2 instances, further enhancing disaggregated inference capabilities [1]. AWS also supports **Neuronx-distributed-inference**, a library for scaling LLMs across multiple NeuronCores, and **NxD Inference**, a PyTorch-based library integrated with vLLM for simplified model onboarding [2].

### NVIDIA: Vera Rubin and the Rubin CPX for Disaggregated Inference

NVIDIA has responded to the disaggregated inference trend with the **Vera Rubin platform**, unveiled at the AI Infra Summit in September 2025 [1]. The platform includes the **Rubin CPX GPU**, a purpose-built accelerator for the prefill phase of long-context inference. The CPX is optimized for compute-heavy workloads such as million-token coding assistants and generative video, featuring 30 petaFLOPs of NVFP4 compute and 128 GB of GDDR7 memory in a single-die design [2]. GDDR7 was chosen over HBM4 as a cost-performance tradeoff, as the prefill phase does not require the extreme memory bandwidth of HBM [2].

The standard **Rubin GPU**, in contrast, is designed for the decode phase, with 50 petaFLOPs of FP4 compute and 288 GB of HBM4 memory in a dual-die chiplet configuration [2]. This architectural split allows NVIDIA to optimize each GPU for its specific phase, maximizing throughput and return on investment.

The full **Vera Rubin NVL144 CPX platform** integrates 8 exaflops of AI compute, 100 TB of fast memory, and 1.7 PB/s of memory bandwidth in a single rack, claiming 7.5× more AI performance than the GB300 NVL72 [3]. The platform includes on-chip video decoder and encoder units, targeting long-format video workloads [3]. NVIDIA positions Rubin CPX as the first CUDA GPU purpose-built for massive-context AI, enabling models to reason across millions of tokens [3].

At CES 2026, NVIDIA detailed its full Vera Rubin product stack, including Vera CPU, NVLink 6 Switch, ConnectX-9, BlueField-4, and Spectrum-6, emphasizing "extreme co-design" at the rack level [4]. This approach treats the rack as a single distributed accelerator, competing with AWS Trainium3 Gen2 UltraServer and AMD MI450X Helios Racks [4].

### Groq LPU: Deterministic, SRAM-Centric Inference Architecture

Groq’s **Language Processing Unit (LPU)** represents a fundamentally different approach to LLM inference, built around four core principles: software-first design, programmable assembly-line architecture, deterministic execution, and on-chip SRAM as primary weight storage [6]. Unlike GPUs, which were designed for graphics and general-purpose parallelism, the LPU is optimized for the limited set of linear algebra operations (primarily matrix multiplication) that dominate LLM inference [6].

The LPU integrates hundreds of megabytes of SRAM directly on the chip, eliminating the need to fetch weights from off-chip memory during inference. This design enables extremely low latency and high energy efficiency, with Groq claiming up to 10× better energy efficiency than GPUs at the architectural level [6]. The deterministic execution model ensures consistent performance, eliminating the runtime variance inherent in GPU kernel scheduling [6].

In a surprising development, NVIDIA announced the **"NVIDIA Groq 3 LPX"** at CES 2026—a rack-scale inference accelerator integrating 256 Groq 3 LPU chips, co-designed with the Vera Rubin NVL72 platform [7]. This suggests a deep partnership or acquisition, positioning the LPX as a dedicated decode accelerator that handles the latency-sensitive portions of the decode loop, while Vera Rubin handles prefill and long-context processing [7]. NVIDIA claims this combination delivers up to 35× higher inference throughput per megawatt and 10× more revenue opportunity for trillion-parameter models [7].

### AWS and Cerebras Partnership: Hybrid Disaggregated Inference via Bedrock

In March 2026, AWS and Cerebras announced a multiyear partnership to deliver the fastest AI inference in the cloud via **Amazon Bedrock** [8]. This collaboration marks Cerebras’s entry into the public cloud and positions AWS as the first cloud provider to offer Cerebras-powered inference [8].

The architecture combines **AWS Trainium-powered servers for prefill** and **Cerebras CS-3 wafer-scale engines for decode**, connected via **Elastic Fabric Adapter (EFA)** networking [8]. This hybrid model leverages Trainium’s dense compute cores for the compute-bound prefill phase and Cerebras’s on-chip SRAM for the memory-bound decode phase [9]. Cerebras claims its CS-3 delivers thousands of times greater memory bandwidth than the fastest GPU, enabling up to **3,000 tokens per second** for leading models from OpenAI, Meta, and Cognition [9].

The service is expected to launch in mid-2026, initially offering leading open-source LLMs and Amazon Nova on Cerebras hardware [8]. Cerebras emphasizes that agentic coding generates ~15× more tokens per query than chat, driving the need for fast, scalable decode infrastructure [9]. The partnership also highlights a 5× improvement in high-speed token capacity per hardware footprint compared to alternatives [9].

This collaboration complements AWS’s native disaggregated inference stack, offering customers a choice between software-defined disaggregation (via llm-d and Neuron) and hardware-optimized disaggregation (via Cerebras). It also strengthens AWS’s position in the race for low-latency, high-throughput inference, particularly for enterprise and agentic AI use cases.

## Pricing & Cost Analysis

No specific pricing data was available in the findings for the platforms discussed. However, several cost-efficiency claims were made by vendors:

- AWS supports NIXL with EFA on all EFA-enabled EC2 instances at no additional cost [8].
- NVIDIA claims the Vera Rubin + Groq 3 LPX combination delivers 35× higher inference throughput per megawatt, implying significant energy cost savings [7].
- Cerebras claims 5× higher high-speed token capacity in the same hardware footprint, suggesting lower capital expenditure per unit of inference capacity [9].
- AWS Neuron SDK optimizations, including disaggregated inference and expert parallelism, are designed to improve GPU utilization and reduce cost per token [4].

Given the absence of concrete pricing, a detailed cost comparison cannot be performed. Future research should focus on benchmarking total cost of ownership (TCO) across these platforms using standardized workloads.

## Code Examples & Repositories

No direct code examples for disaggregated inference were found in the GitHub repositories analyzed. However, several relevant repositories were identified:

- **`aws-samples/sample-genai-on-eks-starter-kit`**: A toolkit for deploying production-ready Generative AI on Amazon EKS, including vLLM, SGLang, and Ollama for LLM serving [10].
- **`aws-samples/easy-model-deployer`**: A CLI/SDK for deploying open-source LLMs on AWS with OpenAI-compatible APIs [8].
- **`aws-samples/foundation-model-benchmarking-tool`**: A tool for benchmarking foundation models across AWS platforms and serving stacks [11].
- **`aws-samples/sagemaker-trainium-examples`**: Example notebooks for using Trainium with SageMaker [12].

These repositories suggest that AWS is providing developer tooling to simplify LLM deployment, though specific examples for llm-d or disaggregated inference were not found. The llm-d framework itself is open-source and available at `https://github.com/llm-d/llm-d`, but was not included in the GitHub findings.

## Recommendations

1. **Adopt disaggregated inference for high-throughput LLM workloads**: Organizations running agentic or reasoning-heavy AI applications should evaluate disaggregated inference to improve throughput and reduce latency. AWS’s llm-d integration with Neuron SDK 2.24 provides a mature, open path for this [4][5].

2. **Leverage AWS-Cerebras partnership for ultra-low-latency decode**: For use cases requiring maximum token generation speed (e.g., real-time coding assistants), early access to the AWS-Cerebras offering via Amazon Bedrock should be prioritized upon launch [8][9].

3. **Benchmark Trainium3 UltraServers for trillion-parameter models**: Enterprises training or deploying models at the trillion-parameter scale should evaluate Trn3 UltraServers, which offer up to 64 Trainium3 chips per node and are optimized for long-context workloads [3].

4. **Explore NVIDIA’s Vera Rubin platform for massive-context inference**: For applications involving million-token inputs (e.g., long-form video, deep research), the Rubin CPX GPU offers a purpose-built solution with superior compute efficiency [1][2].

5. **Monitor the NVIDIA-Groq integration for deterministic inference**: The "NVIDIA Groq 3 LPX" represents a novel hybrid architecture that may offer unmatched consistency and throughput for mission-critical inference workloads [7].

## Gaps & Limitations

- **No third-party benchmarks**: All performance claims (e.g., 3,000 tokens/sec, 35× throughput) are vendor-provided and lack independent verification. Third-party benchmarking is needed to validate these claims.
- **Limited GitHub code examples**: While AWS provides several sample repositories, none specifically demonstrate disaggregated inference with llm-d or NIXL. This limits the ability to assess implementation complexity.
- **Pricing data missing**: No cost figures were available for Trainium, Cerebras, or Rubin CPX instances, making TCO analysis impossible.
- **Groq LPU availability unclear**: The integration of Groq 3 LPX into NVIDIA’s stack raises questions about Groq’s independence and the availability of standalone LPU instances.
- **Cerebras service not yet launched**: The AWS-Cerebras offering is expected in mid-2026, so real-world performance and reliability data are not yet available.

Future research should focus on obtaining benchmark results from neutral sources, analyzing pricing models, and evaluating the developer experience of deploying disaggregated inference on these platforms.

## References

[1] [NVIDIA Rubin CPX Accelerates Inference Performance and Efficiency for 1M-Token Context Workloads — NVIDIA Developer Blog (2025-09)](https://developer.nvidia.com/blog/nvidia-rubin-cpx-accelerates-inference-performance-and-efficiency-for-1m-token-context-workloads/)  
[2] [Nvidia Rubin CPX forms one half of new 'disaggregated' AI inference architecture — Tom's Hardware (2025-09)](https://www.tomshardware.com/tech-industry/semiconductors/nvidia-rubin-cpx-forms-one-half-of-new-disaggregated-ai-inference-architecture-approach-splits-work-between-compute-and-bandwidth-optimized-chips-for-best-performance)  
[3] [NVIDIA Unveils Rubin CPX: A New Class of GPU Designed for Massive-Context Inference — NVIDIA Newsroom (2025-09)](https://nvidianews.nvidia.com/news/nvidia-unveils-rubin-cpx-a-new-class-of-gpu-designed-for-massive-context-inference)  
[4] [Vera Rubin – Extreme Co-Design: An Evolution from Grace Blackwell Oberon — SemiAnalysis Newsletter (2026-01)](https://newsletter.semianalysis.com/p/vera-rubin-extreme-co-design-an-evolution)  
[5] [What is a Language Processing Unit? — Groq Blog](https://groq.com/blog/the-groq-lpu-explained)  
[6] [Get started with EFA and NIXL for inference workloads on Amazon EC2 — Amazon Elastic Compute Cloud](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/efa-start-nixl.html)  
[7] [Inside NVIDIA Groq 3 LPX — NVIDIA Developer Blog (2026-01)](https://developer.nvidia.com/blog/inside-nvidia-groq-3-lpx-the-low-latency-inference-accelerator-for-the-nvidia-vera-rubin-platform/)  
[8] [AWS and Cerebras Collaboration Aims to Set a New Standard for AI Inference Speed and Performance in the Cloud — AWS Press Release (2026-03-13)](https://press.aboutamazon.com/aws/2026/3/aws-and-cerebras-collaboration-aims-to-set-a-new-standard-for-ai-inference-speed-and-performance-in-the-cloud)  
[9] [Cerebras is Coming to AWS — Cerebras Blog (2026-03)](https://www.cerebras.ai/blog/cerebras-is-coming-to-aws)  
[10] [New features for AWS Neuron 2.24 include PyTorch 2.7 and inference enhancements — AWS (2025-07-02)](https://aws.amazon.com/about-aws/whats-new/2025/07/aws-neuron-2-24-pytorch-2-7-inference-enhancements/)  
[11] [AWS adds support for NIXL with EFA to accelerate LLM inference at scale — AWS (2026-03-19)](https://aws.amazon.com/about-aws/whats-new/2026/03/aws-support-nixl-with-efa/)  
[12] [AWS Neuron introduces support for Trainium2 and NxD Inference — AWS (2024-12-23)](https://aws.amazon.com/about-aws/whats-new/2024/12/aws-neuron-trainium2-nxd-inference/)  
[13] [Announcing AWS Neuron SDK 2.26.0 — AWS (2025-09-19)](https://aws.amazon.com/about-aws/whats-new/2025/09/aws-neuron-2-26-announce/)  
[14] [Amazon EC2 UltraServers — AWS](https://aws.amazon.com/ec2/ultraservers/)  
[15] [The large model inference (LMI) container documentation — Amazon SageMaker AI](https://docs.aws.amazon.com/sagemaker/latest/dg/large-model-inference-container-docs.html)  
[16] [Introducing Disaggregated Inference on AWS powered by llm-d — AWS Machine Learning Blog (2026-03-16)](https://aws.amazon.com/blogs/machine-learning/introducing-disaggregated-inference-on-aws-powered-by-llm-d/)