"""Tests for the kanban → learning-dataset flywheel bridge."""

from __future__ import annotations

from pathlib import Path

import pytest

from hermes_cli import kanban_db as kb
from hermes_cli.jarvis_prime.learning_dataset import (
    NEGATIVE_EXAMPLE,
    CandidateStatus,
    DatasetStore,
    QualityGates,
    TraceType,
)
from hermes_cli.jarvis_prime.learning_ingest import from_kanban_outcome


@pytest.fixture
def kanban_home(tmp_path, monkeypatch):
    home = tmp_path / ".hermes"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    kb.init_db()
    return home


@pytest.fixture
def store(tmp_path):
    return DatasetStore(path=tmp_path / "dataset.jsonl")


def _run_task(conn, *, complete: bool, assignee="executor"):
    task_id = kb.create_task(conn, title="ship feature X", assignee=assignee)
    claimed = kb.claim_task(conn, task_id)
    assert claimed is not None
    if complete:
        kb.complete_task(
            conn, task_id, result="shipped", summary="all tests pass"
        )
    else:
        kb.block_task(conn, task_id, reason="cannot reach the API")
    return task_id


class TestFromKanbanOutcome:
    def test_completed_without_gates_is_rejected_honestly(self, kanban_home, store):
        """A completed task can't become a positive example without real
        gate evidence — the pipeline never auto-mints a 'passed' trace."""
        with kb.connect() as conn:
            task_id = _run_task(conn, complete=True)

        assert from_kanban_outcome(task_id, store) is None
        assert any("quality gates" in d for d in store.load_diagnostics)

    def test_completed_task_becomes_coding_trace_pending(self, kanban_home, store):
        with kb.connect() as conn:
            task_id = _run_task(conn, complete=True)

        candidate = from_kanban_outcome(
            task_id, store,
            quality=QualityGates(
                tests_passed=True,
                reviewer_passed=True,
                rollback_available=True,
            ),
        )

        assert candidate is not None
        assert candidate.trace_type == TraceType.CODING_TASK
        # Pending until the owner approves — never auto-minted as passed.
        assert candidate.status == CandidateStatus.PENDING
        assert candidate.provenance.source_kind == "job"
        assert candidate.provenance.job_id == task_id
        assert f"kanban://default/{task_id}" == candidate.provenance.source_uri
        assert candidate.task_key == task_id
        assert NEGATIVE_EXAMPLE not in candidate.labels

    def test_failed_task_becomes_negative_example(self, kanban_home, store):
        with kb.connect() as conn:
            task_id = _run_task(conn, complete=False)

        candidate = from_kanban_outcome(task_id, store)

        assert candidate is not None
        assert candidate.trace_type == TraceType.FAILED_ATTEMPT
        assert NEGATIVE_EXAMPLE in candidate.labels
        assert candidate.content["outcome"] == "blocked"

    def test_unknown_task_returns_none(self, kanban_home, store):
        assert from_kanban_outcome("t_000000000000", store) is None

    def test_unfinished_task_returns_none(self, kanban_home, store):
        with kb.connect() as conn:
            task_id = kb.create_task(conn, title="still queued")
        assert from_kanban_outcome(task_id, store) is None

    def test_candidate_is_persisted(self, kanban_home, store, tmp_path):
        with kb.connect() as conn:
            task_id = _run_task(conn, complete=False)

        from_kanban_outcome(task_id, store)

        reloaded = DatasetStore.load(tmp_path / "dataset.jsonl")
        assert any(
            c.task_key == task_id for c in reloaded.candidates.values()
        )


class TestDescriberOutcomeSummary:
    def test_summary_none_without_history(self, kanban_home):
        from hermes_cli.profile_describer import _collect_outcome_summary

        assert _collect_outcome_summary("executor") is None

    def test_summary_reflects_runs_and_reviews(self, kanban_home):
        from hermes_cli.profile_describer import _collect_outcome_summary

        with kb.connect() as conn:
            _run_task(conn, complete=True, assignee="executor")
            _run_task(conn, complete=False, assignee="executor")

        summary = _collect_outcome_summary("executor")
        assert summary is not None
        assert "completed=1" in summary
        assert "blocked=1" in summary
