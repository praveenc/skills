"""Tests for the persistent web-search budget tracker in common.py.

Run: uv run --python 3.13 --with pytest python -m pytest evals/test_budget.py -q
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import common


@pytest.fixture
def budget_path(tmp_path: Path) -> Path:
    return tmp_path / "budget.json"


def test_record_and_get_usage(budget_path: Path) -> None:
    assert common.get_usage("brave", path=budget_path) == 0
    assert common.record_search("brave", path=budget_path) == 1
    assert common.record_search("brave", path=budget_path) == 2
    assert common.get_usage("brave", path=budget_path) == 2


def test_record_count_multiple_credits(budget_path: Path) -> None:
    # Tavily advanced searches cost 2 credits.
    assert common.record_search("tavily", count=2, path=budget_path) == 2
    assert common.record_search("tavily", count=2, path=budget_path) == 4
    assert common.get_usage("tavily", path=budget_path) == 4


def test_engines_are_independent(budget_path: Path) -> None:
    common.record_search("brave", count=3, path=budget_path)
    common.record_search("tavily", count=5, path=budget_path)
    assert common.get_usage("brave", path=budget_path) == 3
    assert common.get_usage("tavily", path=budget_path) == 5


def test_engine_name_is_case_insensitive(budget_path: Path) -> None:
    common.record_search("BRAVE", path=budget_path)
    assert common.get_usage("brave", path=budget_path) == 1
    assert common.get_usage("Brave", path=budget_path) == 1


def test_budget_status_shape_and_over_80(budget_path: Path) -> None:
    # 1600 / 2000 = 80% -> trips the wire.
    common.record_search("brave", count=1600, path=budget_path)
    status = common.budget_status("brave", path=budget_path)
    assert status["engine"] == "brave"
    assert status["used"] == 1600
    assert status["cap"] == 2000
    assert status["remaining"] == 400
    assert status["pct_used"] == 80.0
    assert status["over_80"] is True


def test_budget_status_under_80(budget_path: Path) -> None:
    common.record_search("brave", count=100, path=budget_path)
    status = common.budget_status("brave", path=budget_path)
    assert status["over_80"] is False
    assert status["pct_used"] == 5.0
    assert status["remaining"] == 1900


def test_budget_status_custom_cap(budget_path: Path) -> None:
    common.record_search("brave", count=90, path=budget_path)
    status = common.budget_status("brave", cap=100, path=budget_path)
    assert status["cap"] == 100
    assert status["remaining"] == 10
    assert status["over_80"] is True


def test_stale_month_pruned_on_write(budget_path: Path) -> None:
    # Seed a stale month by hand; a new record for the current month should
    # drop the stale entry entirely (file stays small).
    budget_path.write_text(
        json.dumps({"brave": {"2000-01": 999}}), encoding="utf-8"
    )
    common.record_search("brave", path=budget_path)
    data = json.loads(budget_path.read_text(encoding="utf-8"))
    assert list(data["brave"].keys()) == [common._current_month()]
    assert data["brave"][common._current_month()] == 1


def test_corrupt_file_is_tolerated(budget_path: Path) -> None:
    budget_path.write_text("not json {{{", encoding="utf-8")
    # Should not raise; treats corrupt file as empty and overwrites.
    assert common.record_search("brave", path=budget_path) == 1
    assert common.get_usage("brave", path=budget_path) == 1


def test_missing_file_returns_zero(budget_path: Path) -> None:
    assert common.get_usage("brave", path=budget_path) == 0
    status = common.budget_status("brave", path=budget_path)
    assert status["used"] == 0
    assert status["over_80"] is False


def test_unknown_engine_has_no_cap(budget_path: Path) -> None:
    common.record_search("kagi", count=10, path=budget_path)
    status = common.budget_status("kagi", path=budget_path)
    assert status["used"] == 10
    assert status["cap"] is None
    assert status["remaining"] is None
    assert status["over_80"] is False
