# Palmyra X5 vs Claude — synthesizer eval (3 cases)

Generated: 2026-04-26 08:13:51

Both backends read the **identical** findings files from the shared
`$WORK_DIR/<slug>/` directories. Only the synthesizer model differs.

- **Claude reports**: `$WORK_DIR/<slug>/<slug>-report.md` (produced by the default synthesizer agent in prior sessions)
- **Palmyra reports**: `evals/palmyra-vs-claude/<slug>-palmyra.md` (produced by `scripts/synthesize_palmyra.py` during this spike)

## Summary table

| # | Slug | Input bytes | Claude report bytes | Palmyra report bytes | Claude words | Palmyra words | Claude cites | Palmyra cites | Claude refs | Palmyra refs |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | `aws-health-api-overview-sentiment-oss-alternatives` | 34806 | 22894 | 17266 | 2913 | 2207 | 107 | 73 | 27 | 12 |
| 2 | `bedrock-guardrails-contextual-grounding-enterprise-accuracy` | 67607 | 35317 | 21251 | 4713 | 2742 | 154 | 73 | 15 | 9 |
| 3 | `bedrock-automated-reasoning-checks-rag-oss-alternatives` | 100156 | 33206 | 19123 | 4049 | 2546 | 216 | 83 | 35 | 9 |

## Per-case structural diff

### aws-health-api-overview-sentiment-oss-alternatives

```
metric                                  Claude         Palmyra
------                                  ------         -------
bytes                                    22894           17266
words                                     2913            2207
H2 sections (##)                             6               6
H3 sections (###)                            7               4
citation markers [N]                       107              73
unique [N] markers                          27              13
references entries                          27              12
```

**Claude Executive Summary head:**


AWS Health API is a service that provides programmatic access to notifications about events affecting the health and availability of AWS infrastructure and resources in a customer's account [1]. Events range from regional outages and service degradations to scheduled maintenance and account-specific issues like EC2 instance retirements [1]. The service delivers notifications through several channels — the AWS Health Dashboard (free for all accounts), Amazon EventBridge (free, event-driven), and the Health API itself (requires a Business or Enterprise Support plan) [9]. Most customers integrate Health events through EventBridge rules that route to Lambda functions, SNS topics, or chat platforms like Slack and Microsoft Teams [3][5].

Customer sentiment is decidedly mixed. Users appreciate the personal (account-specific) Health Dashboard as more reliable than the public status page [11], and enterprise customers value the Organizations-level aggregation for multi-account visibility [7]. However, significant frustrations persist: the dashboard itself was affected during a major US-EAST-1 outage — undermining trust in the very tool meant to report outages [10] — and the requirement for a paid Business or Enterprise Support plan to access the API programmatically is a recurring pain point for smaller organizations [12][13].

No open-source tool can fully replace AWS Health API, because its core value — first-party knowledge of AWS internal incidents and maintenance — is proprietary data only AWS can generate [1]. However, several open-source tools complement it effectively. Cloud Custodian (5,966 stars) can react to Health events and trigger automated remediation [20]. Steampipe (7,785 stars) can query Health data via SQL [18]. Prowler (13,634 stars) adds proactive security and compliance scanning [16]. The practical approach is to use AWS Health API as the event source and layer open-source tools on top for alerting, analysis, and automation.

---


**Palmyra Executive Summary head:**


AWS Health is a service that provides real-time notifications about operational events affecting AWS infrastructure, including outages, scheduled changes, and account-specific issues. It comprises two main components: the AWS Health Dashboard (formerly Personal Health Dashboard), which offers a visual interface accessible to all AWS customers, and the AWS Health API, which enables programmatic access to event data but requires a Business, Enterprise On-Ramp, or Enterprise Support plan [5]. The API delivers events categorized by type (`issue`, `scheduledChange`, `accountNotification`, `investigation`) and actionability (`ACTION_REQUIRED`, `ACTION_MAY_BE_REQUIRED`, `INFORMATIONAL`), allowing organizations to automate responses via Amazon EventBridge, Lambda, and other AWS services [1].

Community sentiment reveals both appreciation and criticism. Users value the AWS Health Dashboard for its early visibility into service disruptions not always reflected on the public status page, but express concern about its reliability during major outages, as the dashboard itself can be impacted by the very incidents it reports [10]. A significant point of frustration is the paywall on the Health API, which locks smaller organizations without premium support plans out of automated monitoring capabilities [12]. Despite these concerns, AWS Health remains a critical tool for incident awareness and response coordination.

No open-source tool fully replicates the AWS Health API, as it provides proprietary, first-party data about AWS infrastructure health that cannot be externally sourced. However, several open-source tools complement AWS Health by enabling proactive monitoring, automated remediation, and enhanced observability. Notable examples include Prowler for security and compliance auditing [6], Cloud Custodian for policy enforcement and auto-remediation [10], and Steampipe for querying AWS Health events using SQL [8]. These tools integrate with AWS Health via EventBridge or direct API calls, forming a layered approach to cloud health management.


---

### bedrock-guardrails-contextual-grounding-enterprise-accuracy

```
metric                                  Claude         Palmyra
------                                  ------         -------
bytes                                    35317           21251
words                                     4713            2742
H2 sections (##)                            14               7
H3 sections (###)                           20               5
citation markers [N]                       154              73
unique [N] markers                          15               9
references entries                          15               9
```

**Claude Executive Summary head:**


- **What it is.** Contextual grounding is a safeguard policy inside Amazon Bedrock Guardrails that **detects and filters hallucinations** in model responses by comparing the response against a customer-supplied *reference source* (the grounding context) and a *user query*. It was added in July 2024 as the fifth Guardrails safeguard alongside the new `ApplyGuardrail` API [^1][^7].
- **Two independent scores.** Each evaluated response gets a **Grounding score** ("is the response factually supported by the source?") and a **Relevance score** ("does the response actually answer the user's query?"). Both are confidence scores between 0 and 1 and each has its own configurable threshold (valid range 0 to 0.99; 1 is invalid because it would block everything) [^1][^2].
- **Block or observe.** For each filter (`GROUNDING` or `RELEVANCE`), the `action` can be `BLOCK` (replace the response with a canned blocked message) or `NONE` (don't intervene, but return the detection in the trace so teams can log and analyze) [^3][^4].
- **Supported use cases.** Summarization, paraphrasing, and single-turn question answering are officially supported. **Multi-turn conversational QA / chatbots are explicitly called out as *not* a supported use case** because context evolves across turns [^1][^7].
- **Integrates with RAG.** Retrieved passages from Amazon Bedrock Knowledge Bases, or any custom retriever, are passed as the `grounding_source`. Guardrails (including contextual grounding) plug directly into the `RetrieveAndGenerate` pipeline, and can also be enforced via the standalone `ApplyGuardrail` API against *any* FM — Bedrock, self-hosted, or third-party like OpenAI or Google Gemini [^5][^6][^7][^10].
- **AWS-reported effectiveness.** AWS claims contextual grounding checks filter **over 75% of hallucinated responses** in RAG and summarization workloads, with Automated Reasoning checks reaching up to **99% validation accuracy** on their targeted logical checks [^7][^9].
- **Pricing.** Contextual grounding is billed at **$0.10 per 1,000 text units**, where a text unit is up to 1,000 characters and is computed across `source + query + response` combined [^8].
- **Enterprise accuracy angle.** For banks and retailers, contextual grounding is the probabilistic first line of defense that ties chatbot / assistant answers to curated enterprise corpora (policy docs, product catalog, FAQs, T&Cs). For regulated banking flows where provability matters, it is typically layered with **Automated Reasoning checks** (deterministic, rule-based, with natural-language explanations) [^9][^11][^12].

---


**Palmyra Executive Summary head:**


Amazon Bedrock Guardrails' contextual grounding check is a critical safeguard designed to detect hallucinations and irrelevance in generative AI responses by evaluating them against a provided reference source and user query. It operates by generating two confidence scores—grounding and relevance—each ranging from 0 to 1, which assess whether the model’s output is factually supported by the source material and whether it directly answers the user’s question, respectively. These scores enable enterprises to enforce accuracy and compliance, particularly in high-stakes domains like banking and retail where factual integrity is paramount [1]. The feature supports use cases such as summarization, paraphrasing, and single-turn question answering, but explicitly excludes conversational or multi-turn chatbot interactions due to limitations in streaming evaluation [1].

Contextual grounding integrates seamlessly with Retrieval-Augmented Generation (RAG) workflows via Amazon Bedrock Knowledge Bases, allowing organizations to ground responses in proprietary data without fine-tuning models. When combined with the `ApplyGuardrail` API, it enables centralized policy enforcement across both Bedrock-hosted and third-party foundation models, supporting consistent governance and auditability [6]. Customers can configure thresholds for grounding and relevance between 0 and 0.99, with AWS recommending a starting point of 0.7 for both; increasing thresholds reduces hallucination leakage at the cost of higher false-positive blocking rates [1]. The service is priced at $0.10 per 1,000 text units, where a text unit is defined as up to 1,000 characters across the combined input of grounding source, query, and model response [2].

In financial services, contextual grounding helps mitigate regulatory risks by ensuring responses align with policy documents and underwriting rules, often complemented by Automated Reasoning checks for deterministic validation of structured logic [9]. In retail, it ensures product recommendations and customer support responses are grounded in catalog data, preventing misinformation about pricing, availability, or features [7]. However, limitations include lack of native support for multi-turn conversations, potential for irrelevant content to stream before being flagged, and absence of customer-reported performance metrics beyond AWS’s internal benchmark of filtering over 75% of hallucinated responses in RAG workloads [1].


---

### bedrock-automated-reasoning-checks-rag-oss-alternatives

```
metric                                  Claude         Palmyra
------                                  ------         -------
bytes                                    33206           19123
words                                     4049            2546
H2 sections (##)                            13               7
H3 sections (###)                            8               4
citation markers [N]                       216              83
unique [N] markers                          35               9
references entries                          35               9
```

**Claude Executive Summary head:**


- **What ARC is.** Automated Reasoning checks (ARC) is a policy type in Amazon Bedrock Guardrails that validates natural-language content produced by a foundation model against a formal, logic-based policy derived from your source documents. Unlike content filters or topic policies (binary allow/deny), ARC is a *verification layer* that returns structured, mathematically grounded feedback about *why* a response is correct or incorrect [1][2].
- **Timeline.** ARC was previewed at AWS re:Invent 2024 (December 3, 2024), at the time positioned as the first integration of automated reasoning into a major cloud provider's generative-AI stack [3]. General availability was announced August 6, 2025 [1], with further enhancements (natural-language test-QA generation, expanded regions) added in November 2025 [4].
- **How it works.** You upload a source document; Bedrock extracts **variables**, **custom enum types**, and **logical rules** (if-then constraints) into an *Automated Reasoning Policy* resource through `CreateAutomatedReasoningPolicy` and a build workflow [5][6][7]. At runtime, `ApplyGuardrail` (or a guardrail attached to `Converse`/`InvokeModel`/`InvokeAgent`/`RetrieveAndGenerate`) translates the model response into logical claims, runs an SMT-style solver against the policy, and returns one of seven finding types: `VALID`, `INVALID`, `SATISFIABLE`, `IMPOSSIBLE`, `TRANSLATION_AMBIGUOUS`, `TOO_COMPLEX`, or `NO_TRANSLATIONS` [8][9][10].
- **The science.** ARC is a direct descendant of the AWS Automated Reasoning Group's "provable security" stack (Zelkova, Tiros, s2n, boot-code proofs). Byron Cook's group has applied theorem proving / SMT to AWS for ~a decade; ARC reuses the same NL-to-logic → solver pattern for LLM validation [11][12][13]. AWS claims up to 99% verification accuracy, contrasted with probabilistic grounding techniques [1].
- **Use cases.** Regulated, rule-heavy domains: mortgage approval, insurance underwriting/triage/claims, HR/benefits eligibility, healthcare eligibility, compliance and legal/contract Q&A, and customer-facing policy chatbots [2][14].
- **RAG and chatbots.** ARC plugs into Bedrock Knowledge Bases (`RetrieveAndGenerate`), Agents (`InvokeAgent`), and direct LLM calls because it is a Guardrail policy. It operates in *detect* mode (it does not block by itself) and is complementary to Contextual Grounding checks: grounding asks "did you stick to the retrieved context?", ARC asks "is the answer consistent with the formal rules encoded from that context?" [9][15]. ARC does not support streaming, is English-only, and has no native multi-turn memory — chatbots should validate per turn [2].
- **Open-source landscape.** No OSS project replicates ARC end-to-end. The closest *slices* are: Logic-LM (NL→symbolic→Z3/Prover9) for the translation-plus-solver core [16]; Z3 itself as the underlying SMT engine [17]; NeMo Guardrails and Guardrails AI for the policy-management/dialog-rails surface [18][19]; TruLens/Ragas/SelfCheckGPT for probabilistic faithfulness evaluation [20][21][22]; and LMQL/Guidance for constrained decoding [23][24]. None offer managed NL→formal-logic authoring + SMT verification + proof-style explanations as a single product.
- **Pricing gap.** The AWS Pricing MCP did not surface an ARC SKU at time of research; pricing is documented on the Bedrock pricing page and Bedrock User Guide "Pricing" section rather than retrievable via the Pricing API at the time of this work [25].

---


**Palmyra Executive Summary head:**


Amazon Bedrock Guardrails Automated Reasoning Checks (ARC) is a formal verification system that uses mathematical logic to validate the factual accuracy of large language model (LLM) outputs against human-authored domain policies. Announced at AWS re:Invent 2024 and generally available as of August 2025, ARC provides up to 99% verification accuracy by translating natural language claims into logical forms and evaluating them using Satisfiability Modulo Theories (SMT) solvers, a technique rooted in AWS's decade-long use of automated reasoning for infrastructure security [1]. ARC is designed to detect hallucinations, highlight unstated assumptions, and generate mathematically verifiable explanations, making it particularly valuable in regulated domains such as financial services, healthcare, and human resources [2].

The ARC workflow begins with uploading a source document (e.g., a policy manual) from which AWS automatically extracts logical rules and variables to form a formal policy [3]. This policy is then applied at inference time to validate LLM responses, returning structured findings such as `VALID`, `INVALID`, or `SATISFIABLE`, along with natural language explanations that cite specific rules and variable assignments [4]. ARC complements probabilistic methods like contextual grounding by providing deterministic, provable assurance of correctness, and it integrates seamlessly with Retrieval-Augmented Generation (RAG) systems—where contextual grounding ensures answers are supported by retrieved documents, and ARC ensures they comply with formal business rules [5].

Despite its power, ARC has limitations: it supports only English, does not protect against prompt injection, and operates on complete responses (no streaming) [2]. Pricing details remain opaque due to incomplete data from AWS's pricing API, though usage is metered per text unit [6]. Open-source alternatives such as Guardrails AI, NVIDIA NeMo Guardrails, and LMQL offer rule-based or constrained generation approaches but lack ARC’s formal verification core [7]. The closest conceptual analog is Logic-LLM, a research project that translates natural language to symbolic logic and uses solvers like Z3, but it lacks ARC’s managed policy lifecycle and production-ready integration [8]. No existing OSS project fully replicates ARC’s end-to-end pipeline of document ingestion, rule extraction, formal validation, and explainable feedback.


---

## Qualitative review checklist (fill in manually after eyeballing)

For each case, score 1 (worse) / 0 (tie) / +1 (better) — Palmyra relative to Claude:

| Case | Structure fidelity | Citation discipline | Prose tightness | Coverage | Actionability | Verdict |
|---|---|---|---|---|---|---|
| `aws-health-api-overview-sentiment-oss-alternatives` | ? | ? | ? | ? | ? | ? |
| `bedrock-guardrails-contextual-grounding-enterprise-accuracy` | ? | ? | ? | ? | ? | ? |
| `bedrock-automated-reasoning-checks-rag-oss-alternatives` | ? | ? | ? | ? | ? | ? |

## Cost & latency (from run)

| Case | Input tokens | Output tokens | Latency | Cost (USD) |
|---|---:|---:|---:|---:|
| aws-health-api | 8,811 | 3,421 | 45.8 s | $0.0258 |
| bedrock-guardrails | 16,716 | 4,218 | 57.7 s | $0.0353 |
| bedrock-automated-reasoning | 25,721 | 3,882 | 55.3 s | $0.0387 |

Palmyra X5 pricing used: $0.60/1M input, $6.00/1M output.
