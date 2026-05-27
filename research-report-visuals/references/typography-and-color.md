# Typography and Color Reference

## Contents
- Typography Strategy (pairings, size scale, letter-spacing, rules, breathing room)
- Color Strategy (base palette, semantic assignment, color budget, code blocks)
- Things That Break Readability

## Typography Strategy

### Font Pairing Principles

Every visual uses exactly two (occasionally three) typefaces:

1. **Display/Heading font** - Carries editorial authority. Used for the
   hero title and section headings ONLY. Serif or distinctive sans.
2. **Body font** - Optimized for reading. Used for all body text,
   descriptions, labels. Clean sans-serif.
3. **Mono font** (optional) - Used for data, numbers, code, and technical
   identifiers. Signals precision.

### Recommended Pairings

Pick ONE pairing per visual. Do not mix across visuals for the same project.
**Default pairing is Newsreader + DM Sans** unless the content specifically
demands a different register.

| Register | Heading | Body | Mono | When |
|----------|---------|------|------|------|
| **Default** (editorial) | Newsreader | DM Sans | JetBrains Mono | Most reports. Best breathing room. |
| Technical/engineering | Space Grotesk | Inter | Fira Code | Protocol specs, API docs |
| Warm/accessible | Fraunces | DM Sans | DM Mono | Non-technical, narrative-heavy |
| Product/modern | Instrument Sans | Geist | Geist Mono | Product comparisons, vendor analysis |
| Research/academic | Newsreader | Source Sans 3 | Source Code Pro | Papers, citations-heavy |

### Size Scale

| Element | Size | Weight | Line-height |
|---------|------|--------|-------------|
| Hero title | 38-44px | 400 (serif) or 700 (sans) | 1.15-1.2 |
| Section title | 26-30px | 400 (serif) or 700 (sans) | 1.2 |
| Body text | 16px | 400 | **1.8** |
| Card title | 16-18px | 700 | 1.3 |
| Label/eyebrow | 11-12px | 600 | 1.4 |
| Table text | 14px | 400 | 1.5 |
| Code blocks | 13-14px | 400 | 1.7 |
| Big numbers | 28-36px | 700 | 1.0 |

### Letter-spacing

- Hero title: `-0.02em` to `-0.03em` (tighter, more confident)
- Section title: `-0.01em`
- Eyebrow/labels: `0.04em` to `0.08em` (spaced out, uppercase)
- Body: `0` (default)
- Mono: `0` (never adjust mono spacing)

### Non-Negotiable Rules

- Body text MUST be at minimum `#2d2d2d` on light backgrounds
- Line-height for body text MUST be **1.8** (non-negotiable for readability)
- Maximum body line length: 720px (prevents eye fatigue)
- Headings use negative letter-spacing; body uses none
- Never use more than 3 font sizes on a single screen (excluding data)

### Breathing Room (Vertical Rhythm)

Generous whitespace is the single biggest differentiator between a
professional visual and a cramped one. These minimums are mandatory:

| Element | Minimum spacing |
|---------|----------------|
| Hero top padding | 64px |
| Hero bottom (to first section) | 56px |
| Between sections | 64px |
| Section title to body text | 20px |
| Body text to visual element below | 28px |
| Between cards in a grid | 20px |
| Inside card padding | 24-28px |
| After a visual element to next section | 48px |

When in doubt, add MORE space, not less. A visual that breathes reads
faster than one that packs information tightly. The reader should never
feel like they're reading a wall of text.

---

## Color Strategy

### Base Palette (Light Theme)

Every visual starts with this neutral foundation:

| Token | Value | Usage |
|-------|-------|-------|
| `--bg` | `#fafaf9` or `#fafafa` | Page background (warm off-white) |
| `--surface` | `#ffffff` | Cards, elevated elements |
| `--text` | `#1a1a1a` | Headings, primary emphasis |
| `--body` | `#2d2d2d` | Body text (MINIMUM darkness) |
| `--secondary` | `#525252` | Supporting text, labels |
| `--muted` | `#737373` | Metadata only (dates, footnotes) |
| `--border` | `#d4d4d4` | Visible structural borders |
| `--border-soft` | `#e5e5e5` | Subtle card borders |

**Never go lighter than `#737373` for ANY text the reader needs to read.**
Reserve `#9ca3af`-range only for purely decorative elements (line rules).

### Semantic Color Assignment

Colors carry MEANING. Assign them deliberately:

**For entities (companies, products, platforms):**
- Use the entity's brand color when recognizable
- NVIDIA: `#76b900` (green)
- AWS: `#ff9900` (amber/orange)
- If no brand color, pick from: blue, teal, violet, rose, amber, emerald

**For categories (phases, statuses, types):**
- Prefill/compute: violet family (`#7c3aed`)
- Decode/memory: teal/cyan family (`#0891b2`)
- Success/supported: green family (`#059669`)
- Warning/partial: amber family (`#d97706`)
- Error/breaking: red family (`#dc2626`)
- Neutral/previous: gray (`#6b7280`)

**For each color, define THREE values:**
1. Full: The color itself (for text, borders, icons)
2. Soft: Very light tint (for backgrounds of boxes/badges)
3. Border: Medium tint (for card/box borders)

Example:
```css
--prefill: #7c3aed;        /* Text, labels */
--prefill-soft: #f5f3ff;   /* Box backgrounds */
--prefill-border: #c4b5fd; /* Box borders */
```

### Color Budget

- Maximum 4-5 semantic colors per visual (beyond the neutral base)
- Each color must be USED in at least 2 places (otherwise it's noise)
- If an entity appears in one place only, use gray; color is for recurring actors

### Code Block Colors (dark theme)

When showing code, use a dark block that contrasts with the light page:

```css
--code-bg: #1c1917;       /* Near-black warm background */
--code-text: #e7e5e4;     /* Light warm gray for default text */
--code-keyword: #c4b5fd;  /* Soft purple for keywords */
--code-string: #86efac;   /* Soft green for strings */
--code-comment: #78716c;  /* Dim for comments */
--code-method: #67e8f9;   /* Cyan for function/method names */
--code-number: #fbbf24;   /* Amber for numbers */
```

Code blocks MUST use `white-space: pre-wrap` and `max-width: 720px` to
prevent horizontal scrolling while preserving indentation.

---

## Things That Break Readability

1. **Gray body text** - Anything lighter than `#525252` for body copy
2. **Insufficient line-height** - Below 1.6 for paragraphs
3. **Too-wide lines** - Body text wider than 720px
4. **Font-size below 14px** for anything the reader needs to actually read
5. **Low-contrast labels** - Uppercase + light gray + small = invisible
6. **Monospace for prose** - Mono is for data and code ONLY
7. **Too many font weights** - Stick to 400 (body) + 600/700 (emphasis)
