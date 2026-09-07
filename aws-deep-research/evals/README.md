# aws-deep-research evals

Eval layer for the `aws-deep-research` skill. Nothing runs these for you: the
Agent Skills spec defines no `evals/` runtime contract, so treat this directory
as a maintainer and CI artifact.

## Layout

```
evals/
  routing.json              trigger corpus - 27 cases, should_trigger + split + rationale
  behavior.json             9 end-to-end cases, forced-load, artifact-graded
  faults.json               9 model-facing degradation cases
  synthesis-rubric.json     10 scored dimensions, each classed hard or soft
  run.py                    the executor: --static, --selftest, grading, routing metrics, JSON/JUnit
  run.sh                    thin python3 wrapper
  run_tests.sh              the one supported pytest invocation
  routing_judge.sh          routing evidence via an isolated judge (metadata-only or --catalog)
  behavior_driver.sh        runs a behavior case end-to-end and assembles its evidence
  eval_synthesis.sh         re-synthesizes retained fixtures, gated by lint_report.py
  extract_behavior_meta.py  builds behavior meta.json from a pi session log
  fixtures/                 committed sanitized findings dirs for eval_synthesis --fixtures
  test_*.py                 the model-free pytest suite (180 tests; 167 with --fast)
  outputs/                  generated evidence, one dir per case id (gitignored)
  results/                  generated run artifacts (gitignored; conclusions live below)
```

## What lives where

`scripts/` is what the SKILL invokes at runtime. `evals/` is what measures it.
Nothing that only exists to test the skill belongs in `scripts/`, because it
ships to every user who installs the skill and adds nothing to a research run.

Two files sit in `scripts/` and are also used by evals, which is correct:
`verify_findings.sh` (SKILL.md Step 5) and `lint_report.py` (SKILL.md Step 6)
are skill tools the eval layer reuses, not eval tools.

The boundary is enforced in both directions by `test_package.py`:
`test_no_eval_only_script_lives_in_scripts_dir` fails if a `test_*.py`,
`run_tests.sh`, or `eval_synthesis.sh` reappears under `scripts/`, and
`test_every_runtime_script_is_actually_referenced` fails if a `scripts/` entry
stops being reachable from SKILL.md, an agent, or a reference.

Deterministic mechanics are pytest, not agent-driven cases:

| Surface | Where | Command |
|---|---|---|
| dispatch command construction, harness detection, guards | `evals/test_dispatch.py` | 29 tests |
| search-budget accounting and thresholds | `evals/test_budget.py` | 12 tests |
| GitHub REST search client | `evals/test_github_search.py` | 4 tests |
| domain blocklist (suffix match, defang, comments, cache) | `evals/test_blocklist.py` | 12 tests |
| config/trust-boundary security | `evals/test_security.py` | 6 tests |
| findings size gate + report linter faults | `evals/test_verify.py` | 42 tests |
| package structure, doc parity, publish hygiene | `evals/test_package.py` | structural + CLI-help gate |

Run all of it with `bash evals/run_tests.sh` - that is the only supported
invocation, because `scripts/common.py` imports `rich` at module level and a
bare `pytest evals/` fails at collection.

## The three modes, kept separate

| Mode | Corpus | What it establishes | What it cannot |
|---|---|---|---|
| metadata-only | `routing.json` | whether the description expresses the intended scope | that the skill actually invoked |
| forced-load | `behavior.json`, `faults.json` | behavior once the skill is available | trigger quality |
| native discovery | `behavior-harness-smoke-native-activation` | end-to-end discovery on a real harness | behavior independent of routing |

Conflating these is the classic error. A forced-load pass says nothing about
triggering; a routing pass says nothing about whether the loaded skill helped.

## Routing

27 cases, 11 positive / 16 negative, stratified across a fixed 60/40
train/validation split (16 train / 11 validation). 3 trials each.

Negatives are near-misses by design - they share vocabulary with the skill and
differ in intent (`research why my unit test is flaky`, `compare these two
Python functions`, `write CDK code for an S3 bucket`). Five are **sibling
near-misses** (`route-023`..`route-027`, tagged `contested-sibling`): queries a
neighbouring skill owns - `amazon-bedrock` (write Converse code, add a
guardrail), `aws-billing-and-cost-management` (set a budget, explain a bill
jump), `brave-search` (a single-lookup web fetch). They catch a description that
over-reaches into a sibling's domain, which a plain positive/negative split
misses. Four positives that a sibling could also legitimately claim
(`route-002/003/004/006`) are tagged `contested`: in `--catalog` mode a loss
there is a sibling overlap, not a pure description defect. One low-overlap
decorative negative (`route-021`) is kept as a control: if it ever triggers,
the description has become far too broad.

Isolation is mandatory and structural, not prose. The judge sees only `name`
and `description`. Deny file, shell, search, network, and subagent tools, and
run with cwd outside the skill directory. "Do not read the skill files" is not
isolation.

Tune the description against `train` only. Never edit it in response to a
`validation` failure - that turns validation into training data. Confirm on
5-10 fresh queries afterwards.

When a positive fails, first check the query really carries enough evidence for
the intended scope; do not widen the description to rescue a mislabeled case.
When a negative triggers, sharpen the intent boundary rather than bolting on
keywords.

Metrics: precision, recall, false-selection rate, no-selection rate. Report
per-class results, never one aggregate.

### Generating routing evidence

```bash
./routing_judge.sh --verify-isolation                       # canary check, no cases run
./routing_judge.sh --trials 3 --jobs 12 --model claude-haiku-4-5
./routing_judge.sh --catalog ~/.claude/skills --trials 3    # realistic router setting
./run.sh --suite routing                                    # grade either mode
```

Two modes, both writing the same `outputs/<id>/meta.json` so `run.py` grades
them identically:

- **metadata-only** (default): the judge sees ONLY this skill's `name` +
  `description` and answers YES/NO. Measures the boundary in isolation.
- **`--catalog <skills-dir>`**: the judge sees the `name` + `description` of
  EVERY skill under `<skills-dir>` (this one is added if missing) and must CHOOSE
  one; `triggered` = it chose `aws-deep-research`. This is the realistic router
  setting - a description that wins alone can still lose a contested query to
  `amazon-bedrock` or `aws-billing-and-cost-management`. Run it against the same
  catalog your target harness installs. `meta.json` records `mode: "catalog"`.

The vote parse is **first-token exact**: the first standalone `YES`/`NO` (or, in
catalog mode, the first skill name) wins, so a hedged "No, but ... Yes" scores
NO. A substring scan wrongly read that as YES.

Isolation is verified by CANARY, not self-report: the script extracts the real
`metadata.version` from SKILL.md and confirms the judge cannot produce it. A
chatty refusal therefore passes, because the model demonstrably lacks the value.
Asking a model to declare its own tool access fails on phrasing rather than on
access, which produced a false abort the first time this ran.

Each case runs `--trials` times and the majority vote decides `triggered`.
Per-trial votes and a `stable_across_trials` flag are retained, so a case the
judge is split on stays visible instead of being averaged into a clean number.
`run.py` then reports a per-split confusion matrix with precision, recall,
false-selection rate, and no-selection rate (`--json` carries `routing_metrics`).

Cost is dominated by fixed process startup, roughly 90s per call regardless of
model, so raise `--jobs` rather than shrinking the model.

### Measured baseline

> **STALE - v6.15, pre-v7.0.** The table below was measured against the v6.15
> description on the pre-v7.0 22-case corpus. v7.0 changed both (`description`
> trimmed + `amazon-bedrock` boundary clause; corpus now 27 cases with five
> sibling near-misses), so by this doc's own rule - *`description` change →
> rerun routing* - it MUST be re-measured before it is trusted. Re-measure both
> modes and overwrite this table in the same commit:
>
> ```bash
> ./routing_judge.sh --trials 3 --jobs 12 --model claude-haiku-4-5   # metadata-only
> ./routing_judge.sh --catalog <harness-skills-dir> --trials 3       # realistic
> ./run.sh --suite routing --json routing-metrics.json               # precision/recall
> ```
>
> Expect the sibling near-misses to be the hard cases and the `contested`
> positives to be where catalog mode diverges from metadata-only.

Skill v6.15, metadata-only judge (`kiro/claude-haiku-4-5`), 3 trials per case,
canary-verified isolation, measured 2026-08-27:

| Metric | before route-003 fix | after |
|---|---|---|
| precision | 1.000 | 1.000 |
| recall | 0.818 | 0.909 |
| false-selection rate | 0.000 | 0.000 |
| accuracy | 0.909 | 0.955 |
| train split | 13/14 | 14/14 |

Perfect precision is the half that matters most: over-triggering spends four
CLI cold starts and real API credits on work the base model should just do. It
held across the fix, so the added triggers sharpened the boundary rather than
widening it.

Two positives missed in the baseline, both informative:

- `route-003` (train), unanimous 0Y/3N. A service-quota lookup read as a simple
  factual recall. The description had no language separating a STABLE fact the
  model knows from a CURRENT value that must be looked up. Fixed by naming
  quotas, limits, pricing, and version availability as explicit triggers - this
  is what moved recall to 0.909.
- `route-008` (validation), 1Y/2N and unstable. The generic-scope boundary case.
  Recorded, deliberately NOT tuned against - editing the description in response
  to a validation failure would turn validation into training data. Only the
  train split was re-measured after the fix. Re-measure validation after the next
  description change and treat a persistent split as evidence that generic
  support needs to be more load-bearing in the description.

These numbers are the durable record; regenerate the underlying per-case data
with `./routing_judge.sh` whenever the description, judge model, or corpus
changes. Run artifacts are gitignored on purpose - a committed JSON dump goes
stale the next time the description changes and then misinforms whoever finds
it. Update this table in the same commit as the change that moved it.

## Behavior and faults

Both are forced-load. Grade artifacts, not trajectories - the agent
legitimately reaches a correct outcome by different routes.

`behavior_driver.sh` is the executor: it runs one case end-to-end, isolates
every artifact into a scratch tree via the documented env surface, and leaves
gradeable evidence in `outputs/<case-id>/`.

```bash
./behavior_driver.sh behavior-pricing-focused                 # pi (default)
./behavior_driver.sh --all --model claude-haiku-4-5           # every case
./run.sh --suite behavior                                     # grade it
```

On **pi** it spawns `pi -p --append-system-prompt @SKILL.md "<prompt>"` (SKILL_DIR
injected, since a forced-loaded agent cannot self-locate it), tees the transcript
to `trace.txt`, copies the `<slug>-report.md`, and runs the extractor. On
**Claude Code** the skill is driven in-session via the native Agent tool, not a
subprocess the script spawns; run `--harness claude-code` to print that
procedure, then re-run with `--session <jsonl> --work-dir <slug-dir>` to assemble
the same evidence from the transcript the Agent-tool run produced.

To do it by hand instead, set an isolated work dir, run the case with the skill
force-loaded, and write evidence to `outputs/<case-id>/`:

```bash
export RESEARCH_WORK_DIR="$(mktemp -d)"
export REPORT_OUTPUT_DIR="$RESEARCH_WORK_DIR/reports"
# fresh agent session, one prompt, skill force-loaded
```

Evidence layout under `outputs/<case-id>/`:

| File | Contents |
|---|---|
| `report.md` | the final report the run produced |
| `trace.txt` | the run transcript (tool calls, printed decisions, dispatch echoes) |
| `meta.json` | the observed invariants below |
| `artifacts/` | optional copy of the findings files, if the work dir is gone |

`meta.json` is generated from the run, not written by hand:

```bash
./extract_behavior_meta.py --latest --work-dir "$RESEARCH_WORK_DIR/<slug>" \
  -o outputs/<case-id>/meta.json
```

pi records every `toolCall` in its session JSONL, so all the invariants below
are recoverable from the parent's own tool record with no instrumentation of the
skill. The extractor reads that log and reports which findings files the parent
read, which fetch tools it called, the peak (and minimum) subagents in one round,
artifacts written outside the work dir, URLs actually retrieved, and Kroki hosts
contacted.

It reads inside shell calls, not just tool names. On pi and Claude Code,
dispatch and retrieval happen INSIDE a `bash`/`execute_bash` call, so the tool
name is `bash` and the action is in the command string: the extractor counts
`dispatch.sh` occurrences per shell call as one parallel round, and flags a
search script or `curl`/`wget` in a *parent* shell call as a parent fetch (a
context-isolation violation). Without this it reported `max_parallel_subagents:0`
and `parent_fetch_calls:[]` for every non-Kiro run. `retrieved_urls` is sourced
from BOTH the trace and the findings files the researchers wrote - otherwise, on
pi/Claude Code where fetches happen in subagents, every citation would look
fabricated to `no_fabricated_citations`.

`meta.json` fields, all optional - a missing field yields PENDING, never a
false PASS:

```json
{
  "slug": "bedrock-llama3-70b-inference-pricing-analysis",
  "work_dir": "/tmp/xyz/bedrock-llama3-70b-inference-pricing-analysis",
  "triggered": true,
  "skill_md_loaded": true,
  "max_parallel_subagents": 4,
  "min_parallel_subagents": 2,
  "subagent_return_chars": 240,
  "parent_findings_reads": [],
  "parent_fetch_calls": [],
  "artifacts_outside_work_dir": [],
  "retrieved_urls": ["https://docs.aws.amazon.com/..."],
  "kroki_hosts_contacted": ["http://localhost:8000"]
}
```

`max_parallel_subagents` feeds both `max_parallel` (cap: never more than 4 in a
round) and `min_parallel` (floor: real fan-out happened, not one-at-a-time
dispatch).

`parent_findings_reads`, `parent_fetch_calls`, and `native_activation` are the
hard invariants. The first two protect the skill's central architectural
promise: raw research content never enters the parent context. A run that
produces a beautiful report while the parent read the findings has failed.

Faults are injected only through the documented environment surface - a scratch
`AWS_DEEP_RESEARCH_CONFIG`, a seeded `budget.json`, a scratch blocklist. Never
edit the skill tree to inject a fault.

## Synthesis regression

`eval_synthesis.sh` re-synthesizes a retained findings set with the CURRENT
synthesizer prompt and gates the output on `lint_report.py`'s hard checks; the
soft `synthesis-rubric.json` dimensions stay advisory until a judge is
calibrated. It spends no search credits - only one synthesis LLM call per
fixture.

Three sanitized fixtures ship under `evals/fixtures/<slug>/` (referenced by
`synthesis-rubric.json`'s `regression_fixtures`), so the regression is
reproducible without a user's prior work dir:

```bash
./eval_synthesis.sh --fixtures --all                     # re-synth the shipped fixtures
./eval_synthesis.sh --fixtures --all --model claude-haiku-4-5   # pin the model
./eval_synthesis.sh <slug>                               # a slug in $RESEARCH_WORK_DIR
```

`--fixtures` stages each committed fixture into the run's scratch dir first, so
the `<slug>-report.eval.md` output never lands in the committed fixture. Pin
`--model` for a release-comparison run so the arms differ only by the prompt.

## Grading

```bash
./run.sh --selftest              # 27 engine assertions, no evidence needed
./run.sh --static                # 259 corpus-structure checks, no agent needed
./run.sh                         # grade every case that has evidence
./run.sh --suite behavior
./run.sh --case route-014        # unknown case id exits 2, not a false pass
./run.sh --lenient               # missing evidence is PENDING, not FAIL
./run.sh --json r.json --junit r.xml
```

Check types: `slug_valid`, `artifact_exists`, `artifact_absent`,
`artifact_in_work_dir_only`, `report_lint`, `report_regex`, `min_citations`,
`max_parallel`, `min_parallel`, `trace_regex`, `trace_absent_regex`,
`no_parent_findings_read`, `no_parent_fetch`, `subagent_return_budget`,
`native_activation`, `no_fabricated_citations`, `no_remote_kroki_fallback`,
`should_trigger`, and `judge` (INFO only, never affects pass/fail).

`report_lint` shells out to `scripts/lint_report.py`, so the behavior gate and
the synthesis gate agree by construction rather than by convention.

## Gates

| Layer | Treatment | Model needed |
|---|---|---|
| `evals/run_tests.sh` | hard | no |
| `run.sh --static` + `--selftest` | hard | no |
| routing, metadata-only | hard | cheap judge |
| behavior + faults, deterministic checks | hard | full runs |
| native activation per harness | hard | full runs |
| soft rubric dimensions | advisory | judge |
| efficacy ablation | pre-release | 3 arms |

CI runs only the model-free rows (`.github/workflows/skills-ci.yml`). The rest
runs before a release or on a schedule.

## Efficacy

Not yet built. Measuring report quality proves nothing about whether the skill
beats the base agent, which is the question that justifies its process, token,
and API cost.

The design: 5 representative tasks (AWS, cross-cloud, intentional generic) run
under three arms - `no-skill`, `previous-release`, `candidate` - with identical
model, harness, tools, inputs, and graders, 3 trials each. Make the skill
directory physically inaccessible in the no-skill arm; a prose instruction to
ignore it is not an ablation. Report paired per-case deltas with uncertainty
alongside latency, tokens, and external cost. Cluster uncertainty at the
source-case level, since trials of one case are related observations, not
independent ones.

## Maintenance

Different edits threaten different axes:

- `name` or `description` → rerun routing.
- body, references, agents, scripts → rerun behavior, faults, and the pytest gate.
- the installed skill catalog → rerun routing even though this skill did not change.
- model, harness, or tool upgrade → requalify everything; results are a property
  of the whole stack, not of `SKILL.md` alone.

Feed production false triggers, missed triggers, and safety surprises back in as
new cases. Retire stale cases deliberately, recording why, instead of quietly
rewriting the corpus.

`evals.json` (the pre-6.15 prose corpus) was replaced by `routing.json`,
`behavior.json`, and `faults.json`. It was documentation nothing executed: no
`should_trigger` field, no splits, no trials, no graders. It remains in git
history.
