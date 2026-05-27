---
name: research-report-visuals
description: Transform markdown research reports into interactive HTML visual narratives. Use when the user asks to create a visual, infographic, interactive page, or visual summary from a research report, deep research output, technical analysis, or any structured markdown document. Activates for requests like "create a visual for this report", "visualize this research", "make this report consumable", "turn this into an interactive page", or "generate a visual summary". Does NOT activate for general web design, landing pages, dashboards without a source report, or data visualization from raw datasets.
metadata:
  author: praveenc
  version: "0.1.0"
---

# Research Report Visuals

Transform markdown research reports into interactive, single-file HTML visual
narratives that convey the report's core message in 60 seconds of scrolling.

## Core Philosophy

In the age of AI, everyone generates markdown reports and nobody reads them.
This skill bridges that gap: it takes a research report and produces a
**visual narrative** that tells the report's story so the reader walks away
with the "so what" without reading the source.

The visual is NOT a dashboard. It is NOT a collection of charts. It is a
**story** with a beginning (the problem), middle (the evidence), and end
(the conclusion). Every element earns its place by advancing that story.

## Workflow

```
Read Report --> Classify Type --> Extract Narrative Arc -->
Choose Visual Mode --> Select Typography + Color --> Build HTML
```

### Step 1: Confirm Output Location

Before generating, ask the user where to save the visual:

> "Where should I save the visual? Default: `~/.report-visuals/<slug>.html`"

The `<slug>` is derived from the report filename (kebab-case, without
extension). Examples:
- `gpu-comparison-report.md` -> `gpu-comparison-report.html`
- `disaggregated-inference-llm-platforms-report.md` -> `disaggregated-inference-llm-platforms-report.html`

If the user provides a path, use it. If they accept the default, ensure
`~/.report-visuals/` exists (create if needed).

If the user has already specified a path in their request, skip this prompt.

### Step 2: Read and Understand the Report

Read the entire report. Do not skim. Identify:

1. **What is this report about?** (one sentence)
2. **What is the narrative arc?** (problem -> insight -> evidence -> conclusion)
3. **What are the 3-5 things the reader MUST walk away knowing?**
4. **What data is quantitative vs. qualitative?**
5. **What are the key entities/actors?** (companies, technologies, concepts)

### Step 3: Classify Report Type

Determine which category best fits. This drives visual mode selection.

| Type | Signal | Example |
|------|--------|---------|
| `comparison` | Side-by-side evaluation of options | GPU hardware comparison, framework shootout |
| `technical-strategy` | Industry direction, converging trends | Disaggregated inference platforms |
| `learning-concept` | Explains how something works | Protocol overview, architecture explainer |
| `myth-debunking` | Claims vs. evidence, fact-checking | Hundredth monkey effect |
| `migration-guide` | From A to B, pitfalls and steps | T4 to L4 migration |
| `optimization` | How to make X faster/better/cheaper | ModernBERT on Ada Lovelace |
| `cost-analysis` | Pricing, ROI, economics | Instance cost comparison |
| `service-overview` | What a service/product does | ACP protocol overview |

### Step 4: Extract Narrative Arc

Structure the visual as a **story**, not a reference. Map the report's
content into narrative beats:

1. **Hook** - Why should I care? (the problem, the opportunity, the stakes)
2. **Core Insight** - The "aha" moment (the key finding or principle)
3. **Evidence** - Data, comparisons, specifics that prove the insight
4. **Actors/Options** - Who/what is involved, compared side by side
5. **Timeline/Trajectory** - Where this is going, what happens next
6. **Takeaway** - The "so what" the reader carries away

Not every report uses all six. A myth-debunking might be: Hook (the myth) ->
Core Insight (what actually happened) -> Evidence (the timeline) -> Takeaway.
A comparison report might skip timeline entirely.

### Step 5: Choose Visual Mode

Based on report type and narrative structure, select a visual approach.

> **Load:** [references/visual-modes.md](references/visual-modes.md)
> **When:** You have classified the report and need structural patterns for the chosen mode.

| Mode | When | Structure |
|------|------|-----------|
| `narrative-scroll` | Strategy, concepts, explainers | Single continuous scroll, numbered sections |
| `verdict-split` | Myth vs fact, before/after, old vs new | Dual-panel contrast at the top, evidence below |
| `platform-cards` | Comparing 3-5 options/vendors | Cards grid with color-coded entities |
| `timeline-narrative` | Historical, evolution, convergence | Annotated timeline as spine |
| `problem-solution` | Migration guides, optimization | Problem block -> solution flow -> checklist |
| `tabbed-reference` | Dense technical specs (use sparingly) | Tabs only when content is genuinely parallel |

**Default to `narrative-scroll`.** Tabs fragment the story. Use them only
when content is genuinely parallel (e.g., five independent platform specs
where the reader will only care about 1-2).

### Step 6: Typography and Color

> **Load:** [references/typography-and-color.md](references/typography-and-color.md)
> **When:** You are selecting fonts, colors, and spacing for the visual.

**Quick rules:**
- Body text: `#2d2d2d` minimum darkness (never lighter)
- Secondary text: `#525252` (not lighter)
- Background: warm off-white (`#fafaf9` or `#fafafa`)
- One serif for headings (editorial authority), one sans for body (clarity)
- Color reserved for MEANING: entities, categories, status. Never decorative.
- Assign each key entity a color early and use it consistently throughout.
- Line-height 1.8 for body. 64px between sections. Breathing room is mandatory.

### Step 6b: Icons and Visual Differentiation

> **Load:** [references/icons-and-accents.md](references/icons-and-accents.md)
> **When:** You need icon names, CDN setup, or card differentiation patterns.

**Quick rules:**
- Use Lucide Icons from CDN (clean, consistent, technical)
- Every card/item gets a CONTEXTUAL icon representing its topic
- Never use generic decorative accents (colored corners, gradient blobs)
- Cards must be differentiated by content, not random color placement
- Icons represent concepts, not decoration

### Step 6c: Visual Signature

> **Load:** [references/visual-signature.md](references/visual-signature.md)
> **When:** You are making the 5 signature decisions (dominant color, hero treatment, grid-breaker, font register, light/dark).

Every visual MUST have at least one element that makes it feel crafted for
THIS specific report, not stamped from a template. This is the difference
between "professional" and "generic."

**Quick rules:**
- Pick ONE dominant accent color (used 3x more than others). The visual
  should have a recognizable color personality.
- The hero section gets atmosphere (subtle gradient, texture, or tinted bg)
- Stagger the hero entrance (title, subtitle, lede fade in sequentially)
- One element per visual breaks the grid (oversized stat, pull-quote in
  gutter, full-bleed section)
- Cards lift on hover (`translateY(-2px)` + shadow increase)
- The signature choices flow from the CONTENT, not random aesthetics

### Step 7: Build the HTML

> **Load:** [references/build-rules.md](references/build-rules.md)
> **When:** You are ready to write the HTML file (file structure, masthead, footer, CSS patterns, responsive rules).

**Output path:** Ask the user where to save, or use a sensible default
alongside the source report.

## Validation Loop

After building the HTML, run through the checklist. If any item fails:

1. Fix only the failing items in-place (edit the HTML, do not regenerate from scratch).
2. Re-check only the previously-failing items.
3. Maximum 2 fix passes. If still failing after 2 passes, deliver the file with a note to the user about the remaining issue.

Before delivering, verify:

- [ ] Masthead present (report type left, date right, mono, uppercase)
- [ ] Reader gets the "so what" in 60 seconds of scrolling
- [ ] Visual tells a STORY (not a collection of disconnected sections)
- [ ] Every element advances the narrative (no filler, no decoration)
- [ ] Visual has a SIGNATURE (dominant color, hero atmosphere, grid-breaker)
- [ ] Font pairing matches content register (not always the default)
- [ ] Body text is readable (dark enough, large enough, sufficient line-height)
- [ ] Color has meaning (entities, phases, categories) not decoration
- [ ] One accent color dominates (3x more than others, not even distribution)
- [ ] Footer has hyperlinked sources (flex-wrap list, not scrunched paragraph) AND centered attribution with heart
- [ ] Icons are contextual (represent the topic, not generic accents)
- [ ] Cards have NO colored top borders/bars (use icons, badges, bg tint instead)
- [ ] Cards respond to hover (lift, shadow, or reveal)
- [ ] Hero title and structural elements use full container width (no max-width)
- [ ] No em dashes or en dashes anywhere in the output
- [ ] Works as a standalone HTML file (opens in any browser)
- [ ] Responsive on mobile (grid collapses, text remains readable)
- [ ] Interactive elements serve comprehension (hover for detail, not spectacle)

## Anti-Patterns

- **Colored top/left borders on cards**: The #1 AI-generated visual tell.
  BANNED. No `border-top: 3px solid [color]` on any card element.
  Use icons, badges, or background tints instead. See build-rules.md.
- **Lazy quote styling**: Do not just put quotes in italic text with
  quotation marks. Use proper pull-quote or source-quote patterns with
  decorative open-quote mark, attribution, and visual weight.
  See build-rules.md for three quote patterns.
- **Tabbed dashboard syndrome**: Splitting the story into tabs that hide
  the narrative. Tabs make sense for reference; stories scroll.
- **Chart-first thinking**: Reaching for Highcharts before asking "does
  this data need a chart?" Often a styled table or big number is clearer.
- **Decorative color**: Gradients, random accents, colored backgrounds
  that carry no information. Color must mean something.
- **Over-distillation**: Reducing a code-heavy report to only tables and
  blocks, stripping out the actual code samples that make it useful.
- **Muted text syndrome**: Using `#9ca3af` or lighter for body text.
  This is unreadable. Body text minimum is `#2d2d2d`.
- **Generic AI aesthetic**: Purple gradients, Inter font, card grids
  with icons. Every visual should feel designed for its specific content.

## Gotchas

- Reports with heavy code samples: SHOW the code. Use dark code blocks
  with `white-space: pre-wrap` (not `pre`) and syntax highlighting via
  span classes. Keep code blocks narrow (max-width 720px) so they don't
  run off-screen.
- Reports with no quantitative data: Do NOT force charts. Use timelines,
  claim cards, quote blocks, flow diagrams, entity relationship SVGs.
- Long reports (>5000 words): Prioritize ruthlessly. The visual is NOT
  a 1:1 reproduction. It is the report's highlights reel.
- Mixed reports (some sections quantitative, some narrative): Use the
  narrative-scroll mode and embed charts inline where data demands them.
