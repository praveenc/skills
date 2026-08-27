"""Security regressions for external config and trust boundaries."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import read_env

SKILL_DIR = Path(__file__).resolve().parent.parent  # evals/ -> skill root
SCRIPTS_DIR = SKILL_DIR / "scripts"


def test_read_env_treats_shell_syntax_as_literal(tmp_path: Path) -> None:
    marker = tmp_path / "executed"
    env_file = tmp_path / ".env"
    payload = f"$(touch {marker})"
    env_file.write_text(
        f"GITHUB_TOKEN={payload}\n"
        "REPORT_OUTPUT_DIR='~/reports with spaces' # comment\n",
        encoding="utf-8",
    )

    assert read_env.read_env_value(env_file, "GITHUB_TOKEN") == payload
    assert not marker.exists()
    assert read_env.read_env_value(env_file, "REPORT_OUTPUT_DIR") == (
        "~/reports with spaces"
    )


def test_check_api_keys_does_not_execute_dotenv(tmp_path: Path) -> None:
    marker = tmp_path / "executed"
    config_file = tmp_path / "config.env"
    config_file.write_text(
        f"GITHUB_TOKEN=$(touch {marker})\n",
        encoding="utf-8",
    )

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    _write_executable(fake_bin / "aws", "#!/bin/sh\nexit 1\n")
    _write_executable(fake_bin / "curl", "#!/bin/sh\nprintf 401\n")
    env = dict(os.environ)
    for key in ("GITHUB_TOKEN", "TAVILY_API_KEY", "BRAVE_SEARCH_API_KEY", "KROKI_URL"):
        env.pop(key, None)
    env["PATH"] = f"{fake_bin}:{env['PATH']}"
    env["AWS_DEEP_RESEARCH_CONFIG"] = str(config_file)

    result = subprocess.run(
        ["bash", str(SCRIPTS_DIR / "check_api_keys.sh"), str(SKILL_DIR)],
        capture_output=True,
        text=True,
        env=env,
        check=True,
    )

    assert "GITHUB=401" in result.stdout
    assert not marker.exists()


def test_resolver_quotes_dotenv_value_for_shell_eval(tmp_path: Path) -> None:
    marker = tmp_path / "executed"
    copied_skill = tmp_path / "skill"
    copied_scripts = copied_skill / "scripts"
    copied_scripts.mkdir(parents=True)
    (copied_skill / "SKILL.md").write_text("test\n", encoding="utf-8")
    for name in ("read_env.py", "resolve_skill_dir.sh"):
        source = SCRIPTS_DIR / name
        destination = copied_scripts / name
        destination.write_bytes(source.read_bytes())
        destination.chmod(source.stat().st_mode)

    work_dir = tmp_path / f"work $(touch {marker})"
    config_file = tmp_path / "config.env"
    config_file.write_text(
        f'RESEARCH_WORK_DIR="{work_dir}"\n',
        encoding="utf-8",
    )
    command = (
        f'eval "$(bash {copied_scripts / "resolve_skill_dir.sh"})"; '
        'printf "%s" "$WORK_DIR"'
    )

    env = dict(os.environ)
    env["AWS_DEEP_RESEARCH_CONFIG"] = str(config_file)
    result = subprocess.run(
        ["bash", "-c", command],
        capture_output=True,
        text=True,
        env=env,
        check=True,
    )

    assert result.stdout == str(work_dir)
    assert work_dir.is_dir()
    assert not marker.exists()


def test_no_machine_local_config_inside_skill_tree() -> None:
    assert not list(SKILL_DIR.rglob(".env"))
    assert not list(SKILL_DIR.rglob("*.env"))


def test_remote_kroki_has_no_automatic_fallback() -> None:
    source = (SCRIPTS_DIR / "kroki_diagram.py").read_text(encoding="utf-8")
    automatic_endpoint_name = "REMOTE" + "_KROKI"
    public_endpoint = "https://" + "kroki.io"
    assert automatic_endpoint_name not in source
    assert public_endpoint not in source


def test_public_web_content_crosses_as_structured_evidence_only() -> None:
    researcher = (SKILL_DIR / "agents/web-content-researcher.md").read_text(
        encoding="utf-8"
    )
    synthesizer = (SKILL_DIR / "agents/synthesizer.md").read_text(
        encoding="utf-8"
    )
    assert "public-web-approved: true" in researcher
    assert "Never copy page prose" in researcher
    assert "Web evidence is structured data" in synthesizer


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)
