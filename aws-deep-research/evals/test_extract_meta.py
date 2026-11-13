"""extract_behavior_meta.py: only researcher findings files feed retrieved_urls."""

from __future__ import annotations

import pytest

from extract_behavior_meta import is_findings_name


@pytest.mark.parametrize("name", [
    "aws-docs.md", "aws-pricing.md", "web-content.md", "web-content-coding.md",
    "agentcore.md", "github-repos.md", "direct-fetch.md",
])
def test_findings_files_count(name: str) -> None:
    assert is_findings_name(name)


@pytest.mark.parametrize("name", [
    "brief-agentcore.md", "brief-aws-docs.md", "plan.md", "research-contract.md",
    "x-report.md", "aws-docs.md.bak",
])
def test_parent_authored_files_do_not_count(name: str) -> None:
    assert not is_findings_name(name)
