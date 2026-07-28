# Scoring Rubric

Detailed criteria for each of the 10 audit dimensions. Score each as
**🟢 pass / 🟡 partial / 🔴 fail**.

---

## 1. Frontmatter spec *(00.spec)*

- `name`: ≤64 chars, lowercase `a-z/0-9/-`, no leading/trailing/consecutive hyphens, matches parent directory name.
- `description`: 1-1024 chars, present and non-empty.
- `compatibility`: ≤500 chars if present.
- No unknown required fields missing.
- 🟢 All fields valid and within limits.
- 🟡 One minor violation (e.g., 1-5 chars over a limit).
- 🔴 Missing required field, name doesn't match dir, or gross spec violation.

## 2. Body size / token budget *(01.bp, 01a.claude)*

- SKILL.md under **500 lines** and under **~5000 tokens** (chars/4).
- Every section earns its tokens - no explaining what the agent already knows.
- No redundant preamble ("You are an AI assistant that...").
- 🟢 Under both limits, content is dense and purposeful.
- 🟡 Near the ceiling (400-500 lines or 4000-5000 tokens) or has some filler.
- 🔴 Exceeds either limit or has significant filler/redundancy.

## 3. Progressive disclosure *(01.bp, 01a.claude)*

- Detail pushed to `references/` with explicit **load-when triggers** in SKILL.md.
- File references are **one level deep** from SKILL.md (no nested reference chains).
- Long reference files (>100 lines) have a **TOC** at the top.
- SKILL.md contains only what's needed for every invocation; specialized detail is deferred.
- Deterministic, always-identical procedures (fixed command sequences with no branching or judgment calls) are extracted into `scripts/` rather than spelled out as prose steps for the model to re-derive and re-type every run. **This only applies to genuinely rote sequences.** Do NOT flag a workflow whose steps depend on what the model observes (branching, classification, "if X then Y"), nor a trivial 2-3 command sequence where a script would add more ceremony than it saves. A judgment-driven workflow correctly stays as prose.
- 🟢 Clear triggers, 1-level refs, TOCs on long files, no genuinely-rote multi-step procedure left inline.
- 🟡 References exist but missing TOCs on long files, triggers are vague, or one clearly-rote procedure should be a script but isn't.
- 🔴 Everything crammed into SKILL.md, multi-level reference chains, or multiple clearly-rote procedures left as prose instead of scripts.

## 4. Description quality & triggers *(02.desc)*

**Score this dimension first and most carefully.** Trigger failures cause roughly
half of all real-world skill failures, so a weak description is the single
highest-severity defect a skill can have - never treat it as a nit.

- Imperative or third-person phrasing (not "I will help you...").
- Specific **trigger keywords** that name both *what* the skill does and *when* to use it.
- Covers non-obvious trigger phrasings (synonyms, alternate ways users might ask).
- Under 1024 chars.
- **Negative-trigger coverage that actually matches the positive triggers.** Presence of a `Does NOT...` clause is *not* enough. Do the coverage analysis:
  1. List every positive trigger keyword.
  2. For each, ask "what *unrelated* request would this fire on?" - i.e. its over-trigger vector. The usual offenders are bare single common words (a generic verb or noun used elsewhere in everyday work) and short acronyms that mean something different in another domain.
  3. Check whether the negative clause (or an `evals/` negative case) actually guards *those specific vectors*. A negative clause that only excludes adjacent in-domain cases while leaving the bare-keyword collisions unguarded does **not** count as coverage.
- 🟢 Clear, specific, covers edge triggers, good length, AND every over-broad positive trigger is either qualified (scoped with a domain-specific modifier rather than left as a bare common word) or explicitly guarded by a matching negative clause / negative eval case.
- 🟡 Has a negative clause but it does not cover the over-trigger vectors of one or more bare/generic keywords; OR good positive triggers but no negative-trigger evidence anywhere; OR near the char ceiling (>~90%) leaving no room to add guards.
- 🔴 Vague ("helps with tasks"), missing trigger words, over 1024 chars, or multiple broad/generic keywords with no matching negative guard anywhere (high over-trigger risk).

## 5. Gotchas *(01.bp)*

- Concrete, **environment-specific** corrections to mistakes the agent would otherwise make.
- Live in SKILL.md (loaded before the agent hits the situation).
- Not generic advice ("be careful with paths") - must be specific to this skill's domain.
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

## 9. Eval scaffolding & rigor *(03.eval)*

Evals are the default expectation, not a nice-to-have - "don't ship skills without evals."
Absence of `evals/` is itself a finding, scored 🔴, not skipped or marked N/A.

The items below split into **core** (the rigor that makes an eval set trustworthy - a 🟢 needs these) and **maturity** (raises confidence and matters for widely-used skills, but a small honest eval set should not be knocked to 🟡 just for lacking them). Judge the eval set against its skill's scope: a tight single-purpose skill with a solid core set is 🟢 even with few maturity items; a broad high-traffic skill is expected to reach into the maturity items too.

**Core (needed for 🟢):**

1. **Presence** - `evals/` exists with a runnable set of cases (JSON/YAML + runner script, or an equivalently concrete documented procedure). Gating: if entirely absent, score 🔴 and stop (still note it as a finding).
2. **Genuine negative / boundary cases** - the set contains cases where the skill should *not* fire or should stop early, AND those cases guard the skill's *actual* over-trigger vectors (see dimension 4), not just carry a `"kind": "negative"` label on an easy or irrelevant prompt. A negative case that fires on something the skill would never be confused for is not real coverage. Aim for ~30% of the set, but one well-targeted negative beats five decorative ones.
3. **Outcome-based assertions** - checks grade the final state, output, or API/behavioral correctness, not the exact tool-call path or which file was read first. Agents legitimately reach correct answers via different routes.
4. **Cheap-first assertions** - regex, exit codes, file diffs, or other deterministic checks are used wherever possible; LLM-as-judge is reserved for cases deterministic checks genuinely cannot capture.
5. **Isolation** - cases run in a clean/isolated workspace per case, not chained through shared conversation state, so an agent can't "cheat" by reusing context outside the intended skill trigger.

**Maturity (raises the ceiling; expected for broad/high-traffic skills, optional for tight ones):**

6. **Case coverage** - roughly 10-20+ cases for a broad skill, scaling with surface area. A narrow skill may be fully covered by fewer; judge against scope, not an absolute count.
7. **Trial count** - reliability-sensitive cases are run 3-6 times with a reported pass rate, not single-shot, given agents are non-deterministic.
8. **Cross-harness / cross-model awareness** - evals note which harness(es) and model(s) they were validated against, or explicitly flag single-harness-only as a known gap.
9. **Ablation evidence** - an informal with-skill vs. without-skill comparison exists somewhere, demonstrating the skill actually helps.
10. **Real-trace inclusion** - at least one case sourced from an actual production/user transcript rather than purely synthetic.
11. **Lifecycle note** - some signal for when to re-run, graduate, or retire the eval.

Scoring:
- 🟢 `evals/` present and satisfies **all 5 core items**, with maturity items proportionate to the skill's scope (a tight skill needs few; a broad one needs several).
- 🟡 `evals/` present but misses one or more core items - commonly: only decorative/mislabeled negatives, path-based asserts, no isolation - or is clearly under-scoped for a broad skill (core met but essentially zero maturity items on a wide surface area).
- 🔴 No `evals/` directory at all, or evals exist but are purely path-based, single-shot, and/or have zero genuine negative cases.

## 10. Anti-patterns & no-ops *(01a.claude)*

Check for the **absence** of these:

- Windows-style backslash paths (should be forward-slash only).
- Voodoo constants in scripts (magic numbers without explanation).
- "Punt to the agent" error handling in scripts (scripts should handle errors, not say "ask the user").
- Time-sensitive info (dates/versions that will expire without update mechanism).
- Inconsistent terminology (same concept called different names).
- Unclear execute-vs-read intent for bundled scripts.
- Menu of equal options instead of one sensible default.
- **No-ops** - instructions that restate default agent behavior without changing it (e.g. "write clean code," "be careful with edge cases," "make sure to test your changes," "use best practices"). These cost tokens on *every* invocation while producing zero behavior change; quote the offending line and name the default behavior it merely restates. **Discriminator:** a directive is NOT a no-op if it changes behavior in a specific, checkable way - even when phrased imperatively. "Group log lines by job id before reading" or "check the final exit line, not the last human-readable one" are real constraints (they redirect what the agent would otherwise do); "be careful with logs" is a no-op. When unsure, ask: would removing this line change what a competent agent does? If yes, keep it; if no, it's a no-op.

Scoring:
- 🟢 None of the anti-patterns present, including no-ops.
- 🟡 One minor anti-pattern instance, or one or two low-cost no-op lines.
- 🔴 Multiple anti-patterns, one severe instance, or a pattern of no-ops (three or more) padding the file.
