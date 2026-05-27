# Scoring Rubric

Detailed criteria for each of the 10 audit dimensions. Score each as
**🟢 pass / 🟡 partial / 🔴 fail**.

---

## 1. Frontmatter spec *(00.spec)*

- `name`: ≤64 chars, lowercase `a-z/0-9/-`, no leading/trailing/consecutive hyphens, matches parent directory name.
- `description`: 1–1024 chars, present and non-empty.
- `compatibility`: ≤500 chars if present.
- No unknown required fields missing.
- 🟢 All fields valid and within limits.
- 🟡 One minor violation (e.g., 1–5 chars over a limit).
- 🔴 Missing required field, name doesn't match dir, or gross spec violation.

## 2. Body size / token budget *(01.bp, 01a.claude)*

- SKILL.md under **500 lines** and under **~5000 tokens** (chars/4).
- Every section earns its tokens — no explaining what the agent already knows.
- No redundant preamble ("You are an AI assistant that...").
- 🟢 Under both limits, content is dense and purposeful.
- 🟡 Near the ceiling (400–500 lines or 4000–5000 tokens) or has some filler.
- 🔴 Exceeds either limit or has significant filler/redundancy.

## 3. Progressive disclosure *(01.bp, 01a.claude)*

- Detail pushed to `references/` with explicit **load-when triggers** in SKILL.md.
- File references are **one level deep** from SKILL.md (no nested reference chains).
- Long reference files (>100 lines) have a **TOC** at the top.
- SKILL.md contains only what's needed for every invocation; specialized detail is deferred.
- 🟢 Clear triggers, 1-level refs, TOCs on long files.
- 🟡 References exist but missing TOCs on long files, or triggers are vague.
- 🔴 Everything crammed into SKILL.md, or multi-level reference chains.

## 4. Description quality & triggers *(02.desc)*

- Imperative or third-person phrasing (not "I will help you...").
- Specific **trigger keywords** that name both *what* the skill does and *when* to use it.
- Covers non-obvious trigger phrasings (synonyms, alternate ways users might ask).
- Under 1024 chars.
- 🟢 Clear, specific, covers edge triggers, good length.
- 🟡 Functional but missing non-obvious triggers or slightly generic.
- 🔴 Vague ("helps with tasks"), missing trigger words, or over 1024 chars.

## 5. Gotchas *(01.bp)*

- Concrete, **environment-specific** corrections to mistakes the agent would otherwise make.
- Live in SKILL.md (loaded before the agent hits the situation).
- Not generic advice ("be careful with paths") — must be specific to this skill's domain.
- Version-stamped or dated where relevant.
- 🟢 3+ concrete gotchas, environment-specific, in SKILL.md.
- 🟡 Some gotchas but generic or too few for the complexity.
- 🔴 No gotchas section, or only generic advice.

## 6. Output templates *(01.bp, 01a.claude)*

- When the skill produces structured output, a **concrete template** exists.
- Short templates inline in SKILL.md; long templates in `assets/` or `references/`.
- Template shows the exact structure, not just a description of it.
- 🟢 Template exists, concrete, appropriately placed.
- 🟡 Partial template or described but not shown.
- 🔴 Structured output expected but no template provided.
- **N/A** if the skill doesn't produce structured output.

## 7. Validation / feedback loops *(01.bp, 01a.claude)*

- Do-work → validate → fix → repeat pattern is present for fragile or batch operations.
- Plan-validate-execute pattern where applicable.
- Clear criteria for when to stop iterating.
- 🟢 Explicit validation loops with stop conditions.
- 🟡 Some validation but no iteration or vague stop conditions.
- 🔴 No validation for operations that clearly need it.
- **N/A** if all operations are simple/atomic.

## 8. Script design *(04.scripts)*

For **each script** in `scripts/`:

- Non-interactive (no TTY prompts).
- Has `--help` with: usage, options, examples.
- Distinct **documented exit codes**.
- Structured output: stdout = data, stderr = diagnostics.
- Helpful error messages (what failed / expected / received).
- Idempotent or `--dry-run` where destructive.
- Forward-slash paths only.

Scoring:
- 🟢 All scripts meet all criteria.
- 🟡 Scripts work but missing --help, undocumented exit codes, or minor gaps.
- 🔴 Scripts are interactive, no error handling, or mixing stdout data with diagnostics.
- **N/A** if no `scripts/` directory exists.

## 9. Eval scaffolding *(03.eval)*

- `evals/evals.json` exists with varied prompts + expected outputs + assertions.
- At least one negative / boundary case.
- Prompts are realistic (file paths, context), not generic.
- Baseline without-skill comparison recommended (🟡 if missing, not 🔴).
- Iteration workspace (`iteration-N/`) recommended.
- 🟢 `evals.json` with diverse cases, assertions, negative tests.
- 🟡 `evals.json` exists but sparse, or missing baseline/iteration workspace.
- 🔴 No `evals/` directory or no `evals.json`.

## 10. Anti-patterns *(01a.claude)*

Check for the **absence** of these:

- Windows-style backslash paths (should be forward-slash only).
- Voodoo constants in scripts (magic numbers without explanation).
- "Punt to the agent" error handling in scripts (scripts should handle errors, not say "ask the user").
- Time-sensitive info (dates/versions that will expire without update mechanism).
- Inconsistent terminology (same concept called different names).
- Unclear execute-vs-read intent for bundled scripts.
- Menu of equal options instead of one sensible default.

Scoring:
- 🟢 None of the anti-patterns present.
- 🟡 One minor anti-pattern instance.
- 🔴 Multiple anti-patterns or one severe instance.
