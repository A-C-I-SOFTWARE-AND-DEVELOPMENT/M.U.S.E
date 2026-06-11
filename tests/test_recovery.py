"""Tests for hermes_cli.recovery — disconnect/restart recovery.

Recovery glues the queue and checkpoint store together. These tests
seed both stores with a known state, then run recovery and assert the
expected actions and per-job report.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from hermes_cli.checkpoints import (
    CheckpointPhase,
    CheckpointStore,
    WorkerCheckpointStatus,
)
from hermes_cli.job_queue import (
    JobQueue,
    QueueState,
    WorkerQueueEntry,
    WorkerStatus,
)
from hermes_cli.recovery import (
    DEFAULT_STALE_WORKER_SECONDS,
    JobRecoveryReport,
    RecoveryManager,
    query_queue_state,
    resume_job_by_id,
)


@pytest.fixture
def root(tmp_path: Path) -> Path:
    return tmp_path / ".hermes-orchestrator"


@pytest.fixture
def queue(root: Path) -> JobQueue:
    return JobQueue(root=root)


@pytest.fixture
def checkpoints(root: Path) -> CheckpointStore:
    return CheckpointStore(root=root)


@pytest.fixture
def mgr(queue: JobQueue, checkpoints: CheckpointStore) -> RecoveryManager:
    return RecoveryManager(queue=queue, checkpoints=checkpoints)


# ──────────────────────────────────────────────────────────────────────
# detect_incomplete_jobs
# ──────────────────────────────────────────────────────────────────────


class TestDetectIncompleteJobs:
    def test_empty_queue(self, mgr: RecoveryManager):
        assert mgr.detect_incomplete_jobs() == []

    def test_skips_queued_and_terminal(
        self, queue: JobQueue, mgr: RecoveryManager
    ):
        queue.add_job("a", state=QueueState.QUEUED)
        queue.add_job("b", state=QueueState.COMPLETED)
        queue.add_job("c", state=QueueState.CANCELLED)
        queue.add_job("d", state=QueueState.RUNNING)
        queue.add_job("e", state=QueueState.PAUSED)
        queue.add_job("f", state=QueueState.DISCONNECTED)
        queue.add_job("g", state=QueueState.FAILED)
        ids = sorted(e.job_id for e in mgr.detect_incomplete_jobs())
        assert ids == ["d", "e", "f", "g"]


# ──────────────────────────────────────────────────────────────────────
# detect_interrupted_phase
# ──────────────────────────────────────────────────────────────────────


class TestDetectInterruptedPhase:
    def test_no_checkpoints(self, queue: JobQueue, mgr: RecoveryManager):
        queue.add_job("j", state=QueueState.RUNNING)
        phase, cp = mgr.detect_interrupted_phase("j")
        assert phase is None and cp is None

    def test_returns_latest_phase_and_cp(
        self,
        queue: JobQueue,
        checkpoints: CheckpointStore,
        mgr: RecoveryManager,
    ):
        queue.add_job("j", state=QueueState.RUNNING)
        checkpoints.create_checkpoint("j", CheckpointPhase.PRE_IMPLEMENTATION)
        latest = checkpoints.create_checkpoint(
            "j", CheckpointPhase.PRE_VALIDATION
        )
        phase, cp = mgr.detect_interrupted_phase("j")
        assert phase == CheckpointPhase.PRE_VALIDATION
        assert cp.checkpoint_id == latest.checkpoint_id  # ty: ignore[unresolved-attribute]  # mock/duck-typed test fixture


# ──────────────────────────────────────────────────────────────────────
# find_stale_workers
# ──────────────────────────────────────────────────────────────────────


class TestFindStaleWorkers:
    def test_empty(self, queue: JobQueue, mgr: RecoveryManager):
        queue.add_job("j", state=QueueState.RUNNING)
        assert mgr.find_stale_workers(queue.get_job("j"), now=1000.0) == []

    def test_stale_running_workers(
        self, queue: JobQueue, mgr: RecoveryManager
    ):
        now = 10_000.0
        old = now - DEFAULT_STALE_WORKER_SECONDS - 10
        queue.add_job("j", state=QueueState.RUNNING, workers=[
            WorkerQueueEntry(
                worker_id="w1",
                status=WorkerStatus.RUNNING,
                last_heartbeat=old,
            ),
            WorkerQueueEntry(
                worker_id="w2",
                status=WorkerStatus.RUNNING,
                last_heartbeat=now - 5,
            ),
        ])
        stale = mgr.find_stale_workers(queue.get_job("j"), now=now)
        assert [w.worker_id for w in stale] == ["w1"]

    def test_skips_pending_zero_heartbeat(
        self, queue: JobQueue, mgr: RecoveryManager
    ):
        # last_heartbeat==0 means "never started" — not stale.
        queue.add_job("j", state=QueueState.RUNNING, workers=[
            WorkerQueueEntry(
                worker_id="w1",
                status=WorkerStatus.RUNNING,
                last_heartbeat=0.0,
            ),
        ])
        stale = mgr.find_stale_workers(queue.get_job("j"), now=10_000.0)
        assert stale == []

    def test_skips_terminal_workers(
        self, queue: JobQueue, mgr: RecoveryManager
    ):
        now = 10_000.0
        old = now - DEFAULT_STALE_WORKER_SECONDS - 10
        queue.add_job("j", state=QueueState.RUNNING, workers=[
            WorkerQueueEntry(
                worker_id="w1",
                status=WorkerStatus.SUCCEEDED,
                last_heartbeat=old,
            ),
            WorkerQueueEntry(
                worker_id="w2",
                status=WorkerStatus.FAILED,
                last_heartbeat=old,
            ),
        ])
        assert mgr.find_stale_workers(queue.get_job("j"), now=now) == []


# ──────────────────────────────────────────────────────────────────────
# recover_job
# ──────────────────────────────────────────────────────────────────────


class TestRecoverJob:
    def test_terminal_job_skipped(
        self, queue: JobQueue, mgr: RecoveryManager
    ):
        queue.add_job("j", state=QueueState.COMPLETED)
        report = mgr.recover_job("j")
        assert report.queue_state_before == QueueState.COMPLETED
        assert report.queue_state_after == QueueState.COMPLETED
        assert report.requires_approval is False
        assert any("terminal" in n for n in report.notes)

    def test_clean_resume_paused(
        self,
        queue: JobQueue,
        checkpoints: CheckpointStore,
        mgr: RecoveryManager,
    ):
        queue.add_job("j", state=QueueState.PAUSED, workers=[
            WorkerQueueEntry(
                worker_id="w1",
                status=WorkerStatus.RUNNING,
                last_heartbeat=time.time(),
            ),
        ])
        checkpoints.create_checkpoint("j", CheckpointPhase.PRE_VALIDATION)
        report = mgr.recover_job("j")
        assert report.queue_state_after == QueueState.QUEUED
        assert report.last_safe_phase == CheckpointPhase.PRE_VALIDATION
        assert report.resume_phase == CheckpointPhase.PRE_VALIDATION
        assert report.requires_approval is True

    def test_stale_workers_get_blocked(
        self,
        queue: JobQueue,
        checkpoints: CheckpointStore,
        mgr: RecoveryManager,
    ):
        now = 10_000.0
        old = now - DEFAULT_STALE_WORKER_SECONDS - 100
        queue.add_job("j", state=QueueState.RUNNING, workers=[
            WorkerQueueEntry(
                worker_id="w1",
                status=WorkerStatus.RUNNING,
                last_heartbeat=old,
            ),
        ])
        checkpoints.create_checkpoint("j", CheckpointPhase.PRE_IMPLEMENTATION)
        report = mgr.recover_job("j", now=now)
        assert report.queue_state_after == QueueState.BLOCKED
        # The action list includes the stale-blocked record.
        assert any(
            a.action == "stale_blocked" and a.worker_id == "w1"
            for a in report.actions
        )
        # And the worker is now persisted as blocked.
        e = queue.get_job("j")
        assert e.worker("w1").status == WorkerStatus.BLOCKED  # ty: ignore[unresolved-attribute]  # mock/duck-typed test fixture

    def test_disconnected_worker_is_retained(
        self,
        queue: JobQueue,
        mgr: RecoveryManager,
    ):
        queue.add_job("j", state=QueueState.DISCONNECTED, workers=[
            WorkerQueueEntry(
                worker_id="w1",
                status=WorkerStatus.DISCONNECTED,
                pending_prompt="finish step 3",
                pending_output="halfway done",
            ),
        ])
        report = mgr.recover_job("j")
        # DISCONNECTED is preserved — explicit reconnect required.
        assert report.queue_state_after == QueueState.DISCONNECTED
        actions = {a.action for a in report.actions}
        assert "disconnected_retained" in actions
        # Pending IO is still there for replay.
        e = queue.get_job("j")
        assert e.worker("w1").pending_prompt == "finish step 3"  # ty: ignore[unresolved-attribute]  # mock/duck-typed test fixture
        assert e.worker("w1").pending_output == "halfway done"  # ty: ignore[unresolved-attribute]  # mock/duck-typed test fixture

    def test_failed_job_not_silently_requeued(
        self, queue: JobQueue, mgr: RecoveryManager
    ):
        queue.add_job("j", state=QueueState.FAILED, workers=[
            WorkerQueueEntry(
                worker_id="w1",
                status=WorkerStatus.FAILED,
                last_heartbeat=time.time(),
            ),
        ])
        report = mgr.recover_job("j")
        assert report.queue_state_after == QueueState.FAILED
        assert any("explicit retry" in n for n in report.notes)

    def test_recovered_at_stamped(
        self, queue: JobQueue, mgr: RecoveryManager
    ):
        queue.add_job("j", state=QueueState.PAUSED)
        before = time.time()
        mgr.recover_job("j")
        e = queue.get_job("j")
        assert e.recovered_at >= before

    def test_last_checkpoint_pinned(
        self,
        queue: JobQueue,
        checkpoints: CheckpointStore,
        mgr: RecoveryManager,
    ):
        queue.add_job("j", state=QueueState.PAUSED)
        cp = checkpoints.create_checkpoint(
            "j", CheckpointPhase.PRE_VALIDATION,
        )
        mgr.recover_job("j")
        e = queue.get_job("j")
        assert e.last_phase == CheckpointPhase.PRE_VALIDATION
        assert e.last_checkpoint_id == cp.checkpoint_id

    def test_pre_publish_does_not_auto_advance(
        self,
        queue: JobQueue,
        checkpoints: CheckpointStore,
        mgr: RecoveryManager,
    ):
        # Even if we had a pre_publish checkpoint, recovery never
        # auto-publishes — it leaves requires_approval=True.
        queue.add_job("j", state=QueueState.PAUSED)
        checkpoints.create_checkpoint("j", CheckpointPhase.PRE_PUBLISH)
        report = mgr.recover_job("j")
        assert report.requires_approval is True
        assert report.resume_phase == CheckpointPhase.PRE_PUBLISH


# ──────────────────────────────────────────────────────────────────────
# recover_all
# ──────────────────────────────────────────────────────────────────────


class TestRecoverAll:
    def test_runs_one_report_per_incomplete_job(
        self,
        queue: JobQueue,
        checkpoints: CheckpointStore,
        mgr: RecoveryManager,
    ):
        queue.add_job("a", state=QueueState.QUEUED)              # skipped
        queue.add_job("b", state=QueueState.RUNNING)             # included
        queue.add_job("c", state=QueueState.PAUSED)              # included
        queue.add_job("d", state=QueueState.COMPLETED)           # skipped
        report = mgr.recover_all()
        ids = sorted(j.job_id for j in report.jobs)
        assert ids == ["b", "c"]
        assert report.finished_at >= report.started_at

    def test_report_to_dict_is_json_safe(
        self, queue: JobQueue, mgr: RecoveryManager
    ):
        import json
        queue.add_job("j", state=QueueState.PAUSED)
        report = mgr.recover_all()
        # Should round-trip cleanly through JSON.
        json.dumps(report.to_dict())


# ──────────────────────────────────────────────────────────────────────
# log preservation
# ──────────────────────────────────────────────────────────────────────


class TestLogPreservation:
    def test_preserves_existing_logs(
        self,
        root: Path,
        queue: JobQueue,
        mgr: RecoveryManager,
    ):
        # Seed a fake log file inside <root>/logs/<job-id>/.
        log_dir = root / "logs" / "j"
        log_dir.mkdir(parents=True)
        (log_dir / "worker.log").write_text("hello\n")

        queue.add_job("j", state=QueueState.PAUSED)
        mgr.recover_job("j")

        # A timestamped recovered/ subfolder should contain the copy.
        recovered_root = log_dir / "recovered"
        assert recovered_root.exists()
        # Exactly one stamp directory.
        stamps = list(recovered_root.iterdir())
        assert len(stamps) == 1
        assert (stamps[0] / "worker.log").read_text() == "hello\n"

    def test_no_logs_no_problem(
        self, queue: JobQueue, mgr: RecoveryManager
    ):
        queue.add_job("j", state=QueueState.PAUSED)
        # Should not raise even though logs/j/ doesn't exist.
        mgr.recover_job("j")


# ──────────────────────────────────────────────────────────────────────
# API-facing convenience helpers
# ──────────────────────────────────────────────────────────────────────


class TestApiHelpers:
    def test_query_queue_state(self, root: Path, queue: JobQueue):
        queue.add_job("a")
        queue.add_job("b", state=QueueState.PAUSED)
        view = query_queue_state(root=root)
        assert "entries" in view
        assert len(view["entries"]) == 2
        assert view["counts"][QueueState.QUEUED] == 1
        assert view["counts"][QueueState.PAUSED] == 1

    def test_query_queue_state_no_queue_file(self, root: Path):
        view = query_queue_state(root=root)
        assert view == {"entries": [], "counts": {}}

    def test_resume_job_by_id(self, root: Path, queue: JobQueue):
        queue.add_job("j", state=QueueState.PAUSED)
        report = resume_job_by_id("j", root=root)
        assert isinstance(report, JobRecoveryReport)
        assert report.queue_state_after == QueueState.QUEUED

    def test_from_root_env_var(self, tmp_path: Path, monkeypatch):
        monkeypatch.setenv(
            "HERMES_ORCHESTRATOR_HOME", str(tmp_path / "h")
        )
        mgr = RecoveryManager.from_root()
        assert mgr.queue.root == tmp_path / "h"
        assert mgr.checkpoints.root == tmp_path / "h"
