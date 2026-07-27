# Icons and Visual Accents Reference

## Contents
- Icon Library: Lucide
- Fallback: Font Awesome 6
- Anti-Patterns: Generic Visual Accents
- Icon Sizing Convention

## Icon Library: Lucide

Use **Lucide Icons** as the primary icon library. Clean, consistent, 24x24
SVG-based icons with excellent coverage of technical and abstract concepts.

### CDN Include

```html
<!-- Pinned to a specific version with the explicit UMD path (do NOT use
     @latest: a breaking release can silently drop every icon). Version
     live-verified against the npm registry at build time, not just dated.
     The explicit /dist/umd/ path avoids relying on unpkg's bare-URL redirect
     and guarantees the global `lucide.createIcons()` used below is exposed. -->
<script src="https://unpkg.com/lucide@1.27.0/dist/umd/lucide.min.js"></script>
```

Place in `<head>` or before closing `</body>`. Then call:

```html
<script>lucide.createIcons();</script>
```

### Usage

```html
<i data-lucide="shield-check" class="icon"></i>
<i data-lucide="database" class="icon"></i>
<i data-lucide="network" class="icon"></i>
```

### Styling Icons

```css
.icon {
  width: 20px;
  height: 20px;
  stroke-width: 1.5;
  color: var(--secondary); /* or semantic color */
}
.icon-lg {
  width: 28px;
  height: 28px;
}
```

### Icon Selection by Domain

Choose icons that represent the CONCEPT, not generic decoration.

**Cloud/Infrastructure:**
- `cloud` - general cloud
- `server` - compute/instances
- `database` - databases/storage
- `hard-drive` - block storage
- `network` - networking
- `shield-check` - security/compliance
- `lock` - encryption/access control
- `globe` - regions/global
- `map-pin` - availability zones
- `layers` - stacks/layers
- `container` - containers/Docker
- `cpu` - processors/compute
- `memory-stick` - memory/RAM
- `zap` - performance/speed
- `gauge` - metrics/monitoring

**Architecture/Systems:**
- `workflow` - pipelines/flows
- `git-branch` - branching/versioning
- `boxes` - microservices
- `arrow-right-left` - data transfer
- `repeat` - replication/sync
- `split` - disaggregation/splitting
- `merge` - aggregation/combining
- `route` - routing
- `cable` - connections/links

**Security/Compliance:**
- `shield` - general security
- `shield-check` - compliance achieved
- `shield-alert` - security warning
- `key` - keys/credentials
- `fingerprint` - identity
- `scan` - scanning/audit
- `file-check` - certification
- `badge-check` - verified/certified

**Data/Analytics:**
- `bar-chart-3` - metrics
- `trending-up` - growth/improvement
- `trending-down` - decline
- `activity` - monitoring
- `pie-chart` - distribution
- `target` - goals/SLOs

**Communication/Events:**
- `bell` - notifications
- `mail` - messaging
- `webhook` - events/hooks
- `rss` - feeds/subscriptions
- `radio` - broadcasting

**Documents/Content:**
- `file-text` - reports/posts
- `book-open` - documentation
- `pen-tool` - authoring
- `link` - references/URLs
- `external-link` - external sources

---

## Fallback: Font Awesome 6

When Lucide lacks a specific icon (rare), use Font Awesome:

```html
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
<i class="fa-solid fa-aws"></i>
```

Font Awesome has brand icons (`fa-brands fa-aws`, `fa-brands fa-docker`)
that Lucide does not. Use for brand logos only.

---

## Anti-Patterns: Generic Visual Accents

**NEVER use these:**

1. **Colored corner swoops/curves** on cards (the "CSS border-radius accent"
   pattern). This is the most generic AI-design tell. It says nothing.

2. **Gradient blobs** as decorative backgrounds. Meaningless.

3. **Random emoji** as section icons. Childish in professional contexts.

4. **Colored left borders** alone without content context. The color must
   mean something (entity, category, severity).

5. **Generic card grids** where every card looks identical except the text.
   Cards must be visually differentiated by their CONTENT:
   - Different icon per card (representing the topic)
   - Tag/badge showing category
   - Key metric or date pulled out as a visual anchor

**INSTEAD, differentiate cards by:**

- A **contextual icon** (Lucide) that represents what the card is about
- A **category badge** with semantic color
- A **key metric** or date as a visual anchor (font-size bump, mono font)
- The card's **structure** varying by content type (some have lists,
  some have metrics, some have architecture callouts)

### Example: Blog Post Cards

Bad:
```
[colored corner curve]
Title
Date / Author
Description text
```

Good:
```
[icon: shield-check]  SECURITY          [icon: globe]  MULTI-REGION
Mar 14 / A. Milanovic                   Mar 10 / J. Herlinghaus

Title                                   Title
Description                             Description

Key services: IAM, KMS, Route 53       Certifications: SOC 2, C5, ISO 27001
[Link to post ->]                       [Link to post ->]
```

Each card has:
- A Lucide icon representing the topic (not decoration)
- A category badge (colored by theme, not randomly)
- A "key detail" strip at the bottom that's different per card
- A link to the source

---

## Icon Sizing Convention

| Context | Size | Stroke |
|---------|------|--------|
| Inline with text | 16px | 1.5 |
| Card header icon | 20px | 1.5 |
| Section/feature icon | 24px | 1.5 |
| Hero/large callout | 32-40px | 1.25 |

Never scale icons above 48px. They become blurry and lose detail.
