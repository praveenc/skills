# Subagent Dispatch (portable across coding-agent harnesses)

This skill runs all research in **subagents**; the parent only routes,
dispatches, and reads the finished report. How you dispatch depends on which
coding-agent harness is running. There are two dispatch worlds.

## Contents

- [Step 1 — Determine the harness](#step-1--determine-the-harness)
- [Two dispatch worlds](#two-dispatch-worlds)
- [Backend A — Kiro (in-session subagent tool)](#backend-a--kiro-in-session-subagent-tool)
  - [Detect the engine (v2 vs v3)](#first-detect-the-engine-the-call-shape-differs)
  - [The generic path (no registration) — PREFERRED](#the-generic-path-no-registration-required--preferred)
  - [The named-agent path (optional)](#the-named-agent-path-optional-optimization)
- [Backend B — pi / Claude Code (process fan-out via `dispatch.sh`)](#backend-b--pi--claude-code-process-fan-out-via-dispatchsh)
- [Batching rounds (both backends: ≤4 parallel)](#batching-rounds-both-backends-4-parallel)
- [Task brief (both backends)](#task-brief-both-backends)

## Step 1 — Determine the harness

Detect it, do not assume. Cheap → certain:

1. **Env fingerprint**:
   - pi → `PI_CODING_AGENT`
   - Claude Code → `CLAUDECODE` / `CLAUDE_CODE_ENTRYPOINT` / `CLAUDE_CODE_USE_BEDROCK`
   - Codex → `CODEX_SANDBOX` / `CODEX_HOME`
   - Kiro → `KIRO_AGENT` / `KIRO_CLI` / `KIRO_VERSION`
2. **If zero or more-than-one fingerprint matches → ASK the user exactly one
   question**: *"Which coding agent is running this — pi, claude, codex, or
   kiro?"* The environment can be ambiguous (e.g. a pi runtime pointed at a
   Kiro endpoint), so never silently guess when signals conflict.
3. **The user may name anything.** If they name a harness that is not one of
   the four tested (pi, claude, codex, kiro), say plainly: *"‹X› isn't one of
   the four tested harnesses. Most harnesses follow the process-fan-out
   pattern, so I can try that as a best effort — proceed?"* and let them
   confirm. Do not refuse.
4. **Always echo the chosen harness + backend + the exact command before
   dispatching.** `scripts/dispatch.sh` does this for you.

## Two dispatch worlds

| Harness | Backend | Mechanism |
|---|---|---|
| Kiro | **in-session** | native subagent tool (`use_subagent` on v2, `subagent` on v3) — no subprocess |
| pi, Claude Code | **process-fan-out** | `scripts/dispatch.sh` spawns headless children |
| Codex | (process-fan-out, not yet enabled — pending sandbox/network spike) |
| untested | process-fan-out, best effort | try `dispatch.sh --harness <name>`; likely needs a per-CLI tweak |

The agent role prompts in `$SKILL_DIR/agents/*.md` are the **single source of
truth** both backends use.

---

## Backend A — Kiro (in-session subagent tool)

Kiro dispatches subagents **inside the current session** via its native
subagent tool. **Do NOT shell out to `kiro-cli chat --agent …`** — that runs
one agent as an entire new session, not a fan-out primitive. **Do NOT reach for
any other delegate-shaped tool** (e.g. an MCP `*_Delegate`); use only Kiro's
built-in subagent tool.

### First: detect the engine (the call shape differs)

Kiro has two agent engines and the subagent tool differs between them. Detect
which one is live by checking the tool surface, then use the matching call:

| Engine | Subagent tool | How to dispatch |
|---|---|---|
| **v2** (current default) | `use_subagent` | `command: InvokeSubagents` with a `subagents[]` array |
| **v3** (opt-in beta) | `subagent` | name the agents in natural language; Kiro plans the DAG |

If you can see a tool named `use_subagent`, you are on **v2** — use the v2 call
below. If you see `subagent` (and not `use_subagent`), you are on **v3**. When
in doubt, v2 is the safe default (it is the current engine for kiro-cli 2.x).

### The generic path (no registration required) — PREFERRED

Kiro's default subagent can take an **inline role prompt**, so this skill does
**not** need any agent to be pre-registered. The `agents/*.md` files are the
single source of truth: hand each one to a subagent as its role.

**v2 — `use_subagent` / `InvokeSubagents`:** call the tool with one entry in
`content.subagents[]` per researcher (≤4 per call). For each entry:

- `query` — instruct it to adopt the role and write findings to disk, e.g.:
  *"Read `$SKILL_DIR/agents/web-content-researcher.md` and act as that agent.
  Follow the task brief below. Write your findings to
  `$WORK_DIR/<slug>/web-content.md`. \n\n<task brief per subagent-task-contract.md>"*
- `agent_name` — **omit it** to use the default subagent (this is the generic path).
- `relevant_context` — optional extra context.

All entries in one `subagents[]` array run in parallel, so a round of ≤4
researchers is a single `InvokeSubagents` call. Run the synthesizer as a second
call after the size-gate check.

**v3 — `subagent` tool:** describe the round in natural language, naming the
role files (*"dispatch four researchers in parallel, each adopting the role in
`$SKILL_DIR/agents/<name>.md`, writing to `$WORK_DIR/<slug>/<file>.md`; then run
the synthesizer"*). Kiro plans the 4-parallel DAG and returns results via the
built-in `summary` tool.

**Permission note:** on the generic path the subagents run under the default
agent's permissions, so without `--trust-all-tools` Kiro will prompt per
subagent. That is expected. Users who dislike prompts should launch with
`kiro-cli chat --trust-all-tools`. This skill assumes that is acceptable and
does not require named-agent registration to suppress prompts.

### The named-agent path (optional optimization)

If the user has run `setup/register.sh`, the researchers are registered as
named Kiro agents and the orchestrator config (`setup/kiro-agent.json`) scopes
them under `toolsSettings.subagent` (`availableAgents` + `trustedAgents`) so
they spawn **without** approval prompts. In that case, pass `agent_name` (v2)
or reference the agent by name (v3) instead of an inline role prompt.

Use this path when you specifically want pre-scoped tools/permissions or a
launch-by-name entry point (e.g. running the whole skill headless via ACP
without loading it into the caller's context). For this skill's internal
researcher fan-out, the generic path above is preferred.

Either way, author the task brief per the shared
[subagent-task-contract.md](subagent-task-contract.md).

---

## Backend B — pi / Claude Code (process fan-out via `dispatch.sh`)

There is no native subagent tool in pi or Claude Code, so the parent spawns
each subagent as a **headless child process**. Use the shim — never improvise a
delegate-shaped tool from the environment.

```bash
scripts/dispatch.sh [--harness pi|claude] <agent-name> <task> <outfile>
```

- `<agent-name>` — base name under `$SKILL_DIR/agents/` (e.g. `synthesizer`)
- `<task>` — literal task string, or `@/path/to/taskfile` to read from a file
- `<outfile>` — where the child's findings/report are written

The shim loads `$SKILL_DIR/agents/<agent-name>.md` as the child's system
prompt, maps tool names per-CLI (pi `read,write,bash`; claude `Read Write
Bash`), echoes the exact command, prints the process disclaimer once, then
runs the child with stdout redirected to `<outfile>`.

### Run a parallel round (≤4 subagents)

The shim dispatches **one** subagent. The parent backgrounds several and waits:

```bash
# print the disclaimer once for the whole round, then suppress per-call
export DISPATCH_BANNER_SHOWN=1
echo "⚠️  Each subagent below launches a full, separate CLI process."

scripts/dispatch.sh aws-mcp-researcher     "@$WORK_DIR/$SLUG/brief-aws.md"       "$WORK_DIR/$SLUG/aws-docs.md"      &
scripts/dispatch.sh web-content-researcher "@$WORK_DIR/$SLUG/brief-web.md"       "$WORK_DIR/$SLUG/web-content.md"   &
scripts/dispatch.sh github-researcher      "@$WORK_DIR/$SLUG/brief-github.md"    "$WORK_DIR/$SLUG/github-repos.md"  &
scripts/dispatch.sh agentcore-researcher   "@$WORK_DIR/$SLUG/brief-agentcore.md" "$WORK_DIR/$SLUG/agentcore.md"     &
wait
```

Then run the silent-failure size gate (SKILL.md Step 5), then dispatch the
`synthesizer` in its own round.

### Dry-run / debugging

`DISPATCH_DRY_RUN=1` prints the resolved command and exits without spawning —
use it to preview exactly what will run.

### Exit codes

| Code | Meaning | What the parent should do |
|---|---|---|
| 0 | success (or dry-run) | continue |
| 2 | usage error | fix the invocation |
| 3 | harness undetermined | ask the user, re-invoke with `--harness` |
| 4 | harness known but unsupported here (kiro, or untested) | use Backend A for kiro; for untested, confirm with user then best-effort |

---

## Batching rounds (both backends: ≤4 parallel)

Both Kiro and the process-fan-out CLIs cap at 4 parallel subagents. Plan rounds
to minimise wall-clock time.

**Simple queries (2–3 researchers)** — one research round + synthesizer:
```
Round 1: [aws-mcp-researcher, web-content-researcher]   → ~2 min
Round 2: [synthesizer]                                    → ~2 min
```

**Comprehensive queries (4 researchers)** — one full round + synthesizer:
```
Round 1: [aws-mcp-researcher, web-content-researcher, github-researcher, agentcore-researcher]  → ~3 min
Round 2: [synthesizer]                                                                            → ~2 min
```

**With diagram (optional)** — add to the synthesizer round if a slot is free:
```
Round 2: [synthesizer, diagram-generator]  → ~2 min (parallel)
```

## Task brief (both backends)

Every subagent task string carries the fields defined in
[subagent-task-contract.md](subagent-task-contract.md): the resolved
`SKILL_DIR`, the research-contract path, the original query, the assigned
subqueries, the output file path, and the log dir. That file is the single
source of truth for what every subagent needs.
