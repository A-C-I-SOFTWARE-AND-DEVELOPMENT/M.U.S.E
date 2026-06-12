"""Disconnect/restart recovery for the Hermes orchestrator.

Phase 08 mission: Hermes must survive phone-network disconnects, app
restarts, Termux restarts, Windows tunnel disconnects, and partial
worker failures. This module is the glue between :mod:`job_queue` and
:mod:`checkpoints` that makes recovery deterministic.

The flow is deliberately conservative:

1. On boot, :class:`RecoveryManager.detect_incomplete_jobs` scans the
   queue for entries in non-terminal, non-queued states (running,
   paused, blocked, disconnected, failed).

2. For each, :meth:`detect_interrupted_phase` reads the last
   checkpoint and asks: did we crash *before* implementation, *before*
   validation, or *before* publish?

3. Stale workers — those that haven't heartbeated within the
   configured TTL — are flipped to ``blocked``. The queue entry is
   *not* auto-resumed: recovery's job is to expose the situation, not
   to silently re-run someone's failed code.

4. The caller (usually a CLI ``hermes orchestrator recover`` or the
   API ``POST /recover``) inspects the :class:`RecoveryReport` and
   decides whether to re-queue.

5. Even when recovery does re-queue, the queue entry is marked
   ``recovered_at`` and any prior ``pre_publish`` checkpoint is
   *ignored* by the publisher: a human approval is mandatory before
   publish on a recovered job.

Nothing in this module talks to the network. It only reads/writes
``queue.json`` and the checkpoint store.
"""

from __future__ import annotations

import logging
import os
import shutil
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

from muse_cli.checkpoints import (
    Checkpoint,
    CheckpointPhase,
    CheckpointStore,
    ORCHESTRATOR_ROOT_DIRNAME,
)
from muse_cli.job_queue import (
    JobQueue,
    JobQueueEntry,
    JobQueueError,
    JobQueueNotFoundError,
    QueueState,
    WorkerNotFoundError,
    WorkerQueueEntry,
    WorkerStatus,
)

logger = logging.getLogger(__name__)

LOGS_DIRNAME = "logs"
RECOVERED_LOGS_DIRNAME = "recovered"

# Default: a worker is considered "stale" if it hasn't heartbeated in
# 10 minutes. The dispatcher writes a heartbeat each time it polls a
# worker, so anything older than this strongly implies the tunnel or
# the worker process is dead.
DEFAULT_STALE_WORKER_SECONDS = 10 * 60


# ──────────────────────────────────────────────────────────────────────
# Report dataclasses
# ──────────────────────────────────────────────────────────────────────


@dataclass
class WorkerRecoveryAction:
    """One worker-level action taken by recovery."""

    worker_id: str
    action: str           # "stale_blocked", "disconnected_retained", etc.
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class JobRecoveryReport:
    """Per-job recovery decision."""

    job_id: str
    queue_state_before: str
    queue_state_after: str
    last_safe_phase: str | None
    resume_phase: str | None
    requires_approval: bool
    actions: list[WorkerRecoveryAction] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "queue_state_before": self.queue_state_before,
            "queue_state_after": self.queue_state_after,
            "last_safe_phase": self.last_safe_phase,
            "resume_phase": self.resume_phase,
            "requires_approval": self.requires_approval,
            "actions": [a.to_dict() for a in self.actions],
            "notes": list(self.notes),
        }


@dataclass
class RecoveryReport:
    """Aggregated recovery report from one ``recover_all`` call."""

    started_at: float
    finished_at: float
    jobs: list[JobRecoveryReport] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "jobs": [j.to_dict() for j in self.jobs],
        }


# ──────────────────────────────────────────────────────────────────────
# Manager
# ──────────────────────────────────────────────────────────────────────


class RecoveryManager:
    """Coordinates queue + checkpoint store for disconnect recovery.

    Construct with a :class:`JobQueue` and :class:`CheckpointStore`
    that share the same root, or call :meth:`from_root` to build both
    from a single root path.
    """

    # Queue states that represent "we did not reach a terminal state
    # cleanly" and therefore need a look from recovery.
    INCOMPLETE_STATES = frozenset({
        QueueState.RUNNING,
        QueueState.PAUSED,
        QueueState.BLOCKED,
        QueueState.DISCONNECTED,
        QueueState.FAILED,
    })

    def __init__(
        self,
        queue: JobQueue,
        checkpoints: CheckpointStore,
        *,
        stale_worker_seconds: float = DEFAULT_STALE_WORKER_SECONDS,
        log_root: str | Path | None = None,
    ) -> None:
        self.queue = queue
        self.checkpoints = checkpoints
        self.stale_worker_seconds = float(stale_worker_seconds)
        if log_root is None:
            log_root = queue.root / LOGS_DIRNAME
        self.log_root = Path(log_root)

    @classmethod
    def from_root(
        cls,
        root: str | Path | None = None,
        *,
        stale_worker_seconds: float = DEFAULT_STALE_WORKER_SECONDS,
    ) -> "RecoveryManager":
        if root is None:
            env_root = os.environ.get("HERMES_ORCHESTRATOR_HOME")
            root = (
                Path(env_root) if env_root
                else Path.cwd() / ORCHESTRATOR_ROOT_DIRNAME
            )
        root = Path(root)
        return cls(
            queue=JobQueue(root=root),
            checkpoints=CheckpointStore(root=root),
            stale_worker_seconds=stale_worker_seconds,
            log_root=root / LOGS_DIRNAME,
        )

    # ── detection ─────────────────────────────────────────────────────

    def detect_incomplete_jobs(self) -> list[JobQueueEntry]:
        """Return every queue entry that needs a recovery decision.

        A job is "incomplete" if its queue state is one of running,
        paused, blocked, disconnected, or failed. Jobs in ``queued``
        are not incomplete — they simply haven't started yet.
        """
        return [
            entry for entry in self.queue.list_jobs()
            if entry.state in self.INCOMPLETE_STATES
        ]

    def detect_interrupted_phase(
        self, job_id: str
    ) -> tuple[str | None, Checkpoint | None]:
        """Determine the last safe phase reached for ``job_id``.

        Returns ``(safe_phase, latest_checkpoint)`` where ``safe_phase``
        is one of the phases in :class:`CheckpointPhase.ALL` or
        ``None`` if the job has no checkpoints (work was interrupted
        before the first safe point).
        """
        latest = self.checkpoints.latest(job_id)
        safe = self.checkpoints.latest_safe_phase(job_id)
        return safe, latest

    def find_stale_workers(
        self,
        entry: JobQueueEntry,
        *,
        now: float | None = None,
    ) -> list[WorkerQueueEntry]:
        """Return workers whose heartbeat is older than the TTL.

        A worker with ``last_heartbeat == 0`` is treated as
        non-stale — it just hasn't started yet. Workers in terminal
        statuses (succeeded/failed/cancelled) are skipped.
        """
        now = now if now is not None else time.time()
        threshold = now - self.stale_worker_seconds
        skip = {
            WorkerStatus.SUCCEEDED,
            WorkerStatus.FAILED,
            WorkerStatus.CANCELLED,
            WorkerStatus.PENDING,
        }
        stale: list[WorkerQueueEntry] = []
        for w in entry.workers:
            if w.status in skip:
                continue
            if w.last_heartbeat <= 0:
                continue
            if w.last_heartbeat < threshold:
                stale.append(w)
        return stale

    # ── action: per-job ───────────────────────────────────────────────

    def recover_job(
        self,
        job_id: str,
        *,
        now: float | None = None,
    ) -> JobRecoveryReport:
        """Recover a single job and return the per-job report.

        This is a pure orchestration step — it does not start workers.
        It only:

        * marks stale workers as ``blocked``
        * preserves logs into ``logs/<job-id>/recovered/<timestamp>/``
        * decides which phase a resume would start from
        * flags ``requires_approval`` so the publisher refuses to
          auto-push after a recovered run

        The queue entry's state is set back to ``queued`` only when a
        clean resume is possible (no stale-blocked workers remain in
        non-terminal status). Otherwise the entry is left at
        ``blocked`` for human inspection.
        """
        now = now if now is not None else time.time()
        entry = self.queue.get_job(job_id)
        state_before = entry.state

        if entry.state == QueueState.CANCELLED or entry.state == QueueState.COMPLETED:
            # Terminal — nothing to recover.
            return JobRecoveryReport(
                job_id=job_id,
                queue_state_before=state_before,
                queue_state_after=entry.state,
                last_safe_phase=None,
                resume_phase=None,
                requires_approval=False,
                notes=[f"job in terminal state {entry.state}; no recovery needed"],
            )

        safe_phase, latest_cp = self.detect_interrupted_phase(job_id)
        actions: list[WorkerRecoveryAction] = []
        notes: list[str] = []

        # Mark stale workers as blocked.
        for w in self.find_stale_workers(entry, now=now):
            try:
                self.queue.set_worker_status(
                    job_id,
                    w.worker_id,
                    WorkerStatus.BLOCKED,
                    error=f"stale: no heartbeat in {self.stale_worker_seconds:.0f}s",
                )
            except WorkerNotFoundError:
                # Concurrent mutation; skip and move on.
                continue
            actions.append(WorkerRecoveryAction(
                worker_id=w.worker_id,
                action="stale_blocked",
                reason=(
                    f"last_heartbeat={int(w.last_heartbeat)} "
                    f"(>{self.stale_worker_seconds:.0f}s ago)"
                ),
            ))

        # Re-load the entry after the stale-worker mutations.
        entry = self.queue.get_job(job_id)

        # Record the disconnected workers (without re-running them).
        for w in entry.workers:
            if w.status == WorkerStatus.DISCONNECTED:
                actions.append(WorkerRecoveryAction(
                    worker_id=w.worker_id,
                    action="disconnected_retained",
                    reason=(
                        "pending prompt/output preserved; "
                        "will resume when worker reconnects"
                    ),
                ))

        # Preserve logs (best-effort, never raises).
        self._preserve_logs(job_id, now=now)

        # Decide resume phase.
        resume_phase = self._resume_phase_for(safe_phase)

        # If there are workers stuck in BLOCKED/DISCONNECTED with no
        # successful peer, we leave the queue in ``blocked`` for a
        # human to deal with.
        leave_blocked = any(
            w.status in (WorkerStatus.BLOCKED, WorkerStatus.DISCONNECTED)
            for w in entry.workers
        )

        # If the entry was FAILED, we don't silently re-queue — only a
        # manual ``retry_worker`` lifts it back. Same for DISCONNECTED:
        # the tunnel must be back up first.
        if entry.state in (QueueState.FAILED, QueueState.DISCONNECTED):
            new_state = entry.state
            notes.append(
                f"job state {entry.state}: explicit retry/reconnect required"
            )
        elif leave_blocked:
            new_state = QueueState.BLOCKED
            notes.append("workers blocked/disconnected; queue left as blocked")
        else:
            new_state = QueueState.QUEUED
            notes.append("clean resume: queue set to queued")

        # Recovered jobs always require explicit human approval before
        # any publish step. The publisher enforces this by checking the
        # entry's ``recovered_at`` field at publish time.
        requires_approval = True

        if latest_cp is not None:
            self.queue.set_phase_checkpoint(
                job_id, latest_cp.phase, latest_cp.checkpoint_id
            )
        self.queue.set_state(
            job_id, new_state, note=f"recovered at {int(now)}"
        )
        self.queue.mark_recovered(job_id, recovered_at=now)

        notes.append(
            f"last_safe_phase={safe_phase!r}; resume_phase={resume_phase!r}"
        )
        if requires_approval:
            notes.append("requires_approval=True: do NOT auto-publish")

        return JobRecoveryReport(
            job_id=job_id,
            queue_state_before=state_before,
            queue_state_after=new_state,
            last_safe_phase=safe_phase,
            resume_phase=resume_phase,
            requires_approval=requires_approval,
            actions=actions,
            notes=notes,
        )

    def recover_all(self, *, now: float | None = None) -> RecoveryReport:
        """Walk the queue and recover every incomplete job."""
        now = now if now is not None else time.time()
        started = now
        reports: list[JobRecoveryReport] = []
        for entry in self.detect_incomplete_jobs():
            try:
                reports.append(self.recover_job(entry.job_id, now=now))
            except JobQueueNotFoundError:
                # Disappeared between detect and recover.
                continue
            except JobQueueError as exc:
                logger.exception(
                    "recovery: failed to recover %s (%s)", entry.job_id, exc
                )
                reports.append(JobRecoveryReport(
                    job_id=entry.job_id,
                    queue_state_before=entry.state,
                    queue_state_after=entry.state,
                    last_safe_phase=None,
                    resume_phase=None,
                    requires_approval=True,
                    notes=[f"recovery error: {exc}"],
                ))
        return RecoveryReport(
            started_at=started,
            finished_at=time.time(),
            jobs=reports,
        )

    # ── helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _resume_phase_for(safe_phase: str | None) -> str | None:
        """Map a "last safe phase" to the phase that should run next.

        If the last safe phase was ``pre_publish``, recovery still
        resumes *at* ``pre_publish`` — because we never auto-publish
        on a recovered job, the human approval step is the resume
        point.
        """
        if safe_phase is None:
            return None
        order = list(CheckpointPhase.ALL)
        try:
            idx = order.index(safe_phase)
        except ValueError:
            return None
        # The "resume" phase is the *same* checkpoint phase — recovery
        # never silently advances; it always restarts the phase whose
        # checkpoint we have.
        return order[idx]

    def _preserve_logs(self, job_id: str, *, now: float) -> Path | None:
        """Copy existing logs into a timestamped recovered/ subfolder.

        Best-effort. Returns the path if logs were preserved, ``None``
        if there was nothing to preserve.
        """
        src = self.log_root / job_id
        if not src.exists():
            return None
        stamp = time.strftime("%Y%m%dt%H%M%Sz", time.gmtime(now))
        dst = src / RECOVERED_LOGS_DIRNAME / stamp
        dst.mkdir(parents=True, exist_ok=True)
        copied = 0
        for entry in src.iterdir():
            # Don't recurse into our own recovered/ subdir.
            if entry == src / RECOVERED_LOGS_DIRNAME:
                continue
            try:
                if entry.is_file():
                    shutil.copy2(entry, dst / entry.name)
                    copied += 1
                elif entry.is_dir():
                    shutil.copytree(
                        entry,
                        dst / entry.name,
                        dirs_exist_ok=True,
                    )
                    copied += 1
            except OSError as exc:
                logger.warning(
                    "recovery: could not preserve %s (%s)", entry, exc
                )
        if copied == 0:
            try:
                dst.rmdir()
            except OSError:
                pass
            return None
        return dst

# ──────────────────────────────────────────────────────────────────────
# Convenience: API-facing helpers
# ──────────────────────────────────────────────────────────────────────


def query_queue_state(root: str | Path | None = None) -> dict[str, Any]:
    """Return a compact JSON-safe view of the queue.

    Used by the local API (``GET /queue``) and the Android cockpit to
    render the queue tab. Never raises — a missing or corrupt
    ``queue.json`` returns an empty list with an ``error`` field.
    """
    queue = JobQueue(root=root)
    try:
        entries = queue.list_jobs()
    except JobQueueError as exc:
        return {"entries": [], "error": str(exc)}
    return {
        "entries": [e.to_dict() for e in entries],
        "counts": _state_counts(entries),
    }


def resume_job_by_id(
    job_id: str,
    *,
    root: str | Path | None = None,
    now: float | None = None,
) -> JobRecoveryReport:
    """Public entry point invoked by the mobile app to resume a job."""
    mgr = RecoveryManager.from_root(root=root)
    return mgr.recover_job(job_id, now=now)


def _state_counts(entries: Iterable[JobQueueEntry]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for e in entries:
        counts[e.state] = counts.get(e.state, 0) + 1
    return counts
