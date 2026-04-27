#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "boto3>=1.35.0",
# ]
# ///
"""
synthesize_palmyra.py — alternate synthesizer backend using Writer Palmyra X5
on Amazon Bedrock (inference profile: us.writer.palmyra-x5-v1:0).

This is an OPT-IN backend. The default synthesizer path remains the agent
at agents/synthesizer.md — this script is invoked only when dispatched
explicitly (e.g., via a comprehensive-raw strategy or --use-palmyra flag).

Behavior intentionally mirrors the existing synthesizer agent:
  * Reads research-contract.md + every other *.md in the work dir
    (excludes any pre-existing *-report*.md files to avoid self-referencing)
  * Enforces the SAME report schema (Executive Summary, Detailed Findings,
    Pricing & Cost, Code Examples, Recommendations, Gaps, References)
  * Preserves citation rules: [N] inline, strict reference format
  * Emits a one-line status to stdout + a detailed metadata line

Output path must be provided. Does NOT touch the existing report file.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import textwrap
import time
from pathlib import Path
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

# --- Constants -------------------------------------------------------------

DEFAULT_MODEL_ID = "us.writer.palmyra-x5-v1:0"
DEFAULT_REGION = "us-east-1"
DEFAULT_PROFILE = "001"

# Palmyra X5 hard caps (as of Apr 2025 launch): 1,040,000 input / 8,192 output
PALMYRA_INPUT_CAP_TOKENS = 1_040_000
PALMYRA_OUTPUT_CAP_TOKENS = 8_192

# Approximate byte-to-token ratio for English prose. Conservative.
CHARS_PER_TOKEN = 4.0

# Pricing ($/1M tokens) — used for cost estimate in the status line.
PRICE_INPUT_PER_1M = 0.60
PRICE_OUTPUT_PER_1M = 6.00


# --- Prompts ---------------------------------------------------------------

SYSTEM_PROMPT = textwrap.dedent("""\
    You are the Research Synthesizer for the aws-deep-research skill.

    Your job: ingest a research contract + one or more findings files from
    specialized researcher subagents, and produce a single cohesive research
    report with proper inline citations. Do not concatenate — synthesize.

    ## Hard rules

    - Every factual claim MUST carry an inline citation of the form [N].
    - Same URL = same [N] throughout the report. Number sequentially as they
      first appear.
    - Do NOT fabricate. If a claim is not supported by the findings files,
      omit it or place it in the Gaps & Limitations section.
    - If a findings file is marked WEAK or MISSING by the caller, record that
      explicitly in Gaps & Limitations — never paper over it.
    - Organize by topic, not by source. Use bridging sentences between sections.
    - Keep prose tight. Cut redundancy ruthlessly.

    ## Reference format (strict)

    One entry per URL, numbered, in this exact shape:

        [N] [Human-readable title](https://url)

    For blog posts, append the publication date in the title text when known.
    For pricing items, append the date the price was queried.
    Do NOT use bare URLs, extra text after links, or inline `([source](url))`.

    ## Report schema (use these headings verbatim)

    ```markdown
    # Research Report: <Descriptive Title>

    **Date**: <YYYY-MM-DD>
    **Query**: <original query>
    **Intents**: <comma-separated list>
    **Sources consulted**: <list of source types present in the findings>
    **Synthesizer backend**: Writer Palmyra X5 (Bedrock)

    ## Executive Summary
    <2-3 paragraphs. Every factual claim gets [N]. Standalone value.>

    ## Detailed Findings
    ### <Topic Section 1>
    <Organized by topic. Inline citations throughout.>

    ## Pricing & Cost Analysis
    <Only if pricing data was gathered. Tables for comparisons.>

    ## Code Examples & Repositories
    <Only if GitHub findings were present.>

    ## Recommendations
    <3-5 actionable, concrete recommendations.>

    ## Gaps & Limitations
    <What could NOT be found, plus any WEAK/MISSING source notes. Suggest follow-ups.>

    ## References
    [1] [Title](https://url)
    [2] [Title — Blog Name (YYYY-MM-DD)](https://url)
    ```

    ## Output budget

    Target 2,500-6,000 words. Hard ceiling: ~7,500 words (Palmyra X5 max
    output is 8,192 tokens). If approaching the ceiling, tighten prose
    before dropping content.

    Produce ONLY the report markdown. No preamble, no explanation, no
    trailing commentary.
    """)


USER_TEMPLATE = textwrap.dedent("""\
    Produce the research report for the following session.

    **Original query**: {query}
    **Detected intents**: {intents}
    **Today's date**: {today}

    ## Findings-file status (from parent)

    {status_block}

    ---

    ## Research contract

    ```markdown
    {contract}
    ```

    ---

    {findings_block}

    ---

    Now write the report following the schema in the system prompt.
    """)


# --- I/O helpers -----------------------------------------------------------


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return ""


def discover_findings(work_dir: Path, explicit: list[str] | None = None) -> list[Path]:
    """Return the list of findings files to ingest.

    Excludes research-contract.md and any *-report*.md to avoid self-reference.
    If `explicit` is provided, uses that list instead of autodiscovery.
    """
    if explicit:
        return [work_dir / name for name in explicit]
    out: list[Path] = []
    for p in sorted(work_dir.glob("*.md")):
        name = p.name.lower()
        if name == "research-contract.md":
            continue
        if "-report" in name:
            continue
        out.append(p)
    return out


def classify_file(path: Path, min_bytes: int = 500) -> str:
    if not path.exists():
        return "MISSING"
    size = path.stat().st_size
    if size < min_bytes:
        return "WEAK"
    return "OK"


# --- Bedrock call ----------------------------------------------------------


def call_palmyra(
    system_prompt: str,
    user_message: str,
    *,
    model_id: str,
    region: str,
    profile: str,
    max_output_tokens: int,
    temperature: float,
) -> tuple[str, dict[str, Any]]:
    """Invoke Palmyra X5 via the Bedrock Converse API. Returns (text, usage_dict)."""
    session = boto3.Session(profile_name=profile, region_name=region)
    cfg = Config(
        retries={"max_attempts": 3, "mode": "standard"},
        read_timeout=180,  # long contexts take tens of seconds
        connect_timeout=10,
    )
    brt = session.client("bedrock-runtime", config=cfg)

    resp = brt.converse(
        modelId=model_id,
        system=[{"text": system_prompt}],
        messages=[{"role": "user", "content": [{"text": user_message}]}],
        inferenceConfig={
            "maxTokens": max_output_tokens,
            "temperature": temperature,
            # Note: omit topP. Anthropic Bedrock rejects sending both temperature
            # and topP in the same request; relying on temperature alone is
            # portable across Palmyra and Claude.
        },
    )

    # Extract text. Converse returns a list of content blocks.
    blocks = resp.get("output", {}).get("message", {}).get("content", []) or []
    text = "\n".join(b.get("text", "") for b in blocks if "text" in b).strip()
    usage = resp.get("usage", {}) or {}
    stop_reason = resp.get("stopReason", "unknown")
    usage["stopReason"] = stop_reason
    return text, usage


# --- Main ------------------------------------------------------------------


def build_prompt(
    work_dir: Path,
    query: str,
    intents: str,
    findings: list[Path],
) -> tuple[str, list[tuple[Path, str, int]]]:
    """Assembles the user message. Also returns per-file status tuples."""
    contract_path = work_dir / "research-contract.md"
    contract = read_text(contract_path) if contract_path.exists() else "(no research contract on disk)"

    status_lines = []
    findings_chunks = []
    per_file: list[tuple[Path, str, int]] = []

    for fp in findings:
        status = classify_file(fp)
        size = fp.stat().st_size if fp.exists() else 0
        per_file.append((fp, status, size))
        status_lines.append(f"- `{fp.name}` — **{status}** ({size} bytes)")
        if status == "OK":
            body = read_text(fp)
            findings_chunks.append(f"## Findings from `{fp.name}`\n\n{body}")
        elif status == "WEAK":
            body = read_text(fp)
            findings_chunks.append(
                f"## Findings from `{fp.name}` (WEAK — low content, treat as low-signal)\n\n{body}"
            )
        # MISSING → skip content; still listed in status block

    today = time.strftime("%Y-%m-%d")
    user = USER_TEMPLATE.format(
        query=query,
        intents=intents or "(not provided)",
        today=today,
        status_block="\n".join(status_lines) if status_lines else "(none)",
        contract=contract.strip(),
        findings_block="\n\n---\n\n".join(findings_chunks) if findings_chunks else "(no findings content available)",
    )
    return user, per_file


def estimate_tokens(text: str) -> int:
    return int(len(text) / CHARS_PER_TOKEN)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    ap.add_argument("--work-dir", required=True, type=Path,
                    help="Session work dir, e.g. $WORK_DIR/<slug>/")
    ap.add_argument("--report-path", required=True, type=Path,
                    help="Where to write the generated report markdown")
    ap.add_argument("--query", required=True, help="Original user query")
    ap.add_argument("--intents", default="", help="Comma-separated intent list")
    ap.add_argument("--findings", nargs="*", default=None,
                    help="Explicit findings filenames (auto-discover if omitted)")
    ap.add_argument("--model-id", default=DEFAULT_MODEL_ID)
    ap.add_argument("--region", default=DEFAULT_REGION)
    ap.add_argument("--profile", default=DEFAULT_PROFILE)
    ap.add_argument("--max-output-tokens", type=int, default=PALMYRA_OUTPUT_CAP_TOKENS)
    ap.add_argument("--temperature", type=float, default=0.3,
                    help="Lower = more faithful synthesis. Default 0.3.")
    ap.add_argument("--dry-run", action="store_true",
                    help="Build and print the prompt; do not call Bedrock")
    args = ap.parse_args()

    work_dir = args.work_dir.expanduser().resolve()
    if not work_dir.is_dir():
        print(f"ERROR: work dir not found: {work_dir}", file=sys.stderr)
        return 2

    findings = discover_findings(work_dir, args.findings)
    if not findings:
        print(f"ERROR: no findings files found under {work_dir}", file=sys.stderr)
        return 2

    user_msg, per_file = build_prompt(work_dir, args.query, args.intents, findings)
    input_tokens_est = estimate_tokens(SYSTEM_PROMPT) + estimate_tokens(user_msg)

    if input_tokens_est > PALMYRA_INPUT_CAP_TOKENS:
        print(f"ERROR: estimated {input_tokens_est} input tokens exceeds "
              f"Palmyra X5 cap ({PALMYRA_INPUT_CAP_TOKENS})", file=sys.stderr)
        return 2

    if args.dry_run:
        print(f"DRY RUN — would call {args.model_id} @ {args.region}")
        print(f"Estimated input tokens: {input_tokens_est:,}")
        print(f"Max output tokens:      {args.max_output_tokens:,}")
        print(f"Findings files:")
        for fp, status, size in per_file:
            print(f"  {status:7s} {size:>8} B  {fp.name}")
        print("\n--- USER MESSAGE HEAD ---")
        print(user_msg[:2000])
        print(f"... (+{len(user_msg)-2000} chars)")
        return 0

    t0 = time.time()
    try:
        text, usage = call_palmyra(
            SYSTEM_PROMPT,
            user_msg,
            model_id=args.model_id,
            region=args.region,
            profile=args.profile,
            max_output_tokens=args.max_output_tokens,
            temperature=args.temperature,
        )
    except ClientError as e:
        print(f"❌ Failed: Bedrock ClientError: {e.response.get('Error', {}).get('Code')} "
              f"— {e.response.get('Error', {}).get('Message')}", file=sys.stderr)
        return 3
    except Exception as e:
        print(f"❌ Failed: {type(e).__name__}: {e}", file=sys.stderr)
        return 3

    elapsed = time.time() - t0
    args.report_path.parent.mkdir(parents=True, exist_ok=True)
    args.report_path.write_text(text, encoding="utf-8")

    in_tokens = usage.get("inputTokens", 0)
    out_tokens = usage.get("outputTokens", 0)
    cost = (in_tokens / 1_000_000) * PRICE_INPUT_PER_1M + \
           (out_tokens / 1_000_000) * PRICE_OUTPUT_PER_1M

    # Citation count — crude but useful
    citations = sum(1 for _ in __import__("re").finditer(r"\[\d+\]", text))

    print(f"✅ Wrote report to {args.report_path} "
          f"({len(text)} chars, {citations} citation markers)")
    print(f"   model={args.model_id} region={args.region} "
          f"stop={usage.get('stopReason')} elapsed={elapsed:.1f}s "
          f"tokens_in={in_tokens} tokens_out={out_tokens} cost≈${cost:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
