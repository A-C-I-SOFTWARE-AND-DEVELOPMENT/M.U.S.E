"""Phase 13 parallel runner — execution plans, approval gating, resume.

This module is the Phase 13 successor to
:mod:`muse_cli.orchestrator_parallel` (Phase 12). It is intentionally
self-contained: callers that need the older PROMPT_ONLY / LOCAL_RUN
shape can keep using the Phase 12 module; new code that wants
``remote-run`` execution, explicit approval gating, or resume support
should target this one.

Concepts:

* :class:`ExecutionMode` — ``prompt-only``, ``handoff-required``,
  ``local-run``, ``remote-run``. ``remote-run`` is gated behind an
  explicit approval and never executes by default.
* :class:`ApprovalState` — ``pending``, ``approved``, ``rejected``.
  Plans that touch remote resources must be ``approved`` before the
  runner will dispatch them.
* :class:`ExecutionPlan` — selected workers, mode, timeout, concurrency
  limit, approval state.
* :class:`ParallelRunner` — runs the plan, captures stdout/stderr per
  worker, persists ``status.json`` after every state transition,
  supports cancellation (in-process or via cancel-flag file) and
  resume (re-running a plan skips workers that are already
  ``completed`` / ``awaiting-handoff`` / ``cancelled``).

Safety invariants (all enforced in code and tested in
``tests/test_parallel_runner.py``):

* No ``git push``, ``git reset --hard``, ``rm -rf /``, or other
  destructive tokens are tolerated in ``local-run`` or ``remote-run``
  commands.
* ``remote-run`` workers refuse to start unless the plan's
  ``approval_state`` is :attr:`ApprovalState.APPROVED`.
* Worktrees are never deleted by the runner. Cleanup is opt-in via
  :func:`cleanup_job_worktrees` with ``confirm_destructive=True``.
* The runner never auto-pushes a branch, never force-pushes, never
  rewinds an existing branch.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional, Sequence
import json
import os
import shlex
import subprocess
import threading
import time

from muse_cli import worktrees as wt

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
MAX_TIMEOUT_SECONDS = 24 * 60 * 60

FORBIDDEN_COMMAND_TOKENS: tuple[str, ...] = (
    "git push",
    "git push --force",
    "git push -f",
    "git reset --hard",
    "git clean -fd",
    "rm -rf /",
    "rm -rf ~",
    ":(){:|:&};:",
)


class ExecutionMode(str, Enum):
    """Per-worker execution shape."""

    PROMPT_ONLY = "prompt-only"
    HANDOFF_REQUIRED = "handoff-required"
    LOCAL_RUN = "local-run"
    REMOTE_RUN = "remote-run"


class ApprovalState(str, Enum):
    """Plan-level approval gating for remote / privileged actions."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class WorkerState(str, Enum):
    """Lifecycle states a single worker passes through."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMED_OUT = "timed-out"
    CANCELLED = "cancelled"
    AWAITING_HANDOFF = "awaiting-handoff"
    BLOCKED_BY_APPROVAL = "blocked-by-approval"
    SKIPPED_RESUMED = "skipped-resumed"


TERMINAL_STATES: frozenset[WorkerState] = frozenset(
    {
        WorkerState.COMPLETED,
        WorkerState.FAILED,
        WorkerState.TIMED_OUT,
        WorkerState.CANCELLED,
        WorkerState.AWAITING_HANDOFF,
        WorkerState.BLOCKED_BY_APPROVAL,
        WorkerState.SKIPPED_RESUMED,
    }
)

RESUMABLE_STATES: frozenset[WorkerState] = frozenset(
    {
        WorkerState.PENDING,
        WorkerState.RUNNING,
        WorkerState.FAILED,
        WorkerState.TIMED_OUT,
        WorkerState.BLOCKED_BY_APPROVAL,
    }
)


class RunnerError(RuntimeError):
    """Raised when a plan is malformed, unsafe, or rejected."""


# ─── plan ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class WorkerPlan:
    """One worker entry within an :class:`ExecutionPlan`."""

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
    metadata: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if not self.worker_id or not self.worker_id.strip():
            raise RunnerError("worker_id is required")
        if not self.profile or not self.profile.strip():
            raise RunnerError("profile is required")
        if not isinstance(self.mode, ExecutionMode):
            raise RunnerError("mode must be an ExecutionMode")
        if self.timeout_seconds <= 0:
            raise RunnerError("timeout_seconds must be positive")
        if self.timeout_seconds > MAX_TIMEOUT_SECONDS:
            raise RunnerError(
                f"timeout_seconds {self.timeout_seconds} exceeds cap "
                f"{MAX_TIMEOUT_SECONDS}"
            )
        if self.mode in (ExecutionMode.LOCAL_RUN, ExecutionMode.REMOTE_RUN):
            if not self.command:
                raise RunnerError(
                    f"worker {self.worker_id!r} mode {self.mode.value!r} "
                    "requires a command"
                )
            joined = " ".join(str(part) for part in self.command)
            for forbidden in FORBIDDEN_COMMAND_TOKENS:
                if forbidden in joined:
                    raise RunnerError(
                        f"worker {self.worker_id!r} command contains "
                        f"forbidden token: {forbidden!r}"
                    )
        if self.mode is ExecutionMode.HANDOFF_REQUIRED and not self.handoff:
            raise RunnerError(
                f"worker {self.worker_id!r} is handoff-required but has no "
                "handoff metadata"
            )


@dataclass(frozen=True)
class ExecutionPlan:
    """A job: ``job_id``, selected workers, concurrency, approval state."""

    job_id: str
    workers: Sequence[WorkerPlan]
    concurrency: int = DEFAULT_CONCURRENCY
    use_worktrees: bool = False
    base_ref: Optional[str] = None
    allow_dirty: bool = False
    approval_state: ApprovalState = ApprovalState.PENDING
    description: str = ""

    def validate(self) -> None:
        if not self.job_id or not self.job_id.strip():
            raise RunnerError("job_id is required")
        if not self.workers:
            raise RunnerError("plan must contain at least one worker")
        if self.concurrency < 1:
            raise RunnerError("concurrency must be >= 1")
        if self.concurrency > MAX_CONCURRENCY:
            raise RunnerError(
                f"concurrency {self.concurrency} exceeds safe cap {MAX_CONCURRENCY}"
            )
        if not isinstance(self.approval_state, ApprovalState):
            raise RunnerError("approval_state must be an ApprovalState")
        seen: set[str] = set()
        for worker in self.workers:
            worker.validate()
            if worker.worker_id in seen:
                raise RunnerError(f"duplicate worker_id: {worker.worker_id!r}")
            seen.add(worker.worker_id)

    def has_remote_run(self) -> bool:
        return any(w.mode is ExecutionMode.REMOTE_RUN for w in self.workers)

    def with_approval(self, approval_state: ApprovalState) -> "ExecutionPlan":
        """Return a copy of the plan with a new approval state."""

        return ExecutionPlan(
            job_id=self.job_id,
            workers=tuple(self.workers),
            concurrency=self.concurrency,
            use_worktrees=self.use_worktrees,
            base_ref=self.base_ref,
            allow_dirty=self.allow_dirty,
            approval_state=approval_state,
            description=self.description,
        )


# ─── status ───────────────────────────────────────────────────────────


@dataclass
class WorkerStatus:
    """Mutable per-worker status snapshot persisted to ``status.json``."""

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
    attempt: int = 1

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["state"] = (
            self.state.value if isinstance(self.state, WorkerState) else self.state
        )
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorkerStatus":
        state_value = data.get("state") or WorkerState.PENDING.value
        try:
            state = WorkerState(state_value)
        except ValueError:
            state = WorkerState.PENDING
        return cls(
            worker_id=str(data.get("worker_id", "")),
            profile=str(data.get("profile", "")),
            mode=str(data.get("mode", "")),
            state=state,
            started_at=data.get("started_at"),
            ended_at=data.get("ended_at"),
            return_code=data.get("return_code"),
            error=data.get("error"),
            stdout_path=data.get("stdout_path"),
            stderr_path=data.get("stderr_path"),
            worktree_path=data.get("worktree_path"),
            branch=data.get("branch"),
            handoff_path=data.get("handoff_path"),
            prompt_path=data.get("prompt_path"),
            attempt=int(data.get("attempt", 1) or 1),
        )


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
    """Drop the ``cancel.requested`` flag for ``job_id``.

    Safe to call from another process while a :class:`ParallelRunner`
    is running. The runner polls for this file between iterations and
    terminates any in-flight subprocesses when it appears.
    """

    target = cancel_flag_path(repo, job_id)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(_now_iso() + "\n", encoding="utf-8")
    return target


def clear_cancel(repo: Path, job_id: str) -> bool:
    """Remove the cancel flag if it exists. Idempotent."""

    target = cancel_flag_path(repo, job_id)
    if not target.exists():
        return False
    try:
        target.unlink()
        return True
    except OSError:
        return False


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ─── runner ───────────────────────────────────────────────────────────


StatusCallback = Callable[[WorkerStatus], None]


class ParallelRunner:
    """Run an :class:`ExecutionPlan` and persist auditable artifacts."""

    def __init__(
        self,
        repo: Path,
        plan: ExecutionPlan,
        *,
        on_status: Optional[StatusCallback] = None,
        poll_interval: float = 0.5,
        resume: bool = False,
    ) -> None:
        self.repo = Path(repo).resolve()
        plan.validate()
        self.plan = plan
        self.on_status = on_status
        self.poll_interval = max(0.05, float(poll_interval))
        self.resume = bool(resume)
        self.statuses: dict[str, WorkerStatus] = {
            w.worker_id: WorkerStatus(
                worker_id=w.worker_id,
                profile=w.profile,
                mode=w.mode.value,
            )
            for w in plan.workers
        }
        if self.resume:
            self._merge_existing_status()
        self._cancel_event = threading.Event()
        self._status_lock = threading.Lock()
        self._worktrees: dict[str, wt.WorktreeInfo] = {}

    # ── public API ────────────────────────────────────────────────

    def run(self) -> dict[str, WorkerStatus]:
        """Run the plan to completion and return per-worker statuses."""

        job_root = job_dir(self.repo, self.plan.job_id)
        job_root.mkdir(parents=True, exist_ok=True)
        self._write_status_snapshot(initial=True)

        pending_workers = [
            w for w in self.plan.workers if self._should_dispatch(w.worker_id)
        ]

        if self.plan.use_worktrees:
            self._provision_worktrees(pending_workers)

        if self.plan.concurrency <= 1 or len(pending_workers) <= 1:
            for worker in pending_workers:
                if self._is_cancelled():
                    self._mark_cancelled(worker.worker_id)
                    continue
                self._execute_worker(worker)
        else:
            with ThreadPoolExecutor(max_workers=self.plan.concurrency) as pool:
                futures = {
                    pool.submit(self._execute_worker, worker): worker
                    for worker in pending_workers
                }
                for future in as_completed(futures):
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
        """Set the in-process cancel event AND drop the flag file."""

        self._cancel_event.set()
        request_cancel(self.repo, self.plan.job_id)

    # ── resume ────────────────────────────────────────────────────

    def _merge_existing_status(self) -> None:
        existing = load_status(self.repo, self.plan.job_id)
        if not existing:
            return
        for entry in existing.get("workers", []) or []:
            wid = str(entry.get("worker_id") or "")
            if wid not in self.statuses:
                continue
            prior = WorkerStatus.from_dict(entry)
            if prior.state in (
                WorkerState.COMPLETED,
                WorkerState.AWAITING_HANDOFF,
                WorkerState.CANCELLED,
                WorkerState.SKIPPED_RESUMED,
            ):
                prior.state = (
                    WorkerState.SKIPPED_RESUMED
                    if prior.state is WorkerState.COMPLETED
                    else prior.state
                )
                self.statuses[wid] = prior
            else:
                # Reset state so resume can re-dispatch it, but keep the
                # attempt counter so the audit trail shows the retry.
                self.statuses[wid] = WorkerStatus(
                    worker_id=prior.worker_id,
                    profile=prior.profile,
                    mode=prior.mode,
                    state=WorkerState.PENDING,
                    attempt=prior.attempt + 1,
                )

    def _should_dispatch(self, worker_id: str) -> bool:
        status = self.statuses.get(worker_id)
        if status is None:
            return False
        if status.state in (
            WorkerState.COMPLETED,
            WorkerState.AWAITING_HANDOFF,
            WorkerState.CANCELLED,
            WorkerState.SKIPPED_RESUMED,
        ):
            return False
        return True

    # ── worktree provisioning ────────────────────────────────────

    def _provision_worktrees(self, workers: list[WorkerPlan]) -> None:
        for worker in workers:
            if not worker.use_worktree:
                continue
            if self.statuses[worker.worker_id].worktree_path:
                # Resume: a previous run already created the worktree.
                continue
            info = wt.create_worktree(
                self.repo,
                job_id=self.plan.job_id,
                worker_id=worker.worker_id,
                base_ref=self.plan.base_ref,
                allow_dirty=self.plan.allow_dirty,
                extra_metadata={
                    "profile": worker.profile,
                    "mode": worker.mode.value,
                    "attempt": self.statuses[worker.worker_id].attempt,
                },
            )
            self._worktrees[worker.worker_id] = info
            self._update(
                worker.worker_id,
                worktree_path=str(info.path),
                branch=info.branch,
            )

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
        self._update(
            worker.worker_id,
            prompt_path=str(prompt_path) if worker.prompt else None,
        )

        if worker.mode is ExecutionMode.PROMPT_ONLY:
            self._update(
                worker.worker_id,
                state=WorkerState.COMPLETED,
                started_at=_now_iso(),
                ended_at=_now_iso(),
            )
            return

        if worker.mode is ExecutionMode.HANDOFF_REQUIRED:
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
            return

        if worker.mode is ExecutionMode.REMOTE_RUN:
            if self.plan.approval_state is not ApprovalState.APPROVED:
                self._update(
                    worker.worker_id,
                    state=WorkerState.BLOCKED_BY_APPROVAL,
                    started_at=_now_iso(),
                    ended_at=_now_iso(),
                    error=(
                        "remote-run requires plan approval_state="
                        "approved; refusing to dispatch"
                    ),
                )
                return

        # LOCAL_RUN or APPROVED REMOTE_RUN
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
            ended_at=None,
            return_code=None,
            error=None,
        )

        proc: Optional[subprocess.Popen[str]] = None
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
                            state=(
                                WorkerState.COMPLETED
                                if rc == 0
                                else WorkerState.FAILED
                            ),
                            return_code=rc,
                            ended_at=_now_iso(),
                            error=None if rc == 0 else f"exit code {rc}",
                        )
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
                        return
                    if time.monotonic() >= deadline:
                        _terminate(proc)
                        self._update(
                            worker.worker_id,
                            state=WorkerState.TIMED_OUT,
                            ended_at=_now_iso(),
                            error=(
                                f"exceeded timeout {worker.timeout_seconds}s"
                            ),
                            return_code=proc.returncode,
                        )
                        return
                    time.sleep(self.poll_interval)
        except FileNotFoundError as exc:
            self._update(
                worker.worker_id,
                state=WorkerState.FAILED,
                ended_at=_now_iso(),
                error=f"command not found: {exc}",
            )
        except OSError as exc:
            self._update(
                worker.worker_id,
                state=WorkerState.FAILED,
                ended_at=_now_iso(),
                error=f"os error: {exc}",
            )

    # ── status bookkeeping ──────────────────────────────────────

    def _update(self, worker_id: str, **fields: Any) -> None:
        snapshot: Optional[WorkerStatus] = None
        with self._status_lock:
            status = self.statuses[worker_id]
            for key, value in fields.items():
                setattr(status, key, value)
            snapshot = WorkerStatus(
                worker_id=status.worker_id,
                profile=status.profile,
                mode=status.mode,
                state=(
                    status.state
                    if isinstance(status.state, WorkerState)
                    else WorkerState(status.state)
                ),
                started_at=status.started_at,
                ended_at=status.ended_at,
                return_code=status.return_code,
                error=status.error,
                stdout_path=status.stdout_path,
                stderr_path=status.stderr_path,
                worktree_path=status.worktree_path,
                branch=status.branch,
                handoff_path=status.handoff_path,
                prompt_path=status.prompt_path,
                attempt=status.attempt,
            )
            self._write_status_snapshot_locked()
        if self.on_status is not None and snapshot is not None:
            try:
                self.on_status(snapshot)
            except Exception:
                # Status callbacks must never break execution.
                pass

    def _mark_cancelled(self, worker_id: str) -> None:
        with self._status_lock:
            status = self.statuses[worker_id]
            if status.state is WorkerState.PENDING:
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
        payload: dict[str, Any] = {
            "job_id": self.plan.job_id,
            "updated_at": _now_iso(),
            "concurrency": self.plan.concurrency,
            "use_worktrees": self.plan.use_worktrees,
            "approval_state": self.plan.approval_state.value,
            "description": self.plan.description,
            "workers": [s.as_dict() for s in self.statuses.values()],
        }
        if initial:
            payload["created_at"] = payload["updated_at"]
        else:
            existing = _load_existing_created_at(path)
            if existing:
                payload["created_at"] = existing
            else:
                payload["created_at"] = payload["updated_at"]
        path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


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


# ─── convenience helpers ────────────────────────────────────────────


def parse_command(command: str | Sequence[str]) -> list[str]:
    """Turn a string command into argv. Lists pass through unchanged."""

    if isinstance(command, str):
        return shlex.split(command)
    return list(command)


def load_status(repo: Path, job_id: str) -> Optional[dict[str, Any]]:
    """Read ``status.json`` for ``job_id`` (or return ``None``)."""

    path = status_path(Path(repo), job_id)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def list_jobs(repo: Path) -> list[str]:
    """List the job IDs that have a ``status.json`` on disk."""

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
    """Tear down every worktree belonging to ``job_id``.

    Requires explicit ``confirm_destructive=True`` — otherwise this is
    a no-op that returns ``[]``. Matches the Phase 13 safety rule
    "no destructive cleanup".
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
    "ApprovalState",
    "CANCEL_FLAG_FILENAME",
    "DEFAULT_CONCURRENCY",
    "DEFAULT_TIMEOUT_SECONDS",
    "ExecutionMode",
    "ExecutionPlan",
    "FORBIDDEN_COMMAND_TOKENS",
    "MAX_CONCURRENCY",
    "MAX_TIMEOUT_SECONDS",
    "ParallelRunner",
    "RESUMABLE_STATES",
    "RunnerError",
    "STATUS_FILENAME",
    "TERMINAL_STATES",
    "WorkerPlan",
    "WorkerState",
    "WorkerStatus",
    "cancel_flag_path",
    "cleanup_job_worktrees",
    "clear_cancel",
    "job_dir",
    "list_jobs",
    "load_status",
    "parse_command",
    "request_cancel",
    "status_path",
    "worker_dir",
]
