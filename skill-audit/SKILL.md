---
name: skill-audit
description: >
  Audit an Agent Skill directory against published skill-authoring best practices.
  Use when the user asks to audit, review, score, or evaluate a skill's quality,
  structure, or compliance with best-practice guidelines. Triggers on: "audit skill",
  "review skill quality", "score this skill", "skill best practices check",
  "evaluate skill structure", "skill compliance". Produces a scorecard + prioritized
  findings report written to disk.
compatibility: >
  Requires bash for preflight script execution. Works with any skill directory
  containing a SKILL.md file. The audit is read-only against the target skill.
---

# Skill Audit

Audit an Agent Skill against six best-practice source docs. Produce a
scorecard + prioritized findings report and **write it to disk**.

## Workflow

### Step 0 — Preflight (deterministic)

Run the preflight script to validate the target and resolve the output path:

```bash
bash <skill-audit-dir>/scripts/preflight.sh <skill-dir> [output-file]
```

Where `<skill-audit-dir>` is the directory containing this SKILL.md.

The script:
- Validates `<skill-dir>` exists and contains `SKILL.md`
- Creates `<skill-dir>/meta/` if it does not exist
- Resolves the output file path (default: `<skill-dir>/meta/AUDIT-<YYYY-MM-DD>.md`)
- Prints structured JSON to stdout:

```json
{"skill_dir": "/abs/path", "output_file": "/abs/path/meta/AUDIT-2026-05-26.md", "skill_name": "my-skill"}
```

If the script exits non-zero, **stop and report the error** from stderr to the user. Do not proceed.

### Step 1 — Load the skill (read-only)

Read these files from the validated skill directory:

- `SKILL.md` (full body; note line-count and token estimate = chars/4)
- All files under `agents/`, `references/`, `scripts/`, `evals/` if present
- `meta/CHANGELOG.md` if present (for context only, do not audit it)

Use `read` / `bash` (`wc -l`, `ls`, `grep -n`) only. **Never** `edit`/`write` against the target skill.

### Step 2 — Score against each dimension

Load the scoring rubric for detailed criteria:

> **Load when:** Always, after Step 1 completes.
> **File:** `references/scoring-rubric.md`

Score each dimension **🟢 pass / 🟡 partial / 🔴 fail** with one-sentence
rationale and concrete file/line evidence. Cite the source doc tag in
parentheses after each dimension name.

**Score dimension 4 (description & triggers) first and hardest.** Trigger
failures cause ~50% of real-world skill failures, so this is the highest-severity
dimension. Do not stop at "a negative clause exists." List each positive trigger
keyword, identify its over-trigger vector (the unrelated request it would wrongly
fire on - bare common words and short acronyms that mean something else in
another domain are the usual offenders), and verify the negative clause or a
negative eval case actually guards *those* vectors. Presence without matching
coverage is a 🟡, not a 🟢.

### Step 3 — Write the report

Write the report to the output file resolved in Step 0. Use this exact structure:

```markdown
# Skill Best-Practices Audit — <skill name>

**Skill path:** <absolute path>
**Audited:** <YYYY-MM-DD HH:MM local>
**SKILL.md:** <N> lines, ~<T> tokens
**References:** <N> files / <L> lines total
**Scripts:** <N>
**Evals:** <N cases>

## Scorecard

| # | Dimension | Source | Result | One-liner |
|---|-----------|--------|--------|-----------|
| 1 | Frontmatter spec        | 00.spec       | 🟢/🟡/🔴 | ... |
| 2 | Body size / tokens      | 01.bp, 01a    | 🟢/🟡/🔴 | ... |
| 3 | Progressive disclosure  | 01.bp, 01a    | 🟢/🟡/🔴 | ... |
| 4 | Description & triggers  | 02.desc       | 🟢/🟡/🔴 | ... |
| 5 | Gotchas                 | 01.bp         | 🟢/🟡/🔴 | ... |
| 6 | Output templates        | 01.bp, 01a    | 🟢/🟡/🔴 | ... |
| 7 | Validation loops        | 01.bp, 01a    | 🟢/🟡/🔴 | ... |
| 8 | Script design           | 04.scripts    | 🟢/🟡/🔴 | ... |
| 9 | Eval scaffolding & rigor | 03.eval       | 🟢/🟡/🔴 | ... |
| 10 | Anti-patterns & no-ops | 01a.claude    | 🟢/🟡/🔴 | ... |

**Overall:** 🟢 / 🟡 / 🔴  (worst-of with brief justification)

## Prioritized Findings

Order by severity (🔴 first, then 🟡). Use F1, F2, … IDs.

### F<N> — <short title>  [🔴|🟡]

- **Dimension:** <#> (<source-doc-tag>)
- **Evidence:** `<relative/path>:<line>` — "<short quote or observation>"
- **Why it matters:** one sentence grounded in the cited doc.
- **Suggested fix:** concrete, minimal change. If a rewrite, show a 2–5 line before/after snippet.

## Options for follow-up

- **Quick wins (≤15 min each):** F<ids>
- **Medium edits (script or reference rewrite):** F<ids>
- **Structural (re-split references, add evals iteration):** F<ids>

## Out of scope / not checked

Brief list of things the audit intentionally didn't assess.
```

### Step 4 — Report back

After writing the file, respond with **only** a 3-line summary:

```
audit: <output-file-path>
overall: 🟢|🟡|🔴
findings: <total>  (🔴 <n>  🟡 <n>)
```

## Rules

- **Read-only** against the skill under audit. No edits, no renames.
- Cite evidence with `path:line` — no vague "the SKILL.md is too long".
- Be specific. "Description lacks trigger verbs" is weak; quote the description and name the missing verbs.
- Keep findings <~12. Merge related nits into one finding.
- If a dimension genuinely does not apply (e.g. no scripts at all), mark it **N/A** in the scorecard row and do not invent findings for it.
- Every dimension row must cite its source doc tag (00.spec / 01.bp / 01a.claude / 02.desc / 03.eval / 04.scripts).

## Gotchas

- The preflight script uses forward-slash paths only. Do not pass Windows-style paths.
- The output file will be **overwritten** if it already exists (e.g. running twice on the same day).
- Token estimate is `chars / 4` — approximate, not tiktoken-accurate. Fine for ceiling checks.
- If `references/` or `scripts/` don't exist in the target skill, skip dimensions 3/8 or mark N/A — do not error.
- `evals/` is treated differently: its absence is a scored 🔴 for dimension 9, not N/A. Current best practice is "don't ship skills without evals" - a missing evals directory is itself a finding, not something to skip.
- Dimension 4 requires evidence of negative-trigger coverage (cases where the skill should NOT fire), either in the description's own counter-examples or in `evals/`. Absence of any such evidence caps dimension 4 at 🟡 even when positive triggers are strong.
- When scoring dimension 10, actively hunt for no-ops - instructions that just restate default agent behavior ("write clean code", "be careful", "test your changes") without changing what the agent actually does. These cost tokens on every invocation for zero behavior change.
