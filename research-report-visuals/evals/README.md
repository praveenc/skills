# Evals for research-report-visuals

This directory separates discovery from behavior:

| Suite | Mode | What it proves |
|---|---|---|
| `routing.json` | metadata-only | the description expresses the intended boundary |
| `native.json` | native discovery | the target harness selected and loaded the expected skills |
| `behavior.json` | forced load | the skill improves the generated HTML after it is available |

A routing pass does not prove native activation. A forced-load pass does not
prove routing.

## Layout

```text
evals/
  routing.json
  native.json
  behavior.json
  routing_judge.sh
  run.py
  run.sh
  samples/
  outputs/              generated evidence, ignored by Git
```

The runner uses only the Python standard library.

## Model-free checks

Run these on every relevant change:

```bash
./run.sh --static
./run.sh --selftest
```

`--static` validates corpus shape, case IDs, splits, fixture references,
expected-skill sets, arms, and check types. `--selftest` proves the behavior
check engine against inline fixtures.

## Evidence layout

Each evaluation run has one immutable ID:

```text
outputs/<run-id>/
  manifest.json
  no-skill/
    behavior/<case-id>/trial-01/
    native/<case-id>/trial-01/
  released/
    routing/<case-id>/trial-01/
    behavior/<case-id>/trial-01/
    native/<case-id>/trial-01/
  candidate/
    routing/<case-id>/trial-01/
    behavior/<case-id>/trial-01/
    native/<case-id>/trial-01/
```

The runner requires `manifest.json`:

```json
{
  "run_id": "20260907T190000Z",
  "created_at": "2026-09-07T19:00:00Z",
  "corpus_revision": {
    "routing": "<sha256>",
    "native": "<sha256>",
    "behavior": "<sha256>"
  },
  "model": "<model and settings>",
  "harness": "<harness and adapter version>",
  "permissions": "<tool and permission policy>",
  "catalog_revision": "<catalog commit or digest>",
  "catalog_skills": {
    "aws-architecture-diagram": "<SKILL.md sha256>",
    "aws-deep-research": "<SKILL.md sha256>",
    "lieflat-charts": "<SKILL.md sha256>"
  },
  "arms": ["no-skill", "released", "candidate"],
  "arm_definitions": {
    "no-skill": {
      "target_skill_access": "absent",
      "skill_revision": "absent"
    },
    "released": {
      "target_skill_access": "available",
      "skill_revision": "<released SKILL.md sha256>",
      "skill_path": "/retained/snapshots/released/research-report-visuals"
    },
    "candidate": {
      "target_skill_access": "available",
      "skill_revision": "<candidate SKILL.md sha256>",
      "skill_path": "/retained/snapshots/candidate/research-report-visuals"
    }
  }
}
```

Use the same prompt, fixture, model, harness, tools, permissions, and output
contract across matched arms. Make the skill directory physically unavailable
in the no-skill arm. Keep released and candidate skill snapshots at their
recorded paths until grading is complete.

Corpus digests cover transitive repository inputs. The behavior digest includes
every referenced report fixture. The native digest includes `native.json` and
the routing prompts that native cases reference.

## Metadata-only routing

`routing_judge.sh` adapts the isolated routing driver used by
`aws-deep-research/evals`. It exposes only the tested skill's frontmatter name
and description. It runs the judge outside the skill directory with tools,
skills, extensions, context files, prompt templates, and session history
disabled.

Run the released and candidate descriptions under the same run ID:

```bash
RUN_ID=20260907T190000Z

./routing_judge.sh \
  --run-id "$RUN_ID" \
  --arm released \
  --skill-dir /path/to/released/research-report-visuals \
  --model claude-haiku-4-5 \
  --trials 3

./routing_judge.sh \
  --run-id "$RUN_ID" \
  --arm candidate \
  --skill-dir /path/to/candidate/research-report-visuals \
  --model claude-haiku-4-5 \
  --trials 3

./run.sh --run "outputs/$RUN_ID" --suite routing
```

Use `--verify-isolation` after changing the judge command or harness. The
script checks that the judge cannot obtain a version canary from `SKILL.md`.

The runner uses majority vote for the routing decision. It retains every vote.
Split votes fail validation cases and remain visible for training cases.

Tune the description against the train split only. The validation prompts use
different wording from the current frontmatter. After selecting a description,
create six fresh prompts outside the repository and run them under a new run
ID. Attach the sealed prompt set and evidence to the release record only after
the description is frozen. Do not edit the description in response to held-out
failures.

## Native discovery

Run each `native.json` case in a fresh session with the real catalog. Retain
the harness's actual skill-selection and body-load events in `meta.json`:

```json
{
  "provenance": {
    "run_id": "20260907T190000Z",
    "arm": "candidate",
    "suite": "native",
    "case_id": "native-001-target-explicit",
    "trial": 1,
    "model": "<exact manifest value>",
    "harness": "<exact manifest value>",
    "permissions": "<exact manifest value>",
    "catalog_revision": "<exact manifest value>",
    "corpus_digest": "<native corpus digest>",
    "skill_revision": "<candidate SKILL.md sha256>"
  },
  "selected_skills": ["research-report-visuals"],
  "load_events": [
    {
      "skill": "research-report-visuals",
      "path": "/resolved/path/SKILL.md",
      "digest": "<sha256>"
    }
  ]
}
```

Do not ask a model whether the skill probably loaded. The evidence must come
from the target harness. Each load-event digest must match the retained arm
snapshot or the skill digest recorded in `catalog_skills`.

For the no-skill arm, the runner removes the target from the expected set and
checks the remaining selection and load events. This shows which adjacent skill
wins when the target is unavailable. Released and candidate arms use the full
expected set.

## Forced-load behavior

Run each behavior case in a fresh session and trial directory.

- `no-skill`: target skill is physically absent.
- `released`: force-load the released skill.
- `candidate`: force-load the candidate skill.

Each trial can retain:

```text
output.html       generated artifact
response.txt      final response, optional
trace.jsonl       normalized observed actions, required
meta.json         provenance and cost data, required
desktop.png       optional visual-judge input
mobile.png        optional visual-judge input
```

Every `meta.json` binds the trial to its manifest:

```json
{
  "provenance": {
    "run_id": "20260907T190000Z",
    "arm": "candidate",
    "suite": "behavior",
    "case_id": "behavior-01-comparison-report",
    "trial": 1,
    "model": "<exact manifest value>",
    "harness": "<exact manifest value>",
    "permissions": "<exact manifest value>",
    "catalog_revision": "<exact manifest value>",
    "corpus_digest": "<behavior corpus digest>",
    "skill_revision": "<candidate SKILL.md sha256>"
  },
  "wall_time_seconds": 0,
  "model_calls": 0,
  "input_tokens": 0,
  "output_tokens": 0,
  "tool_calls": 0
}
```

The harness adapter must normalize observable actions into one JSON object per
line in `trace.jsonl`:

```json
{"type":"file_read","path":"evals/samples/example.md"}
{"type":"file_write","path":"output.html"}
{"type":"tool_call","tool":"browser.fetch","arguments":{"url":"https://example.com"}}
{"type":"network","url":"https://example.com"}
```

Hard safety checks inspect actionable trace events. They do not trust
self-reported empty arrays in `meta.json`. A write outside the trial directory
or any network action fails behavior cases.

Generate all three arms before a release comparison. A pull request can run
candidate-only evidence for a quick deterministic check.

## Grading

```bash
./run.sh --run outputs/<run-id>
./run.sh --run outputs/<run-id> --suite behavior --arm candidate
./run.sh --run outputs/<run-id> --case behavior-05-code-heavy
./run.sh --run outputs/<run-id> --lenient

./run.sh --run outputs/<run-id> \
  --json outputs/<run-id>/results.json \
  --junit outputs/<run-id>/junit.xml \
  --summary outputs/<run-id>/summary.md
```

Strict mode fails when selected evidence is missing. Candidate hard failures
gate the run. Baseline outcome failures remain comparison evidence, but invalid
provenance invalidates the comparison. The runner rejects unknown or ungraded
`--gate-arm` values. When released and candidate arms are both present, it also
rejects validation routing regressions and negative paired case-level deltas
for native or behavior cases.

Reported metrics include:

- train, validation, and overall routing precision, recall, false-selection
  rate, no-selection rate, and instability;
- native and behavior trial pass rates;
- cases that pass all trials;
- paired candidate-minus-released and candidate-minus-no-skill case deltas;
- HTML byte size, visible words, and longest visible sentence per trial;
- wall time, model calls, tokens, and tool calls when `meta.json` records them.

## Hard and advisory checks

Hard checks cover document structure, source and protected-literal
preservation, primary-layer length, unsupported network access, outside writes,
and explicit skill design rules such as no em or en dashes.

Visual quality remains advisory until a judge is calibrated against human
reviews. Use blind pairwise comparison with randomized arm labels. Give the
judge the source report, desktop and mobile screenshots, and extracted visible
text. Grade one narrow dimension at a time and allow `tie` and `unknown`.

Store optional pairwise results under `outputs/<run-id>/judges/<case-id>.json`.
The runner validates the comparison labels, winner, confidence, and evidence,
then reports judge validity without making it a hard gate.

## Recommended gates

| Layer | Treatment |
|---|---|
| `--static` and `--selftest` | hard on every relevant change |
| candidate deterministic behavior | hard on skill-changing pull requests |
| metadata routing | hard when name or description changes |
| native discovery | hard before release and after catalog or harness changes |
| three-arm, three-trial comparison | hard before release |
| blind visual judgment | advisory until calibrated |

Production false triggers, missed triggers, user corrections, and safety
failures should become regression cases without rewriting existing labels.
