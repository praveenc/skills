# Build Rules

Rules for constructing the final HTML output file.

## Contents
- File Structure
- Standard Header (Masthead)
- Standard Footer
- Content Width Rules
- Card Styling Rules
- CSS Rules
- JavaScript Rules
- Charting Libraries (when needed)
- SVG Diagrams
- Content Rules
- Interactivity Patterns
- Responsive Breakpoints
- File Size Budget
- Output Location

---

## File Structure

Single self-contained HTML file. No external dependencies except Google Fonts
and optionally a CDN charting library. Must open correctly as `file://` in
any modern browser.

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>[Report Title]</title>
  <!-- Google Fonts (2-3 families max) -->
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=..." rel="stylesheet">
  <!-- Optional: charting library from CDN (only if charts needed) -->
  <style>
    /* All CSS inline. No external stylesheets. */
  </style>
</head>
<body>
  <!-- Content -->
  <script>
    /* Minimal JS for interactivity. At end of body. */
  </script>
</body>
</html>
```

## Standard Header (Masthead)

Every visual begins with a consistent masthead above the hero title.
Category/type on the left, date on the right, same line:

```html
<div class="masthead">
  <span class="masthead-type">Research Report</span>
  <span class="masthead-date">May 2026</span>
</div>
```

```css
.masthead {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 16px;
}
.masthead-type, .masthead-date {
  font-family: var(--mono);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--muted);
}
```

The `masthead-type` reflects the report classification (e.g., "Technical
Strategy", "Migration Guide", "Security Analysis"). The `masthead-date`
uses the report's publication date. This pattern is NON-NEGOTIABLE and
appears in every visual.

## Standard Footer

Every visual ends with a two-part footer: sources displayed clearly,
then a centered attribution on its own line.

```html
<footer class="footer">
  <div class="footer-sources">
    <div class="footer-sources-title">Sources</div>
    <div class="footer-sources-list">
      <a href="...">Source Name 1</a>
      <a href="...">Source Name 2</a>
      <a href="...">Source Name 3</a>
    </div>
  </div>
  <div class="footer-attribution">
    Made with &#10084;&#65039; by Research Report Visuals
  </div>
</footer>
```

```css
.footer {
  padding-top: 32px;
  border-top: 1px solid var(--border-soft);
}
.footer-sources {
  margin-bottom: 24px;
}
.footer-sources-title {
  font-family: var(--mono);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--muted);
  margin-bottom: 10px;
}
.footer-sources-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 16px;
}
.footer-sources-list a {
  font-size: 13px;
  color: var(--secondary);
  text-decoration: underline;
  text-underline-offset: 2px;
  text-decoration-color: var(--border);
}
.footer-sources-list a:hover {
  color: var(--text);
  text-decoration-color: var(--text);
}
.footer-attribution {
  text-align: center;
  font-family: var(--mono);
  font-size: 11px;
  letter-spacing: 0.03em;
  color: var(--muted);
  padding-top: 16px;
  border-top: 1px solid var(--border-soft);
}
```

Sources are displayed as a flex-wrap list with clear spacing between each
link (not a comma-separated paragraph). Each source is individually clickable.
The attribution sits on its own line, centered, with a red heart emoji.

---

## Content Width Rules

The `max-width: 720px` constraint applies ONLY to body paragraphs (continuous
prose). Other elements use the full available width:

| Element | Width behavior |
|---------|---------------|
| Hero title | Full container width (no max-width) |
| Hero lede paragraph | `max-width: 720px` |
| Section body paragraphs | `max-width: 720px` |
| Cards / grids | Full container width |
| Callout boxes | Full container width |
| Tables / comparison strips | Full container width |
| Big numbers row | Full container width |
| Timelines | Full container width |
| Pull-quotes | Full container width (or wider) |

Do NOT apply `max-width` to the hero title, callout boxes, card grids,
or any structural element. Only flowing prose gets the line-length
constraint. This ensures the page uses its screen real-estate efficiently.

---

## Card Styling Rules

Cards must NOT have colored top borders/bars. This is the single most
common cookie-cutter pattern in AI-generated visuals and it MUST be avoided.

**BANNED card patterns (do NOT use under any circumstance):**
```css
/* NEVER DO THIS */
border-top: 3px solid [color];
border-top: 4px solid [color];
border-left: 3px solid [color];
```
- No colored accent bars at top of cards
- No colored accent bars at left of cards
- No colored corner decorations
- No colored border segments of any kind used as "category indicators"

This rule applies to ALL card-like elements: model cards, platform cards,
entity cards, comparison cards, quote cards, feature cards. No exceptions.

**Correct card differentiation:**
- Contextual Lucide icon above or inside the card
- Category badge/tag with semantic color (small, inside the card)
- Key metric or differentiator pulled out visually
- Subtle full-card background tint (using entity's soft color)
- Hover lift effect for interactivity

```css
.card {
  background: var(--surface);
  border: 1px solid var(--border-soft);
  border-radius: var(--radius);
  padding: 24px;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}
.card:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(0,0,0,0.06);
}
```

If you need to color-code cards by entity/category, use a subtle
full-card background tint:
```css
.card.primary { background: var(--dominant-soft); }
.card.secondary { background: #f8fafc; }
```

Or a small colored dot/badge inside the card:
```html
<span class="card-badge" style="background: var(--entity-color)">Bedrock KB</span>
```

---

## Quote and Citation Styling

When a report contains quotes (expert quotes, paper citations, key
statements from sources), they deserve distinctive treatment. Quotes
ground the report's credibility and should feel authoritative.

### Pattern A: Pull-Quote (for key statements, 1-2 sentences)

Use when highlighting a single powerful statement from the report.

```html
<blockquote class="pull-quote">
  <p>BERT language models have quietly handled most enterprise natural language tasks in production.</p>
  <cite>Benczur et al., 2025</cite>
</blockquote>
```

```css
.pull-quote {
  position: relative;
  margin: 40px 0;
  padding: 32px 36px 24px;
  background: var(--bg);
  border-radius: var(--radius);
}
.pull-quote::before {
  content: '\201C';
  position: absolute;
  top: -8px;
  left: 24px;
  font-family: var(--serif);
  font-size: 72px;
  line-height: 1;
  color: var(--dominant);
  opacity: 0.3;
}
.pull-quote p {
  font-family: var(--serif);
  font-size: 20px;
  font-style: italic;
  line-height: 1.6;
  color: var(--text);
  margin: 0;
}
.pull-quote cite {
  display: block;
  margin-top: 12px;
  font-family: var(--mono);
  font-size: 12px;
  font-style: normal;
  color: var(--muted);
  letter-spacing: 0.02em;
}
```

### Pattern B: Source Quote (for attributed statements from people/orgs)

Use when citing what a specific person or organization said.

```html
<div class="source-quote">
  <div class="source-quote-mark">&#8220;</div>
  <div class="source-quote-content">
    <p>We have deployed multilingual BERT across 47 languages with zero-shot transfer achieving 94% of supervised performance.</p>
    <div class="source-quote-attribution">
      <strong>Jeff Dean</strong>
      <span>VP of Research, Google</span>
    </div>
  </div>
</div>
```

```css
.source-quote {
  display: flex;
  gap: 16px;
  padding: 24px;
  margin: 24px 0;
  background: var(--surface);
  border: 1px solid var(--border-soft);
  border-radius: var(--radius);
}
.source-quote-mark {
  font-family: var(--serif);
  font-size: 48px;
  line-height: 1;
  color: var(--dominant);
  opacity: 0.5;
  flex-shrink: 0;
}
.source-quote-content p {
  font-size: 16px;
  font-style: italic;
  line-height: 1.7;
  color: var(--body);
  margin: 0 0 12px;
}
.source-quote-attribution {
  font-size: 13px;
}
.source-quote-attribution strong {
  color: var(--text);
}
.source-quote-attribution span {
  color: var(--muted);
  margin-left: 6px;
}
```

### Pattern C: Evidence Quote (for multiple short quotes supporting a point)

Use when showing 2-4 quotes as evidence for a claim.

```html
<div class="evidence-grid">
  <div class="evidence-item">
    <p>Quote text here.</p>
    <cite>Source, 2025</cite>
  </div>
  <!-- more items -->
</div>
```

```css
.evidence-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
  margin: 24px 0;
}
.evidence-item {
  padding: 20px;
  background: var(--bg);
  border-radius: var(--radius);
  border-left: 2px solid var(--dominant);
}
.evidence-item p {
  font-size: 14px;
  font-style: italic;
  line-height: 1.6;
  color: var(--body);
  margin: 0 0 8px;
}
.evidence-item cite {
  font-size: 12px;
  font-style: normal;
  color: var(--muted);
}
```

Note: The evidence-item uses a left border, which IS acceptable for
quote blocks (it's a traditional typographic convention for blockquotes).
This is different from colored top/left borders on CARDS, which are banned.
The distinction: quotes are inline content elements, cards are containers.

### Choosing a Quote Pattern

| Situation | Pattern |
|-----------|--------|
| One powerful statement (hero area) | Pull-Quote (A) |
| Attributed to specific person/org | Source Quote (B) |
| Multiple quotes as evidence | Evidence Grid (C) |
| Inline reference in flowing text | Just use `<em>` with attribution |

---

## CSS Rules

- All styles in a single `<style>` block in `<head>`
- Use CSS custom properties (`:root` block) for all colors
- Mobile-first is not required, but include a basic `@media (max-width: 768px)`
  breakpoint that collapses grids to single column
- Maximum page width: `1080px` (centered with `margin: 0 auto`)
- Page padding: `48px` sides on desktop, `20px` on mobile
- No CSS frameworks (no Tailwind, no Bootstrap)

## JavaScript Rules

- Minimal. Only for interactivity that serves comprehension.
- Valid uses: tab switching, hover tooltips, scroll-triggered reveals
- Invalid uses: animations that delay content visibility, complex state
- Place all `<script>` tags at end of `<body>` (no DOMContentLoaded needed)
- No JS frameworks (no React, no Vue)
- No `eval()`, no dynamic imports

## Charting Libraries (when needed)

Only include a charting library when the report has quantitative data that
genuinely benefits from a chart (not a table). Options:

| Library | CDN | When |
|---------|-----|------|
| Highcharts 12.x | `cdn.jsdelivr.net/npm/highcharts@12.1.2/` | Complex charts, multiple series, interactivity |
| Chart.js 4.x | `cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js` | Simple charts (bar, line, pie) |
| None (CSS/SVG) | N/A | Diagrams, flows, timelines, comparisons |

**Default to no library.** Most research reports are better served by
styled tables, big numbers, SVG diagrams, and CSS-only visualizations.
Only pull in a charting library when you have 3+ data series that need
axis scales, tooltips, or responsive reflow.

## SVG Diagrams

Use inline SVG for:
- Architecture/flow diagrams
- Sequence diagrams
- Relationship maps
- Layer/stack diagrams

SVG rules:
- Use `viewBox` for responsive scaling
- Set explicit width/height on wrapper or use `width: 100%; max-width: Npx`
- Use the same font-family as the page (via `font-family` attribute on text)
- Use the same color variables (reference them as literal values in SVG)
- Keep SVG simple: boxes, arrows, text. Not illustrations.

## Content Rules

- **No em dashes** (`&#8212;`) or en dashes (`&#8211;`) anywhere in the output.
  Use commas, colons, semicolons, or periods instead.
- **No Lorem ipsum.** All content comes from the source report.
- **Attribute sources.** Include a footer with hyperlinked source references.
  If the research report includes URLs in its citations, link them:
  ```html
  <a href="https://..." target="_blank" rel="noopener">Source Name (2026)</a>
  ```
  Sources must ALWAYS be clickable when URLs are available in the report.
- **Prioritize ruthlessly.** A 5000-word report becomes a 1500-word visual.
  Cut supporting detail; keep key findings, numbers, and verdicts.

## Interactivity Patterns

**Tab navigation** (when genuinely needed):
```js
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
    btn.classList.add('active');
    document.getElementById('panel-' + btn.dataset.panel).classList.add('active');
  });
});
```

**Hover details** (for dense tables):
- Use `title` attribute for simple cases
- Use CSS `::after` with `content: attr(data-tip)` for styled tooltips
- Keep tooltip text under 80 characters

**Scroll-triggered entrance** (sparingly):
- Use `IntersectionObserver` to add an `.visible` class
- CSS: `opacity: 0; transform: translateY(8px)` -> `opacity: 1; transform: none`
- Transition: `0.4s ease-out`
- Apply to sections, not individual elements

## Responsive Breakpoints

Single breakpoint is sufficient:

```css
@media (max-width: 768px) {
  .page { padding: 0 20px 60px; }
  /* All grids collapse to single column */
  .grid-2, .grid-3, .platforms, .big-numbers { grid-template-columns: 1fr; }
  /* Hero title shrinks */
  .hero h1 { font-size: 28px; }
  /* Tables scroll horizontally */
  .compare-strip { overflow-x: auto; }
}
```

## File Size Budget

Target: **20-35 KB** for the HTML file. This is achievable with:
- Inline CSS (~5-8 KB)
- HTML content (~12-20 KB)
- Inline SVG diagrams (~3-5 KB)
- JavaScript (~1-2 KB)

If the file exceeds 40 KB, you're including too much content. Cut.
If it's under 15 KB, you may be under-investing in visual quality.

## Output Location

Default location: `~/.report-visuals/<slug>.html`

The agent MUST ask the user where to save before generating (Step 1 in
SKILL.md). If the user accepts the default, create `~/.report-visuals/`
if it does not exist:

```bash
mkdir -p ~/.report-visuals
```

Slug derivation: take the report filename, remove extension, keep kebab-case.

```
~/.report-visuals/
  gpu-comparison-report.html
  disaggregated-inference-llm-platforms-report.html
  aws-security-blog-march-2026.html
```

If the user provides an explicit path, use it verbatim. If they say
"same folder as the report" or "next to it", place it in a `visuals/`
subdirectory alongside the source.
