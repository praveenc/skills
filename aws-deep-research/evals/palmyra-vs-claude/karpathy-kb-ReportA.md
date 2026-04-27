# Research Report: Karpathy's LLM Knowledge Base Pattern — Concept, Rationale, and Obsidian Adaptation

**Date**: 2026-04-26
**Query**: What is the LLM knowledge base pattern Andrej Karpathy describes? How is it useful, what problem does it solve? How to adapt an existing Obsidian vault, and what operational discipline is required to make it work?
**Intents**: service-overview, best-practices
**Sources consulted**: Primary GitHub gist (Karpathy), practitioner blog posts, community implementation guides, context-engineering theory posts

---

## Executive Summary

On April 4, 2026, Andrej Karpathy published a GitHub gist describing a pattern he calls a "personal LLM knowledge base" — a persistent, LLM-maintained wiki of markdown files that sits between a person's raw source documents and their questions [1]. The core problem it solves is the statelessness of conventional AI document tools: every RAG system, every ChatGPT file upload, every NotebookLM session starts from zero, rediscovering the same knowledge from scratch on every query with no accumulation across sessions [1]. Karpathy's pattern breaks that cycle by having the LLM incrementally build and maintain a structured wiki — updating entity pages, flagging contradictions, strengthening cross-references — so that each new source makes the entire knowledge base smarter rather than just adding another file to a pile [1]. The post went viral, generating an estimated 16–19 million impressions on X [8].

The pattern is organized around three layers (raw sources, wiki, schema), three operations (ingest, query, lint), and two navigation files (`index.md` and `log.md`) [1]. Obsidian is Karpathy's own chosen interface, and the adaptation path for an existing vault is well-documented by early adopters: restructure into the three-layer directory, author a schema file (`CLAUDE.md` or equivalent), and let an agentic LLM (Claude Code, Cursor, Windsurf) own the wiki layer entirely while you own curation and questioning [5][6]. The operational discipline required is lighter than traditional note-taking systems precisely because the LLM absorbs the maintenance burden — but it is not zero. Consistent source ingestion, periodic lint passes, and a deliberately small initial scope are the habits that separate a compounding knowledge base from an abandoned one [6][7].

---

## Detailed Findings

### The Problem Karpathy Is Solving

The starting point is a critique of how most people currently use LLMs with documents. Karpathy writes directly: "Most people's experience with LLMs and documents looks like RAG: you upload a collection of files, the LLM retrieves relevant chunks at query time, and generates an answer. This works, but the LLM is rediscovering knowledge from scratch on every question. There's no accumulation." [1] The failure mode is compounding: ask a question that requires synthesizing five documents and the LLM has to find and reassemble the relevant fragments every time, from scratch, with no memory that it has done this before [1].

This critique extends to the entire category of "AI knowledge" tools. As one practitioner framing puts it: "Every 'AI knowledge' tool on the market right now is a smarter search engine. It's not a knowledge system… Ask the same question tomorrow and it runs the same search again. The answer might even differ because it pulled from a different set of documents." [8] The problem is architectural, not a matter of model quality.

The second problem Karpathy identifies is the human maintenance burden on traditional wikis and note-taking systems. Humans abandon wikis because the bookkeeping — updating cross-references, keeping summaries current, noting when new data contradicts old claims — grows faster than the value it produces [1]. This is the honest diagnosis that practitioners confirm: "Because it took so much effort, I didn't actually do it as often as I expected. That's the honest truth about note-taking systems like Zettelkasten and 'building a second brain.' The theory is beautiful; in practice, the maintenance kills it." [5]

### The Core Idea: A Persistent, Compounding Wiki

Karpathy's solution is to interpose a new layer between raw sources and queries: a structured, interlinked collection of markdown files that the LLM builds and maintains incrementally. When a new source arrives, the LLM does not merely index it for later retrieval — it reads it, extracts key information, and integrates it into the existing wiki: updating entity pages, revising topic summaries, noting contradictions, strengthening the evolving synthesis [1].

The canonical metaphor Karpathy coined captures the role division precisely: **"Obsidian is the IDE; the LLM is the programmer; the wiki is the codebase."** [1] The human's job is to curate sources, direct the analysis, and ask good questions. The LLM's job is everything else — the summarizing, cross-referencing, filing, and bookkeeping [1].

The historical framing Karpathy himself offers is Vannevar Bush's 1945 Memex concept: a personal, curated knowledge store with associative trails between documents. "Bush's vision was closer to this than to what the web became: private, actively curated, with the connections between documents as valuable as the documents themselves. The part he couldn't solve was who does the maintenance. The LLM handles that." [1] The context-engineering literature frames the same idea in systems terms: the LLM context window is like RAM in an operating system — limited capacity, requiring deliberate management of what gets written out, selected in, compressed, and isolated [2].

### The Three-Layer Architecture

Karpathy specifies three distinct layers, each with a clear ownership model [1]:

**Layer 1 — Raw Sources.** Curated source documents: articles, papers, images, data files. These are **immutable** — the LLM reads them but never modifies them. They are the source of truth. The Obsidian Web Clipper browser extension is Karpathy's recommended capture tool for converting web articles to markdown [1].

**Layer 2 — The Wiki.** A directory of LLM-generated markdown files: summaries, entity pages, concept pages, comparisons, an overview, a synthesis. **The LLM owns this layer entirely.** It creates pages, updates them when new sources arrive, maintains cross-references, and keeps everything consistent. A useful taxonomy of page types includes entity pages (people, companies, products), concept pages (frameworks, mental models), source summary pages, pattern pages (recurring themes), and synthesis pages that connect dots across the wiki [8].

**Layer 3 — The Schema.** A configuration document — `CLAUDE.md` for Claude Code, `AGENTS.md` for Codex, or equivalent — that tells the LLM how the wiki is structured, what the conventions are, and what workflows to follow when ingesting sources, answering questions, or maintaining the wiki. Karpathy calls this "the key configuration file — it's what makes the LLM a disciplined wiki maintainer rather than a generic chatbot. You and the LLM co-evolve this over time." [1]

Two special navigation files complete the architecture. **`index.md`** is content-oriented: a catalog of every page in the wiki with a link, one-line summary, and optional metadata, organized by category. The LLM reads the index first when answering a query, then drills into relevant pages. Karpathy notes this works "surprisingly well at moderate scale (~100 sources, ~hundreds of pages) and avoids the need for embedding-based RAG infrastructure." [1] **`log.md`** is chronological: an append-only record of every ingest, query, and lint pass, with consistent prefixes (e.g., `## [2026-04-02] ingest | Article Title`) so that `grep "^## \[" log.md | tail -5` returns the last five entries instantly [1].

### The Three Operations

**Ingest** is the primary growth mechanism. Drop a new source into `raw/`, tell the LLM to process it. The LLM reads the source, discusses key takeaways, writes a summary page, updates the index, and updates relevant entity and concept pages across the wiki. Karpathy notes: "A single source might touch 10–15 wiki pages." [1] This cross-file integration is what distinguishes the pattern from simple summarization — the new source is woven into the existing fabric rather than appended to a pile.

**Query** is where the compounding value becomes visible. You ask questions against the wiki rather than against raw files. The LLM searches relevant pages, reads them, and synthesizes an answer with citations. Crucially, good answers can be filed back into the wiki as new pages: "A comparison you asked for, an analysis, a connection you discovered — these are valuable and shouldn't disappear into chat history." [1] This closes the loop: querying the wiki also enriches it.

**Lint** is the health-check operation. Periodically, ask the LLM to audit the wiki for: contradictions between pages, stale claims superseded by newer sources, orphan pages with no inbound links, important concepts mentioned but lacking their own page, missing cross-references, and data gaps that could be filled with a web search [1]. One practitioner is blunt about the stakes: "Most people skip this part. That is a mistake." [6]

### Why the Maintenance Problem Is Solved

The key insight is economic. Karpathy: "LLMs don't get bored, don't forget to update a cross-reference, and can touch 15 files in one pass. The wiki stays maintained because the cost of maintenance is near zero." [1] The compounding effect that practitioners observe follows directly: "Every new source the LLM ingests makes the whole wiki smarter. It becomes a network that grows denser over time… Three completely different topics, three different authors, one thread running through all of them that I never would have drawn on my own." [5]

A LlamaIndex benchmark cited by one practitioner provides empirical grounding: a filesystem-explorer agent beat a hybrid vector RAG pipeline on correctness (8.4 vs 6.4) and relevance (9.6 vs 8.0) at sub-60 document scale, precisely because the LLM saw whole files rather than chunks [4]. At moderate scale — roughly 100 articles or 400,000 words — the wiki becomes capable of answering complex synthesis questions with substantially less effort than any RAG-based alternative [7].

---

## Adapting an Existing Obsidian Vault

### Structural Reorganization

The adaptation path for an existing Obsidian vault requires restructuring around the three-layer directory model. The recommended approach from practitioners is to start fresh rather than migrate everything at once [6]. Create a new vault (or a new top-level folder within your existing vault) with the following structure:

```
vault/
├── raw/
│   ├── articles/
│   ├── papers/
│   └── assets/          ← Obsidian attachment folder path
├── wiki/
│   ├── index.md
│   ├── log.md
│   └── [LLM-generated pages]
└── CLAUDE.md            ← the schema file
```

Set Obsidian's "Attachment folder path" setting to `raw/assets/` and bind a hotkey to "Download attachments for current file" so that clipped articles land with their images in the right place [1]. Set the Obsidian Web Clipper destination folder to `raw/articles/` for one-click capture [6].

### The Schema File Is the Linchpin

The `CLAUDE.md` (or `AGENTS.md`) schema file is what transforms a generic LLM into a disciplined wiki maintainer. It should specify: the directory structure and what each folder contains; the page types and their YAML frontmatter conventions; the ingest workflow (what the LLM should do step by step when a new source arrives); the query workflow (read index first, then drill into relevant pages, file good answers back); and the lint checklist [1]. A minimal YAML frontmatter convention for wiki pages might look like:

```yaml
---
page_type: entity          # entity | concept | source | synthesis
entity_type: person        # for entity pages
name: Tim Dettmers
last_updated: 2026-04-10
sources: [dettmers-qlora-2023, dettmers-interview-2024]
confidence: high
---
```

This frontmatter enables Obsidian's Dataview plugin to generate dynamic tables across the wiki — for example, all entity pages updated in the last 30 days, or all concept pages with `confidence: low` [1][8].

### Tooling Prerequisites

Karpathy's pattern requires an **agentic LLM** — one that can read and write files autonomously across a session, not just answer questions in a chat window. The tools practitioners have confirmed working are [5][6]:

- **Claude Code** (Anthropic's agentic CLI) — Karpathy's own setup; pairs with `CLAUDE.md`
- **Cursor** or **Windsurf** — IDE-based agents that can operate on a local vault
- **Obsidian Skills** (released by Steph Ango, Obsidian CEO) — a set of skill definitions that teach Claude Code to use Obsidian's native features: wikilinks, callouts, Canvas, frontmatter, Dataview, Bases, and the CLI [5]

The Obsidian CLI is required for terminal operations to work correctly within Claude Code [5]. The optional `qmd` tool provides local hybrid BM25/vector search over markdown files with an MCP server interface, useful once the wiki grows beyond a few hundred pages [1]. Practitioners explicitly recommend **against** MCP servers for most tooling at small scale: "A skill enters Claude Code's context at boot at ~100 tokens of metadata; Notion's MCP server dumps ~20,000 tokens of self-documenting tools at startup. That is roughly 200× less context before you have done anything." [4]

### Migration Strategy for Existing Notes

Do not import your entire existing vault in one weekend [6]. The recommended migration path:

1. **Scaffold first.** Open the new vault folder in Claude Code, hand it Karpathy's gist as instruction, and let the agent create the directory structure, `CLAUDE.md`, `index.md`, and `log.md` [6].
2. **Start with ten sources.** Clip ten articles on a topic you care about into `raw/articles/`. Run ingest on each. Supervise the first few — naming conventions will evolve, some pages will be messy early [6].
3. **Query before expanding.** Make sure ingest, query, and lint feel natural before adding more sources. The first lint pass will reveal schema inconsistencies worth fixing before they propagate [6].
4. **Migrate existing notes selectively.** Treat your existing Obsidian notes as raw sources, not as wiki pages. Drop them into `raw/` and let the LLM integrate them into the wiki layer. Do not try to preserve your existing folder structure — the wiki layer will supersede it [1][6].
5. **Use domain-specific vaults rather than one giant directory.** Nick Spisak's variant, cited by multiple practitioners, uses separate vaults per domain (research, competitive analysis, personal) rather than one monolithic wiki [7]. This keeps the index manageable and the schema focused.

### The Graph View as Navigation

Karpathy specifically calls out Obsidian's graph view as "the best way to see the shape of your wiki" [1]. As the LLM adds wikilinks between pages during ingest, the graph view becomes a live map of the knowledge base — clusters of densely linked pages reveal the topics where synthesis is deepest, while isolated nodes flag orphan pages that need lint attention. This is a native Obsidian feature that requires no additional tooling and provides immediate visual feedback on the health of the wiki.

---

## Operational Discipline

### What the Human Must Do

The pattern dramatically reduces maintenance burden but does not eliminate human judgment. The human's required contributions are [1][6]:

- **Source curation**: deciding what to read and clip. The LLM cannot decide what is worth knowing — only what to do with it once you've decided.
- **Directing analysis**: telling the LLM what angle to take on a new source, what existing pages to check for contradictions, what synthesis questions to ask.
- **Asking good questions**: the query operation is only as valuable as the questions posed. Shallow questions produce shallow synthesis pages.
- **Reviewing lint output**: the LLM's lint pass surfaces contradictions and gaps, but a human must decide which contradictions to resolve and which gaps to fill.

### Cadence and Habits

The operational cadence that practitioners have found sustainable [5][6][7]:

| Operation | Frequency | Time cost |
|---|---|---|
| Ingest new source | As sources arrive (daily or weekly) | 5–10 min per source |
| Query the wiki | As needed | Near-zero overhead |
| File good answers back | After each substantive query | 1–2 min |
| Lint pass | Weekly or when wiki feels stale | 15–30 min |
| Schema revision | When naming conventions break down | Occasional |

The key discipline insight is that **ingest must happen close to reading**. If you clip articles and let them pile up in `raw/` without ingesting, the wiki stagnates and the compounding effect stops. The Obsidian Web Clipper + immediate ingest habit is the single most important operational practice [1][6].

### What Breaks the System

The failure modes are well-documented by practitioners [5][6][8]:

- **Skipping lint**: contradictions accumulate, confidence in the wiki degrades, queries return inconsistent answers.
- **Over-engineering the schema upfront**: spending a weekend designing the perfect frontmatter taxonomy before ingesting a single source. The schema should evolve from actual use.
- **Importing everything at once**: flooding the wiki with hundreds of sources before the schema is stable produces a mess that is expensive to clean up.
- **Treating the wiki as a chat history**: good synthesis answers that disappear into the chat window are lost value. Filing them back is a discipline, not an automatic behavior.
- **Context poisoning**: if the LLM hallucinates during ingest and the error makes it into a wiki page, it can propagate to other pages via cross-references [2]. The lint operation is the primary defense, but human review of early ingests is important.

---

## Code Examples & Repositories

The primary reference implementation is Karpathy's own gist, which is intentionally abstract — it describes the pattern rather than a specific codebase [1]. Three concrete implementations are available:

- **Karpathy's gist** (`gist.github.com/karpathy/442a6bf555914893e9891c11519de94f`) — the canonical pattern document, including the three-layer architecture, operation definitions, schema conventions, and tooling recommendations [1].
- **NicholasSpisak/second-brain** — Nick Spisak's three-folder variant (source / wiki / answers) with domain-specific vaults, using Obsidian Web Clipper + Vercel Labs' agent-browser + Node.js + Claude Code or Codex [7].
- **davidkimai/Context-Engineering** — a broader context-engineering patterns repository surfaced by the research; relevant for understanding the theoretical scaffolding around the pattern.

Paul Iusztin's DecodingAI implementation provides the most detailed architectural documentation of the agentic layer: three Claude Code skills (`/research_create`, `/research_search`, `/research_distill`), a `memory/` folder with `index.yaml` using progressive disclosure (summary → key highlights → full document), and a strict rule that the orchestrator never loads source files directly [4].

---

## Recommendations

**1. Start with the schema file, not the directory structure.** Before moving a single note, draft your `CLAUDE.md`. Specify the page types you need, the frontmatter fields, and the three operation workflows. A one-hour investment here prevents weeks of inconsistency cleanup. Co-evolve it with the LLM from the first ingest session [1].

**2. Treat your existing Obsidian notes as raw sources, not as wiki pages.** Drop your most valuable existing notes into `raw/` and let the LLM integrate them into the wiki layer. Do not try to preserve your existing folder hierarchy — the wiki's cross-linked structure will supersede it and provide better navigation [1][6].

**3. Establish the clip-then-ingest habit before expanding scope.** The compounding effect only works if ingest happens close to reading. Set up Obsidian Web Clipper to deposit directly into `raw/articles/`, and make ingest the last step of your reading workflow — not a batch job you do later [1][6].

**4. Use Obsidian's graph view as your primary health indicator.** After each ingest session, check the graph view. Dense clusters indicate healthy synthesis; isolated nodes indicate orphan pages that need lint attention or deletion. This gives you a five-second health check without running a full lint pass [1].

**5. Run lint before you trust the wiki for anything important.** The first time you rely on the wiki for a high-stakes synthesis — a research summary, a decision memo, a competitive analysis — run a lint pass first. Contradictions and stale claims are invisible until surfaced. Build lint into your workflow before you need it, not after you've been burned by it [1][6].

---

## Gaps & Limitations

**Primary source partially indirect.** Karpathy's gist at [1] was retrieved in full and is the primary source for all architectural claims. However, his X/Twitter post (`x.com/karpathy/status/1937902205765607626`) was JavaScript-walled and could not be retrieved. Any additional nuance or caveats Karpathy expressed in the tweet thread are not captured here.

**No Reddit community implementation data.** A Reddit thread in r/ObsidianMD documenting a community implementation was captcha-walled and could not be retrieved. This would have provided additional practitioner experience, particularly around edge cases and failure modes.

**Obsidian Skills plugin not independently verified.** The claim that Steph Ango (Obsidian CEO) released "Obsidian Skills" for Claude Code [5] is reported by a single practitioner source and was not independently confirmed against Obsidian's official documentation or GitHub. Users should verify availability before building a workflow around it.

**No long-term longitudinal data.** The gist was published April 4, 2026 — less than a month before this report. All practitioner accounts are early adopters reporting initial experiences. The long-term maintenance characteristics of a wiki at 500+ sources, or the degradation patterns that emerge over months, are not yet documented.

**Agentic tooling is a prerequisite, not a given.** The entire pattern requires an agentic LLM that can read and write files autonomously. Claude Code, Cursor, and Windsurf are the confirmed options [5][6]. Users without access to these tools, or who prefer a purely in-Obsidian workflow, will need to adapt the pattern significantly — potentially falling back to manual ingest with LLM assistance, which reintroduces the maintenance burden the pattern is designed to eliminate.

**Context-engineering theory sources partially truncated.** The Addy Osmani substack post [3] was retrieved at the 20,000-character cap and the full ~60KB document was not available. The theoretical framing from that source may be incomplete.

---

## References

[1] [A pattern for building personal knowledge bases using LLMs — Andrej Karpathy (GitHub Gist, 2026-04-04)](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)

[2] [Context Engineering for Agents — LangChain Blog](https://blog.langchain.com/context-engineering-for-agents/)

[3] [Context Engineering: Bringing Engineering Discipline to Prompts — Addy Osmani (Substack)](https://addyo.substack.com/p/context-engineering-bringing-engineering)

[4] [Karpathy Named It. I Built One on My Notes. — DecodingAI (Paul Iusztin)](https://www.decodingai.com/p/llm-knowledge-base-obsidian-readwise-notebooklm)

[5] [How I Took Karpathy's LLM Wiki and Built an AI-Powered Second Brain in Obsidian — AI Maker Lab (Substack)](https://aimaker.substack.com/p/llm-wiki-obsidian-knowledge-base-andrej-karphaty)

[6] [Step-by-Step Guide: Build Your Own AI Second Brain with Obsidian and Karpathy's LLM Wiki Pattern — TheToolNerd](https://www.thetoolnerd.com/p/step-by-step-guide-build-your-own-second-brain-obsidian-kaparthy)

[7] [Karpathy's Instructions for Building an AI-Driven Second Brain — Techstrong.ai](https://techstrong.ai/features/karpathys-instructions-for-building-an-ai-driven-second-brain/)

[8] [Build Karpathy's Self-Updating AI Knowledge Base in Just 90 Minutes — StartupGTM (Substack)](https://startupgtm.substack.com/p/self-updating-ai-wiki-knowledge-base)