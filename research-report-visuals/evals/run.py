#!/usr/bin/env python3
"""Eval runner for research-report-visuals.

The suites stay separate:

  routing  - metadata-only semantic routing
  native   - actual harness selection and SKILL.md load evidence
  behavior - forced-load HTML output quality

Agent runs generate evidence. This script grades it deterministically, reports
matched-arm deltas, and emits JSON, Markdown, or JUnit when requested.
"""

from __future__ import annotations

import argparse
import hashlib
from html.parser import HTMLParser
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUTDIR = HERE / "outputs"
TARGET_SKILL = "research-report-visuals"
SUITES = {
    "routing": "routing.json",
    "native": "native.json",
    "behavior": "behavior.json",
}
BEHAVIOR_CHECK_TYPES = {
    "regex",
    "absent",
    "absent_regex",
    "count_regex",
    "max_bytes",
    "max_visible_words",
    "max_sentence_words",
    "html_structure",
    "contains_source_urls",
    "contains_content_literals",
    "min_visible_words",
    "details_min_words",
    "trace_no_network",
    "trace_writes_within_trial",
    "trace_forbidden_actions",
    "judge",
}

GREEN, YELLOW, RED, DIM, BOLD, RESET = (
    "\033[32m", "\033[33m", "\033[31m", "\033[2m", "\033[1m", "\033[0m"
)


def _flags(spec: dict) -> int:
    flags = 0
    if "i" in (spec.get("flags") or ""):
        flags |= re.IGNORECASE
    if "s" in (spec.get("flags") or ""):
        flags |= re.DOTALL
    return flags


class _VisibleTextParser(HTMLParser):
    """Collect primary visible text and omit implementation and closed detail."""

    _SKIP = {"head", "style", "script", "svg", "pre", "code", "template"}
    _BLOCK = {
        "article", "aside", "blockquote", "div", "figcaption", "footer",
        "h1", "h2", "h3", "h4", "h5", "h6", "header", "li", "main",
        "p", "section", "summary", "td", "th",
    }

    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self._closed_details = 0
        self._details_stack: list[bool] = []
        self._summary_depth = 0
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "details":
            is_open = any(name == "open" for name, _ in attrs)
            self._details_stack.append(is_open)
            if not is_open:
                self._closed_details += 1
        elif tag == "summary":
            self._summary_depth += 1
            self._parts.append("\n")
        elif tag in self._SKIP:
            self._skip_depth += 1
        elif self._is_visible() and tag in self._BLOCK:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag == "details":
            if self._details_stack and not self._details_stack.pop():
                self._closed_details = max(0, self._closed_details - 1)
        elif tag == "summary":
            self._parts.append("\n")
            self._summary_depth = max(0, self._summary_depth - 1)
        elif tag in self._SKIP:
            self._skip_depth = max(0, self._skip_depth - 1)
        elif self._is_visible() and tag in self._BLOCK:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._is_visible():
            self._parts.append(data)

    def _is_visible(self) -> bool:
        return not self._skip_depth and (
            self._closed_details == 0 or self._summary_depth > 0
        )

    def blocks(self) -> list[str]:
        text = "".join(self._parts)
        return [
            re.sub(r"\s+", " ", block).strip()
            for block in text.splitlines()
            if block.strip()
        ]


def _visible_blocks(html: str) -> list[str]:
    parser = _VisibleTextParser()
    parser.feed(html)
    return parser.blocks()


class _ContentTextParser(HTMLParser):
    """Collect meaningful body content, including code and closed details."""

    _SKIP = {"head", "style", "script", "svg", "template"}
    _VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input",
             "link", "meta", "param", "source", "track", "wbr"}

    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self._hidden_stack: list[bool] = []
        self._hidden_depth = 0
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        hidden = (
            "hidden" in attrs_dict
            or (attrs_dict.get("aria-hidden") or "").lower() == "true"
        )
        if tag in self._VOID:
            return
        self._hidden_stack.append(hidden)
        if hidden:
            self._hidden_depth += 1
        if tag in self._SKIP:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIP:
            self._skip_depth = max(0, self._skip_depth - 1)
        if self._hidden_stack and self._hidden_stack.pop():
            self._hidden_depth = max(0, self._hidden_depth - 1)

    def handle_data(self, data: str) -> None:
        if not self._skip_depth and not self._hidden_depth:
            self._parts.append(data)

    def text(self) -> str:
        return re.sub(r"\s+", " ", " ".join(self._parts)).strip()


class _LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.urls: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        href = dict(attrs).get("href")
        if href:
            self.urls.append(href)


class _DetailsParser(HTMLParser):
    """Count non-summary words in each details element."""

    _SKIP = {"style", "script", "svg", "template"}

    def __init__(self) -> None:
        super().__init__()
        self._details_depth = 0
        self._summary_depth = 0
        self._skip_depth = 0
        self._current: list[str] = []
        self.word_counts: list[int] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "details":
            if self._details_depth == 0:
                self._current = []
            self._details_depth += 1
        elif tag == "summary" and self._details_depth:
            self._summary_depth += 1
        elif tag in self._SKIP:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag == "summary":
            self._summary_depth = max(0, self._summary_depth - 1)
        elif tag in self._SKIP:
            self._skip_depth = max(0, self._skip_depth - 1)
        elif tag == "details" and self._details_depth:
            self._details_depth -= 1
            if self._details_depth == 0:
                self.word_counts.append(len(_words(" ".join(self._current))))

    def handle_data(self, data: str) -> None:
        if self._details_depth and not self._summary_depth and not self._skip_depth:
            self._current.append(data)


def _content_text(html: str) -> str:
    parser = _ContentTextParser()
    parser.feed(html)
    return parser.text()


def _source_urls(html: str) -> list[str]:
    parser = _LinkParser()
    parser.feed(html)
    return parser.urls


def _details_word_counts(html: str) -> list[int]:
    parser = _DetailsParser()
    parser.feed(html)
    return parser.word_counts


def _words(text: str) -> list[str]:
    return re.findall(r"\b[\w][\w'./+-]*\b", text, re.UNICODE)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def suite_digest(name: str) -> str:
    """Hash a suite and every repository input that changes its cases."""
    paths = [HERE / SUITES[name]]
    if name == "routing":
        return sha256_file(paths[0])
    if name == "behavior":
        suite = json.loads(paths[0].read_text(encoding="utf-8"))
        paths.extend(HERE / case["input"] for case in suite["cases"])
    elif name == "native":
        paths.append(HERE / SUITES["routing"])
    digest = hashlib.sha256()
    for path in sorted(paths, key=lambda item: str(item)):
        relative = str(path.relative_to(HERE)).encode("utf-8")
        digest.update(relative)
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def html_metrics(html: str | None) -> dict:
    if html is None:
        return {}
    blocks = _visible_blocks(html)
    longest = 0
    for block in blocks:
        for sentence in re.split(r"(?<=[.!?])\s+", block):
            longest = max(longest, len(_words(sentence)))
    return {
        "bytes": len(html.encode("utf-8")),
        "visible_words": sum(len(_words(block)) for block in blocks),
        "longest_sentence_words": longest,
    }


def html_structure_errors(html: str) -> list[str]:
    checks = [
        (r"(?is)^\s*<!doctype\s+html", "doctype"),
        (r"(?is)<html\b[^>]*\blang\s*=", "html lang"),
        (r"(?is)<title>\s*\S", "non-empty title"),
        (r"(?is)<meta\b[^>]*name\s*=\s*[\"']viewport[\"']", "viewport meta"),
        (r"(?is)<body\b", "body"),
        (r"(?is)<header\b", "header landmark"),
        (r"(?is)<main\b", "main landmark"),
        (r"(?is)<h1\b", "h1"),
        (r"(?is)<footer\b", "footer landmark"),
    ]
    return [label for pattern, label in checks if not re.search(pattern, html)]


class Evidence:
    """Files retained for one arm, case, and trial."""

    def __init__(self, trial_dir: Path) -> None:
        self.dir = trial_dir
        self.html = self._read("output.html")
        self.response = self._read("response.txt")
        self.trace = self._read("trace.jsonl")
        self.meta, self.meta_error = self._read_json("meta.json")

    def _read(self, name: str) -> str | None:
        try:
            return (self.dir / name).read_text(encoding="utf-8")
        except OSError:
            return None

    def _read_json(self, name: str) -> tuple[dict, str | None]:
        raw = self._read(name)
        if raw is None:
            return {}, None
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            return {}, f"{name} is invalid JSON: {exc}"
        if not isinstance(value, dict):
            return {}, f"{name} must contain a JSON object"
        return value, None

    @property
    def present(self) -> bool:
        return self.dir.is_dir() and (
            any(
                value is not None
                for value in (self.html, self.response, self.trace)
            ) or bool(self.meta)
        )


class FakeEvidence:
    """Small self-test evidence object."""

    def __init__(
        self,
        html: str | None = None,
        meta: dict | None = None,
        trace: str | None = None,
    ) -> None:
        self.html = html
        self.response = None
        self.trace = trace
        self.meta = meta or {}
        self.meta_error = None
        self.dir = Path("/nonexistent")

    @property
    def present(self) -> bool:
        return self.html is not None or bool(self.meta) or self.trace is not None


def trace_events(ev: Evidence | FakeEvidence) -> tuple[list[dict], str | None]:
    if ev.trace is None:
        return [], "no normalized trace.jsonl"
    events = []
    for number, line in enumerate(ev.trace.splitlines(), 1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            return [], f"trace.jsonl line {number} is invalid JSON: {exc}"
        if not isinstance(event, dict) or not isinstance(event.get("type"), str):
            return [], f"trace.jsonl line {number} needs an object with type"
        events.append(event)
    return events, None


def provenance_check(
    ev: Evidence | FakeEvidence,
    manifest: dict,
    suite: str,
    arm: str,
    case_id: str,
    trial: int,
) -> dict:
    if ev.meta_error:
        return {"type": "provenance", "status": "FAIL", "message": ev.meta_error}
    provenance = ev.meta.get("provenance")
    if not isinstance(provenance, dict):
        return {
            "type": "provenance",
            "status": "PENDING" if not ev.present else "FAIL",
            "message": "meta.json needs provenance{}",
        }
    corpus = manifest["corpus_revision"][suite]
    expected = {
        "run_id": manifest["run_id"],
        "arm": arm,
        "suite": suite,
        "case_id": case_id,
        "trial": trial,
        "model": manifest["model"],
        "harness": manifest["harness"],
        "permissions": manifest["permissions"],
        "catalog_revision": manifest["catalog_revision"],
        "corpus_digest": corpus,
        "skill_revision": manifest["arm_definitions"][arm]["skill_revision"],
    }
    mismatches = [
        f"{field}={provenance.get(field)!r}, expected {value!r}"
        for field, value in expected.items()
        if provenance.get(field) != value
    ]
    return {
        "type": "provenance",
        "status": "FAIL" if mismatches else "PASS",
        "message": "evidence provenance matches manifest" if not mismatches
        else "; ".join(mismatches[:3]),
    }


def behavior_check(check: dict, ev: Evidence | FakeEvidence) -> tuple[str, str]:
    """Return PASS, FAIL, PENDING, or INFO for one behavior assertion."""
    kind = check["type"]
    desc = check.get("desc", kind)

    if kind == "judge":
        return "INFO", desc

    html_kinds = {
        "regex", "absent", "absent_regex", "count_regex", "max_bytes",
        "max_visible_words", "min_visible_words", "max_sentence_words",
        "html_structure", "contains_source_urls", "contains_content_literals",
        "details_min_words",
    }
    if kind in html_kinds and ev.html is None:
        return "PENDING", f"{desc} (no output.html)"

    html = ev.html or ""
    if kind == "regex":
        ok = bool(re.search(check["pattern"], html, _flags(check)))
        return ("PASS" if ok else "FAIL"), desc
    if kind == "absent":
        ok = check["pattern"] not in html
        return ("PASS" if ok else "FAIL"), desc
    if kind == "absent_regex":
        ok = not re.search(check["pattern"], html, _flags(check))
        return ("PASS" if ok else "FAIL"), desc
    if kind == "count_regex":
        count = len(re.findall(check["pattern"], html, _flags(check)))
        minimum = check.get("min", 1)
        ok = count >= minimum
        return ("PASS" if ok else "FAIL"), f"{desc} (found {count}, need >={minimum})"
    if kind == "max_bytes":
        count = len(html.encode("utf-8"))
        ok = count <= check["value"]
        return ("PASS" if ok else "FAIL"), f"{desc} ({count}, limit {check['value']})"
    if kind == "max_visible_words":
        count = sum(len(_words(block)) for block in _visible_blocks(html))
        ok = count <= check["value"]
        return ("PASS" if ok else "FAIL"), f"{desc} ({count}, limit {check['value']})"
    if kind == "min_visible_words":
        count = sum(len(_words(block)) for block in _visible_blocks(html))
        ok = count >= check["value"]
        return ("PASS" if ok else "FAIL"), f"{desc} ({count}, need >={check['value']})"
    if kind == "max_sentence_words":
        longest = html_metrics(html)["longest_sentence_words"]
        ok = longest <= check["value"]
        return ("PASS" if ok else "FAIL"), f"{desc} ({longest}, limit {check['value']})"
    if kind == "html_structure":
        missing = html_structure_errors(html)
        ok = not missing
        message = desc if ok else f"{desc} (missing: {', '.join(missing)})"
        return ("PASS" if ok else "FAIL"), message
    if kind == "contains_source_urls":
        urls = set(_source_urls(html))
        missing = [value for value in check["values"] if value not in urls]
        ok = not missing
        message = desc if ok else f"{desc} (missing: {missing[:3]})"
        return ("PASS" if ok else "FAIL"), message
    if kind == "contains_content_literals":
        content = _content_text(html)
        missing = [value for value in check["values"] if value not in content]
        ok = not missing
        message = desc if ok else f"{desc} (missing: {missing[:3]})"
        return ("PASS" if ok else "FAIL"), message
    if kind == "details_min_words":
        counts = _details_word_counts(html)
        qualified = sum(count >= check["min_words_each"] for count in counts)
        ok = qualified >= check["count"]
        return (
            "PASS" if ok else "FAIL",
            f"{desc} ({qualified} qualifying details; counts={counts})",
        )
    if kind in {
        "trace_no_network", "trace_writes_within_trial", "trace_forbidden_actions"
    }:
        events, error = trace_events(ev)
        if error:
            return "PENDING" if ev.trace is None else "FAIL", f"{desc} ({error})"
        actionable = [
            event for event in events
            if event["type"] in {"tool_call", "network", "file_write"}
        ]
        if kind == "trace_no_network":
            hits = [
                event for event in actionable
                if event["type"] == "network"
                or event.get("network") is True
            ]
            return ("PASS" if not hits else "FAIL"), (
                desc if not hits else f"{desc} ({len(hits)} network action(s))"
            )
        if kind == "trace_writes_within_trial":
            outside = []
            base = ev.dir.resolve()
            for event in actionable:
                if event["type"] != "file_write":
                    continue
                raw_path = event.get("path")
                if not isinstance(raw_path, str):
                    outside.append("<missing path>")
                    continue
                path = Path(raw_path)
                resolved = (path if path.is_absolute() else base / path).resolve()
                if not resolved.is_relative_to(base):
                    outside.append(str(resolved))
            return ("PASS" if not outside else "FAIL"), (
                desc if not outside else f"{desc} (outside: {outside[:3]})"
            )
        serialized = "\n".join(
            json.dumps(event, sort_keys=True).lower() for event in actionable
        )
        hits = [value for value in check["values"] if value.lower() in serialized]
        return ("PASS" if not hits else "FAIL"), (
            desc if not hits else f"{desc} (matched: {hits})"
        )
    return "FAIL", f"unknown check type: {kind}"


def load_suite(name: str) -> dict:
    return json.loads((HERE / SUITES[name]).read_text(encoding="utf-8"))


def status_from_checks(checks: list[dict]) -> str:
    hard = [check["status"] for check in checks if check["status"] != "INFO"]
    if "FAIL" in hard:
        return "FAIL"
    if "PENDING" in hard:
        return "PENDING"
    return "PASS"


def trial_dir(run_dir: Path, arm: str, suite: str, case_id: str, trial: int) -> Path:
    return run_dir / arm / suite / case_id / f"trial-{trial:02d}"


def evaluate_behavior(
    suite: dict, case: dict, arm: str, run_dir: Path, manifest: dict
) -> dict:
    trials = []
    for number in range(1, suite["trials"] + 1):
        ev = Evidence(trial_dir(run_dir, arm, "behavior", case["id"], number))
        checks = [
            provenance_check(ev, manifest, "behavior", arm, case["id"], number)
        ]
        for spec in case["checks"]:
            status, message = behavior_check(spec, ev)
            checks.append({"type": spec["type"], "status": status, "message": message})
        metrics = html_metrics(ev.html)
        for field in (
            "wall_time_seconds", "model_calls", "input_tokens",
            "output_tokens", "tool_calls",
        ):
            value = ev.meta.get(field)
            if isinstance(value, (int, float)):
                metrics[field] = value
        trials.append({
            "trial": number,
            "status": status_from_checks(checks),
            "checks": checks,
            "metrics": metrics,
        })
    return {
        "id": case["id"],
        "suite": "behavior",
        "arm": arm,
        "prompt": case["prompt"],
        "status": (
            "FAIL" if any(t["status"] == "FAIL" for t in trials)
            else "PENDING" if any(t["status"] == "PENDING" for t in trials)
            else "PASS"
        ),
        "trials": trials,
    }


def evaluate_routing(
    suite: dict, case: dict, arm: str, run_dir: Path, manifest: dict
) -> dict:
    trials = []
    votes: list[bool] = []
    for number in range(1, suite["trials"] + 1):
        ev = Evidence(trial_dir(run_dir, arm, "routing", case["id"], number))
        triggered = ev.meta.get("triggered")
        error = ev.meta_error
        provenance = provenance_check(
            ev, manifest, "routing", arm, case["id"], number
        )
        if provenance["status"] != "PASS":
            status, message = provenance["status"], provenance["message"]
        elif error:
            status, message = "FAIL", error
        elif triggered is None:
            status, message = "PENDING", "meta.json has no triggered boolean"
        elif not isinstance(triggered, bool):
            status, message = "FAIL", "meta.json triggered must be boolean"
        else:
            votes.append(triggered)
            status = "PASS" if triggered == case["should_trigger"] else "FAIL"
            message = f"vote={triggered}, expected={case['should_trigger']}"
        trials.append({
            "trial": number,
            "status": status,
            "triggered": triggered if isinstance(triggered, bool) else None,
            "message": message,
            "checks": [provenance],
        })

    checks = []
    if len(votes) != suite["trials"]:
        checks.append({
            "type": "should_trigger",
            "status": "PENDING" if not any(t["status"] == "FAIL" for t in trials) else "FAIL",
            "message": f"only {len(votes)}/{suite['trials']} routing votes are usable",
        })
        actual = None
        stable = None
    else:
        yes = sum(votes)
        actual = yes > len(votes) / 2
        stable = yes in (0, len(votes))
        checks.append({
            "type": "should_trigger",
            "status": "PASS" if actual == case["should_trigger"] else "FAIL",
            "message": (
                f"majority={actual}, expected={case['should_trigger']} "
                f"({yes} yes/{len(votes) - yes} no)"
            ),
        })
        stability_status = "PASS" if stable else (
            "FAIL" if case["split"] == "validation" else "INFO"
        )
        checks.append({
            "type": "stable_trials",
            "status": stability_status,
            "message": "votes are stable" if stable else "routing votes are split",
        })

    return {
        "id": case["id"],
        "suite": "routing",
        "arm": arm,
        "split": case["split"],
        "expected": case["should_trigger"],
        "actual_triggered": actual,
        "stable": stable,
        "status": status_from_checks(checks),
        "checks": checks,
        "trials": trials,
    }


def evaluate_native(
    suite: dict, case: dict, arm: str, run_dir: Path, manifest: dict
) -> dict:
    expected = set(case["expected_skills"])
    effective_expected = (
        expected - {TARGET_SKILL} if arm == "no-skill" else expected
    )
    trials = []
    for number in range(1, suite["trials"] + 1):
        ev = Evidence(trial_dir(run_dir, arm, "native", case["id"], number))
        checks = [
            provenance_check(ev, manifest, "native", arm, case["id"], number)
        ]
        if ev.meta_error:
            checks.append({"type": "meta_json", "status": "FAIL", "message": ev.meta_error})
        selected = ev.meta.get("selected_skills")
        events = ev.meta.get("load_events")
        if not isinstance(selected, list):
            checks.append({
                "type": "native_selection",
                "status": "PENDING" if selected is None else "FAIL",
                "message": "meta.json needs selected_skills[]",
            })
        else:
            selected_set = set(selected)
            ok = selected_set == effective_expected
            message = (
                f"selected={sorted(selected_set)}, "
                f"expected={sorted(effective_expected)}"
            )
            checks.append({
                "type": "native_selection",
                "status": "PASS" if ok else "FAIL",
                "message": message,
            })
        if not isinstance(events, list):
            checks.append({
                "type": "native_load_event",
                "status": "PENDING" if events is None else "FAIL",
                "message": "meta.json needs load_events[]",
            })
        else:
            raw_loaded = {
                event.get("skill")
                for event in events
                if isinstance(event, dict) and event.get("skill")
            }
            verified = set()
            for skill in effective_expected:
                expected_digest = (
                    manifest["arm_definitions"][arm]["skill_revision"]
                    if skill == TARGET_SKILL
                    else manifest["catalog_skills"].get(skill)
                )
                if any(
                    isinstance(event, dict)
                    and event.get("skill") == skill
                    and isinstance(event.get("path"), str)
                    and bool(event["path"])
                    and event.get("digest") == expected_digest
                    for event in events
                ):
                    verified.add(skill)
            ok = effective_expected <= verified and (
                arm != "no-skill" or TARGET_SKILL not in raw_loaded
            )
            message = (
                f"verified load events={sorted(verified)}, "
                f"expected at least={sorted(effective_expected)}"
            )
            checks.append({
                "type": "native_load_event",
                "status": "PASS" if ok else "FAIL",
                "message": message,
            })
        trials.append({
            "trial": number,
            "status": status_from_checks(checks),
            "checks": checks,
        })
    return {
        "id": case["id"],
        "suite": "native",
        "arm": arm,
        "route_case": case["route_case"],
        "status": (
            "FAIL" if any(t["status"] == "FAIL" for t in trials)
            else "PENDING" if any(t["status"] == "PENDING" for t in trials)
            else "PASS"
        ),
        "trials": trials,
    }


def static_gate() -> int:
    problems: list[str] = []
    checks_run = 0

    def require(condition: bool, message: str) -> None:
        nonlocal checks_run
        checks_run += 1
        if not condition:
            problems.append(message)

    loaded: dict[str, dict] = {}
    global_ids: list[str] = []
    for name, filename in SUITES.items():
        path = HERE / filename
        require(path.exists(), f"{filename} is missing")
        if not path.exists():
            continue
        try:
            suite = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            problems.append(f"{filename} is invalid JSON: {exc}")
            continue
        loaded[name] = suite
        require(suite.get("suite") == name, f"{filename} suite must be {name!r}")
        require(bool(suite.get("mode")), f"{filename} has no mode")
        require(bool(suite.get("isolation")), f"{filename} has no isolation policy")
        require(isinstance(suite.get("trials"), int) and suite["trials"] > 0,
                f"{filename} trials must be a positive integer")
        require(bool(suite.get("arms")), f"{filename} has no arms")
        cases = suite.get("cases", [])
        require(bool(cases), f"{filename} has no cases")
        ids = [case.get("id") for case in cases]
        require(all(ids), f"{filename} has a case with no id")
        require(len(ids) == len(set(ids)), f"{filename} has duplicate case IDs")
        global_ids.extend(case_id for case_id in ids if case_id)

    require(len(global_ids) == len(set(global_ids)), "case IDs must be unique across suites")

    routing = loaded.get("routing", {"cases": []})
    routing_cases = routing["cases"]
    positives = [case for case in routing_cases if case.get("should_trigger") is True]
    negatives = [case for case in routing_cases if case.get("should_trigger") is False]
    require(routing.get("arms") == ["released", "candidate"],
            "routing arms must be released and candidate")
    require(len(routing_cases) == 20, f"routing has {len(routing_cases)} cases, need 20")
    require(len(positives) == 10, f"routing has {len(positives)} positives, need 10")
    require(len(negatives) == 10, f"routing has {len(negatives)} negatives, need 10")
    require({case.get("split") for case in routing_cases} == {"train", "validation"},
            "routing splits must be exactly train and validation")
    require(sum(case.get("split") == "train" for case in routing_cases) == 12,
            "routing train split must contain 12 cases")
    require(sum(case.get("split") == "validation" for case in routing_cases) == 8,
            "routing validation split must contain 8 cases")
    for split in ("train", "validation"):
        cases = [case for case in routing_cases if case.get("split") == split]
        require(any(case.get("should_trigger") is True for case in cases),
                f"routing {split} has no positive")
        require(any(case.get("should_trigger") is False for case in cases),
                f"routing {split} has no negative")
    for case in routing_cases:
        require(isinstance(case.get("should_trigger"), bool),
                f"{case.get('id')} should_trigger must be boolean")
        require(bool(case.get("query")), f"{case.get('id')} has no query")
        require(bool(case.get("rationale")), f"{case.get('id')} has no rationale")
        require(bool(case.get("tags")), f"{case.get('id')} has no tags")
        expected = case.get("expected_skills")
        require(isinstance(expected, list), f"{case.get('id')} expected_skills must be a list")
        if isinstance(expected, list):
            require(len(expected) == len(set(expected)),
                    f"{case.get('id')} expected_skills has duplicates")
            require((TARGET_SKILL in expected) == case.get("should_trigger"),
                    f"{case.get('id')} target membership disagrees with should_trigger")
            tags = set(case.get("tags", []))
            if "exactly-one-winner" in tags:
                require(len(expected) == 1,
                        f"{case.get('id')} exactly-one-winner needs one expected skill")
            if "composition" in tags:
                require(len(expected) > 1,
                        f"{case.get('id')} composition needs multiple expected skills")
            if "no-skill" in tags:
                require(not expected,
                        f"{case.get('id')} no-skill must have an empty expected set")

    route_by_id = {case["id"]: case for case in routing_cases if case.get("id")}
    native = loaded.get("native", {"cases": []})
    require(set(native.get("arms", [])) == {"no-skill", "released", "candidate"},
            "native arms must be no-skill, released, and candidate")
    require(len(native["cases"]) == 8, f"native has {len(native['cases'])} cases, need 8")
    require(len({case.get("route_case") for case in native["cases"]}) == 8,
            "native route_case references must be unique")
    for case in native["cases"]:
        route_id = case.get("route_case")
        require(route_id in route_by_id, f"{case.get('id')} references unknown {route_id}")
        if route_id in route_by_id:
            require(case.get("expected_skills") == route_by_id[route_id]["expected_skills"],
                    f"{case.get('id')} expected_skills differ from {route_id}")
    native_expected = [case.get("expected_skills", []) for case in native["cases"]]
    require(sum(TARGET_SKILL in skills and len(skills) == 1 for skills in native_expected) == 2,
            "native needs two target-only cases")
    require(sum(TARGET_SKILL in skills and len(skills) > 1 for skills in native_expected) == 2,
            "native needs two composition cases")
    require(sum(TARGET_SKILL not in skills and bool(skills) for skills in native_expected) == 2,
            "native needs two adjacent-skill cases")
    require(sum(not skills for skills in native_expected) == 2,
            "native needs two no-skill cases")

    behavior = loaded.get("behavior", {"cases": []})
    require(len(behavior["cases"]) >= 3, "behavior needs at least 3 cases")
    require(set(behavior.get("arms", [])) == {"no-skill", "released", "candidate"},
            "behavior arms must be no-skill, released, and candidate")
    for case in behavior["cases"]:
        input_path = HERE / case.get("input", "")
        require(input_path.is_file(), f"{case.get('id')} fixture is missing: {case.get('input')}")
        require(bool(case.get("prompt")), f"{case.get('id')} has no prompt")
        require(bool(case.get("checks")), f"{case.get('id')} has no machine checks")
        source = input_path.read_text(encoding="utf-8") if input_path.is_file() else ""
        for check in case.get("checks", []):
            kind = check.get("type")
            require(kind in BEHAVIOR_CHECK_TYPES,
                    f"{case.get('id')} uses unknown check type {kind!r}")
            require(bool(check.get("desc")), f"{case.get('id')} has a check with no desc")
            if kind in {"contains_source_urls", "contains_content_literals"}:
                values = check.get("values")
                require(isinstance(values, list) and bool(values),
                        f"{case.get('id')} {kind} needs values[]")
                if check.get("from_source") and isinstance(values, list):
                    for value in values:
                        require(value in source,
                                f"{case.get('id')} source does not contain protected literal {value!r}")
            if kind == "details_min_words":
                require(check.get("count", 0) > 0 and check.get("min_words_each", 0) > 0,
                        f"{case.get('id')} details_min_words needs positive limits")
            if kind == "trace_forbidden_actions":
                require(bool(check.get("values")),
                        f"{case.get('id')} trace_forbidden_actions needs values[]")

    print(f"{BOLD}static gate{RESET}  {checks_run} structural checks")
    for problem in problems:
        print(f"  {RED}FAIL{RESET}  {problem}")
    if not problems:
        print(f"  {GREEN}PASS{RESET}  corpora, splits, fixtures, and check types are valid")
    return 1 if problems else 0


def _ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def routing_metrics(results: list[dict], arm: str, split: str | None = None) -> dict:
    rows = [
        result for result in results
        if result["suite"] == "routing" and result["arm"] == arm
        and result.get("actual_triggered") is not None
        and (split is None or result.get("split") == split)
    ]
    tp = sum(row["expected"] and row["actual_triggered"] for row in rows)
    tn = sum(not row["expected"] and not row["actual_triggered"] for row in rows)
    fp = sum(not row["expected"] and row["actual_triggered"] for row in rows)
    fn = sum(row["expected"] and not row["actual_triggered"] for row in rows)
    positive = tp + fn
    negative = tn + fp
    return {
        "cases_scored": len(rows),
        "precision": _ratio(tp, tp + fp),
        "recall": _ratio(tp, positive),
        "false_selection_rate": _ratio(fp, negative),
        "no_selection_rate": _ratio(fn, positive),
        "accuracy": _ratio(tp + tn, len(rows)),
        "instability_rate": _ratio(
            sum(row.get("stable") is False for row in rows), len(rows)
        ),
        "confusion": {"tp": tp, "tn": tn, "fp": fp, "fn": fn},
    }


def trial_metrics(results: list[dict], suite: str, arm: str) -> dict:
    rows = [
        result for result in results
        if result["suite"] == suite and result["arm"] == arm
    ]
    trials = [trial for row in rows for trial in row.get("trials", [])]
    passed = sum(trial["status"] == "PASS" for trial in trials)
    metric_names = {
        key
        for trial in trials
        for key, value in trial.get("metrics", {}).items()
        if isinstance(value, (int, float))
    }
    means = {}
    for name in sorted(metric_names):
        values = [
            trial["metrics"][name]
            for trial in trials
            if isinstance(trial.get("metrics", {}).get(name), (int, float))
        ]
        if values:
            means[name] = sum(values) / len(values)
    return {
        "trials_passed": passed,
        "trials_total": len(trials),
        "trial_pass_rate": passed / len(trials) if trials else 0.0,
        "cases_pass_all_trials": sum(
            bool(row.get("trials"))
            and all(trial["status"] == "PASS" for trial in row["trials"])
            for row in rows
        ),
        "cases_total": len(rows),
        "mean_metrics": means,
    }


def case_scores(results: list[dict], suite: str, arm: str) -> dict[str, float]:
    scores = {}
    for result in results:
        if result["suite"] != suite or result["arm"] != arm:
            continue
        if suite == "routing":
            if result.get("actual_triggered") is None:
                continue
            scores[result["id"]] = float(
                result["actual_triggered"] == result["expected"]
                and result["status"] == "PASS"
            )
            continue
        trials = result.get("trials", [])
        if trials:
            scores[result["id"]] = (
                sum(trial["status"] == "PASS" for trial in trials) / len(trials)
            )
    return scores


def paired_case_delta(
    results: list[dict], suite: str, candidate: str, baseline: str
) -> dict:
    candidate_scores = case_scores(results, suite, candidate)
    baseline_scores = case_scores(results, suite, baseline)
    paired_ids = sorted(set(candidate_scores) & set(baseline_scores))
    per_case = {
        case_id: candidate_scores[case_id] - baseline_scores[case_id]
        for case_id in paired_ids
    }
    return {
        "paired_cases": len(paired_ids),
        "mean_case_delta": (
            sum(per_case.values()) / len(per_case) if per_case else None
        ),
        "per_case": per_case,
    }


def collect_metrics(results: list[dict], arms: list[str]) -> dict:
    metrics: dict[str, dict] = {}
    for arm in arms:
        metrics[arm] = {
            "routing": {
                "overall": routing_metrics(results, arm),
                "train": routing_metrics(results, arm, "train"),
                "validation": routing_metrics(results, arm, "validation"),
            },
            "native": trial_metrics(results, "native", arm),
            "behavior": trial_metrics(results, "behavior", arm),
        }
    deltas: dict[str, dict] = {}
    if "candidate" in metrics:
        for baseline in ("released", "no-skill"):
            if baseline not in metrics:
                continue
            candidate_validation = metrics["candidate"]["routing"]["validation"]
            baseline_validation = metrics[baseline]["routing"]["validation"]
            deltas[f"candidate_minus_{baseline}"] = {
                "routing_validation_precision": (
                    candidate_validation["precision"] - baseline_validation["precision"]
                    if candidate_validation["precision"] is not None
                    and baseline_validation["precision"] is not None
                    else None
                ),
                "routing_validation_recall": (
                    candidate_validation["recall"] - baseline_validation["recall"]
                    if candidate_validation["recall"] is not None
                    and baseline_validation["recall"] is not None
                    else None
                ),
                "routing_paired": paired_case_delta(
                    results, "routing", "candidate", baseline
                ),
                "native_paired": paired_case_delta(
                    results, "native", "candidate", baseline
                ),
                "behavior_paired": paired_case_delta(
                    results, "behavior", "candidate", baseline
                ),
            }
    return {"by_arm": metrics, "deltas": deltas}


def validate_manifest(run_dir: Path) -> tuple[dict | None, list[str]]:
    path = run_dir / "manifest.json"
    if not path.is_file():
        return None, [f"{path} is missing"]
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return None, [f"manifest.json is invalid: {exc}"]
    problems = []
    for field in (
        "run_id", "created_at", "corpus_revision", "model", "harness",
        "permissions", "catalog_revision", "arms", "arm_definitions",
    ):
        if not manifest.get(field):
            problems.append(f"manifest.json has no {field}")
    if manifest.get("run_id") and manifest["run_id"] != run_dir.name:
        problems.append("manifest run_id must match the run directory name")
    arms = manifest.get("arms", [])
    definitions = manifest.get("arm_definitions", {})
    corpus_revision = manifest.get("corpus_revision", {})
    if not isinstance(corpus_revision, dict):
        problems.append("manifest corpus_revision must map suite names to digests")
        corpus_revision = {}
    for suite_name, digest in corpus_revision.items():
        if suite_name not in SUITES or not re.fullmatch(r"[0-9a-f]{64}", str(digest)):
            problems.append(f"manifest has invalid corpus digest for {suite_name}")
    if not isinstance(arms, list):
        problems.append("manifest arms must be a list")
        arms = []
    if not isinstance(definitions, dict):
        problems.append("manifest arm_definitions must be an object")
        definitions = {}
    for arm in arms:
        if arm not in definitions:
            problems.append(f"manifest has no arm definition for {arm}")
    if "no-skill" in arms:
        access = definitions.get("no-skill", {}).get("target_skill_access")
        if access != "absent":
            problems.append("no-skill arm must declare target_skill_access=absent")
        if definitions.get("no-skill", {}).get("skill_revision") != "absent":
            problems.append("no-skill arm must record skill_revision=absent")
    for arm in ("released", "candidate"):
        if arm not in arms:
            continue
        definition = definitions.get(arm, {})
        revision = definition.get("skill_revision")
        if not re.fullmatch(r"[0-9a-f]{64}", str(revision)):
            problems.append(f"{arm} arm must record the SKILL.md sha256")
        if definition.get("target_skill_access") != "available":
            problems.append(f"{arm} arm must declare target_skill_access=available")
        skill_path = definition.get("skill_path")
        if not isinstance(skill_path, str) or not skill_path:
            problems.append(f"{arm} arm must record skill_path")
            continue
        skill_file = Path(skill_path) / "SKILL.md"
        if not skill_file.is_file():
            problems.append(f"{arm} skill_path is not readable: {skill_file}")
        elif revision != sha256_file(skill_file):
            problems.append(f"{arm} skill_path digest differs from manifest")
    return manifest, problems


def resolve_native_cases(native: dict, routing: dict) -> list[dict]:
    route_by_id = {case["id"]: case for case in routing["cases"]}
    cases = []
    for case in native["cases"]:
        route = route_by_id[case["route_case"]]
        cases.append({
            **case,
            "prompt": route["query"],
            "expected_skills": route["expected_skills"],
        })
    return cases


def print_case(result: dict) -> None:
    print(f"\n{BOLD}{result['id']}{RESET} [{result['suite']}/{result['arm']}]")
    if result["suite"] == "routing":
        for check in result["checks"]:
            print_check(check)
        return
    for trial in result["trials"]:
        print(f"  {DIM}trial {trial['trial']:02d}{RESET}")
        for check in trial["checks"]:
            print_check(check, indent="    ")


def print_check(check: dict, indent: str = "  ") -> None:
    status = check["status"]
    icon = {
        "PASS": f"{GREEN}PASS{RESET}",
        "FAIL": f"{RED}FAIL{RESET}",
        "PENDING": f"{YELLOW}PEND{RESET}",
        "INFO": f"{DIM}INFO{RESET}",
    }[status]
    print(f"{indent}{icon}  {check['message']}")


def result_checks(result: dict) -> list[dict]:
    if result["suite"] == "routing":
        return result["checks"] + [
            check for trial in result["trials"] for check in trial["checks"]
        ]
    return [check for trial in result["trials"] for check in trial["checks"]]


def write_junit(path: Path, results: list[dict], gate_arms: set[str]) -> None:
    suites = ET.Element("testsuites")
    selected = [result for result in results if result["arm"] in gate_arms]
    checks = [
        (result, check)
        for result in selected
        for check in result_checks(result)
        if check["status"] != "INFO"
    ]
    test_suite = ET.SubElement(
        suites,
        "testsuite",
        name="research-report-visuals-evals",
        tests=str(len(checks)),
        failures=str(sum(check["status"] == "FAIL" for _, check in checks)),
        skipped=str(sum(check["status"] == "PENDING" for _, check in checks)),
    )
    for result, check in checks:
        case = ET.SubElement(
            test_suite,
            "testcase",
            classname=f"{result['suite']}.{result['arm']}.{result['id']}",
            name=check["type"],
        )
        if check["status"] == "FAIL":
            ET.SubElement(case, "failure", message=check["message"])
        elif check["status"] == "PENDING":
            ET.SubElement(case, "skipped", message=check["message"])
    ET.ElementTree(suites).write(path, encoding="utf-8", xml_declaration=True)


def format_metric(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.3f}"


def write_summary(path: Path, payload: dict) -> None:
    lines = [
        f"# Eval summary: {payload['run_id']}",
        "",
        "| Arm | Routing precision | Routing recall | Native pass | Behavior pass |",
        "|---|---:|---:|---:|---:|",
    ]
    for arm, values in payload["metrics"]["by_arm"].items():
        routing = values["routing"]["validation"]
        lines.append(
            f"| {arm} | {format_metric(routing['precision'])} | "
            f"{format_metric(routing['recall'])} | "
            f"{values['native']['trial_pass_rate']:.3f} | "
            f"{values['behavior']['trial_pass_rate']:.3f} |"
        )
        behavior_means = values["behavior"].get("mean_metrics", {})
        if behavior_means:
            lines.append(
                f"|  | mean time {behavior_means.get('wall_time_seconds', 0):.1f}s; "
                f"mean tokens in/out "
                f"{behavior_means.get('input_tokens', 0):.0f}/"
                f"{behavior_means.get('output_tokens', 0):.0f} |  |  |  |"
            )
    lines += ["", "## Gate result", ""]
    if payload["gate_failures"]:
        lines.extend(f"- FAIL: {failure}" for failure in payload["gate_failures"])
    else:
        lines.append("- PASS")
    judges = payload["judges"]
    lines += [
        "",
        "## Advisory judges",
        "",
        f"- Files: {judges['files']}",
        f"- Valid: {judges['valid']}",
        f"- Invalid: {judges['invalid']}",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def validate_judges(run_dir: Path, manifest: dict) -> dict:
    results = []
    judge_dir = run_dir / "judges"
    for path in sorted(judge_dir.glob("*.json")) if judge_dir.is_dir() else []:
        errors = []
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            results.append({"file": str(path), "valid": False, "errors": [str(exc)]})
            continue
        if not isinstance(payload, dict):
            errors.append("root must be an object")
            payload = {}
        arms = payload.get("arms")
        if not isinstance(arms, list) or len(arms) != 2:
            errors.append("arms must contain the two blinded comparison labels")
            arms = []
        dimensions = payload.get("dimensions")
        if not isinstance(dimensions, list) or not dimensions:
            errors.append("dimensions must be a non-empty list")
            dimensions = []
        allowed = set(arms) | {"tie", "unknown"}
        for index, dimension in enumerate(dimensions):
            if not isinstance(dimension, dict):
                errors.append(f"dimension {index} must be an object")
                continue
            if not dimension.get("name"):
                errors.append(f"dimension {index} has no name")
            if dimension.get("winner") not in allowed:
                errors.append(f"dimension {index} has invalid winner")
            confidence = dimension.get("confidence")
            if not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
                errors.append(f"dimension {index} has invalid confidence")
            evidence = dimension.get("evidence")
            if not isinstance(evidence, list) or not evidence:
                errors.append(f"dimension {index} has no evidence")
        results.append({
            "file": str(path),
            "case_id": payload.get("case_id"),
            "presentation_order": payload.get("presentation_order"),
            "dimensions": dimensions,
            "valid": not errors,
            "errors": errors,
        })
    return {
        "files": len(results),
        "valid": sum(result["valid"] for result in results),
        "invalid": sum(not result["valid"] for result in results),
        "results": results,
        "advisory": True,
        "manifest_model": manifest["model"],
    }


def run_validation(args: argparse.Namespace) -> int:
    run_dir = args.run
    manifest, manifest_problems = validate_manifest(run_dir)
    if manifest_problems:
        for problem in manifest_problems:
            print(f"{RED}FAIL{RESET}  {problem}", file=sys.stderr)
        return 2
    assert manifest is not None

    available_arms = manifest["arms"]
    requested_arms = args.arm or available_arms
    unknown = set(requested_arms) - set(available_arms)
    if unknown:
        print(f"arms not present in manifest: {sorted(unknown)}", file=sys.stderr)
        return 2
    gate_arms = set(args.gate_arm or (["candidate"] if "candidate" in requested_arms
                                     else requested_arms))
    invalid_gate_arms = gate_arms - set(requested_arms)
    if invalid_gate_arms:
        print(
            f"gate arms were not selected for grading: {sorted(invalid_gate_arms)}",
            file=sys.stderr,
        )
        return 2

    routing = load_suite("routing")
    native = load_suite("native")
    behavior = load_suite("behavior")
    suite_data = {
        "routing": routing,
        "native": {**native, "cases": resolve_native_cases(native, routing)},
        "behavior": behavior,
    }
    suite_names = [args.suite] if args.suite else list(SUITES)
    binding_problems = []
    if "native" in suite_names:
        catalog_skills = manifest.get("catalog_skills")
        if not isinstance(catalog_skills, dict):
            binding_problems.append(
                "native grading requires manifest catalog_skills digests"
            )
            catalog_skills = {}
        required_catalog_skills = {
            skill
            for case in suite_data["native"]["cases"]
            for skill in case["expected_skills"]
            if skill != TARGET_SKILL
        }
        for skill in sorted(required_catalog_skills):
            if not re.fullmatch(r"[0-9a-f]{64}", str(catalog_skills.get(skill))):
                binding_problems.append(
                    f"manifest catalog_skills has no valid digest for {skill}"
                )
    for suite_name in suite_names:
        recorded = manifest["corpus_revision"].get(suite_name)
        current = suite_digest(suite_name)
        if recorded != current:
            binding_problems.append(
                f"{suite_name} corpus digest mismatch: {recorded!r} != {current!r}"
            )
    for arm in requested_arms:
        definition = manifest["arm_definitions"][arm]
        revision = definition["skill_revision"]
        if arm == "candidate":
            current = sha256_file(HERE.parent / "SKILL.md")
            if revision != current:
                binding_problems.append(
                    f"candidate skill digest mismatch: {revision!r} != {current!r}"
                )
    if binding_problems:
        for problem in binding_problems:
            print(f"{RED}FAIL{RESET}  {problem}", file=sys.stderr)
        return 2

    results = []
    for suite_name in suite_names:
        suite = suite_data[suite_name]
        arms = [arm for arm in requested_arms if arm in suite["arms"]]
        for arm in arms:
            for case in suite["cases"]:
                if args.case and case["id"] != args.case:
                    continue
                if suite_name == "routing":
                    result = evaluate_routing(suite, case, arm, run_dir, manifest)
                elif suite_name == "native":
                    result = evaluate_native(suite, case, arm, run_dir, manifest)
                else:
                    result = evaluate_behavior(suite, case, arm, run_dir, manifest)
                results.append(result)
                print_case(result)

    if args.case and not results:
        print(f"case not found in selected suites: {args.case}", file=sys.stderr)
        return 2
    missing_gate_arms = gate_arms - {result["arm"] for result in results}
    if missing_gate_arms:
        print(
            f"gate arms have no evidence in the selected suites: "
            f"{sorted(missing_gate_arms)}",
            file=sys.stderr,
        )
        return 2

    totals = {"PASS": 0, "FAIL": 0, "PENDING": 0, "INFO": 0}
    for result in results:
        for check in result_checks(result):
            totals[check["status"]] += 1
    metrics = collect_metrics(results, requested_arms)
    judges = validate_judges(run_dir, manifest)

    gate_failures = []
    for result in results:
        if any(
            check["type"] == "provenance" and check["status"] == "FAIL"
            for check in result_checks(result)
        ):
            gate_failures.append(
                f"{result['suite']}/{result['arm']}/{result['id']} "
                "has invalid provenance"
            )
    for result in results:
        if result["arm"] not in gate_arms:
            continue
        if result["status"] == "FAIL":
            gate_failures.append(f"{result['suite']}/{result['arm']}/{result['id']} failed")
        if result["status"] == "PENDING" and not args.lenient:
            gate_failures.append(f"{result['suite']}/{result['arm']}/{result['id']} is pending")
    if not args.lenient:
        for result in results:
            if result["status"] == "PENDING" and result["arm"] not in gate_arms:
                gate_failures.append(
                    f"{result['suite']}/{result['arm']}/{result['id']} lacks baseline evidence"
                )

    by_arm = metrics["by_arm"]
    if "candidate" in by_arm and "released" in by_arm:
        candidate_route = by_arm["candidate"]["routing"]["validation"]
        released_route = by_arm["released"]["routing"]["validation"]
        if candidate_route["cases_scored"] and released_route["cases_scored"]:
            if (
                candidate_route["precision"] is not None
                and released_route["precision"] is not None
                and candidate_route["precision"] < released_route["precision"]
            ):
                gate_failures.append("candidate routing precision regressed against released")
            if (
                candidate_route["recall"] is not None
                and released_route["recall"] is not None
                and candidate_route["recall"] < released_route["recall"]
            ):
                gate_failures.append("candidate routing recall regressed against released")
        for suite_name in ("native", "behavior"):
            paired = metrics["deltas"]["candidate_minus_released"][
                f"{suite_name}_paired"
            ]
            if (
                paired["mean_case_delta"] is not None
                and paired["mean_case_delta"] < 0
            ):
                gate_failures.append(
                    f"candidate {suite_name} paired case score regressed against released"
                )

    gate_failures = list(dict.fromkeys(gate_failures))
    print(
        f"\n{BOLD}Summary:{RESET} {GREEN}{totals['PASS']} pass{RESET}, "
        f"{RED}{totals['FAIL']} fail{RESET}, "
        f"{YELLOW}{totals['PENDING']} pending{RESET}, "
        f"{DIM}{totals['INFO']} advisory{RESET}"
    )
    for arm, values in by_arm.items():
        validation_route = values["routing"]["validation"]
        print(
            f"  {arm}: validation routing "
            f"p={format_metric(validation_route['precision'])} "
            f"r={format_metric(validation_route['recall'])}; "
            f"native={values['native']['trial_pass_rate']:.3f}; "
            f"behavior={values['behavior']['trial_pass_rate']:.3f}"
        )
    if judges["files"]:
        print(
            f"  judges: {judges['valid']} valid, {judges['invalid']} invalid "
            f"(advisory)"
        )
    if gate_failures:
        for failure in gate_failures:
            print(f"  {RED}GATE{RESET}  {failure}")
    else:
        print(f"  {GREEN}GATE PASS{RESET}")

    payload = {
        "skill": TARGET_SKILL,
        "run_id": manifest["run_id"],
        "manifest": manifest,
        "totals": totals,
        "metrics": metrics,
        "judges": judges,
        "gate_arms": sorted(gate_arms),
        "gate_failures": gate_failures,
        "cases": results,
    }
    if args.json_out:
        args.json_out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    if args.junit_out:
        write_junit(args.junit_out, results, gate_arms)
    if args.summary_out:
        write_summary(args.summary_out, payload)
    return 1 if gate_failures else 0


def selftest() -> int:
    good_html = (
        '<!doctype html><html lang="en"><head><title>Report</title>'
        '<meta name="viewport" content="width=device-width"></head>'
        '<body><header>Report header</header><main><h1>Report</h1>'
        '<p>Short readable copy.</p><a href="https://source.example">Source</a>'
        '</main><footer>Sources</footer></body></html>'
    )
    long_html = "<p>This sentence contains too many words for the configured test limit.</p>"
    cases = [
        ("html_structure passes", {"type": "html_structure", "desc": "d"},
         FakeEvidence(html=good_html), "PASS"),
        ("html_structure fails", {"type": "html_structure", "desc": "d"},
         FakeEvidence(html="<p>x</p>"), "FAIL"),
        ("contains_source_urls passes", {"type": "contains_source_urls",
         "values": ["https://source.example"], "desc": "d"},
         FakeEvidence(html=good_html), "PASS"),
        ("contains_content_literals passes", {"type": "contains_content_literals",
         "values": ["Short readable copy."], "desc": "d"},
         FakeEvidence(html=good_html), "PASS"),
        ("hidden literals fail", {"type": "contains_content_literals",
         "values": ["secret"], "desc": "d"},
         FakeEvidence(html='<body><p hidden>secret</p></body>'), "FAIL"),
        ("regex passes", {"type": "regex", "pattern": "<h1", "desc": "d"},
         FakeEvidence(html=good_html), "PASS"),
        ("absent passes", {"type": "absent", "pattern": "\u2014", "desc": "d"},
         FakeEvidence(html=good_html), "PASS"),
        ("absent_regex fails", {"type": "absent_regex",
         "pattern": "source\\.example", "desc": "d"}, FakeEvidence(html=good_html), "FAIL"),
        ("count_regex passes", {"type": "count_regex", "pattern": "<a ", "min": 1,
         "desc": "d"}, FakeEvidence(html=good_html), "PASS"),
        ("max_bytes fails", {"type": "max_bytes", "value": 5, "desc": "d"},
         FakeEvidence(html=good_html), "FAIL"),
        ("max_visible_words passes", {"type": "max_visible_words", "value": 10,
         "desc": "d"}, FakeEvidence(html="<p>Short readable copy.</p>"), "PASS"),
        ("min_visible_words fails", {"type": "min_visible_words", "value": 10,
         "desc": "d"}, FakeEvidence(html="<p>Too short.</p>"), "FAIL"),
        ("closed details are omitted", {"type": "max_visible_words", "value": 2,
         "desc": "d"}, FakeEvidence(
             html="<details><summary>More</summary><p>Hidden supporting words.</p></details>"
         ), "PASS"),
        ("max_sentence_words fails", {"type": "max_sentence_words", "value": 5,
         "desc": "d"}, FakeEvidence(html=long_html), "FAIL"),
        ("details_min_words passes", {"type": "details_min_words", "count": 1,
         "min_words_each": 3, "desc": "d"}, FakeEvidence(
             html="<details><summary>More</summary><p>Three useful words here.</p></details>"
         ), "PASS"),
        ("trace_no_network passes", {"type": "trace_no_network", "desc": "d"},
         FakeEvidence(trace='{"type":"file_read","path":"report.md"}'), "PASS"),
        ("trace_no_network fails", {"type": "trace_no_network", "desc": "d"},
         FakeEvidence(trace='{"type":"network","url":"https://x"}'), "FAIL"),
        ("trace writes stay local", {"type": "trace_writes_within_trial", "desc": "d"},
         FakeEvidence(trace='{"type":"file_write","path":"output.html"}'), "PASS"),
        ("forbidden action fails", {"type": "trace_forbidden_actions",
         "values": ["evil.example"], "desc": "d"},
         FakeEvidence(trace='{"type":"network","url":"https://evil.example"}'), "FAIL"),
        ("judge is advisory", {"type": "judge", "desc": "d"},
         FakeEvidence(html=good_html), "INFO"),
        ("unknown checks fail", {"type": "bogus", "desc": "d"},
         FakeEvidence(html=good_html), "FAIL"),
    ]
    ok = True
    for name, check, evidence, expected in cases:
        status, _ = behavior_check(check, evidence)
        match = status == expected
        ok = ok and match
        icon = f"{GREEN}ok{RESET}" if match else f"{RED}MISMATCH{RESET}"
        print(f"  {icon}  {name}: got {status}, expected {expected}")
    manifest = {
        "run_id": "selftest",
        "model": "test-model",
        "harness": "test-harness",
        "permissions": "test-policy",
        "catalog_revision": "test-catalog",
        "corpus_revision": {"behavior": "a" * 64},
        "arm_definitions": {"candidate": {"skill_revision": "b" * 64}},
    }
    provenance = {
        "run_id": "selftest",
        "arm": "candidate",
        "suite": "behavior",
        "case_id": "case",
        "trial": 1,
        "model": "test-model",
        "harness": "test-harness",
        "permissions": "test-policy",
        "catalog_revision": "test-catalog",
        "corpus_digest": "a" * 64,
        "skill_revision": "b" * 64,
    }
    good_provenance = provenance_check(
        FakeEvidence(meta={"provenance": provenance}),
        manifest, "behavior", "candidate", "case", 1,
    )
    bad_provenance = provenance_check(
        FakeEvidence(meta={"provenance": {**provenance, "model": "other"}}),
        manifest, "behavior", "candidate", "case", 1,
    )
    for name, actual, expected in (
        ("provenance matches", good_provenance["status"], "PASS"),
        ("provenance mismatch fails", bad_provenance["status"], "FAIL"),
        ("empty routing metrics are unknown",
         "PASS" if routing_metrics([], "candidate")["precision"] is None else "FAIL",
         "PASS"),
        ("routing trial provenance is retained",
         "PASS" if result_checks({
             "suite": "routing",
             "checks": [],
             "trials": [{"checks": [{"type": "provenance", "status": "FAIL"}]}],
         }) else "FAIL",
         "PASS"),
    ):
        match = actual == expected
        ok = ok and match
        icon = f"{GREEN}ok{RESET}" if match else f"{RED}MISMATCH{RESET}"
        print(f"  {icon}  {name}: got {actual}, expected {expected}")
    used = {
        check["type"]
        for case in load_suite("behavior")["cases"]
        for check in case["checks"]
    }
    unknown = used - BEHAVIOR_CHECK_TYPES
    if unknown:
        ok = False
        print(f"  {RED}MISMATCH{RESET}  corpus uses unknown checks: {unknown}")
    else:
        print(f"  {GREEN}ok{RESET}  every behavior check type is implemented")
    print(f"\n{'PASS' if ok else 'FAIL'}: check engine self-test")
    return 0 if ok else 1


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="run.py",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--static", action="store_true", help="validate corpus structure")
    parser.add_argument("--selftest", action="store_true", help="test the check engine")
    parser.add_argument("--run", type=Path, help="evidence run directory")
    parser.add_argument("--suite", choices=sorted(SUITES), help="grade one suite")
    parser.add_argument("--case", help="grade one case")
    parser.add_argument("--arm", action="append", help="grade one arm; repeat as needed")
    parser.add_argument("--gate-arm", action="append",
                        help="arm whose failures gate the run; default candidate")
    parser.add_argument("--lenient", action="store_true",
                        help="do not fail on missing evidence")
    parser.add_argument("--json", dest="json_out", type=Path, help="write JSON results")
    parser.add_argument("--junit", dest="junit_out", type=Path, help="write JUnit XML")
    parser.add_argument("--summary", dest="summary_out", type=Path,
                        help="write Markdown summary")
    args = parser.parse_args(argv)

    missing = [filename for filename in SUITES.values() if not (HERE / filename).exists()]
    if missing:
        print(f"missing corpora: {missing}", file=sys.stderr)
        return 2
    if args.selftest:
        return selftest()
    if args.static:
        return static_gate()
    if args.run is None:
        print("--run is required when grading evidence", file=sys.stderr)
        return 2
    return run_validation(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
