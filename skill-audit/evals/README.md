# skill-audit evals

Eval set for the `skill-audit` skill. Follows the rigor bar this skill's own
dimension 9 now enforces: negative + boundary cases, outcome-based assertions,
deterministic fixtures, isolation, multiple trials, ablation, and cross-harness
awareness.

## Layout

```
evals/
  evals.json            # the cases (positive / negative / boundary)
  fixtures/
    clean-skill/        # a well-formed skill - auditor should NOT invent 🔴s
    flawed-skill/       # one planted defect per dimension - all must be caught
  README.md             # this file
```

The fixtures are the key to determinism. Because each fixture has known,
fixed contents, the assertions in `evals.json` are checkable with plain regex
against the written audit report - no LLM-as-judge needed for most of them.

## Fixtures and their planted defects

`clean-skill/` is deliberately clean: name matches directory, small body,
concrete gotchas, an explicit `Do NOT use for...` negative-trigger clause, and a
non-interactive `normalize.py` with `--help`, documented exit codes, and
stdout=data / stderr=diagnostics. Its only real gap is a missing `evals/`, so
dim 9 is 🔴 and, by the report's worst-of rule, overall is 🔴 too - attributed
solely to the missing evals. That is the intended lesson: even a pristine skill
is unshippable without evals. The auditor must not invent any other 🔴.

`flawed-skill/` plants exactly one defect per dimension so each finding is
attributable:

| Dimension | Planted defect |
|-----------|----------------|
| 1 Frontmatter      | `name: helper` does not match dir `flawed-skill` |
| 4 Description      | "helps with data tasks and processing and other things" - vague, no triggers, no negatives |
| 3 Progressive disc | rigid always-identical 6-step procedure that should be a script |
| 10 Anti-patterns   | Windows backslash paths (`C:\data\input`, `output\`) |
| 10 Voodoo constants| `--threshold 0.7 --window 42 --mode 3`, unexplained |
| 10 No-ops          | "write clean code", "be careful with edge cases", "test your changes", the whole Notes section |
| 9 Evals            | no `evals/` directory |

## Run protocol

### Isolation (anti-cheating)

Run each case in a **fresh agent session** with cwd set to a scratch copy of
this skill, so the auditor cannot reuse context from a prior case's turn. Copy
the skill to a throwaway dir per run:

```bash
# Resolve this skill's root portably (the dir containing this evals/ dir).
# Adjust SKILL_ROOT if you invoke from elsewhere.
SKILL_ROOT="$(cd "$(dirname "$0")/.." && pwd)"   # or: the skill-audit dir you cloned
WORK="$(mktemp -d)"
cp -R "$SKILL_ROOT" "$WORK/skill-audit"
# run the agent with cwd="$WORK/skill-audit" and only this one prompt
```

Fixtures live under the skill, so paths in the prompts resolve relative to the
copied skill dir. The audit is read-only, but copying also guarantees a clean
`meta/` per run.

### Trials (non-determinism)

Agents are non-deterministic. Run the reliability-sensitive positive cases
(`clean-skill-mostly-green`, `flawed-skill-catches-planted-defects`) **3-6
times** each and report a pass rate, not a single pass/fail. Negative and
boundary cases can run fewer trials but should still be repeated at least twice.

### Grading (outcome, not path)

Grade the **written report**, not the sequence of tool calls the agent made.
The auditor legitimately reaches its verdict via different read orders. Assert
on:

- the overall verdict badge,
- presence of the expected per-dimension scores,
- specific quoted evidence strings (fixture defects are fixed strings), and
- that nothing under `fixtures/` was modified.

Prefer regex/string checks over LLM-as-judge. Example checks:

```bash
REPORT="$WORK/skill-audit/evals/fixtures/flawed-skill/meta/AUDIT-$(date +%F).md"
grep -q "helper" "$REPORT"                 # dim 1 name-mismatch cited
grep -qi "backslash\|C:\\\\data" "$REPORT"  # dim 10 windows paths
grep -qi "no-op\|no-ops" "$REPORT"          # dim 10 no-ops
grep -qi "0.7\|window 42\|mode 3" "$REPORT" # dim 10 voodoo constants
grep -q "🔴" "$REPORT"                       # overall red present
```

### Ablation (does the skill help?)

Run `flawed-skill-catches-planted-defects` **with and without** the skill loaded.
Without the skill, an agent typically eyeballs the file and catches 1-2 obvious
issues (maybe the Windows paths) but misses the name/dir mismatch, the no-ops,
the script-extraction opportunity, and the negative-trigger gap, and produces no
structured scorecard. The delta in defects-caught is the skill's value.

### Cross-harness / cross-model

These cases were authored against pi. Before relying on the skill in another
harness (Claude Code, Cursor, Kiro CLI, Q), re-run at least the two positive
cases there - a skill can trigger well in one harness and poorly in another.
Record which harness/model a pass rate was measured on.

## Lifecycle

`skill-audit` is a **preference/capability hybrid**: the rubric encodes durable
authoring conventions (preference) but some checks (e.g. token-budget ceilings,
specific anti-patterns) track current model behavior (capability). Re-review
these evals when:

- the rubric in `references/scoring-rubric.md` changes (add/adjust a case), or
- a new model materially changes what counts as a no-op or a token-budget
  ceiling (the 500-line / 5000-token thresholds are the likeliest to drift).

Keep these evals even if a dimension is later dropped - they double as
regression guards against the rubric silently weakening.
