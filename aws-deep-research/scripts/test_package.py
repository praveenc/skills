"""Structural, parity, and hygiene gate for the aws-deep-research package.

Model-free. This is the meta-eval the audit asked for: it proves the package
and its eval corpora are internally consistent and shippable, not that the
skill produces good research. Runs in CI on every change.

Covers audit findings F1 (stale agent names in eval data), F9 (SKILL / README /
setup drift), and F10 (publish hygiene - never reads .env contents).
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest

SKILL_DIR = Path(__file__).resolve().parent.parent
SKILL_MD = SKILL_DIR / "SKILL.md"
README = SKILL_DIR / "README.md"
AGENTS_DIR = SKILL_DIR / "agents"
EVALS_DIR = SKILL_DIR / "evals"
KIRO_AGENT = SKILL_DIR / "setup" / "kiro-agent.json"

# Agent-Skills spec limits.
MAX_NAME = 64
MAX_DESCRIPTION = 1024
# Body-size guidance from the skill best-practices note.
MAX_BODY_TOKENS = 5000

MD_LINK = re.compile(r"\[[^\]]*\]\((?!https?://|#|mailto:)([^)#]+)(?:#[^)]*)?\)")
# Agent names are the concrete set on disk, matched as whole words. A pattern
# like `\S+-researcher` also matches prose such as "a 4-researcher round".
AGENT_NAMES = frozenset({
    "aws-mcp-researcher", "web-content-researcher", "agentcore-researcher",
    "github-researcher", "diagram-generator", "synthesizer",
})
AGENT_NAME = re.compile(r"\b(" + "|".join(sorted(AGENT_NAMES, key=len, reverse=True)) + r")\b")
# Link targets that are runtime placeholders or format templates, not real paths.
PLACEHOLDER_LINK = re.compile(r"[<>$]|^url$|^path$")


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def frontmatter(path: Path) -> str:
    text = read(path)
    assert text.startswith("---\n"), f"{path} has no YAML frontmatter"
    return text.split("---", 2)[1]


def folded_field(fm: str, key: str) -> str:
    """Read a YAML folded (`key: >`) scalar as one collapsed line."""
    m = re.search(rf"^{key}: >\n((?:  .*\n)+)", fm, re.MULTILINE)
    if not m:
        m = re.search(rf"^{key}:\s*(.+)$", fm, re.MULTILINE)
        return m.group(1).strip() if m else ""
    return " ".join(line.strip() for line in m.group(1).splitlines())


def agent_names() -> set[str]:
    return {p.stem for p in AGENTS_DIR.glob("*.md")}


def eval_json_files() -> list[Path]:
    return sorted(p for p in EVALS_DIR.glob("*.json"))


def markdown_files() -> list[Path]:
    return [SKILL_MD, README, *sorted((SKILL_DIR / "references").glob("*.md")),
            *sorted(AGENTS_DIR.glob("*.md"))]


# --------------------------------------------------------------------------
# Frontmatter conformance
# --------------------------------------------------------------------------


def test_skill_name_matches_directory() -> None:
    fm = frontmatter(SKILL_MD)
    name = re.search(r"^name:\s*(\S+)", fm, re.MULTILINE).group(1)
    assert name == SKILL_DIR.name
    assert len(name) <= MAX_NAME


def test_description_within_spec_limit() -> None:
    desc = folded_field(frontmatter(SKILL_MD), "description")
    assert desc, "description is required"
    assert len(desc) <= MAX_DESCRIPTION, f"description is {len(desc)} chars"


def test_description_declares_both_positive_and_negative_triggers() -> None:
    """A description without an exclusion clause cannot bound over-triggering."""
    desc = folded_field(frontmatter(SKILL_MD), "description").lower()
    assert "activates when" in desc or "triggers include" in desc
    assert "does not activate" in desc


def test_description_scope_matches_readme_scope() -> None:
    """F8: AWS-first WITH explicit generic support - all three must agree."""
    desc = folded_field(frontmatter(SKILL_MD), "description").lower()
    body = read(SKILL_MD).lower()
    readme = read(README).lower()
    assert "generic" in desc, "frontmatter must declare generic-topic support"
    assert "generic" in body, "Step 1b classifies aws vs generic"
    assert "generic" in readme


def test_compatibility_field_present() -> None:
    assert folded_field(frontmatter(SKILL_MD), "compatibility")


def test_body_within_token_budget() -> None:
    body = read(SKILL_MD).split("---", 2)[2]
    tokens = len(body) // 4
    assert tokens <= MAX_BODY_TOKENS, f"body is ~{tokens} tokens"


# --------------------------------------------------------------------------
# Reference integrity
# --------------------------------------------------------------------------


@pytest.mark.parametrize("md", markdown_files(), ids=lambda p: str(p.relative_to(SKILL_DIR)))
def test_relative_markdown_links_resolve(md: Path) -> None:
    targets = [t for t in MD_LINK.findall(read(md)) if not PLACEHOLDER_LINK.search(t)]
    broken = [t for t in targets if not (md.parent / t).exists()]
    assert not broken, f"{md.relative_to(SKILL_DIR)} has broken links: {broken}"


def test_no_empty_anchor_text() -> None:
    """`[\\](path)` renders as an invisible link - a past regression here."""
    offenders = [str(md.relative_to(SKILL_DIR)) for md in markdown_files()
                 if re.search(r"\[\\?\]\(", read(md))]
    assert not offenders


def test_every_agent_md_has_a_matching_json() -> None:
    md = agent_names()
    js = {p.stem for p in AGENTS_DIR.glob("*.json")}
    assert md == js, f"agents/ md-vs-json mismatch: {md ^ js}"


def test_agent_json_name_matches_filename() -> None:
    for p in sorted(AGENTS_DIR.glob("*.json")):
        assert json.loads(read(p)).get("name") == p.stem


def test_agent_names_on_disk_match_the_declared_set() -> None:
    """Keeps the parity regex honest when an agent is added or renamed."""
    assert agent_names() == set(AGENT_NAMES), agent_names() ^ set(AGENT_NAMES)


def test_skill_md_subagent_table_matches_agents_dir() -> None:
    body = read(SKILL_MD)
    referenced = {n for n in AGENT_NAME.findall(body)}
    assert agent_names() <= referenced, f"agents/ not documented: {agent_names() - referenced}"


# --------------------------------------------------------------------------
# Eval corpus structure (F1: a stale oracle passes regressions)
# --------------------------------------------------------------------------


def test_eval_corpora_exist() -> None:
    names = {p.name for p in eval_json_files()}
    assert {"routing.json", "behavior.json", "faults.json"} <= names, names


@pytest.mark.parametrize("path", eval_json_files(), ids=lambda p: p.name)
def test_eval_json_parses(path: Path) -> None:
    json.loads(read(path))


@pytest.mark.parametrize("path", eval_json_files(), ids=lambda p: p.name)
def test_eval_agent_names_exist(path: Path) -> None:
    cited = set(AGENT_NAME.findall(read(path)))
    stale = cited - agent_names()
    assert not stale, f"{path.name} references non-existent agents: {stale}"


@pytest.mark.parametrize("path", eval_json_files(), ids=lambda p: p.name)
def test_eval_case_ids_are_unique(path: Path) -> None:
    data = json.loads(read(path))
    cases = data.get("cases", data.get("evals", []))
    if not isinstance(cases, list):
        pytest.skip(f"{path.name} is not a case corpus")
    ids = [c["id"] for c in cases if isinstance(c, dict) and "id" in c]
    assert len(ids) == len(set(ids)), f"{path.name} has duplicate case ids"


def test_routing_corpus_is_balanced_and_split() -> None:
    """A one-sided routing corpus measures nothing about the scope boundary."""
    cases = json.loads(read(EVALS_DIR / "routing.json"))["cases"]
    pos = [c for c in cases if c["should_trigger"]]
    neg = [c for c in cases if not c["should_trigger"]]
    assert len(cases) >= 20, f"only {len(cases)} routing cases"
    assert len(pos) >= 8 and len(neg) >= 8, f"{len(pos)} positive / {len(neg)} negative"
    splits = {c["split"] for c in cases}
    assert splits == {"train", "validation"}, splits
    # Both classes must appear in both splits, or the split is not stratified.
    for split in splits:
        in_split = [c for c in cases if c["split"] == split]
        assert any(c["should_trigger"] for c in in_split)
        assert any(not c["should_trigger"] for c in in_split)


def test_behavior_cases_have_machine_checks() -> None:
    """Prose expectations are documentation; `checks` are the gate."""
    cases = json.loads(read(EVALS_DIR / "behavior.json"))["cases"]
    for c in cases:
        assert c.get("checks"), f"behavior case {c['id']} has no machine checks"


def test_behavior_corpus_covers_every_strategy() -> None:
    cases = json.loads(read(EVALS_DIR / "behavior.json"))["cases"]
    covered = {s for c in cases for s in [c.get("strategy")] if s}
    assert {"feed-only", "docs-only", "pricing-focused", "comprehensive"} <= covered, covered


def test_synthesis_rubric_dimensions_declare_hard_or_soft() -> None:
    """F4: a rubric that cannot gate is advice, not a release control."""
    rubric = json.loads(read(EVALS_DIR / "synthesis-rubric.json"))
    for dim in rubric["dimensions"]:
        assert dim.get("gate") in {"hard", "soft"}, f"{dim['id']} has no gate class"
    hard = [d for d in rubric["dimensions"] if d["gate"] == "hard"]
    assert hard, "at least one dimension must be mechanically gating"


def test_synthesis_fixture_slugs_are_valid() -> None:
    """Fixture slugs must satisfy the same rules the skill enforces at runtime."""
    rubric = json.loads(read(EVALS_DIR / "synthesis-rubric.json"))
    for fixture in rubric["regression_fixtures"]:
        slug = fixture["slug"]
        assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", slug), slug
        assert 30 <= len(slug) <= 60, f"{slug} is {len(slug)} chars"
        assert 4 <= len(slug.split("-")) <= 8, f"{slug} has {len(slug.split('-'))} tokens"


# --------------------------------------------------------------------------
# SKILL / README / setup parity (F9)
# --------------------------------------------------------------------------


def test_kiro_setup_prefers_the_documented_dispatch_path() -> None:
    """platform-dispatch.md makes the generic inline-role path preferred."""
    prompt = json.loads(read(KIRO_AGENT))["prompt"]
    dispatch_ref = read(SKILL_DIR / "references" / "platform-dispatch.md")
    assert "PREFERRED" in dispatch_ref
    assert "generic path" in prompt.lower(), "setup must point at the generic path"
    assert not re.search(r"prefer\s+passing\s+`?agent_name", prompt, re.IGNORECASE), \
        "setup still prefers the named-agent path; platform-dispatch.md prefers generic"


def test_setup_step_references_exist_in_skill_md() -> None:
    """A setup prompt citing a step number that no longer exists misroutes."""
    prompt = json.loads(read(KIRO_AGENT))["prompt"]
    body = read(SKILL_MD)
    declared = set(re.findall(r"^##\s+(Step [0-9]+[a-z]?)", body, re.MULTILINE))
    cited = set(re.findall(r"\bStep [0-9]+[a-z]?", prompt))
    assert cited <= declared, f"setup cites missing steps: {sorted(cited - declared)}"


def test_setup_agent_names_match_agents_dir() -> None:
    cited = set(AGENT_NAME.findall(read(KIRO_AGENT)))
    assert not cited - agent_names(), f"setup names missing agents: {cited - agent_names()}"


def test_work_and_report_paths_agree_across_docs() -> None:
    """Paths appear as `~/...` in prose and `$HOME/...` in shell - accept both."""
    for suffix in (".aws-deep-research/work", ".aws-deep-research/outputs"):
        for path in (SKILL_MD, README, KIRO_AGENT):
            text = read(path)
            assert f"~/{suffix}" in text or f"$HOME/{suffix}" in text, \
                f"{path.name} does not document {suffix}"


def test_size_gate_threshold_is_consistent_everywhere() -> None:
    """500 bytes is quoted in several places - drift makes the gate a lie."""
    for path in (SKILL_MD, KIRO_AGENT, AGENTS_DIR / "synthesizer.md"):
        assert "500" in read(path), f"{path.name} lost the 500-byte threshold"
    assert "MIN_BYTES=500" in read(SKILL_DIR / "scripts" / "verify_findings.sh")


# --------------------------------------------------------------------------
# Publish hygiene (F10) - never reads secret file contents
# --------------------------------------------------------------------------


def tracked_files() -> list[str]:
    r = subprocess.run(
        ["git", "ls-files"], cwd=SKILL_DIR, capture_output=True, text=True, check=False
    )
    if r.returncode != 0:
        pytest.skip("not a git checkout")
    return [line for line in r.stdout.splitlines() if line]


FORBIDDEN = re.compile(
    r"(^|/)\.env$|(^|/)\.env\.[^/]*$|(^|/)\.DS_Store$|__pycache__/|\.py[co]$"
    r"|(^|/)\.pytest_cache/|(^|/)\.ruff_cache/|(^|/)id_rsa|\.pem$|(^|/)credentials$",
)


def test_no_secret_or_residue_file_is_tracked() -> None:
    """Rejects by PATH only - the gate must never read a candidate secret."""
    offenders = [f for f in tracked_files()
                 if FORBIDDEN.search(f) and not f.endswith((".env.example", ".env.template"))]
    assert not offenders, f"tracked files that must never ship: {offenders}"


def test_no_generated_report_is_tracked() -> None:
    offenders = [f for f in tracked_files() if f.endswith("-report.md") or f.endswith(".eval.md")]
    assert not offenders, f"generated reports must not be tracked: {offenders}"


def test_gitignore_covers_secrets_and_caches() -> None:
    ignored = read(SKILL_DIR / ".gitignore")
    for pattern in (".env", "__pycache__", ".DS_Store"):
        assert pattern in ignored, f".gitignore does not cover {pattern}"


def test_every_script_is_executable_or_a_module() -> None:
    """A shipped CLI that is not executable fails on first use."""
    for p in sorted((SKILL_DIR / "scripts").glob("*.sh")):
        assert p.stat().st_mode & 0o111, f"{p.name} is not executable"


@pytest.mark.parametrize(
    "script",
    sorted(p.name for p in (SKILL_DIR / "scripts").glob("*.py")
           if not p.name.startswith("test_") and p.name not in {"common.py", "read_env.py"}),
)
def test_python_clis_support_help(script: str) -> None:
    r = subprocess.run(
        ["uv", "run", "--python", "3.13", str(SKILL_DIR / "scripts" / script), "--help"],
        capture_output=True, text=True, check=False, cwd=SKILL_DIR,
    )
    assert r.returncode == 0, f"{script} --help exited {r.returncode}: {r.stderr[-400:]}"
    assert "usage" in r.stdout.lower()
