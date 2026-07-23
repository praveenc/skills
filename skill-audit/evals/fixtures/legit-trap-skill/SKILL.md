---
name: legit-trap-skill
description: >
  Triage a failing CI build for a Node service by reading the CI log, classifying
  the root cause, and proposing the minimal fix. Use when the user asks to
  "triage the CI failure", "why did the build fail", "diagnose the red pipeline",
  or pastes a CI log and wants the cause. Do NOT use for local test failures the
  user can already see, for writing new tests, or for non-CI runtime incidents in
  production (those go to the incident-response skill).
compatibility: >
  Requires bash and node. Read-only against the repo; writes nothing.
---

# Legit Trap Skill (fixture: legitimately fine, sits on the new-dimension traps)

Triage a failing CI build and propose the smallest fix.

## Workflow

This is deliberately judgment-driven, NOT a fixed pipeline - the path depends on
what the log shows:

1. Read the CI log the user provides (or fetch it if given a URL).
2. Classify the failure: dependency, compile, flaky test, timeout, or config.
   Which branch you take depends on this classification.
3. If dependency: check the lockfile drift and propose a pin. If compile: locate
   the first error, not the cascade. If flaky: check for timing/order coupling
   before proposing a retry. If timeout: look for the slowest step. If config:
   diff against the last green run.
4. Propose the *minimal* fix for the branch you landed on. Stop and ask if two
   root causes are equally likely.

## Output

A short triage note: classification, evidence line from the log, proposed fix.

## Gotchas

- CI logs interleave stdout/stderr from parallel jobs; group by job id before
  reading, or you will attribute an error to the wrong step.
- A green "tests passed" line can still precede a non-zero exit when a post-test
  coverage gate fails - check the final exit line, not the last human-readable one.
