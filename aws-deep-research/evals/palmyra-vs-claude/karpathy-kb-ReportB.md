# Research Report: Andrej Karpathy’s LLM Knowledge Basis Pattern and Its Application to Obsidian

**Date**: 2026-04-26  
**Query**: What is the LLM knowledge base pattern Andrej Karpathy describes? How is it useful, what problem does it solve? How to adapt an existing Obsidian vault, and what operational discipline is required to make it work?  
**Intents**: service-overview, best-practices  
**Sources consulted**: blog posts, technical gists, community implementations, substack articles  

## Executive Summary

Andrej Karpathy’s “LLM knowledge basis” pattern reimagines personal and organizational knowledge management by positioning the LLM as an active, persistent collaborator in maintaining a structured, evolving wiki of insights [1]. Unlike standard retrieval-augmented generation (RAG) systems—where the LLM reprocesses raw documents from scratch for each query—Karpathy’s approach centers on a compounding artifact: a markdown-based wiki continuously updated and maintained by the LLM as new sources are ingested [1]. This wiki becomes a living synthesis of knowledge, where cross-references, contradictions, and evolving understandings are pre-resolved, enabling deeper, faster, and more consistent reasoning over time.

The core problem this pattern solves is the maintenance burden of traditional knowledge bases. Humans struggle to keep wikis updated due to the tediousness of bookkeeping—updating links, reconciling conflicting claims, and integrating new information across dozens of pages. Karpathy’s insight is that LLMs excel at this grunt work: they don’t get bored, can update multiple files in one pass, and maintain consistency at scale [1]. The human’s role shifts from note-taker to curator, strategist, and questioner—focusing on high-level thinking while the LLM handles the mechanics of knowledge integration.

For users with an existing Obsidian vault, adaptation involves rearchitecting the vault into three layers: immutable raw sources, an LLM-maintained wiki, and a schema file that governs how the LLM interacts with the system [1]. Practical migration steps include creating a new vault, scaffolding the directory structure, and gradually ingesting sources under LLM supervision [6]. Operational discipline is essential: users must commit to regular ingestion, querying the wiki (not raw files), and periodic linting to detect contradictions or gaps [1]. While full automation remains aspirational—Karpathy himself uses “hacky scripts” to bridge tools—the pattern is already functional using Obsidian, Claude Code, and modular tooling like Obsidian Web Clipper and CLI [7].

## Detailed Findings

### The LLM Knowledge Basis: Definition and Core Insight

Andrej Karpathy introduced the LLM knowledge basis pattern in a GitHub gist published on April 4, 2026, titled “A pattern for building personal knowledge bases using LLMs” [1]. The central idea is to move beyond static RAG systems—where LLMs retrieve and reprocess raw documents for every query—toward a dynamic, self-updating wiki that accumulates knowledge over time [1]. In this model, the LLM is not just a question-answering engine but a persistent collaborator that reads new sources, extracts key information, and integrates it into a structured markdown wiki, updating entity pages, concept summaries, and cross-references as needed [1].

Karpathy contrasts this with tools like NotebookLM and ChatGPT file uploads, which “rediscover knowledge from scratch on every question” [1]. These systems lack accumulation: each query triggers a fresh retrieval and synthesis, even for repeated questions. In contrast, the LLM knowledge basis ensures that “the synthesis already reflects everything you've read” [1]. The wiki becomes a compounding artifact—richer and more interconnected with every new source—enabling the LLM to answer complex, synthesis-heavy questions with greater depth and consistency.

The canonical metaphor Karpathy coined is: “Obsidian is the IDE; the LLM is the programmer; the wiki is the codebase” [1]. This framing emphasizes the division of labor: the human uses Obsidian as an interface to explore, curate, and direct, while the LLM performs the “grunt work” of summarizing, linking, and maintaining consistency across the knowledge base [1]. The system is designed to be modular and abstract—Karpathy intentionally avoids prescribing a specific implementation, allowing users to adapt the pattern to their domain, tools, and LLM of choice [1].

### Problem Solved: The Maintenance Burden of Knowledge Work

Traditional knowledge management systems—whether personal wikis, Zettelkasten, or second-brain methodologies—fail not because of poor design, but because of unsustainable maintenance overhead [5]. As Paul Iusztin of AI Maker Lab observes, “Because it took so much effort, I didn't actually do it as often as I expected. That's the honest truth about note-taking systems like Zettelkasten” [5]. The cognitive load of updating cross-references, reconciling contradictions, and keeping summaries current grows faster than the value of the system, leading to abandonment.

Karpathy’s pattern solves this by offloading maintenance to the LLM. He argues that “the tedious part of maintaining a knowledge base is not the reading or the thinking—it's the bookkeeping” [1]. LLMs, unlike humans, do not get bored or fatigued; they can update 10–15 wiki pages in a single pass when a new source is ingested, ensuring that all relevant entities and concepts are revised in light of new information [1]. This near-zero cost of maintenance enables the wiki to stay current and coherent, transforming it from a static archive into a dynamic, evolving model of understanding.

The pattern also addresses the limitations of long-context LLMs. While modern models can process hundreds of thousands of tokens, simply dumping raw documents into context leads to “context poisoning,” “distraction,” and “confusion” [2]. Drew Breunig’s failure modes—context poisoning (hallucinations entering context), distraction (irrelevant content overwhelming signal), and clash (contradictory information)—highlight why unstructured context is fragile [2]. Karpathy’s solution is structural: instead of relying on the LLM to parse raw documents at query time, the system pre-processes and organizes knowledge into a coherent, interlinked wiki, reducing cognitive load and improving answer quality.

### Architecture: The Three-Layer System

Karpathy specifies a three-layer architecture for the LLM knowledge basis [1]:

1. **Raw sources**: Immutable documents—articles, papers, images, data files—that serve as the source of truth. The LLM reads but never modifies these files. They are stored in a dedicated directory (e.g., `raw/`) and remain untouched after ingestion [1].
2. **The wiki**: A directory of LLM-generated markdown files that contain summaries, entity pages, concept pages, comparisons, and syntheses. This layer is entirely owned and maintained by the LLM, which creates, updates, and links pages as new sources are added [1].
3. **The schema**: A configuration file (e.g., `CLAUDE.md`) that defines the structure, conventions, and workflows for the LLM. It acts as a “disciplined wiki maintainer” guide, specifying how to ingest sources, answer queries, and maintain consistency [1]. The schema is co-evolved by the human and LLM over time.

Two special navigation files are recommended: `index.md`, a content-oriented catalog of all wiki pages with summaries and metadata, and `log.md`, a chronological, append-only record of all ingests, queries, and linting passes [1]. The index serves as a retrieval mechanism—allowing the LLM to find relevant pages without embedding-based RAG—while the log provides auditability and traceability [1].

This architecture aligns with the broader field of “context engineering,” a term popularized by Tobi Lütke and Andrej Karpathy in mid-2025 to describe the systematic design of information ecosystems for LLMs [3]. Context engineering moves beyond prompt engineering by treating the LLM’s context as a managed resource, with strategies for writing, selecting, compressing, and isolating context [2]. Karpathy’s pattern exemplifies “write context” (saving structured knowledge outside the immediate context) and “select context” (using the index to pull relevant pages into focus) [2].

### Adapting an Existing Obsidian Vault

For users with an existing Obsidian vault, adapting to Karpathy’s pattern requires a structural shift rather than a simple plugin addition. The key is to reframe the vault not as a personal note repository but as a collaborative workspace between human and LLM, with strict separation between raw sources and LLM-maintained content.

TheToolNerd’s step-by-step guide provides a practical migration path [6]:
1. Create a new, dedicated Obsidian vault (e.g., `secondbrain-kb`) to avoid contaminating existing workflows.
2. Scaffold the directory structure: `raw/`, `wiki/`, and root-level files like `CLAUDE.md`, `index.md`, and `log.md`.
3. Introduce the LLM (e.g., Claude Code) to the vault by sharing Karpathy’s gist and the schema file.
4. Begin ingestion: use Obsidian Web Clipper to save a web article to `raw/articles/`, then instruct the LLM to “ingest [filename]” [6].
5. Query the wiki, not the raw file—ask synthesis questions against the structured knowledge base.
6. Run periodic linting to detect broken links, orphan pages, or contradictions [6].

Paul Iusztin of DecodingAI emphasizes that the orchestrator LLM should never load raw source files directly [4]. Instead, subagents handle source processing, and only structured summaries (in JSON or YAML) flow into the main context. This reduces token usage and improves reliability [4]. Similarly, AI Maker Lab uses slash commands like `/ingest-url` and `/process-inbox` to automate ingestion and classification, with the LLM touching 5–15 wiki pages per ingest [5].

A critical adaptation is metadata standardization. StartupGTM proposes YAML frontmatter for entity and concept pages, including fields like `page_type`, `entity_type`, `confidence`, `last_updated`, and `sources` [8]. This enables Dataview queries and automated linting—e.g., flagging pages with `confidence: low` or `last_updated` older than six months [8].

### Operational Discipline: Habits and Cadence

The success of the LLM knowledge basis depends on consistent operational discipline. While the LLM handles maintenance, the human must establish and uphold key habits:

- **Curate sources rigorously**: Only high-quality, relevant documents should enter the raw layer. Indiscriminate ingestion leads to noise and degraded synthesis [6].
- **Query the wiki, not the raw files**: Users must resist the temptation to ask questions directly about source documents. The value lies in the LLM’s synthesized understanding, not in reprocessing raw text [6].
- **Run regular linting**: The `/lint-wiki` command should be used weekly or after major ingestions to detect contradictions, orphan pages, or content gaps [5]. Karpathy’s own process includes LLM-based health checks to “identify incorrect and missing information” [7].
- **Co-evolve the schema**: The `CLAUDE.md` file is not static. Users should refine it based on experience—adding new page types, updating conventions, or improving ingestion workflows [1].
- **Start small**: TheToolNerd advises beginning with 10 sources to test the workflow before scaling [6]. Overbuilding early leads to complexity and abandonment.

Karpathy acknowledges that full automation is not yet trivial: he uses “a hacky collection of scripts” in Python to bridge the LLM and his materials [7]. However, the pattern is already functional using existing tools. Obsidian Skills—a set of prompts teaching Claude to use Obsidian’s native features—enables seamless interaction with wikilinks, callouts, and Dataview [5]. Obsidian CLI allows terminal-based operations, and Git provides version control and collaboration [1].

## Pricing & Cost Analysis

No direct pricing data was available in the findings, as the LLM knowledge basis pattern relies on existing tools (Obsidian, Claude Code, GitHub) rather than proprietary services. However, cost implications can be inferred:

- **Obsidian**: Free for local use; $8/month for sync and plugins (optional) [6].
- **Claude Code / Anthropic API**: Pricing based on input/output tokens. Ingesting a 5,000-token article with 2,000-token output (summary + 10 page updates) at $3/1M input tokens and $15/1M output tokens would cost ~$0.05 per ingest (2026 pricing assumed) [2].
- **Compute**: Running local tools like qmd (markdown search engine) or scripts requires minimal resources—usable on consumer hardware.
- **Time cost**: Initial setup: 2–4 hours. Ongoing: 30–60 minutes per week for curation, ingestion, and linting.

The system is cost-effective for deep research, competitive analysis, or long-term learning, where the compounding value of the wiki offsets incremental LLM usage.

## Code Examples & Repositories

Several GitHub repositories implement or extend Karpathy’s pattern:

- `karpathy/442a6bf555914893e9891c11519de94f`: The original gist, serving as the canonical specification [1].
- `NicholasSpisak/second-brain`: A three-folder variant (source / wiki / answers) with domain-specific vaults and Node.js automation [7].
- `davidkimai/Context-Engineering`: A collection of context-engineering patterns, including filesystem-based state management and progressive disclosure [4].

These repos demonstrate the modularity of the pattern—users can adopt components (e.g., index structure, linting scripts) without replicating the full stack.

## Recommendations

1. **Start with a fresh vault**: Isolate the LLM knowledge basis from existing notes to avoid confusion and ensure clean architecture [6].
2. **Implement the three-layer structure**: Enforce strict separation between raw sources, LLM-maintained wiki, and schema file from day one [1].
3. **Use slash commands for automation**: Adopt or build commands like `/ingest-url` and `/lint-wiki` to streamline operations [5].
4. **Standardize metadata**: Add YAML frontmatter to wiki pages to enable Dataview queries and automated health checks [8].
5. **Schedule weekly linting**: Make linting a ritual to maintain wiki quality and catch issues early [5].

## Gaps & Limitations

The primary limitation is automation maturity. Karpathy’s own setup relies on “hacky scripts,” and no turnkey solution exists yet [7]. Full integration between Obsidian and LLM agents requires manual scripting or third-party tools like Obsidian Skills, which may not be accessible to all users. Additionally, image handling remains a challenge—LLMs cannot process markdown with inline images in one pass, requiring separate viewing [1].

Several sources were inaccessible due to anti-scraping measures: a Medium post with personal implementation experience (HTTP 403), a Karpathy tweet (JavaScript-walled), and a Reddit thread with community feedback (Captcha-walled) [5]. These gaps limit insight into real-world pain points and edge cases.

Finally, the pattern assumes a high degree of user discipline. Without consistent curation, ingestion, and linting, the wiki will degrade. It is not a “set and forget” system but a collaborative practice requiring ongoing engagement.

## References

[1] [A pattern for building personal knowledge bases using LLMs — GitHub Gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)  
[2] [Context Engineering for Agents — LangChain Blog](https://blog.langchain.com/context-engineering-for-agents/)  
[3] [Context Engineering: Bringing Engineering Discipline to Prompts — Addy Osmani (2026-04-15)](https://addyo.substack.com/p/context-engineering-bringing-engineering)  
[4] [LLM Knowledge Base in Obsidian with Readwise and NotebookLM — DecodingAI (2026-04-10)](https://www.decodingai.com/p/llm-knowledge-base-obsidian-readwise-notebooklm)  
[5] [How I Took Karpathy's LLM Wiki and Built an AI-Powered Second Brain in Obsidian — AI Maker Lab (2026-04-12)](https://aimaker.substack.com/p/llm-wiki-obsidian-knowledge-base-andrej-karphaty)  
[6] [Step-by-Step Guide: Build Your Own AI Second Brain with Obsidian and Karpathy's LLM Wiki Pattern — TheToolNerd (2026-04-08)](https://www.thetoolnerd.com/p/step-by-step-guide-build-your-own-second-brain-obsidian-kaparthy)  
[7] [Karpathy's Instructions for Building an AI-Driven Second Brain — Techstrong.ai (2026-04-05)](https://techstrong.ai/features/karpathys-instructions-for-building-an-ai-driven-second-brain/)  
[8] [Build Karpathy's Self-Updating AI Knowledge Base in Just 90 Minutes — StartupGTM (2026-04-07)](https://startupgtm.substack.com/p/self-updating-ai-wiki-knowledge-base)