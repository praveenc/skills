# Visual Modes Reference

## Contents
- `narrative-scroll` (default)
- `verdict-split`
- `platform-cards`
- `timeline-narrative`
- `problem-solution`
- `tabbed-reference` (use sparingly)
- Hybrid Approaches

Detailed guidance on each visual mode: when to use it, structural patterns,
and examples.

---

## `narrative-scroll`

**When:** Strategy reports, concept explainers, industry analysis, any report
with a clear beginning-middle-end.

**Structure:**
- Hero section with title + lede paragraph (the hook)
- Numbered sections (01, 02, 03...) flowing top to bottom
- Each section: title + body paragraph + one visual element
- Callout boxes for key insights the reader must remember
- Footer with sources

**Visual elements per section (pick one):**
- Side-by-side comparison boxes (for contrasts)
- Horizontal flow diagram (for processes)
- Platform/entity cards grid (for actors)
- Big numbers row (for key stats)
- Comparison strip/table (for specs)
- Timeline (for chronology)

**Typography pattern:**
- Serif for section titles (editorial gravitas)
- Sans for body text (readability)
- Mono for data/numbers (precision)
- Section numbers in mono, muted

**Example reports:** Disaggregated inference platforms, industry convergence,
technology evolution stories.

---

## `verdict-split`

**When:** Myth vs. fact, old vs. new, before vs. after, science vs. claim.
Reports where the core message is a binary contrast.

**Structure:**
- Hero with title
- Dual-panel verdict banner (top, full-width, two colors)
- Tabbed or scrolled evidence sections below
- Claims list with TRUE/FALSE badges
- Quote blocks for primary sources
- Optional: character/figure cards

**Color strategy:**
- Left panel: positive/science/new (green family)
- Right panel: negative/myth/old (rose/red family)
- Neutral: blue for third-party/debunking

**Typography pattern:**
- Serif for title (literary feel matches narrative reports)
- Sans for body and evidence
- Quotes in serif italic

**Example reports:** Hundredth monkey effect, technology myth-busting,
vendor claim validation.

---

## `platform-cards`

**When:** Comparing 3-5 products, vendors, or approaches. Each entity has
specs, trade-offs, and a use-case verdict.

**Structure:**
- Brief intro (what is being compared and why)
- 2x2 or 3-across card grid
- Each card: contextual icon, name, subtitle, spec list, verdict badge
- Below cards: comparison table for direct spec contrast
- Optional: "when to use which" decision guide

**Color strategy:**
- Each entity gets ONE color (used in border, badges, tags throughout)
- Assign colors from the entity's brand palette when recognizable
- Neutral background; cards are white

**Card anatomy:**
```
[contextual Lucide icon]
Entity Name (bold, 16px)
Subtitle (13px, secondary)
---
Spec label ........... Spec value (mono)
Spec label ........... Spec value (mono)
---
[Verdict box: plain-English tradeoff summary]
```

**Example reports:** GPU comparisons, serving framework shootouts,
cloud service evaluations.

---

## `timeline-narrative`

**When:** Historical progression, technology evolution, convergence stories
where chronology IS the story.

**Structure:**
- Brief intro (what happened and why it matters)
- Vertical timeline with color-coded dots per actor/category
- Legend at top
- Each node: year/date + title + description
- Optional: "where it's going" section at bottom

**Timeline item anatomy:**
```
[year in mono, left-aligned]  [colored dot]  Title (bold)
                                             Description (body text)
```

**Color strategy:**
- One color per actor/category in the timeline
- Keep to 3-4 colors maximum
- Dot color = border of the timeline node

**Example reports:** Protocol evolution, industry convergence, migration
history, research-to-production journeys.

---

## `problem-solution`

**When:** Migration guides, optimization guides, "how to fix X" reports.
Reports with a clear before-state, action steps, and after-state.

**Structure:**
- Problem statement (with pain-point metrics)
- Architecture/flow showing the solution
- Step-by-step checklist (numbered, with priority badges)
- Compatibility/requirements table
- Optional: estimated outcomes

**Visual elements:**
- Priority-coded checklist items (red = critical, amber = high, etc.)
- Requirement rows with version numbers
- Before/after comparison (not tabs; side by side or sequential)

**Example reports:** T4 to L4 migration, framework upgrades, security
remediation guides.

---

## `tabbed-reference` (use sparingly)

**When:** The content is genuinely parallel and independently useful.
The reader will only care about 1-2 sections per visit.

**WARNING:** Tabs hide content. They break narrative flow. Only use when:
- Sections are independent (not sequential)
- Each section stands alone
- Reader won't need to cross-reference between tabs

**Structure:**
- Persistent header with tab navigation
- Each panel: self-contained content with its own visual elements
- Panels should work if extracted as standalone pages

**When to avoid:** If the reader needs to see section 3 to understand
section 5, do NOT use tabs. Use narrative-scroll instead.

**Example:** A report covering 5 independent AWS services where the reader
only cares about 1-2. NOT for a report where sections build on each other.

---

## Hybrid Approaches

Most reports benefit from combining modes:

- `narrative-scroll` + embedded `platform-cards` section
- `verdict-split` hero + `timeline-narrative` evidence
- `problem-solution` structure with `platform-cards` for the options

The primary mode determines the outer structure. Other modes appear as
sections within it. The narrative-scroll mode is the most common outer
container.
