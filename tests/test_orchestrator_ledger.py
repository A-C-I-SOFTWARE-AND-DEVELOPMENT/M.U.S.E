"""Tests for the canonical orchestrator decision ledger."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterator

import pytest

from muse_cli import orchestrator_ledger as ledger


@pytest.fixture(autouse=True)
def _isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    yield tmp_path


class TestPaths:
    def test_job_dir_under_hermes_home(self, _isolated_home: Path) -> None:
        assert ledger.job_dir("abc") == _isolated_home / "jobs" / "abc"

    def test_ledger_path_is_jsonl_under_job_dir(self, _isolated_home: Path) -> None:
        assert ledger.ledger_path("abc") == _isolated_home / "jobs" / "abc" / "ledger.jsonl"

    def test_path_honors_hermes_home_override_per_call(
        self, _isolated_home: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        # Repoint HERMES_HOME and re-resolve — the module must not cache.
        other = tmp_path / "alt"
        other.mkdir()
        monkeypatch.setenv("HERMES_HOME", str(other))
        assert ledger.ledger_path("abc") == other / "jobs" / "abc" / "ledger.jsonl"


class TestAppend:
    def test_append_creates_file_and_directory(self, _isolated_home: Path) -> None:
        assert not ledger.ledger_path("j1").exists()
        ledger.append("j1", {"kind": "submit", "prompt": "hi"})
        assert ledger.ledger_path("j1").is_file()

    def test_append_writes_one_line_per_entry(self, _isolated_home: Path) -> None:
        ledger.append("j1", {"kind": "submit"})
        ledger.append("j1", {"kind": "publish"})
        text = ledger.ledger_path("j1").read_text(encoding="utf-8")
        lines = [ln for ln in text.splitlines() if ln.strip()]
        assert len(lines) == 2
        assert json.loads(lines[0])["kind"] == "submit"
        assert json.loads(lines[1])["kind"] == "publish"

    def test_append_adds_iso_timestamp_when_absent(self, _isolated_home: Path) -> None:
        ledger.append("j1", {"kind": "submit"})
        entry = json.loads(ledger.ledger_path("j1").read_text().strip())
        # ISO-8601 with timezone: "2026-05-25T18:30:00.123456+00:00"
        assert "T" in entry["ts"]
        assert "+00:00" in entry["ts"] or entry["ts"].endswith("Z")

    def test_append_preserves_caller_ts(self, _isolated_home: Path) -> None:
        ledger.append("j1", {"ts": "2020-01-01T00:00:00+00:00", "kind": "submit"})
        entry = json.loads(ledger.ledger_path("j1").read_text().strip())
        assert entry["ts"] == "2020-01-01T00:00:00+00:00"

    def test_append_per_job_isolation(self, _isolated_home: Path) -> None:
        ledger.append("a", {"kind": "submit"})
        ledger.append("b", {"kind": "submit"})
        # Each job has its own file; no cross-contamination.
        assert ledger.ledger_path("a").is_file()
        assert ledger.ledger_path("b").is_file()
        assert ledger.ledger_path("a") != ledger.ledger_path("b")

    def test_append_then_read_returns_dict_payload(self, _isolated_home: Path) -> None:
        ledger.append("j1", {"kind": "submit", "prompt": "x", "extra": [1, 2]})
        entries = ledger.read("j1")
        assert len(entries) == 1
        assert entries[0]["kind"] == "submit"
        assert entries[0]["prompt"] == "x"
        assert entries[0]["extra"] == [1, 2]


class TestRead:
    def test_read_unknown_job_returns_empty(self, _isolated_home: Path) -> None:
        assert ledger.read("does-not-exist") == []

    def test_read_empty_file_returns_empty(self, _isolated_home: Path) -> None:
        path = ledger.ledger_path("j1")
        path.parent.mkdir(parents=True)
        path.touch()
        assert ledger.read("j1") == []

    def test_read_preserves_append_order(self, _isolated_home: Path) -> None:
        for kind in ("submit", "resume", "approve", "publish"):
            ledger.append("j1", {"kind": kind})
        assert [e["kind"] for e in ledger.read("j1")] == [
            "submit", "resume", "approve", "publish",
        ]

    def test_read_skips_malformed_lines(self, _isolated_home: Path) -> None:
        # Hand-edited corruption shouldn't crash the reader.
        path = ledger.ledger_path("j1")
        path.parent.mkdir(parents=True)
        path.write_text(
            '{"kind":"submit"}\n'
            'not json at all\n'
            '{"kind":"publish"}\n'
            '[]\n'           # non-dict, must be skipped
            '\n'             # blank, must be skipped
            '{"kind":"cancel"}\n',
            encoding="utf-8",
        )
        kinds = [e["kind"] for e in ledger.read("j1")]
        assert kinds == ["submit", "publish", "cancel"]


class TestAllLedgers:
    def test_no_jobs_dir_returns_empty(self, _isolated_home: Path) -> None:
        assert ledger.all_ledgers() == {}

    def test_returns_one_entry_per_job_with_ledger(self, _isolated_home: Path) -> None:
        ledger.append("a", {"kind": "submit"})
        ledger.append("b", {"kind": "submit"})
        ledger.append("b", {"kind": "publish"})
        result = ledger.all_ledgers()
        assert set(result) == {"a", "b"}
        assert [e["kind"] for e in result["a"]] == ["submit"]
        assert [e["kind"] for e in result["b"]] == ["submit", "publish"]

    def test_skips_job_dirs_without_ledger_file(self, _isolated_home: Path) -> None:
        # A job dir exists but no ledger.jsonl yet — must not appear in results.
        (ledger.job_dir("partial")).mkdir(parents=True)
        assert ledger.all_ledgers() == {}


class TestAwarenessReaderCompat:
    """The awareness reader watches for the same path; verify the contract."""

    def test_awareness_can_read_what_we_wrote(self, _isolated_home: Path) -> None:
        from muse_cli.jarvis_prime import awareness

        ledger.append("job-x", {"kind": "submit", "prompt": "hello"})
        ledger.append("job-x", {"kind": "publish"})

        # Awareness reads from ~/.hermes/jobs/<id>/ledger.jsonl
        statuses = awareness._collect_jobs(hermes_home=_isolated_home)
        assert len(statuses) == 1
        assert statuses[0].job_id == "job-x"
        assert statuses[0].ledger_path == str(ledger.ledger_path("job-x"))
        assert "publish" in (statuses[0].last_decision or "")


class TestBulkAppend:
    def test_bulk_append_writes_each_as_line(self, _isolated_home: Path) -> None:
        ledger.bulk_append("j1", [
            {"kind": "submit", "ts": "2020-01-01T00:00:00+00:00"},
            {"kind": "resume", "ts": "2020-01-02T00:00:00+00:00"},
        ])
        entries = ledger.read("j1")
        assert [e["kind"] for e in entries] == ["submit", "resume"]
        assert entries[0]["ts"] == "2020-01-01T00:00:00+00:00"
