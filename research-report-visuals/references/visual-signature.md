# Visual Signature Reference

## Contents
- Dominant Accent Color
- Hero Atmosphere
- Staggered Hero Entrance
- One Grid-Breaking Element
- Card Hover Interactions
- Font Diversity by Content Register
- Dark Mode (Optional, Content-Driven)
- Signature Decision Checklist

Every visual must feel crafted for its specific report. Without a signature
element, output becomes "warm-white Newsreader template" regardless of content.
This reference defines the mechanisms that create distinctiveness without
sacrificing readability.

---

## 1. Dominant Accent Color

Do NOT distribute colors evenly. Pick ONE semantic color as the dominant
accent and use it 3x more than any other color.

**How to choose:** The dominant color represents the report's primary
subject or most important entity.

- GPU comparison report? NVIDIA green dominates (it's the incumbent).
- Security audit? A deep blue or slate dominates (trust, authority).
- Migration guide? The target platform's color dominates (where you're going).
- Cost analysis? Amber/green dominates (money, savings).

The dominant color appears in:
- Hero section accent (background tint, border, or title color)
- The most important callout box
- Primary entity cards
- Key stat numbers
- Timeline dots for the main actor

Other colors exist but play supporting roles.

---

## 2. Hero Atmosphere

The hero section is the first thing the reader sees. It should NOT be
bare white with text. Give it a subtle surface:

**Option A: Tinted background**
```css
.hero {
  background: linear-gradient(135deg, #fafaf9 0%, var(--dominant-soft) 100%);
}
```

**Option B: Subtle dot grid**
```css
.hero::before {
  content: '';
  position: absolute;
  inset: 0;
  background-image: radial-gradient(circle, var(--border) 0.5px, transparent 0.5px);
  background-size: 20px 20px;
  opacity: 0.3;
  pointer-events: none;
}
```

**Option C: Soft gradient accent line**
```css
.hero { border-top: 3px solid var(--dominant); }
```

**Option D: Large faded icon/motif**
Position an oversized Lucide icon (80-120px, opacity 0.06) in the hero
background, representing the report's core concept. Subtle but distinctive.

Choose ONE. Not all four. The choice depends on content register:
- Technical strategy: Option A or C
- Historical/narrative: Option B
- Product comparison: Option C or D
- Code-heavy: Option C (simple, doesn't compete with code)

---

## 3. Staggered Hero Entrance

The hero elements animate in sequentially. This gives the page life
without delaying content access (total animation: ~0.5s).

```css
@keyframes fadeInUp {
  from { opacity: 0; transform: translateY(12px); }
  to { opacity: 1; transform: translateY(0); }
}
.hero-eyebrow { animation: fadeInUp 0.5s ease-out both; }
.hero h1 { animation: fadeInUp 0.5s ease-out 0.1s both; }
.hero-lede { animation: fadeInUp 0.5s ease-out 0.2s both; }
```

Rules:
- Only the hero section animates on load. Nothing else.
- Delay between elements: 100-150ms
- Total sequence under 600ms
- The animation is subtle (12px travel, not 40px)
- Use `both` fill-mode so elements don't flash before animating

---

## 4. One Grid-Breaking Element

Every visual based on `narrative-scroll` mode has a consistent vertical
rhythm (1080px max-width, 48px padding, centered). This is correct for
readability. But one element per visual should break this pattern to create
visual interest:

**Options (pick ONE per visual):**

**Pull-quote:** A key finding displayed at larger size, extending slightly
beyond the normal content width or indented with a dramatic left border.
```css
.pull-quote {
  font-family: var(--serif);
  font-size: 22px;
  line-height: 1.5;
  color: var(--text);
  border-left: 3px solid var(--dominant);
  padding-left: 24px;
  margin: 40px -20px 40px 40px; /* extends left */
}
```

**Oversized stat:** One number displayed much larger than the others,
representing the single most important data point.
```css
.mega-stat {
  font-family: var(--mono);
  font-size: 64px;
  font-weight: 700;
  letter-spacing: -0.04em;
  color: var(--dominant);
}
```

**Full-bleed section:** One section gets a background color that extends
edge-to-edge (breaking the contained white space).
```css
.full-bleed {
  margin-left: calc(-50vw + 50%);
  margin-right: calc(-50vw + 50%);
  padding: 48px calc(50vw - 50% + 48px);
  background: var(--dominant-soft);
}
```

**Gutter annotations:** Section numbers or category labels positioned in
the left margin (visible on desktop, hidden on mobile).
```css
.section-num {
  position: absolute;
  left: -60px;
  font-family: var(--mono);
  font-size: 48px;
  font-weight: 700;
  color: var(--border);
  opacity: 0.4;
}
```

---

## 5. Card Hover Interactions

Cards are not static. They respond to the reader's attention:

```css
.card {
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}
.card:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 24px rgba(0,0,0,0.08);
}
```

For comparison tables:
```css
.compare-row:hover {
  background: var(--bg);
}
```

For timeline items:
```css
.timeline-item:hover .timeline-detail {
  max-height: 200px;
  opacity: 1;
}
```

These are small signals that the page is alive and responsive to attention.
They cost nothing in file size or load time.

---

## 6. Font Diversity by Content Register

Do NOT always use Newsreader + DM Sans. The font pairing should reflect
the report's register:

| Report feel | Heading | Body | Rationale |
|-------------|---------|------|-----------|
| Editorial/authoritative | Newsreader | DM Sans | Newspaper editorial energy |
| Technical/precise | Space Grotesk | Inter | Engineering documentation feel |
| Warm/accessible | Fraunces | DM Sans | Friendly, inviting for non-technical readers |
| Modern/product | Instrument Sans | Geist | Clean SaaS feel for product comparisons |
| Academic/research | Libre Baskerville | Source Sans 3 | Paper/journal authority |
| Bold/security | JetBrains Mono (titles) | Inter | Monospace titles signal "system-level" |

Choose based on WHO will read this and WHAT the content feels like, not
a default. A security audit visual should not look like a tech strategy
briefing.

---

## 7. Dark Mode (Optional, Content-Driven)

Some reports benefit from a dark canvas:

- Security/threat reports (dark feels serious, vigilant)
- Performance benchmarks (dark + neon accents feels "monitoring dashboard")
- Developer tooling (dark matches their IDE context)

Dark mode palette:
```css
:root {
  --bg: #0f0f0f;
  --surface: #1a1a1a;
  --text: #f5f5f5;
  --body: #d4d4d4;
  --secondary: #a3a3a3;
  --border: #2d2d2d;
  --border-soft: #262626;
}
```

Rules for dark mode:
- Body text minimum: `#d4d4d4` (equivalent contrast to light mode)
- Code blocks use slightly lighter background (`#1e1e1e` vs page `#0f0f0f`)
- Accent colors need to be lighter/more saturated to read on dark
- Cards use `--surface` with `--border-soft` borders (subtle elevation)

**Default is still light mode.** Only use dark when the content register
demands it AND you explicitly choose it in the signature decisions.

---

## Signature Decision Checklist

Before building, answer these five questions:

1. **What is the dominant color?** (name it, justify from content)
2. **What hero treatment?** (tinted bg / dot grid / accent line / faded motif)
3. **What is the grid-breaker?** (pull-quote / mega-stat / full-bleed / gutter)
4. **What is the font register?** (editorial / technical / warm / modern / academic / bold)
5. **Light or dark?** (default: light; justify dark if chosen)

These five choices produce distinctive output without unbounded creative
freedom. The choices are CONSTRAINED but VARIED — each combination yields
a meaningfully different visual.
