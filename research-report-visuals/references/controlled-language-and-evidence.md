# Controlled Language and Evidence

Use this reference after extracting the narrative and before building HTML.
It keeps the visual concise without weakening the report's claims.

## Contents

- Protect technical terms
- Build a claim ledger
- Write STE-aligned display copy
- Show evidence status
- Use progressive disclosure
- Final meaning check

## 1. Protect Technical Terms

Create a short protected-term list before rewriting. Include:

- Product, service, and company names
- API and operation names
- Model IDs, Region IDs, hostnames, and URLs
- Code, command lines, JSON keys, and configuration values
- Numbers, units, dates, and quoted text
- Terms that the source defines precisely

Inventory every number, percentage, duration, date, version, identifier,
Region, URL, and quantitative range in the source. Every inventory item must
appear in the visual, either in the primary layer or a `<details>` block. Copy
each item exactly. Keep the same characters, punctuation, spacing, units, and
case. Do not normalize a range such as `10-15 minutes` to `10 to 15 minutes`,
and do not expand or contract a technical identifier.

Use one term for each concept. Do not alternate between synonyms such as
"endpoint", "surface", and "route" unless the source makes a real distinction.

## 2. Build a Claim Ledger

Keep the ledger small. Include only claims that appear in the visual.

| Field | Purpose |
|-------|---------|
| Claim | The exact meaning the visual must preserve |
| Source | Citation or source URL |
| Status | Confirmed, Cross-checked, Verify current, Contradiction, or Hypothesis |
| Freshness | Stable or time-sensitive |
| Visual slot | Hero, diagram, comparison, warning, or detail block |

The ledger prevents a concise rewrite from dropping a condition, exception, or
qualification.

## 3. Write STE-Aligned Display Copy

Use ASD-STE100 principles to improve clarity:

- Write one main idea per sentence.
- Prefer active voice.
- Put the conclusion or action first.
- Use the same term for the same concept.
- Define an acronym at first use.
- Keep conditions close to the action or conclusion they modify.
- Use vertical lists when a sentence contains several parallel items.
- Remove filler, repeated setup, and distant cross-references.

House targets for visible prose:

| Measure | Target |
|---------|--------|
| Average sentence length | 15-18 words |
| Maximum sentence length | 25 words |
| Paragraph length | 2-4 sentences |
| Hero verdict | 60 words or fewer |
| Primary layer for a long report | 700-900 visible words |

If the source has 100 words or fewer, keep visible copy below 300 words and do
not invent supporting sections. If the source has at least 1,000 words or seven
substantive sections, keep the primary layer between 600 and 850 words and
include at least two useful native `<details>` blocks with 25 or more words in
each. Count only text outside closed `<details>` blocks toward the primary
layer target. Use one block for decision context and constraints, including
every protected inventory item omitted from the primary layer. Use another for
evidence limits, methods, or implementation detail.

These are editorial targets, not proof of ASD-STE100 compliance. Strict
compliance requires review against the applicable standard and approved
vocabulary.

Do not change:

- Modal strength such as `may`, `should`, `must`, or `will`
- Negation
- Scope, conditions, exceptions, or confidence
- Numbers, units, dates, or version identifiers
- Code, identifiers, quotations, or source titles

## 4. Show Evidence Status

Place evidence status next to the affected claim. Use a word and an icon so
color is not the only signal.

| Status | Use |
|--------|-----|
| Confirmed | Direct primary-source support |
| Cross-checked | Independent sources agree |
| Verify current | Region, price, model, quota, or other time-sensitive fact |
| Contradiction | Reliable sources disagree |
| Hypothesis | Reasoned explanation without direct confirmation |

Do not label every ordinary sentence. Apply status where confidence or
freshness changes how the reader should act.

## 5. Use Progressive Disclosure

The primary layer must answer the reader's main question without interaction.
Put supporting material in native `<details>` elements:

```html
<details>
  <summary>Quota behavior</summary>
  <p>Supporting detail from the source report.</p>
</details>
```

Good detail content:

- Full model or vendor lists
- Authentication and permission details
- Quota mechanics
- Methodology and limitations
- Secondary contradictions

Do not hide the verdict, required warnings, or evidence needed to trust the
main conclusion.

## 6. Final Meaning Check

Compare the display copy with the claim ledger:

1. Did the rewrite preserve every condition and exception?
2. Can each factual claim reach a source?
3. Is uncertainty visible where it affects a decision?
4. Did a short sentence accidentally make a qualified claim absolute?
5. Can a reader state the main conclusion after one minute of scrolling?
