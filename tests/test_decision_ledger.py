"""Tests for the orchestrator decision ledger.

Two ledger surfaces live in the codebase today:

* :mod:`hermes_cli.orchestrator` writes a JSON ledger under
  ``$HERMES_HOME/orchestrator/decision_ledger.json`` keyed by job id.
* :mod:`hermes_cli.job_controller` writes a per-job
  ``decision_ledger.md`` inside the local-orchestrator job folder.

These tests pin both surfaces — the JSON one is what
``/decision-ledger show`` reads, and the markdown one is what the
``github`` artifact bundler consumes.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from hermes_cli import orchestrator as orch
from hermes_cli.job_controller import (
    DECISION_LEDGER_FILE,
    JobController,
    JobNotFoundError,
)
from hermes_cli.orchestrator_models import JobMode


# ── JSON ledger (orchestrator.py) ─────────────────────────────────────


class TestJsonLedger:
    def test_submit_appends_submit_entry(self) -> None:
        job = orch.submit_job("ship the gateway")
        ledger = orch.get_ledger(job.id)
        assert job.id in ledger
        entries = ledger[job.id]
        assert len(entries) == 1
        entry = entries[0]
        assert entry["kind"] == "submit"
        assert entry["prompt"] == "ship the gateway"
        assert entry["ts"] > 0

    def test_resume_appends_resume_entry(self) -> None:
        job = orch.submit_job("retry the migration")
        # Move it to a non-queued state so resume() actually flips status.
        all_jobs = orch._load_jobs()
        all_jobs[-1].status = "paused"
        orch._save_jobs(all_jobs)
        orch.resume_job(job.id)
        ledger = orch.get_ledger(job.id)[job.id]
        kinds = [e["kind"] for e in ledger]
        assert kinds == ["submit", "resume"]

    def test_publish_appends_publish_entry(self) -> None:
        job = orch.submit_job("publish the docs")
        orch.publish_job(job.id)
        ledger = orch.get_ledger(job.id)[job.id]
        kinds = [e["kind"] for e in ledger]
        assert kinds == ["submit", "publish"]

    def test_get_ledger_all_jobs_when_no_id(self) -> None:
        a = orch.submit_job("alpha task")
        b = orch.submit_job("bravo task")
        ledger = orch.get_ledger()
        assert a.id in ledger
        assert b.id in ledger

    def test_get_ledger_empty_for_unknown_job(self) -> None:
        assert orch.get_ledger("does-not-exist") == {}

    def test_ledger_entries_are_chronological(self) -> None:
        job = orch.submit_job("multi step")
        orch.publish_job(job.id)
        entries = orch.get_ledger(job.id)[job.id]
        timestamps = [e["ts"] for e in entries]
        assert timestamps == sorted(timestamps)

    def test_ledger_file_is_json(self) -> None:
        job = orch.submit_job("inspect on disk")
        path = Path(os.environ["HERMES_HOME"]) / "orchestrator" / "decision_ledger.json"
        assert path.is_file()
        raw = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(raw, dict)
        assert job.id in raw

    def test_slash_decision_ledger_show_renders_entries(self) -> None:
        job = orch.submit_job("render ledger")
        output = orch.run_decision_ledger(f"show {job.id}")
        assert job.id in output
        assert "submit" in output

    def test_slash_decision_ledger_show_unknown_returns_empty(self) -> None:
        output = orch.run_decision_ledger("show does-not-exist")
        assert "no ledger entries" in output

    def test_slash_decision_ledger_no_args_returns_help(self) -> None:
        output = orch.run_decision_ledger("")
        assert "Usage:" in output

    def test_slash_decision_ledger_rejects_unknown_subcommand(self) -> None:
        output = orch.run_decision_ledger("delete foo")
        assert "unknown subcommand" in output


# ── Markdown ledger (job_controller.py) ───────────────────────────────


class TestMarkdownLedger:
    @pytest.fixture
    def controller(self, tmp_path: Path) -> JobController:
        return JobController(root=tmp_path / ".hermes-orchestrator")

    def test_write_appends_trailing_newline(self, controller: JobController) -> None:
        job = controller.create_job(
            prompt="test",
            mode=JobMode.BUILD,
            repo_root=".",
            trusted_local=True,
        )
        path = controller.write_decision_ledger(
            job.job_id, "Picked plan A because of test coverage."
        )
        text = path.read_text(encoding="utf-8")
        assert text.endswith("\n")

    def test_write_preserves_existing_trailing_newline(
        self, controller: JobController
    ) -> None:
        job = controller.create_job(
            prompt="test",
            mode=JobMode.BUILD,
            repo_root=".",
            trusted_local=True,
        )
        content = "## decision\n\nfoo\n"
        path = controller.write_decision_ledger(job.job_id, content)
        assert path.read_text(encoding="utf-8") == content

    def test_write_overwrites_idempotently(
        self, controller: JobController
    ) -> None:
        job = controller.create_job(
            prompt="x",
            mode=JobMode.BUILD,
            repo_root=".",
            trusted_local=True,
        )
        controller.write_decision_ledger(job.job_id, "first cut")
        controller.write_decision_ledger(job.job_id, "second cut")
        text = (controller.job_dir(job.job_id) / DECISION_LEDGER_FILE).read_text(
            encoding="utf-8"
        )
        assert "second cut" in text
        assert "first cut" not in text

    def test_write_rejects_unknown_job(self, controller: JobController) -> None:
        with pytest.raises(JobNotFoundError):
            controller.write_decision_ledger("ghost", "content")

    def test_decision_ledger_lands_in_github_bundle(
        self, controller: JobController
    ) -> None:
        job = controller.create_job(
            prompt="bundle test",
            mode=JobMode.REFACTOR,
            repo_root=".",
            trusted_local=True,
        )
        controller.write_decision_ledger(job.job_id, "## chose path X")
        gdir = controller.prepare_github_artifacts(job.job_id)
        copied = gdir / DECISION_LEDGER_FILE
        assert copied.is_file()
        manifest = json.loads((gdir / "manifest.json").read_text(encoding="utf-8"))
        assert DECISION_LEDGER_FILE in manifest["files"]
