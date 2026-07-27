# Evals: research-report-visuals

Deterministic, two-phase eval harness. Phase 1 generates HTML with the skill;
phase 2 validates it with a runner that needs no LLM.

## Layout

```
evals/
  evals.json     9 cases (5 generate, 4 boundary/negative) with machine checks
  run.py         deterministic validator (regex / substring / byte-size / file-absence)
  run.sh         wrapper (python3 -> python fallback)
  samples/       source markdown reports fed to the skill
  outputs/       generated artifacts, one per case (git-ignored; you create these)
```

## Phase 1: generate (per case, isolated)

Each case is generated in its own **fresh session** so an agent cannot pass by
reusing prior context outside the intended trigger. Do not chain cases through
one conversation.

For `generate` cases, run the skill on the case's `input` sample and save the
result as `outputs/<id>.html`. Example (headless pi):

```bash
cd "$(dirname "$0")/.."          # skill root
mkdir -p evals/outputs
# one clean session per case:
pi -p "Use the research-report-visuals skill on evals/samples/gpu-comparison-sample.md. \
Save the HTML to evals/outputs/eval-01-comparison-report.html. Do not ask for a path."
```

For `negative` cases, the **expected outcome is that no HTML visual is produced**.
The runner treats a missing `outputs/<id>.html` as the pass condition. Optionally
capture the agent's textual reply to `outputs/<id>.txt`; if present, the runner
also checks it explains why the skill does not apply.

## Phase 2: validate (deterministic)

```bash
./run.sh                 # validate all cases (strict: a missing output fails)
./run.sh --lenient       # missing outputs are PENDING, not failures
./run.sh --case eval-05-code-heavy
./run.sh --selftest      # prove the check engine works, no outputs needed
```

Statuses: `PASS` / `FAIL` / `PENDING` (output not generated yet) /
`INFO` (a `judge` check for human review; never affects exit code).

Exit codes: `0` all good; `1` a FAIL or (strict) a missing output; `2` usage error.

## Check types (cheap-first)

| type | meaning |
|------|---------|
| `regex` | HTML must match the pattern |
| `absent` | literal substring must be absent (em/en dashes, etc.) |
| `absent_regex` | pattern must not match (e.g. banned card border bars) |
| `count_regex` | pattern must match at least `min` times (e.g. >=2 source links) |
| `max_bytes` | file must be <= `value` bytes |
| `html_absent` | (negative cases) no HTML output must exist |
| `response_regex` | (negative cases) captured transcript must explain the decline |
| `judge` | human-review only; printed as INFO |

Assertions are deliberately **tolerant**: they match structure, not exact class
names (e.g. `class="... masthead ..."` and `footer[-_]?sources`), so a valid
visual that renames or extends a class is not failed for cosmetics.

## Negative coverage (dimension 4 vectors)

The 4 negatives guard the skill's real over-trigger vectors from the SKILL.md
`Does NOT` clause:

- `eval-06` raw CSV + "dashboard" request
- `eval-07` general web design / landing page
- `eval-08` raw-dataset interactive charting
- `eval-09` non-report markdown (a README with install/usage/contributing sections)

## Maintenance

- Re-run after editing `SKILL.md`, `build-rules.md`, `visual-signature.md`, or
  `typography-and-color.md`.
- Regenerate `outputs/` when the skill's HTML contract changes.
- Validated against: pi / kiro-cli chat on claude-opus-4-8 (single-harness; see
  `meta.validated_against` in evals.json). Cross-harness runs are a known gap.
