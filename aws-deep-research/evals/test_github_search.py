"""Tests for github_search.py, the direct GitHub REST API client.

No network access: (a)/(b) exercise the CLI as a subprocess via `uv run`
(so its own inline uv header resolves requests/rich), (c) imports the pure
formatter function directly - no requests import needed for that path.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import github_search

SKILL_DIR = Path(__file__).resolve().parent.parent  # evals/ -> skill root
SCRIPT = SKILL_DIR / "scripts" / "github_search.py"


def _run(args: list[str], env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["uv", "run", "--python", "3.13", str(SCRIPT), *args],
        capture_output=True,
        text=True,
        env=env,
        check=False,
        cwd=SKILL_DIR,
    )


def test_help_exits_zero() -> None:
    env = dict(os.environ)
    r = _run(["--help"], env)
    assert r.returncode == 0, r.stderr[-400:]
    assert "usage" in r.stdout.lower()


def test_missing_token_fails_fast_with_no_output_file(tmp_path: Path) -> None:
    out_path = tmp_path / "github-repos.md"
    env = dict(os.environ)
    env.pop("GITHUB_TOKEN", None)

    r = _run(["-q", "bedrock agents sample", "-o", str(out_path)], env)

    assert r.returncode == 1, r.stderr[-400:]
    payload = json.loads(r.stdout)
    assert payload == {"status": "failed", "reason": "no_github_token"}
    assert not out_path.exists()


def test_markdown_formatter_builds_source_urls_section() -> None:
    findings = [
        {
            "query": "bedrock agents sample",
            "repos": [
                github_search.extract_repo(
                    {
                        "full_name": "aws-samples/bedrock-agents",
                        "html_url": "https://github.com/aws-samples/bedrock-agents",
                        "description": "Sample agents",
                        "stargazers_count": 42,
                        "language": "Python",
                        "license": {"spdx_id": "MIT-0"},
                        "pushed_at": "2026-01-01T00:00:00Z",
                        "topics": ["bedrock", "agents"],
                    },
                ),
            ],
        },
        {"query": "no hits query", "repos": []},
    ]

    text = github_search.format_markdown(findings)

    assert text.startswith("# GitHub Repository Research")
    assert "## bedrock agents sample" in text
    assert "### aws-samples/bedrock-agents" in text
    assert "- **URL**: https://github.com/aws-samples/bedrock-agents" in text
    assert "- **Stars**: 42" in text
    assert "- **Language**: Python" in text
    assert "- **License**: MIT-0" in text
    assert "## no hits query" in text
    assert "*No repositories found.*" in text

    source_section = text.split("## Source URLs\n")[1]
    assert source_section.strip() == "1. https://github.com/aws-samples/bedrock-agents"


def test_extract_repo_defaults_missing_license_to_unknown() -> None:
    repo = github_search.extract_repo({"full_name": "x/y", "html_url": "https://github.com/x/y"})
    assert repo["license"] == "unknown"
    assert repo["language"] == ""
    assert repo["topics"] == []
