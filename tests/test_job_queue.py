"""Tests for muse_cli.job_queue — the persistent orchestrator queue.

Every test runs against a tmp_path root so we never touch the user's
``.hermes-orchestrator``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from muse_cli.job_queue import (
    JobQueue,
    JobQueueError,
    JobQueueNotFoundError,
    QueueState,
    QUEUE_SCHEMA_VERSION,
    WorkerNotFoundError,
    WorkerQueueEntry,
    WorkerStatus,
)


@pytest.fixture
def queue(tmp_path: Path) -> JobQueue:
    return JobQueue(root=tmp_path / ".hermes-orchestrator")


# ──────────────────────────────────────────────────────────────────────
# add_job / list_jobs / get_job
# ──────────────────────────────────────────────────────────────────────


class TestAddJob:
    def test_creates_queue_file_on_first_add(self, queue: JobQueue):
        assert not queue.queue_path.exists()
        entry = queue.add_job("job-1", prompt="do the thing", mode="build")
        assert queue.queue_path.exists()
        assert entry.job_id == "job-1"
        assert entry.state == QueueState.QUEUED
        assert entry.created_at > 0
        assert entry.updated_at == entry.created_at

    def test_persists_schema_version(self, queue: JobQueue):
        queue.add_job("job-1")
        data = json.loads(queue.queue_path.read_text())
        assert data["version"] == QUEUE_SCHEMA_VERSION
        assert isinstance(data["entries"], list)

    def test_rejects_duplicate_job_id(self, queue: JobQueue):
        queue.add_job("job-1")
        with pytest.raises(JobQueueError, match="already queued"):
            queue.add_job("job-1")

    def test_rejects_empty_job_id(self, queue: JobQueue):
        with pytest.raises(JobQueueError, match="job_id is required"):
            queue.add_job("")
        with pytest.raises(JobQueueError, match="job_id is required"):
            queue.add_job("   ")

    def test_rejects_unknown_state(self, queue: JobQueue):
        with pytest.raises(JobQueueError, match="state must be one of"):
            queue.add_job("job-1", state="invented")

    def test_accepts_workers_as_dicts_and_dataclasses(self, queue: JobQueue):
        entry = queue.add_job(
            "job-1",
            workers=[
                WorkerQueueEntry(worker_id="w1", role="builder"),
                {"worker_id": "w2", "role": "reviewer"},
            ],
        )
        assert [w.worker_id for w in entry.workers] == ["w1", "w2"]
        assert entry.worker("w1").role == "builder"  # ty: ignore[unresolved-attribute]  # mock/duck-typed test fixture
        assert entry.worker("w2").role == "reviewer"  # ty: ignore[unresolved-attribute]  # mock/duck-typed test fixture


class TestListJobs:
    def test_returns_empty_when_no_queue_file(self, queue: JobQueue):
        assert queue.list_jobs() == []

    def test_sorted_oldest_first(self, queue: JobQueue, monkeypatch):
        # Force created_at by patching time.
        import muse_cli.job_queue as jq

        times = iter([100.0, 200.0, 150.0])
        monkeypatch.setattr(jq, "_now", lambda: next(times))
        queue.add_job("a")
        queue.add_job("b")
        queue.add_job("c")
        ids = [e.job_id for e in queue.list_jobs()]
        assert ids == ["a", "c", "b"]

    def test_filter_by_state(self, queue: JobQueue):
        queue.add_job("a")
        queue.add_job("b")
        queue.set_state("b", QueueState.PAUSED)
        assert [e.job_id for e in queue.list_jobs(state=QueueState.QUEUED)] == ["a"]
        assert [e.job_id for e in queue.list_jobs(state=QueueState.PAUSED)] == ["b"]

    def test_filter_by_states(self, queue: JobQueue):
        queue.add_job("a")
        queue.add_job("b")
        queue.add_job("c")
        queue.set_state("b", QueueState.PAUSED)
        queue.set_state("c", QueueState.CANCELLED)
        ids = sorted(
            e.job_id
            for e in queue.list_jobs(states=[QueueState.PAUSED, QueueState.CANCELLED])
        )
        assert ids == ["b", "c"]


class TestGetJob:
    def test_round_trip(self, queue: JobQueue):
        queue.add_job("job-1", prompt="x", mode="build", repo_root="/tmp")
        out = queue.get_job("job-1")
        assert out.job_id == "job-1"
        assert out.prompt == "x"
        assert out.mode == "build"
        assert out.repo_root == "/tmp"

    def test_raises_when_missing(self, queue: JobQueue):
        with pytest.raises(JobQueueNotFoundError):
            queue.get_job("nope")


# ──────────────────────────────────────────────────────────────────────
# pause / resume / cancel / remove
# ──────────────────────────────────────────────────────────────────────


class TestPauseResumeCancel:
    def test_pause_running_job(self, queue: JobQueue):
        queue.add_job("j", state=QueueState.RUNNING)
        e = queue.pause_job("j", note="user requested")
        assert e.state == QueueState.PAUSED
        assert e.note == "user requested"

    def test_pause_terminal_fails(self, queue: JobQueue):
        queue.add_job("j")
        queue.cancel_job("j")
        with pytest.raises(JobQueueError, match="terminal"):
            queue.pause_job("j")

    def test_resume_paused(self, queue: JobQueue):
        queue.add_job("j")
        queue.pause_job("j")
        e = queue.resume_job("j")
        assert e.state == QueueState.QUEUED

    def test_resume_from_blocked(self, queue: JobQueue):
        queue.add_job("j", state=QueueState.BLOCKED)
        e = queue.resume_job("j")
        assert e.state == QueueState.QUEUED

    def test_resume_running_fails(self, queue: JobQueue):
        queue.add_job("j", state=QueueState.RUNNING)
        with pytest.raises(JobQueueError, match="cannot resume"):
            queue.resume_job("j")

    def test_cancel_idempotent(self, queue: JobQueue):
        queue.add_job("j")
        queue.cancel_job("j")
        # second cancel does not raise
        queue.cancel_job("j")
        assert queue.get_job("j").state == QueueState.CANCELLED

    def test_cancel_marks_workers_cancelled(self, queue: JobQueue):
        queue.add_job("j", workers=[
            WorkerQueueEntry(worker_id="w1", status=WorkerStatus.RUNNING),
            WorkerQueueEntry(worker_id="w2", status=WorkerStatus.SUCCEEDED),
        ])
        e = queue.cancel_job("j")
        assert e.worker("w1").status == WorkerStatus.CANCELLED  # ty: ignore[unresolved-attribute]  # mock/duck-typed test fixture
        # already-terminal worker stays succeeded
        assert e.worker("w2").status == WorkerStatus.SUCCEEDED  # ty: ignore[unresolved-attribute]  # mock/duck-typed test fixture

    def test_remove_job(self, queue: JobQueue):
        queue.add_job("j")
        queue.remove_job("j")
        assert queue.list_jobs() == []

    def test_remove_missing(self, queue: JobQueue):
        with pytest.raises(JobQueueNotFoundError):
            queue.remove_job("nope")


# ──────────────────────────────────────────────────────────────────────
# worker-level operations
# ──────────────────────────────────────────────────────────────────────


class TestWorkers:
    def test_add_worker(self, queue: JobQueue):
        queue.add_job("j")
        e = queue.add_worker("j", "w1", role="builder", target_tool="codex")
        assert e.worker("w1").role == "builder"  # ty: ignore[unresolved-attribute]  # mock/duck-typed test fixture
        assert e.worker("w1").target_tool == "codex"  # ty: ignore[unresolved-attribute]  # mock/duck-typed test fixture
        assert e.worker("w1").status == WorkerStatus.PENDING  # ty: ignore[unresolved-attribute]  # mock/duck-typed test fixture

    def test_add_duplicate_worker_fails(self, queue: JobQueue):
        queue.add_job("j", workers=[WorkerQueueEntry(worker_id="w1")])
        with pytest.raises(JobQueueError, match="already exists"):
            queue.add_worker("j", "w1")

    def test_set_worker_status_heartbeat(self, queue: JobQueue):
        queue.add_job("j", workers=[WorkerQueueEntry(worker_id="w1")])
        e = queue.set_worker_status(
            "j", "w1", WorkerStatus.RUNNING, heartbeat=True
        )
        assert e.worker("w1").status == WorkerStatus.RUNNING  # ty: ignore[unresolved-attribute]  # mock/duck-typed test fixture
        assert e.worker("w1").last_heartbeat > 0  # ty: ignore[unresolved-attribute]  # mock/duck-typed test fixture

    def test_set_worker_status_unknown_worker(self, queue: JobQueue):
        queue.add_job("j")
        with pytest.raises(WorkerNotFoundError):
            queue.set_worker_status("j", "ghost", WorkerStatus.RUNNING)

    def test_retry_failed_worker(self, queue: JobQueue):
        queue.add_job("j", state=QueueState.FAILED, workers=[
            WorkerQueueEntry(
                worker_id="w1",
                status=WorkerStatus.FAILED,
                last_error="boom",
            ),
        ])
        e = queue.retry_worker("j", "w1")
        assert e.worker("w1").status == WorkerStatus.PENDING  # ty: ignore[unresolved-attribute]  # mock/duck-typed test fixture
        assert e.worker("w1").attempts == 1  # ty: ignore[unresolved-attribute]  # mock/duck-typed test fixture
        assert e.worker("w1").last_error is None  # ty: ignore[unresolved-attribute]  # mock/duck-typed test fixture
        # failed job is lifted back to queued
        assert e.state == QueueState.QUEUED

    def test_retry_succeeded_worker_fails(self, queue: JobQueue):
        queue.add_job("j", workers=[
            WorkerQueueEntry(worker_id="w1", status=WorkerStatus.SUCCEEDED),
        ])
        with pytest.raises(JobQueueError, match="only failed/disconnected"):
            queue.retry_worker("j", "w1")

    def test_mark_worker_disconnected_cascades(self, queue: JobQueue):
        queue.add_job("j", state=QueueState.RUNNING, workers=[
            WorkerQueueEntry(worker_id="w1", status=WorkerStatus.RUNNING),
        ])
        e = queue.mark_worker_disconnected("j", "w1", error="tunnel down")
        assert e.worker("w1").status == WorkerStatus.DISCONNECTED  # ty: ignore[unresolved-attribute]  # mock/duck-typed test fixture
        assert e.worker("w1").disconnected_at > 0  # ty: ignore[unresolved-attribute]  # mock/duck-typed test fixture
        assert e.worker("w1").last_error == "tunnel down"  # ty: ignore[unresolved-attribute]  # mock/duck-typed test fixture
        # Sole running worker → entry flips to DISCONNECTED.
        assert e.state == QueueState.DISCONNECTED

    def test_mark_disconnected_no_cascade_when_other_runs(self, queue: JobQueue):
        queue.add_job("j", state=QueueState.RUNNING, workers=[
            WorkerQueueEntry(worker_id="w1", status=WorkerStatus.RUNNING),
            WorkerQueueEntry(worker_id="w2", status=WorkerStatus.RUNNING),
        ])
        e = queue.mark_worker_disconnected("j", "w1")
        assert e.worker("w1").status == WorkerStatus.DISCONNECTED  # ty: ignore[unresolved-attribute]  # mock/duck-typed test fixture
        # Other worker still running, so entry stays in RUNNING.
        assert e.state == QueueState.RUNNING

    def test_mark_worker_reconnected_lifts_entry(self, queue: JobQueue):
        queue.add_job("j", state=QueueState.RUNNING, workers=[
            WorkerQueueEntry(worker_id="w1", status=WorkerStatus.RUNNING),
        ])
        queue.mark_worker_disconnected("j", "w1")
        e = queue.mark_worker_reconnected("j", "w1")
        assert e.worker("w1").status == WorkerStatus.PENDING  # ty: ignore[unresolved-attribute]  # mock/duck-typed test fixture
        assert e.worker("w1").last_heartbeat > 0  # ty: ignore[unresolved-attribute]  # mock/duck-typed test fixture
        assert e.state == QueueState.QUEUED

    def test_reconnect_non_disconnected_fails(self, queue: JobQueue):
        queue.add_job("j", workers=[
            WorkerQueueEntry(worker_id="w1", status=WorkerStatus.RUNNING),
        ])
        with pytest.raises(JobQueueError, match="not disconnected"):
            queue.mark_worker_reconnected("j", "w1")

    def test_pending_io_preserved_across_disconnect(self, queue: JobQueue):
        queue.add_job("j", workers=[
            WorkerQueueEntry(worker_id="w1", status=WorkerStatus.RUNNING),
        ])
        queue.set_pending_worker_io(
            "j", "w1", prompt="prompt-1", output="partial-output",
        )
        queue.mark_worker_disconnected("j", "w1")
        # The dispatcher reads these to know what to re-deliver:
        e = queue.get_job("j")
        assert e.worker("w1").pending_prompt == "prompt-1"  # ty: ignore[unresolved-attribute]  # mock/duck-typed test fixture
        assert e.worker("w1").pending_output == "partial-output"  # ty: ignore[unresolved-attribute]  # mock/duck-typed test fixture


# ──────────────────────────────────────────────────────────────────────
# Misc
# ──────────────────────────────────────────────────────────────────────


class TestPersistence:
    def test_reload_after_restart(self, tmp_path: Path):
        root = tmp_path / ".hermes-orchestrator"
        q1 = JobQueue(root=root)
        q1.add_job("j", prompt="x", mode="build")
        q1.set_state("j", QueueState.RUNNING)
        q1.add_worker("j", "w1", role="builder")
        q1.set_worker_status("j", "w1", WorkerStatus.RUNNING, heartbeat=True)

        # Simulate Termux restart: fresh queue object, same root.
        q2 = JobQueue(root=root)
        e = q2.get_job("j")
        assert e.state == QueueState.RUNNING
        assert e.worker("w1").status == WorkerStatus.RUNNING  # ty: ignore[unresolved-attribute]  # mock/duck-typed test fixture
        assert e.worker("w1").last_heartbeat > 0  # ty: ignore[unresolved-attribute]  # mock/duck-typed test fixture

    def test_corrupt_queue_raises(self, tmp_path: Path):
        root = tmp_path / ".hermes-orchestrator"
        root.mkdir()
        (root / "queue.json").write_text("{not json")
        q = JobQueue(root=root)
        with pytest.raises(JobQueueError, match="corrupt"):
            q.list_jobs()

    def test_future_schema_version_refused(self, tmp_path: Path):
        root = tmp_path / ".hermes-orchestrator"
        root.mkdir()
        (root / "queue.json").write_text(
            json.dumps({
                "version": QUEUE_SCHEMA_VERSION + 1,
                "entries": [],
            }),
        )
        q = JobQueue(root=root)
        with pytest.raises(JobQueueError, match="newer than"):
            q.list_jobs()

    def test_env_var_root(self, tmp_path: Path, monkeypatch):
        monkeypatch.setenv("HERMES_ORCHESTRATOR_HOME", str(tmp_path / "x"))
        q = JobQueue()
        assert q.root == tmp_path / "x"


class TestSetPhaseCheckpoint:
    def test_sets_phase_and_id(self, queue: JobQueue):
        queue.add_job("j")
        e = queue.set_phase_checkpoint("j", "pre_validation", "cp-1")
        assert e.last_phase == "pre_validation"
        assert e.last_checkpoint_id == "cp-1"


class TestMarkRecovered:
    def test_stamps_timestamp(self, queue: JobQueue):
        queue.add_job("j")
        e = queue.mark_recovered("j", recovered_at=12345.0)
        assert e.recovered_at == 12345.0

    def test_default_uses_now(self, queue: JobQueue):
        queue.add_job("j")
        e = queue.mark_recovered("j")
        assert e.recovered_at > 0
