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

    def test_review_rejected_blocked_task_is_negative_even_with_gates(
        self, kanban_home, store
    ):
        """A task parked in blocked by the review-reject limit has a
        reviewer run closed as 'completed' — it must never ingest as a
        positive, even when the caller supplies passing gates."""
        with kb.connect() as conn:
            task_id = kb.create_task(
                conn, title="rejected work", assignee="executor"
            )
            assert kb.claim_task(conn, task_id) is not None
            kb.complete_task(
                conn, task_id, result="attempt",
                review_before_done=True, reviewer_profile="critic",
            )
            assert kb.claim_review_task(conn, task_id) is not None
            kb.reject_review(
                conn, task_id, critique="not acceptable",
                reviewer="critic", reject_limit=1,
            )
            assert kb.get_task(conn, task_id).status == "blocked"

        candidate = from_kanban_outcome(
            task_id, store,
            quality=QualityGates(
                tests_passed=True,
                reviewer_passed=True,
                rollback_available=True,
            ),
        )

        assert candidate is not None
        assert candidate.trace_type == TraceType.FAILED_ATTEMPT
        assert NEGATIVE_EXAMPLE in candidate.labels
        assert candidate.content["status"] == "blocked"

    def test_task_awaiting_review_returns_none(self, kanban_home, store):
        """A completed builder run whose task sits in the review column is
        mid-flight, not a terminal outcome."""
        with kb.connect() as conn:
            task_id = kb.create_task(
                conn, title="under review", assignee="executor"
            )
            assert kb.claim_task(conn, task_id) is not None
            kb.complete_task(
                conn, task_id, result="attempt", review_before_done=True
            )
            assert kb.get_task(conn, task_id).status == "review"

        assert from_kanban_outcome(task_id, store) is None

    def test_reclaimed_run_is_not_ingested(self, kanban_home, store):
        """A lost claim is an infrastructure event, not a model failure —
        it must never mint a negative example."""
        with kb.connect() as conn:
            task_id = kb.create_task(conn, title="slow host", assignee="executor")
            assert kb.claim_task(conn, task_id) is not None
            with kb.write_txn(conn):
                kb._end_run(conn, task_id, outcome="reclaimed")
                conn.execute(
                    "UPDATE tasks SET status='ready', claim_lock=NULL, "
                    "claim_expires=NULL WHERE id=?",
                    (task_id,),
                )

        assert from_kanban_outcome(task_id, store) is None
        assert not any("rejected" in d for d in store.load_diagnostics)

    def test_large_error_log_still_ingests_as_negative(self, kanban_home, store):
        """First-party crash logs are REPUTABLE provenance — a 25KB error
        must not be rejected as bulk-scraped content."""
        with kb.connect() as conn:
            task_id = kb.create_task(conn, title="crashy", assignee="executor")
            assert kb.claim_task(conn, task_id) is not None
            with kb.write_txn(conn):
                kb._end_run(
                    conn, task_id, outcome="crashed",
                    error="Traceback (most recent call last)\n" + ("x" * 25000),
                )
                conn.execute(
                    "UPDATE tasks SET status='blocked' WHERE id=?", (task_id,)
                )

        candidate = from_kanban_outcome(task_id, store)

        assert candidate is not None
        assert candidate.trace_type == TraceType.FAILED_ATTEMPT
        # Oversized fields are clipped, not refused.
        assert len(candidate.content["error"]) <= 4000

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

    def test_no_kanban_db_created_as_side_effect(self, tmp_path, monkeypatch):
        """The describer's outcome lookup is read-only: on a home with no
        kanban usage it must not create the DB."""
        home = tmp_path / ".hermes"
        home.mkdir()
        monkeypatch.setenv("HERMES_HOME", str(home))
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        from hermes_cli.profile_describer import _collect_outcome_summary

        assert _collect_outcome_summary("executor") is None
        assert not (home / "kanban.db").exists()

    def test_summary_reflects_runs_and_reviews(self, kanban_home):
        from hermes_cli.profile_describer import _collect_outcome_summary

        with kb.connect() as conn:
            _run_task(conn, complete=True, assignee="executor")
            _run_task(conn, complete=False, assignee="executor")

        summary = _collect_outcome_summary("executor")
        assert summary is not None
        assert "completed=1" in summary
        assert "blocked=1" in summary
