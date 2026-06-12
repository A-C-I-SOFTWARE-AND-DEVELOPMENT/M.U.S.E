"""Persistent job queue for the Hermes orchestrator.

The :class:`muse_cli.job_controller.JobController` owns the on-disk
state of a single job (prompt, workers, history). The *queue* is the
layer above it: it tracks scheduling state (queued, running, paused,
cancelled), worker connectivity (online, disconnected, blocked, failed),
and retry intent. A queue survives process restarts, Termux restarts,
Windows tunnel disconnects, and partial worker failures.

The queue is intentionally separate from ``job.json`` for two reasons:

1. The Job state machine (``JobState``) describes the *work* — what
   phase the job is in. The queue state describes the *scheduling* —
   whether the work should run now. A job can be ``WORKERS_RUNNING``
   (work-wise) while its queue entry is ``paused`` (scheduling-wise);
   that means "the controller knows workers are mid-flight, but the
   queue should not advance further until a human resumes".

2. Mobile clients (the Android cockpit) and the local API need a fast,
   compact way to list "what's in flight". Loading every ``job.json``
   would be expensive on a phone; the queue collapses that into a
   single ``queue.json``.

Layout::

    <root>/                         # default: $PWD/.hermes-orchestrator
        queue.json                  # this module
        jobs/<job-id>/job.json      # job controller (existing)
        checkpoints/<job-id>/…      # checkpoints module
        logs/<job-id>/…             # recovery module (preserved logs)

All writes are atomic (temp file + ``os.replace``).
"""

from __future__ import annotations

import json
import logging
import os
import secrets
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

logger = logging.getLogger(__name__)

ROOT_DIRNAME = ".hermes-orchestrator"
QUEUE_FILE = "queue.json"

# Schema version — bumped if/when the on-disk format changes in a
# breaking way. Recovery refuses to load a higher version than it knows.
QUEUE_SCHEMA_VERSION = 1


class JobQueueError(RuntimeError):
    """Base error for queue operations."""


class JobQueueNotFoundError(JobQueueError):
    """Raised when a queue entry for a job_id is missing."""


class WorkerNotFoundError(JobQueueError):
    """Raised when a worker_id is not on the named job."""


class QueueState:
    """Scheduling states for a queue entry.

    ``running`` is the only state a worker may actively progress in.
    ``paused`` is human-requested; ``blocked`` is system-requested (e.g.
    a stale worker or a missing dependency); ``disconnected`` is
    network-requested (the remote worker tunnel is down).
    """

    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    BLOCKED = "blocked"
    DISCONNECTED = "disconnected"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

    ALL = frozenset({
        QUEUED, RUNNING, PAUSED, BLOCKED, DISCONNECTED,
        COMPLETED, FAILED, CANCELLED,
    })

    # States from which a human resume() makes sense.
    RESUMABLE = frozenset({PAUSED, BLOCKED, DISCONNECTED, FAILED})

    # Terminal — never auto-advances.
    TERMINAL = frozenset({COMPLETED, FAILED, CANCELLED})


class WorkerStatus:
    """Per-worker scheduling state inside a queue entry."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    DISCONNECTED = "disconnected"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"

    ALL = frozenset({
        PENDING, RUNNING, SUCCEEDED, FAILED,
        DISCONNECTED, BLOCKED, CANCELLED,
    })


@dataclass
class WorkerQueueEntry:
    """Per-worker queue state.

    Mirrors the WorkerSpec from the job controller but adds the
    scheduling-side fields (status, attempts, disconnection metadata).
    """

    worker_id: str
    role: str = ""
    target_tool: str = "manual"
    status: str = WorkerStatus.PENDING
    attempts: int = 0
    last_heartbeat: float = 0.0
    disconnected_at: float = 0.0
    last_error: str | None = None
    # Free-form context the worker needs to resume — kept here so a
    # tunnel reconnect can re-deliver the same prompt without re-deriving.
    pending_prompt: str | None = None
    pending_output: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorkerQueueEntry":
        return cls(
            worker_id=str(data.get("worker_id", "")),
            role=str(data.get("role", "")),
            target_tool=str(data.get("target_tool", "manual")),
            status=str(data.get("status", WorkerStatus.PENDING)),
            attempts=int(data.get("attempts", 0) or 0),
            last_heartbeat=float(data.get("last_heartbeat", 0.0) or 0.0),
            disconnected_at=float(data.get("disconnected_at", 0.0) or 0.0),
            last_error=data.get("last_error"),
            pending_prompt=data.get("pending_prompt"),
            pending_output=data.get("pending_output"),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class JobQueueEntry:
    """One queued job."""

    job_id: str
    prompt: str = ""
    mode: str = ""
    repo_root: str = ""
    state: str = QueueState.QUEUED
    created_at: float = 0.0
    updated_at: float = 0.0
    last_phase: str | None = None
    last_checkpoint_id: str | None = None
    workers: list[WorkerQueueEntry] = field(default_factory=list)
    note: str | None = None
    # If a recovery happened, we record it here so the UI can warn
    # "this job was resumed, review before publishing".
    recovered_at: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "JobQueueEntry":
        workers_raw: Iterable[Any] = data.get("workers") or []
        return cls(
            job_id=str(data.get("job_id", "")),
            prompt=str(data.get("prompt", "")),
            mode=str(data.get("mode", "")),
            repo_root=str(data.get("repo_root", "")),
            state=str(data.get("state", QueueState.QUEUED)),
            created_at=float(data.get("created_at", 0.0) or 0.0),
            updated_at=float(data.get("updated_at", 0.0) or 0.0),
            last_phase=data.get("last_phase"),
            last_checkpoint_id=data.get("last_checkpoint_id"),
            workers=[
                WorkerQueueEntry.from_dict(w)
                for w in workers_raw
                if isinstance(w, dict)
            ],
            note=data.get("note"),
            recovered_at=float(data.get("recovered_at", 0.0) or 0.0),
            metadata=dict(data.get("metadata") or {}),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "prompt": self.prompt,
            "mode": self.mode,
            "repo_root": self.repo_root,
            "state": self.state,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "last_phase": self.last_phase,
            "last_checkpoint_id": self.last_checkpoint_id,
            "workers": [w.to_dict() for w in self.workers],
            "note": self.note,
            "recovered_at": self.recovered_at,
            "metadata": dict(self.metadata),
        }

    def worker(self, worker_id: str) -> WorkerQueueEntry | None:
        for w in self.workers:
            if w.worker_id == worker_id:
                return w
        return None


def _now() -> float:
    return time.time()


def _atomic_write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(
        f".{path.name}.tmp.{os.getpid()}.{secrets.token_hex(3)}"
    )
    tmp.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp, path)


class JobQueue:
    """Filesystem-backed job queue.

    All public methods are thread-safe (an in-process re-entrant lock
    serializes mutators). Cross-process safety relies on atomic
    ``os.replace`` — a reader will always see a coherent snapshot, but
    two writers racing on the same root may overwrite each other. In
    practice there is exactly one writer (the orchestrator daemon).
    """

    def __init__(self, root: str | Path | None = None) -> None:
        if root is None:
            env_root = os.environ.get("HERMES_ORCHESTRATOR_HOME")
            root = Path(env_root) if env_root else Path.cwd() / ROOT_DIRNAME
        self.root = Path(root)
        self.queue_path = self.root / QUEUE_FILE
        self._lock = threading.RLock()

    # ── load / save ───────────────────────────────────────────────────

    def _load_raw(self) -> dict[str, Any]:
        if not self.queue_path.exists():
            return {
                "version": QUEUE_SCHEMA_VERSION,
                "entries": [],
            }
        try:
            data = json.loads(self.queue_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise JobQueueError(
                f"queue.json is corrupt at {self.queue_path}: {exc}"
            ) from exc
        if not isinstance(data, dict):
            raise JobQueueError(
                f"queue.json must contain a JSON object, got {type(data).__name__}"
            )
        version = int(data.get("version", QUEUE_SCHEMA_VERSION) or 0)
        if version > QUEUE_SCHEMA_VERSION:
            raise JobQueueError(
                f"queue.json schema version {version} is newer than "
                f"this build supports ({QUEUE_SCHEMA_VERSION}). "
                f"Upgrade hermes-agent before continuing."
            )
        return data

    def _save_raw(self, data: dict[str, Any]) -> None:
        data["version"] = QUEUE_SCHEMA_VERSION
        _atomic_write_json(self.queue_path, data)

    def _load_entries(self) -> list[JobQueueEntry]:
        data = self._load_raw()
        entries_raw = data.get("entries") or []
        out: list[JobQueueEntry] = []
        for raw in entries_raw:
            if not isinstance(raw, dict):
                continue
            try:
                out.append(JobQueueEntry.from_dict(raw))
            except Exception as exc:  # noqa: BLE001 — defensive on disk format
                logger.warning("job_queue: skipping bad entry: %s", exc)
        return out

    def _save_entries(self, entries: list[JobQueueEntry]) -> None:
        self._save_raw({"entries": [e.to_dict() for e in entries]})

    # ── public API ────────────────────────────────────────────────────

    def add_job(
        self,
        job_id: str,
        *,
        prompt: str = "",
        mode: str = "",
        repo_root: str = "",
        workers: Iterable[WorkerQueueEntry | dict[str, Any]] | None = None,
        state: str = QueueState.QUEUED,
        metadata: dict[str, Any] | None = None,
    ) -> JobQueueEntry:
        """Add a new job to the queue.

        Raises :class:`JobQueueError` if a job with the same id already
        exists in the queue (caller should ``cancel`` or use a fresh id).
        """
        if not job_id or not str(job_id).strip():
            raise JobQueueError("job_id is required")
        if state not in QueueState.ALL:
            raise JobQueueError(
                f"state must be one of {sorted(QueueState.ALL)}; got {state!r}"
            )

        with self._lock:
            entries = self._load_entries()
            if any(e.job_id == job_id for e in entries):
                raise JobQueueError(f"job already queued: {job_id}")
            normalised_workers: list[WorkerQueueEntry] = []
            for w in workers or []:
                if isinstance(w, WorkerQueueEntry):
                    normalised_workers.append(w)
                elif isinstance(w, dict):
                    normalised_workers.append(WorkerQueueEntry.from_dict(w))
                else:
                    raise JobQueueError(
                        "workers must be WorkerQueueEntry or dict instances"
                    )
            now = _now()
            entry = JobQueueEntry(
                job_id=str(job_id),
                prompt=str(prompt or ""),
                mode=str(mode or ""),
                repo_root=str(repo_root or ""),
                state=state,
                created_at=now,
                updated_at=now,
                workers=normalised_workers,
                metadata=dict(metadata or {}),
            )
            entries.append(entry)
            self._save_entries(entries)
            logger.info("job_queue: added job %s (state=%s)", job_id, state)
            return entry

    def list_jobs(
        self,
        *,
        state: str | None = None,
        states: Iterable[str] | None = None,
    ) -> list[JobQueueEntry]:
        """Return queue entries, oldest-first by created_at.

        Optional ``state=`` filters to a single state; ``states=``
        filters to a set. Both may be combined.
        """
        filt: set[str] = set()
        if state:
            filt.add(state)
        if states:
            filt.update(states)
        with self._lock:
            entries = self._load_entries()
        if filt:
            entries = [e for e in entries if e.state in filt]
        entries.sort(key=lambda e: (e.created_at, e.job_id))
        return entries

    def get_job(self, job_id: str) -> JobQueueEntry:
        with self._lock:
            entries = self._load_entries()
        for entry in entries:
            if entry.job_id == job_id:
                return entry
        raise JobQueueNotFoundError(f"job not in queue: {job_id}")

    def _mutate(self, job_id: str, mutator) -> JobQueueEntry:
        with self._lock:
            entries = self._load_entries()
            for i, entry in enumerate(entries):
                if entry.job_id == job_id:
                    mutator(entry)
                    entry.updated_at = _now()
                    entries[i] = entry
                    self._save_entries(entries)
                    return entry
            raise JobQueueNotFoundError(f"job not in queue: {job_id}")

    def set_state(
        self, job_id: str, state: str, *, note: str | None = None
    ) -> JobQueueEntry:
        """Force a queue state. Used by recovery and the controller."""
        if state not in QueueState.ALL:
            raise JobQueueError(
                f"state must be one of {sorted(QueueState.ALL)}; got {state!r}"
            )

        def _apply(entry: JobQueueEntry) -> None:
            entry.state = state
            if note is not None:
                entry.note = note

        return self._mutate(job_id, _apply)

    def pause_job(self, job_id: str, *, note: str | None = None) -> JobQueueEntry:
        """Pause a job. Allowed from ``queued`` and ``running`` only.

        Pausing a terminal job is an error — terminal jobs need a fresh
        retry, not a pause toggle.
        """

        def _apply(entry: JobQueueEntry) -> None:
            if entry.state in QueueState.TERMINAL:
                raise JobQueueError(
                    f"cannot pause job in terminal state {entry.state}"
                )
            entry.state = QueueState.PAUSED
            if note is not None:
                entry.note = note

        return self._mutate(job_id, _apply)

    def resume_job(self, job_id: str, *, note: str | None = None) -> JobQueueEntry:
        """Resume a paused/blocked/disconnected/failed job.

        Resume marks the queue entry as ``queued`` again — the
        controller's dispatcher is what actually claims it next. The
        worker's per-worker status is *not* reset; recovery is in
        charge of deciding which workers to retry.
        """

        def _apply(entry: JobQueueEntry) -> None:
            if entry.state not in QueueState.RESUMABLE:
                raise JobQueueError(
                    f"cannot resume job in state {entry.state} "
                    f"(resumable states: {sorted(QueueState.RESUMABLE)})"
                )
            entry.state = QueueState.QUEUED
            if note is not None:
                entry.note = note

        return self._mutate(job_id, _apply)

    def cancel_job(self, job_id: str, *, note: str | None = None) -> JobQueueEntry:
        """Cancel a job (terminal). Idempotent on already-cancelled jobs."""

        def _apply(entry: JobQueueEntry) -> None:
            if entry.state == QueueState.CANCELLED:
                return
            if entry.state in (QueueState.COMPLETED, QueueState.FAILED):
                raise JobQueueError(
                    f"cannot cancel job in terminal state {entry.state}"
                )
            entry.state = QueueState.CANCELLED
            if note is not None:
                entry.note = note
            for w in entry.workers:
                if w.status not in (
                    WorkerStatus.SUCCEEDED,
                    WorkerStatus.FAILED,
                    WorkerStatus.CANCELLED,
                ):
                    w.status = WorkerStatus.CANCELLED

        return self._mutate(job_id, _apply)

    def remove_job(self, job_id: str) -> None:
        """Hard delete a queue entry. The job folder on disk is untouched."""
        with self._lock:
            entries = self._load_entries()
            new = [e for e in entries if e.job_id != job_id]
            if len(new) == len(entries):
                raise JobQueueNotFoundError(f"job not in queue: {job_id}")
            self._save_entries(new)

    # ── worker-level mutators ─────────────────────────────────────────

    def add_worker(
        self,
        job_id: str,
        worker_id: str,
        *,
        role: str = "",
        target_tool: str = "manual",
        status: str = WorkerStatus.PENDING,
    ) -> JobQueueEntry:
        if status not in WorkerStatus.ALL:
            raise JobQueueError(
                f"status must be one of {sorted(WorkerStatus.ALL)}; got {status!r}"
            )

        def _apply(entry: JobQueueEntry) -> None:
            if entry.worker(worker_id) is not None:
                raise JobQueueError(
                    f"worker already exists on job {job_id}: {worker_id}"
                )
            entry.workers.append(
                WorkerQueueEntry(
                    worker_id=worker_id,
                    role=role,
                    target_tool=target_tool,
                    status=status,
                )
            )

        return self._mutate(job_id, _apply)

    def set_worker_status(
        self,
        job_id: str,
        worker_id: str,
        status: str,
        *,
        error: str | None = None,
        heartbeat: bool = False,
    ) -> JobQueueEntry:
        if status not in WorkerStatus.ALL:
            raise JobQueueError(
                f"status must be one of {sorted(WorkerStatus.ALL)}; got {status!r}"
            )

        def _apply(entry: JobQueueEntry) -> None:
            w = entry.worker(worker_id)
            if w is None:
                raise WorkerNotFoundError(
                    f"job {job_id} has no worker {worker_id!r}"
                )
            w.status = status
            if error is not None:
                w.last_error = error
            if heartbeat:
                w.last_heartbeat = _now()
            if status == WorkerStatus.DISCONNECTED:
                w.disconnected_at = _now()
            if status == WorkerStatus.SUCCEEDED:
                # Successful completion clears prior error context but
                # preserves pending output for the scorer.
                w.last_error = None

        return self._mutate(job_id, _apply)

    def retry_worker(
        self,
        job_id: str,
        worker_id: str,
        *,
        new_status: str = WorkerStatus.PENDING,
        clear_error: bool = True,
    ) -> JobQueueEntry:
        """Reset a failed/disconnected worker so it will run again.

        Increments the per-worker attempt counter and bumps the parent
        entry back to ``queued`` if it was in a non-running, non-
        terminal state. ``new_status`` defaults to ``pending`` — pass
        ``running`` if the caller already kicked off the next attempt.
        """
        if new_status not in WorkerStatus.ALL:
            raise JobQueueError(
                f"new_status must be one of {sorted(WorkerStatus.ALL)}; "
                f"got {new_status!r}"
            )

        def _apply(entry: JobQueueEntry) -> None:
            w = entry.worker(worker_id)
            if w is None:
                raise WorkerNotFoundError(
                    f"job {job_id} has no worker {worker_id!r}"
                )
            if w.status not in (
                WorkerStatus.FAILED,
                WorkerStatus.DISCONNECTED,
                WorkerStatus.BLOCKED,
            ):
                raise JobQueueError(
                    f"worker {worker_id!r} is in status {w.status!r}; "
                    f"only failed/disconnected/blocked workers can be retried"
                )
            w.attempts += 1
            w.status = new_status
            w.disconnected_at = 0.0
            if clear_error:
                w.last_error = None
            # Don't auto-unblock a terminal job — but if it was failed
            # because of this very worker, lift the parent back to queued.
            if entry.state in (QueueState.FAILED, QueueState.BLOCKED,
                                QueueState.DISCONNECTED):
                entry.state = QueueState.QUEUED

        return self._mutate(job_id, _apply)

    def mark_worker_disconnected(
        self,
        job_id: str,
        worker_id: str,
        *,
        error: str | None = None,
        cascade_to_job: bool = True,
    ) -> JobQueueEntry:
        """Mark a worker disconnected (remote tunnel down).

        If ``cascade_to_job`` is True (default) and the job is currently
        running with no other running workers, the queue entry itself
        flips to ``disconnected`` so callers can find it via
        ``list_jobs(state=DISCONNECTED)``.
        """

        def _apply(entry: JobQueueEntry) -> None:
            w = entry.worker(worker_id)
            if w is None:
                raise WorkerNotFoundError(
                    f"job {job_id} has no worker {worker_id!r}"
                )
            w.status = WorkerStatus.DISCONNECTED
            w.disconnected_at = _now()
            if error is not None:
                w.last_error = error
            if cascade_to_job and entry.state not in QueueState.TERMINAL:
                others = [
                    other for other in entry.workers
                    if other.worker_id != worker_id
                    and other.status == WorkerStatus.RUNNING
                ]
                if not others:
                    entry.state = QueueState.DISCONNECTED

        return self._mutate(job_id, _apply)

    def mark_worker_reconnected(
        self,
        job_id: str,
        worker_id: str,
        *,
        resume_status: str = WorkerStatus.PENDING,
    ) -> JobQueueEntry:
        """Mark a disconnected worker reconnected; queue is re-armed.

        The worker's ``pending_prompt`` / ``pending_output`` are kept
        verbatim so the dispatcher can re-deliver the in-flight prompt
        and pick up where it left off.
        """
        if resume_status not in WorkerStatus.ALL:
            raise JobQueueError(
                f"resume_status must be one of {sorted(WorkerStatus.ALL)}; "
                f"got {resume_status!r}"
            )

        def _apply(entry: JobQueueEntry) -> None:
            w = entry.worker(worker_id)
            if w is None:
                raise WorkerNotFoundError(
                    f"job {job_id} has no worker {worker_id!r}"
                )
            if w.status != WorkerStatus.DISCONNECTED:
                raise JobQueueError(
                    f"worker {worker_id!r} is in status {w.status!r}, "
                    f"not disconnected"
                )
            w.status = resume_status
            w.disconnected_at = 0.0
            w.last_heartbeat = _now()
            # Lift the parent out of "disconnected" if it had cascaded
            # because of this worker.
            if entry.state == QueueState.DISCONNECTED:
                entry.state = QueueState.QUEUED

        return self._mutate(job_id, _apply)

    def set_pending_worker_io(
        self,
        job_id: str,
        worker_id: str,
        *,
        prompt: str | None = None,
        output: str | None = None,
    ) -> JobQueueEntry:
        """Stash the in-flight prompt/output for a worker.

        Used by the dispatcher to make a disconnect non-destructive:
        whatever was being sent / collected is persisted before the
        tunnel drops, so a later reconnect can resume the same
        conversation rather than restart it.
        """

        def _apply(entry: JobQueueEntry) -> None:
            w = entry.worker(worker_id)
            if w is None:
                raise WorkerNotFoundError(
                    f"job {job_id} has no worker {worker_id!r}"
                )
            if prompt is not None:
                w.pending_prompt = prompt
            if output is not None:
                w.pending_output = output

        return self._mutate(job_id, _apply)

    # ── checkpoint linkage ────────────────────────────────────────────

    def set_phase_checkpoint(
        self,
        job_id: str,
        phase: str,
        checkpoint_id: str,
    ) -> JobQueueEntry:
        """Pin the latest checkpoint id + phase on the queue entry.

        Recovery uses this to know where to resume without re-walking
        the on-disk checkpoint store.
        """

        def _apply(entry: JobQueueEntry) -> None:
            entry.last_phase = phase
            entry.last_checkpoint_id = checkpoint_id

        return self._mutate(job_id, _apply)

    def mark_recovered(
        self,
        job_id: str,
        *,
        recovered_at: float | None = None,
    ) -> JobQueueEntry:
        """Stamp the entry with a recovery timestamp.

        ``recovered_at != 0`` is the canonical signal to the publisher
        that this job came back from a disconnect and must not be
        auto-published.
        """

        def _apply(entry: JobQueueEntry) -> None:
            entry.recovered_at = (
                recovered_at if recovered_at is not None else _now()
            )

        return self._mutate(job_id, _apply)
