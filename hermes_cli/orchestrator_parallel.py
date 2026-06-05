"""Parallel worker execution for the Hermes local orchestrator.

This module is the thin runtime under the Phase 12 orchestrator: it
takes an :class:`ExecutionPlan` of workers, runs them sequentially or in
a small thread pool, and writes auditable artifacts (per-worker logs +
``status.json``) under a job-scoped directory.

Three execution modes are supported:

``ExecutionMode.PROMPT_ONLY``
    The runner emits the worker's prompt for the user/agent to consume
    elsewhere. No external process is started. Useful for handoff cards
    that just need a structured prompt rendered to disk.

``ExecutionMode.HANDOFF_REQUIRED``
    Same as ``PROMPT_ONLY`` plus a ``handoff.json`` payload describing
    the external tool / destination. The runner DOES NOT push anything,
    open any apps, or invoke any URL — it just persists the handoff and
    marks the worker ``awaiting_handoff``.

``ExecutionMode.LOCAL_RUN``
    The runner ``subprocess``-launches the worker's command with the
    given environment and ``cwd``. stdout/stderr are streamed to log
    files, and the worker is killed if the timeout elapses or
    ``cancel.requested`` appears.

Safety invariants enforced here (matches Phase 12 requirements):

* No ``git push``, ``git push --force``, ``git reset --hard``, or other
  destructive git ops are invoked.
* No worktree is deleted unless the caller passes
  ``cleanup_worktrees=True`` AND ``confirm_destructive=True``.
* Default concurrency is small (``DEFAULT_CONCURRENCY``).
* All side effects live under the orchestrator dir for the job, so a
  human can audit / delete by hand.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Iterable, Optional, Sequence
import json
import os
import shlex
import subprocess
import threading
import time

from hermes_cli import worktrees as wt
from hermes_cli import worker_lease as wl
from hermes_cli.worker_lease_store import DEFAULT_HOST_ID, WorkerLeaseStore

ORCHESTRATOR_DIRNAME = wt.ORCHESTRATOR_DIRNAME
JOBS_SUBDIR = "jobs"
STATUS_FILENAME = "status.json"
CANCEL_FLAG_FILENAME = "cancel.requested"
HANDOFF_FILENAME = "handoff.json"
PROMPT_FILENAME = "prompt.txt"
STDOUT_LOG = "stdout.log"
STDERR_LOG = "stderr.log"

DEFAULT_CONCURRENCY = 2
MAX_CONCURRENCY = 8
DEFAULT_TIMEOUT_SECONDS = 600


class ExecutionMode(str, Enum):
    PROMPT_ONLY = "prompt-only"
    HANDOFF_REQUIRED = "handoff-required"
    LOCAL_RUN = "local-run"


class WorkerState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMED_OUT = "timed-out"
    CANCELLED = "cancelled"
    AWAITING_HANDOFF = "awaiting-handoff"


class OrchestratorError(RuntimeError):
    """Raised when a plan is malformed or unsafe."""


# ─── plan ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class WorkerPlan:
    """One worker to execute as part of a job."""

    worker_id: str
    profile: str
    mode: ExecutionMode
    prompt: str = ""
    command: Optional[Sequence[str]] = None
    cwd: Optional[str] = None
    env: Optional[dict[str, str]] = None
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
    handoff: dict[str, Any] = field(default_factory=dict)
    use_worktree: bool = False

    def validate(self) -> None:
        if not self.worker_id or not self.worker_id.strip():
            raise OrchestratorError("worker_id is required")
        if not self.profile or not self.profile.strip():
            raise OrchestratorError("profile is required")
        if not isinstance(self.mode, ExecutionMode):
            raise OrchestratorError("mode must be an ExecutionMode")
        if self.timeout_seconds <= 0:
            raise OrchestratorError("timeout_seconds must be positive")
        if self.mode is ExecutionMode.LOCAL_RUN:
            if not self.command:
                raise OrchestratorError(
                    f"worker {self.worker_id!r} is local-run but has no command"
                )
            # Refuse obviously destructive commands as a belt-and-braces
            # check. Workers can still run arbitrary code via shells the
            # caller controls; this is just a guardrail against the
            # easiest footguns.
            joined = " ".join(map(str, self.command))
            for forbidden in (
                "git push",
                "git push --force",
                "git push -f",
                "git reset --hard",
                "rm -rf /",
            ):
                if forbidden in joined:
                    raise OrchestratorError(
                        f"worker {self.worker_id!r} command contains forbidden token: {forbidden!r}"
                    )
        if self.mode is ExecutionMode.HANDOFF_REQUIRED and not self.handoff:
            raise OrchestratorError(
                f"worker {self.worker_id!r} is handoff-required but has no handoff metadata"
            )


@dataclass(frozen=True)
class ExecutionPlan:
    """A job: ``job_id`` plus the workers to dispatch."""

    job_id: str
    workers: Sequence[WorkerPlan]
    concurrency: int = DEFAULT_CONCURRENCY
    use_worktrees: bool = False
    base_ref: Optional[str] = None
    allow_dirty: bool = False

    def validate(self) -> None:
        if not self.job_id or not self.job_id.strip():
            raise OrchestratorError("job_id is required")
        if not self.workers:
            raise OrchestratorError("plan must contain at least one worker")
        if self.concurrency < 1:
            raise OrchestratorError("concurrency must be >= 1")
        if self.concurrency > MAX_CONCURRENCY:
            raise OrchestratorError(
                f"concurrency {self.concurrency} exceeds safe cap {MAX_CONCURRENCY}"
            )
        seen: set[str] = set()
        for worker in self.workers:
            worker.validate()
            if worker.worker_id in seen:
                raise OrchestratorError(f"duplicate worker_id: {worker.worker_id!r}")
            seen.add(worker.worker_id)


# ─── status ───────────────────────────────────────────────────────────


@dataclass
class WorkerStatus:
    worker_id: str
    profile: str
    mode: str
    state: WorkerState = WorkerState.PENDING
    started_at: Optional[str] = None
    ended_at: Optional[str] = None
    return_code: Optional[int] = None
    error: Optional[str] = None
    stdout_path: Optional[str] = None
    stderr_path: Optional[str] = None
    worktree_path: Optional[str] = None
    branch: Optional[str] = None
    handoff_path: Optional[str] = None
    prompt_path: Optional[str] = None

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["state"] = self.state.value if isinstance(self.state, WorkerState) else self.state
        return data


# ─── paths ────────────────────────────────────────────────────────────


def job_dir(repo: Path, job_id: str) -> Path:
    job = wt.sanitize_segment(job_id, field_name="job_id")
    return Path(repo) / ORCHESTRATOR_DIRNAME / JOBS_SUBDIR / job


def worker_dir(repo: Path, job_id: str, worker_id: str) -> Path:
    worker = wt.sanitize_segment(worker_id, field_name="worker_id")
    return job_dir(repo, job_id) / worker


def status_path(repo: Path, job_id: str) -> Path:
    return job_dir(repo, job_id) / STATUS_FILENAME


def cancel_flag_path(repo: Path, job_id: str) -> Path:
    return job_dir(repo, job_id) / CANCEL_FLAG_FILENAME


def request_cancel(repo: Path, job_id: str) -> Path:
    """Drop the ``cancel.requested`` flag file for the job.

    A running :class:`ParallelRunner` polls for this file and signals
    its workers to stop. Safe to call from another process.
    """

    target = cancel_flag_path(repo, job_id)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(_now_iso() + "\n", encoding="utf-8")
    return target


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ─── runner ───────────────────────────────────────────────────────────


StatusCallback = Callable[[WorkerStatus], None]


class ParallelRunner:
    """Executes an :class:`ExecutionPlan` and persists artifacts."""

    def __init__(
        self,
        repo: Path,
        plan: ExecutionPlan,
        *,
        on_status: Optional[StatusCallback] = None,
        poll_interval: float = 0.5,
        lease_store: Optional[WorkerLeaseStore] = None,
        record_leases: bool = True,
    ) -> None:
        self.repo = Path(repo).resolve()
        plan.validate()
        self.plan = plan
        self.on_status = on_status
        self.poll_interval = max(0.05, float(poll_interval))
        self.statuses: dict[str, WorkerStatus] = {
            w.worker_id: WorkerStatus(
                worker_id=w.worker_id, profile=w.profile, mode=w.mode.value
            )
            for w in plan.workers
        }
        self._cancel_event = threading.Event()
        self._status_lock = threading.Lock()
        self._worktrees: dict[str, wt.WorktreeInfo] = {}
        # Durable lease recording. This is *observational only*: it records
        # lease lifecycle alongside the run and must never change scheduling,
        # timeout, or cancel behavior. Any store failure is swallowed so a
        # broken/locked store can't break a run.
        self._record_leases = record_leases
        self._lease_store: Optional[WorkerLeaseStore]
        if not record_leases:
            self._lease_store = None
        elif lease_store is not None:
            self._lease_store = lease_store
        else:
            try:
                self._lease_store = WorkerLeaseStore.load()
            except Exception:
                self._lease_store = None
        self._lease_lock = threading.Lock()
        self._leases: dict[str, wl.WorkerLease] = {}

    # ── public API ────────────────────────────────────────────────

    def run(self) -> dict[str, WorkerStatus]:
        """Run the plan to completion. Returns the per-worker statuses."""

        job_root = job_dir(self.repo, self.plan.job_id)
        job_root.mkdir(parents=True, exist_ok=True)
        self._write_status_snapshot(initial=True)

        if self.plan.use_worktrees:
            self._provision_worktrees()

        if self.plan.concurrency <= 1:
            for worker in self.plan.workers:
                if self._is_cancelled():
                    self._mark_cancelled(worker.worker_id)
                    continue
                self._execute_worker(worker)
        else:
            with ThreadPoolExecutor(max_workers=self.plan.concurrency) as pool:
                futures = {
                    pool.submit(self._execute_worker, worker): worker
                    for worker in self.plan.workers
                }
                for future in as_completed(futures):
                    # Surface unexpected exceptions through the worker
                    # status (we already write per-worker errors inline,
                    # but a raise here would be a programmer bug).
                    exc = future.exception()
                    if exc is not None:
                        worker = futures[future]
                        self._update(
                            worker.worker_id,
                            state=WorkerState.FAILED,
                            error=f"runner exception: {exc!r}",
                            ended_at=_now_iso(),
                        )

        self._write_status_snapshot()
        return dict(self.statuses)

    def request_cancel(self) -> None:
        """In-process cancel signal. Sets the flag file too for symmetry."""

        self._cancel_event.set()
        request_cancel(self.repo, self.plan.job_id)

    # ── worktree provisioning ────────────────────────────────────

    def _provision_worktrees(self) -> None:
        for worker in self.plan.workers:
            if not worker.use_worktree:
                continue
            info = wt.create_worktree(
                self.repo,
                job_id=self.plan.job_id,
                worker_id=worker.worker_id,
                base_ref=self.plan.base_ref,
                allow_dirty=self.plan.allow_dirty,
                extra_metadata={"profile": worker.profile, "mode": worker.mode.value},
            )
            self._worktrees[worker.worker_id] = info
            self._update(
                worker.worker_id,
                worktree_path=str(info.path),
                branch=info.branch,
            )

    # ── lease recording (observational only) ─────────────────────

    def _lease_id(self, worker_id: str) -> str:
        return f"{self.plan.job_id}:{worker_id}"

    def _lease_enabled(self) -> bool:
        return self._record_leases and self._lease_store is not None

    def _record_acquire(self, worker: WorkerPlan) -> None:
        """Record that a worker started by acquiring + persisting a lease.

        Best-effort: a kernel/store error is swallowed so recording can
        never alter the run. The lease TTL mirrors the worker timeout so a
        crashed worker's lease lapses on the same horizon the runner uses.
        """

        if not self._lease_enabled():
            return
        try:
            now = time.time()
            ttl = max(1.0, float(worker.timeout_seconds))
            lease = wl.WorkerLease(
                lease_id=self._lease_id(worker.worker_id),
                job_id=self.plan.job_id,
                worker_id=worker.worker_id,
                host_id=DEFAULT_HOST_ID,
            )
            lease = wl.acquire(lease, now=now, ttl=ttl)
            with self._lease_lock:
                self._leases[worker.worker_id] = lease
            self._lease_store.upsert(lease)  # type: ignore[union-attr]
        except Exception:
            pass

    def _record_complete(self, worker_id: str) -> None:
        """Record a worker that finished cleanly by completing its lease."""

        if not self._lease_enabled():
            return
        try:
            with self._lease_lock:
                lease = self._leases.get(worker_id)
            if lease is None:
                return
            now = time.time()
            # The kernel rejects completing a lapsed lease; in that race the
            # lease is effectively lost, so record it as expired instead.
            if wl.can_complete(lease, now=now):
                updated = wl.complete(lease, now=now)
            else:
                updated = wl.expire_if_stale(lease, now=now)
            self._store_lease(worker_id, updated)
        except Exception:
            pass

    def _record_lost(self, worker_id: str) -> None:
        """Record a worker that timed out / failed / was cancelled.

        A still-running lease is cancelled (an explicit non-terminal stop);
        a lapsed one is expired. Either way the recorded lease ends terminal.
        """

        if not self._lease_enabled():
            return
        try:
            with self._lease_lock:
                lease = self._leases.get(worker_id)
            if lease is None:
                return
            now = time.time()
            staled = wl.expire_if_stale(lease, now=now)
            if staled.status is not lease.status:
                updated = staled  # lapsed → EXPIRED
            elif lease.is_terminal:
                updated = lease
            else:
                updated = wl.cancel(lease)
            self._store_lease(worker_id, updated)
        except Exception:
            pass

    def _store_lease(self, worker_id: str, lease: wl.WorkerLease) -> None:
        with self._lease_lock:
            self._leases[worker_id] = lease
        if self._lease_store is not None:
            self._lease_store.upsert(lease)

    # ── per-worker execution ─────────────────────────────────────

    def _execute_worker(self, worker: WorkerPlan) -> None:
        if self._is_cancelled():
            self._mark_cancelled(worker.worker_id)
            return

        worker_root = worker_dir(self.repo, self.plan.job_id, worker.worker_id)
        worker_root.mkdir(parents=True, exist_ok=True)

        prompt_path = worker_root / PROMPT_FILENAME
        if worker.prompt:
            prompt_path.write_text(worker.prompt, encoding="utf-8")
        self._update(worker.worker_id, prompt_path=str(prompt_path) if worker.prompt else None)

        if worker.mode is ExecutionMode.PROMPT_ONLY:
            self._record_acquire(worker)
            self._update(
                worker.worker_id,
                state=WorkerState.COMPLETED,
                started_at=_now_iso(),
                ended_at=_now_iso(),
            )
            self._record_complete(worker.worker_id)
            return

        if worker.mode is ExecutionMode.HANDOFF_REQUIRED:
            self._record_acquire(worker)
            handoff_path = worker_root / HANDOFF_FILENAME
            handoff_path.write_text(
                json.dumps(worker.handoff, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            self._update(
                worker.worker_id,
                state=WorkerState.AWAITING_HANDOFF,
                started_at=_now_iso(),
                ended_at=_now_iso(),
                handoff_path=str(handoff_path),
            )
            # The worker finished its local responsibility (the handoff was
            # written); the external step happens elsewhere. Record the lease
            # as completed rather than lost.
            self._record_complete(worker.worker_id)
            return

        # LOCAL_RUN
        self._run_subprocess(worker, worker_root)

    def _run_subprocess(self, worker: WorkerPlan, worker_root: Path) -> None:
        stdout_path = worker_root / STDOUT_LOG
        stderr_path = worker_root / STDERR_LOG

        cwd = worker.cwd
        if cwd is None and worker.use_worktree:
            info = self._worktrees.get(worker.worker_id)
            cwd = str(info.path) if info else None
        if cwd is None:
            cwd = str(self.repo)

        env = os.environ.copy()
        if worker.env:
            env.update({str(k): str(v) for k, v in worker.env.items()})

        self._update(
            worker.worker_id,
            state=WorkerState.RUNNING,
            started_at=_now_iso(),
            stdout_path=str(stdout_path),
            stderr_path=str(stderr_path),
        )
        self._record_acquire(worker)

        try:
            with stdout_path.open("w", encoding="utf-8") as out, \
                 stderr_path.open("w", encoding="utf-8") as err:
                proc = subprocess.Popen(
                    list(worker.command or []),
                    cwd=cwd,
                    env=env,
                    stdout=out,
                    stderr=err,
                    text=True,
                )
                deadline = time.monotonic() + worker.timeout_seconds
                while True:
                    rc = proc.poll()
                    if rc is not None:
                        self._update(
                            worker.worker_id,
                            state=WorkerState.COMPLETED if rc == 0 else WorkerState.FAILED,
                            return_code=rc,
                            ended_at=_now_iso(),
                            error=None if rc == 0 else f"exit code {rc}",
                        )
                        if rc == 0:
                            self._record_complete(worker.worker_id)
                        else:
                            self._record_lost(worker.worker_id)
                        return
                    if self._is_cancelled():
                        _terminate(proc)
                        self._update(
                            worker.worker_id,
                            state=WorkerState.CANCELLED,
                            ended_at=_now_iso(),
                            error="cancelled by orchestrator",
                            return_code=proc.returncode,
                        )
                        self._record_lost(worker.worker_id)
                        return
                    if time.monotonic() >= deadline:
                        _terminate(proc)
                        self._update(
                            worker.worker_id,
                            state=WorkerState.TIMED_OUT,
                            ended_at=_now_iso(),
                            error=f"exceeded timeout {worker.timeout_seconds}s",
                            return_code=proc.returncode,
                        )
                        self._record_lost(worker.worker_id)
                        return
                    time.sleep(self.poll_interval)
        except FileNotFoundError as exc:
            self._update(
                worker.worker_id,
                state=WorkerState.FAILED,
                ended_at=_now_iso(),
                error=f"command not found: {exc}",
            )
            self._record_lost(worker.worker_id)
        except OSError as exc:
            self._update(
                worker.worker_id,
                state=WorkerState.FAILED,
                ended_at=_now_iso(),
                error=f"os error: {exc}",
            )
            self._record_lost(worker.worker_id)

    # ── status bookkeeping ──────────────────────────────────────

    def _update(self, worker_id: str, **fields: Any) -> None:
        with self._status_lock:
            status = self.statuses[worker_id]
            for key, value in fields.items():
                setattr(status, key, value)
            snapshot = WorkerStatus(**{**asdict(status)})
            # restore the enum on the snapshot for the callback (asdict
            # turns it into a string)
            snapshot.state = status.state if isinstance(status.state, WorkerState) else WorkerState(status.state)
            self._write_status_snapshot_locked()
        if self.on_status is not None:
            try:
                self.on_status(snapshot)
            except Exception:
                # Status callbacks must never break execution.
                pass

    def _mark_cancelled(self, worker_id: str) -> None:
        with self._status_lock:
            status = self.statuses[worker_id]
            if status.state in (WorkerState.PENDING,):
                status.state = WorkerState.CANCELLED
                status.ended_at = _now_iso()
                status.error = "cancelled before start"
            self._write_status_snapshot_locked()

    def _is_cancelled(self) -> bool:
        if self._cancel_event.is_set():
            return True
        if cancel_flag_path(self.repo, self.plan.job_id).exists():
            self._cancel_event.set()
            return True
        return False

    def _write_status_snapshot(self, *, initial: bool = False) -> None:
        with self._status_lock:
            self._write_status_snapshot_locked(initial=initial)

    def _write_status_snapshot_locked(self, *, initial: bool = False) -> None:
        path = status_path(self.repo, self.plan.job_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "job_id": self.plan.job_id,
            "updated_at": _now_iso(),
            "concurrency": self.plan.concurrency,
            "use_worktrees": self.plan.use_worktrees,
            "workers": [s.as_dict() for s in self.statuses.values()],
        }
        if initial:
            payload["created_at"] = payload["updated_at"]
        else:
            existing = _load_existing_created_at(path)
            if existing:
                payload["created_at"] = existing
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _load_existing_created_at(path: Path) -> Optional[str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        value = data.get("created_at")
        return str(value) if value else None
    except (OSError, ValueError):
        return None


def _terminate(proc: subprocess.Popen[str]) -> None:
    """Best-effort terminate then kill."""

    if proc.poll() is not None:
        return
    try:
        proc.terminate()
    except OSError:
        return
    try:
        proc.wait(timeout=2)
        return
    except subprocess.TimeoutExpired:
        pass
    try:
        proc.kill()
    except OSError:
        return
    try:
        proc.wait(timeout=2)
    except subprocess.TimeoutExpired:
        return


# ─── convenience constructors ────────────────────────────────────────


def parse_command(command: str | Sequence[str]) -> list[str]:
    """Turn a string command into argv. Lists pass through unchanged."""

    if isinstance(command, str):
        return shlex.split(command)
    return list(command)


def load_status(repo: Path, job_id: str) -> Optional[dict[str, Any]]:
    """Read ``status.json`` for a job, or ``None`` if missing."""

    path = status_path(Path(repo), job_id)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def list_jobs(repo: Path) -> list[str]:
    """List the job IDs that have a status file on disk."""

    root = Path(repo) / ORCHESTRATOR_DIRNAME / JOBS_SUBDIR
    if not root.exists():
        return []
    return sorted(
        p.name
        for p in root.iterdir()
        if p.is_dir() and (p / STATUS_FILENAME).exists()
    )


def cleanup_job_worktrees(
    repo: Path,
    job_id: str,
    *,
    confirm_destructive: bool = False,
    delete_branches: bool = False,
) -> list[str]:
    """Tear down every worktree belonging to a job.

    Requires the explicit ``confirm_destructive=True`` flag — otherwise
    returns an empty list without touching the filesystem. Mirrors the
    Phase 12 "no destructive cleanup by default" requirement.
    """

    if not confirm_destructive:
        return []
    removed: list[str] = []
    for info in list(wt.iter_worktrees_for_job(repo, job_id)):
        ok = wt.cleanup_worktree(
            repo,
            job_id=info.job_id,
            worker_id=info.worker_id,
            confirm=True,
            delete_branch=delete_branches,
        )
        if ok:
            removed.append(info.worker_id)
    return removed


__all__ = [
    "CANCEL_FLAG_FILENAME",
    "DEFAULT_CONCURRENCY",
    "DEFAULT_TIMEOUT_SECONDS",
    "ExecutionMode",
    "ExecutionPlan",
    "MAX_CONCURRENCY",
    "OrchestratorError",
    "ParallelRunner",
    "STATUS_FILENAME",
    "WorkerPlan",
    "WorkerState",
    "WorkerStatus",
    "cancel_flag_path",
    "cleanup_job_worktrees",
    "job_dir",
    "list_jobs",
    "load_status",
    "parse_command",
    "request_cancel",
    "status_path",
    "worker_dir",
]
