# Icons and Visual Accents Reference

## Contents
- Semantic Inline SVG
- Brand Marks
- Anti-Patterns: Generic Visual Accents
- Icon Sizing Convention

## Semantic Inline SVG

Use small inline SVG icons with a consistent 24x24 coordinate system. Keep the
geometry simple and use the same stroke width throughout the page. Do not load
an icon library or execute remote JavaScript.

### Accessible Pattern

```html
<svg class="icon" viewBox="0 0 24 24" role="img"
     aria-labelledby="icon-security-title">
  <title id="icon-security-title">Security</title>
  <circle cx="12" cy="12" r="9"></circle>
  <path d="M8 12h8M12 8v8"></path>
</svg>
```

### Styling Icons

```css
.icon {
  width: 20px;
  height: 20px;
  fill: none;
  stroke: currentColor;
  stroke-width: 1.75;
  stroke-linecap: round;
  stroke-linejoin: round;
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

## Brand Marks

Do not recreate a brand logo from memory and do not fetch one at runtime. Use
a text label or a local image that the user supplied. If you embed a local
image, place its bytes in the HTML as a data URL and preserve its alt text.

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
   - Different inline SVG icon per card (representing the topic)
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
- An inline SVG icon representing the topic (not decoration)
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
