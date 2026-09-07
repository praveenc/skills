# Subagent Dispatch (portable across coding-agent harnesses)

This skill runs all research in **subagents**; the parent only routes,
dispatches, and reads the finished report. How you dispatch depends on which
coding-agent harness is running. There are **three dispatch backends** - pick by
harness.

## Contents

- [Step 1 - Determine the harness](#step-1---determine-the-harness)
- [Three dispatch backends](#three-dispatch-backends)
- [Backend A - Kiro (in-session subagent tool)](#backend-a---kiro-in-session-subagent-tool)
  - [Detect the engine (v2 vs v3)](#first-detect-the-engine-the-call-shape-differs)
  - [The generic path (no registration) - PREFERRED](#the-generic-path-no-registration-required---preferred)
  - [The named-agent path (optional)](#the-named-agent-path-optional-optimization)
- [Backend B - Claude Code / Claude Agent SDK (native `Agent` tool)](#backend-b---claude-code--claude-agent-sdk-native-agent-tool)
- [Backend C - pi (process fan-out via `dispatch.sh`)](#backend-c---pi-process-fan-out-via-dispatchsh)
- [Batching rounds and per-harness limits](#batching-rounds-and-per-harness-limits)
- [Task brief (all backends)](#task-brief-all-backends)

## Step 1 - Determine the harness

Detect it, do not assume. Cheap → certain:

1. **Env fingerprint**:
   - pi → `PI_CODING_AGENT`
   - Claude Code → `CLAUDECODE` / `CLAUDE_CODE_ENTRYPOINT` / `CLAUDE_CODE_USE_BEDROCK`
   - Kiro → `KIRO_AGENT` / `KIRO_CLI` / `KIRO_VERSION`
   - Claude Agent SDK → no env fingerprint; you know because you are the SDK host
2. **If zero or more-than-one fingerprint matches → ASK the user exactly one
   question**: *"Which coding agent is running this - pi, claude, or kiro?"* The
   environment can be ambiguous (e.g. a pi runtime pointed at a Kiro endpoint),
   so never silently guess when signals conflict.
3. **The user may name anything.** If they name a harness that is not one of the
   three tested (pi, claude, kiro), say plainly: *"‹X› isn't one of the tested
   harnesses. If it exposes a native subagent/Agent tool, I'll use that; else
   I'll try the process-fan-out path as best effort - proceed?"* and let them
   confirm. Do not refuse.
4. **Always echo the chosen harness + backend + the exact dispatch before
   dispatching.** `scripts/dispatch.sh` does this for the process-fan-out path.

## Three dispatch backends

| Harness | Backend | Mechanism |
|---|---|---|
| Kiro | **A - in-session** | native subagent tool (`use_subagent` on v2, `subagent` on v3) - no subprocess |
| Claude Code, Claude Agent SDK | **B - native `Agent` tool** | one `Agent` call per researcher, issued in a single turn, backgrounded |
| pi | **C - process fan-out** | `scripts/dispatch.sh` spawns headless `pi -p` children |
| untested | best effort | native subagent tool if present; else `dispatch.sh --harness <name>` |

The agent role prompts in `$SKILL_DIR/agents/*.md` are the **single source of
truth** all three backends use.

---

## Backend A - Kiro (in-session subagent tool)

Kiro dispatches subagents **inside the current session** via its native
subagent tool. **Do NOT shell out to `kiro-cli chat --agent …`** - that runs
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

If you can see a tool named `use_subagent`, you are on **v2** - use the v2 call
below. If you see `subagent` (and not `use_subagent`), you are on **v3**. When
in doubt, v2 is the safe default (it is the current engine for kiro-cli 2.x).

### The generic path (no registration required) - PREFERRED

Kiro's default subagent can take an **inline role prompt**, so this skill does
**not** need any agent to be pre-registered. The `agents/*.md` files are the
single source of truth: hand each one to a subagent as its role.

**v2 - `use_subagent` / `InvokeSubagents`:** call the tool with one entry in
`content.subagents[]` per researcher (≤4 per call). For each entry:

- `query` - instruct it to adopt the role and write findings to disk, e.g.:
  *"Read `$SKILL_DIR/agents/web-content-researcher.md` and act as that agent.
  Follow the task brief below. Write your findings to
  `$WORK_DIR/<slug>/web-content.md`. \n\n<task brief per subagent-task-contract.md>"*
- `agent_name` - **omit it** to use the default subagent (this is the generic path).
- `relevant_context` - optional extra context.

All entries in one `subagents[]` array run in parallel, so a round of ≤4
researchers is a single `InvokeSubagents` call. Run the synthesizer as a second
call after the size-gate check.

**v3 - `subagent` tool:** describe the round in natural language, naming the
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

## Backend B - Claude Code / Claude Agent SDK (native `Agent` tool)

Claude Code **does** have a native subagent primitive: the `Agent` tool (the
`Task` tool renamed in 2.1.63). It runs subagents **in-session and in the
background** - no cold `claude -p` child, no auth round-trip per researcher, and
the subagents inherit the session's MCP servers (so `fetchv2` is available to
the web researcher). This is the preferred backend on Claude Code and on the
Claude Agent SDK. **Do NOT shell out to `claude -p` for a normal round** - that
is the process-fan-out fallback (Backend C), only for hosts without the `Agent`
tool.

**Dispatch a round:** issue **one `Agent` call per researcher, all in a single
assistant turn**, so they run concurrently. For each:

- `subagent_type`: `general-purpose`
- `description`: a 3-5 word label (e.g. `research aws docs`)
- `prompt`: *"Read `$SKILL_DIR/agents/<name>.md` and act as that agent. Write
  your findings to `$WORK_DIR/<slug>/<file>.md`.\n\n<task brief per
  subagent-task-contract.md>"*
- run in the background where the host supports it, so the parent is not blocked

While the researchers run, the parent **prepares the synthesizer brief**; when
the completion notifications arrive it runs Step 5 (the size gate) and then
dispatches the synthesizer as its own `Agent` call. This keeps the lead working
while subagents run, which Fable 5.1 explicitly favours.

**Effort:** the synthesizer is the one long deliverable - run it at `high`
(not the Claude Code `xhigh` default, which tends to draft the report in
thinking and then rewrite it). Script-only researchers can run at `medium`.
On the `Agent` tool, set `effort` per agent; on the SDK, set it in the agent
definition.

**SDK note:** the Claude Agent SDK exposes the same subagent mechanism
(`AgentDefinition` / the `Agent` tool). Use it identically. Only fall back to
Backend C if a host genuinely lacks any subagent primitive.

---

## Backend C - pi (process fan-out via `dispatch.sh`)

pi has **no native subagent tool and no MCP**, so the parent spawns each
subagent as a **headless child process**. Use the shim - never improvise a
delegate-shaped tool from the environment. (This backend is also the fallback
for any SDK host that lacks the `Agent` tool.)

```bash
scripts/dispatch.sh [--harness pi|claude] <agent-name> <task> <outfile>
```

- `<agent-name>` - base name under `$SKILL_DIR/agents/` (e.g. `synthesizer`)
- `<task>` - literal task string, or `@/path/to/taskfile` to read from a file
- `<outfile>` - the findings/report path the child writes **with its write
  tool** (the same path is handed to the child inside `<task>`). The child's
  stdout/stderr is captured to `<outfile-dir>/logs/<agent>.stdout`, **not**
  redirected onto `<outfile>` - two writers on one path corrupt the head of
  every findings file.

The shim loads `$SKILL_DIR/agents/<agent-name>.md` as the child's system
prompt, maps tool names per-CLI (pi `read,write,bash,edit`; claude `Read Write
Bash Edit`), checks the child CLI is on PATH (exit 4 if not), echoes the exact
command, prints the process disclaimer once, then runs the child under a
`timeout` (`DISPATCH_TIMEOUT`, default 900s), capturing stdout/stderr to
`<outfile-dir>/logs/<agent>.stdout`. The write tool owns `<outfile>` alone.

Because pi has no MCP, the web researcher cannot use `fetchv2` here - it uses
`trafilatura_scraper.py` for every URL (see
[web-content-researcher.md](../agents/web-content-researcher.md)).

### Run a parallel round

The shim dispatches **one** subagent. The parent backgrounds several and waits
**per PID** so a failure or timeout is attributed, not silently discarded:

```bash
# print the disclaimer once for the whole round, then suppress per-call
export DISPATCH_BANNER_SHOWN=1
echo "⚠️  Each subagent below launches a full, separate pi process."

declare -A PID_AGENT
scripts/dispatch.sh aws-mcp-researcher     "@$WORK_DIR/$SLUG/brief-aws.md"       "$WORK_DIR/$SLUG/aws-docs.md"      & PID_AGENT[$!]=aws-mcp-researcher
scripts/dispatch.sh web-content-researcher "@$WORK_DIR/$SLUG/brief-web.md"       "$WORK_DIR/$SLUG/web-content.md"   & PID_AGENT[$!]=web-content-researcher
scripts/dispatch.sh github-researcher      "@$WORK_DIR/$SLUG/brief-github.md"    "$WORK_DIR/$SLUG/github-repos.md"  & PID_AGENT[$!]=github-researcher
scripts/dispatch.sh agentcore-researcher   "@$WORK_DIR/$SLUG/brief-agentcore.md" "$WORK_DIR/$SLUG/agentcore.md"     & PID_AGENT[$!]=agentcore-researcher
for pid in "${!PID_AGENT[@]}"; do
  wait "$pid" || echo "⚠️  ${PID_AGENT[$pid]} exited $? (see logs/)"
done
```

Then run the silent-failure size gate (SKILL.md Step 5), then dispatch the
`synthesizer` in its own round.

### Dry-run / debugging

`DISPATCH_DRY_RUN=1` prints the resolved command and exits without spawning -
use it to preview exactly what will run.

### Exit codes

| Code | Meaning | What the parent should do |
|---|---|---|
| 0 | success (or dry-run) | continue |
| 2 | usage error | fix the invocation |
| 3 | harness undetermined | ask the user, re-invoke with `--harness` |
| 4 | harness unsupported here (kiro), or child CLI not on PATH | use Backend A/B; or install the CLI |
| 124 | child exceeded `DISPATCH_TIMEOUT` | treat that source as failed; the gate will flag it |

---

## Batching rounds and per-harness limits

Plan rounds to minimise wall-clock time. The parallelism cap is **per harness**,
not universal:

| Harness | Parallel cap per round |
|---|---|
| Kiro | 4 (the subagent tool's documented limit) |
| Claude Code / SDK | the host default (`CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS`, default 20) - the skill never needs more than ~5, so one round covers all researchers |
| pi (process fan-out) | keep small (≤4): each child is a full cold process |

**Simple queries (2-3 researchers)** - one research round + synthesizer:
```
Round 1: [aws-mcp-researcher, web-content-researcher]   → ~2 min
Round 2: [synthesizer]                                    → ~2 min
```

**Comprehensive queries (4 researchers)** - one full round + synthesizer:
```
Round 1: [aws-mcp-researcher, web-content-researcher, github-researcher, agentcore-researcher]
Round 2: [synthesizer]
```

**With diagram (optional)** - add to the synthesizer round if a slot is free:
```
Round 2: [synthesizer, diagram-generator]  (parallel)
```

## Task brief (all backends)

Every subagent task string carries the fields defined in
[subagent-task-contract.md](subagent-task-contract.md): the resolved
`SKILL_DIR`, the research-contract path, the original query, the assigned
subqueries, the output (findings) file path, and the log dir. That file is the
single source of truth for what every subagent needs.
