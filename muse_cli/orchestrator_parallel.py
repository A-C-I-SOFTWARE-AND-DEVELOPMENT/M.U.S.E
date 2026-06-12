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

Per-job cost emission (the producer side of the Sprint 10 cost seam)
----------------------------------------------------------------------

A LOCAL_RUN worker that runs the agent can record its token/cost usage so
the per-job cost meter actually accumulates. The contract is a sidecar
file, ``usage.json``, written into the worker's own dir *before it exits*,
in the shape produced by ``agent.conversation_loop.build_usage_record``::

    {"usage": {<token buckets>}, "cost_usd": float,
     "model": str, "provider": str}

When such a worker finishes cleanly (exit code 0), the runner reads and
sanitizes that sidecar and folds it into the worker's ``WorkerStatus.usage``,
which is persisted into ``status.json`` verbatim — already in the exact shape
``muse_cli.orchestrator_api._extract_usage_report`` consumes.

This runner is intentionally **standalone**: it is not wired to a
``JobStore`` and never calls ``accumulate_cost`` itself (it only persists
artifacts to disk). The one remaining hop — draining the persisted usage into
a job's ``JobCost`` — is exposed as :func:`iter_worker_usage`, which yields
``(worker_id, usage_block)`` pairs ready to hand to
``JobStore.update_worker`` (the consumer seam merged in #301). A caller that
holds a ``JobStore`` performs that final fold; the runner deliberately does
not fabricate a store connection it doesn't own.

Budget hard-stop (the enforcement side of the Sprint 10 budget kernel)
----------------------------------------------------------------------

The runner can be given an optional per-job budget via
``budget_soft_limit`` / ``budget_hard_limit`` (USD). It meters each
worker's reported ``cost_usd`` as it completes, and — once the accumulated
spend reaches the **hard** limit — stops launching the remaining workers
(:func:`muse_cli.budget_policy.evaluate_budget`). In the sequential path
every still-pending worker is recorded as stopped; in the concurrent path
the runner signals cancel so the pool stops starting not-yet-launched
workers (in-flight workers finish). The stop is persisted as a ``budget``
block in ``status.json``. Both limits default to ``None`` (no enforcement),
so the budget feature is strictly additive and behavior-preserving.

Runtime adapter + reschedule plan (the Sprint 13 wiring, both opt-in)
----------------------------------------------------------------------

Two Sprint 13 building blocks can be wired in *without* changing the default
path — when neither is requested, execution is byte-for-byte the existing
inline-subprocess local run:

* ``runtime_adapter`` (a :class:`muse_cli.runtime_adapter.RuntimeAdapter`,
  default ``None``) — when supplied, a *plain* LOCAL_RUN worker's command runs
  through ``adapter.run(command, timeout=...)`` instead of the inline
  ``subprocess`` loop, and the returned
  :class:`~muse_cli.runtime_adapter.RuntimeResult`
  (returncode / stdout_path / stderr_path / duration / timed_out) is mapped onto
  the same :class:`WorkerStatus` fields. For a
  :class:`~muse_cli.runtime_adapter.LocalRuntimeAdapter` the two paths are
  observably equivalent (same terminal state, return code, captured streams).
  A worker that carries per-worker placement the adapter cannot honor — its own
  ``cwd``, an ``env`` overlay, or a worktree-derived cwd — stays on the inline
  path (see ``_needs_inline_placement``), so the adapter path is never used
  where it would run the command in the wrong directory/environment; and
  adapter-backed cancellation is bounded by ``timeout_seconds`` rather than
  prompt (see :meth:`ParallelRunner._run_via_adapter`). When ``None`` (the
  default) nothing about the local path changes.
* :meth:`ParallelRunner.compute_reschedule_plan` — an *observable* computation
  that folds :func:`muse_cli.lease_scheduler.reschedule_plan` over the lease
  store's host registry + leases and returns / records the resulting
  :class:`~muse_cli.lease_scheduler.Reschedule` proposals (also exposed as
  :attr:`ParallelRunner.reschedule_plan`). It **decides, it does not act**: no
  retry is auto-executed and no lease is mutated — actually re-leasing the lost
  work on the chosen host is a documented follow-up. Computing the plan is the
  deliverable.

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

from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
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

from muse_cli import lease_scheduler
from muse_cli import worktrees as wt
from muse_cli import worker_lease as wl
from muse_cli.budget_policy import BudgetDecision, evaluate_budget
from muse_cli.lease_scheduler import Reschedule
from muse_cli.runtime_adapter import RuntimeAdapter, RuntimeResult
from muse_cli.worker_lease_store import DEFAULT_HOST_ID, WorkerLeaseStore

ORCHESTRATOR_DIRNAME = wt.ORCHESTRATOR_DIRNAME
JOBS_SUBDIR = "jobs"
STATUS_FILENAME = "status.json"
CANCEL_FLAG_FILENAME = "cancel.requested"
HANDOFF_FILENAME = "handoff.json"
PROMPT_FILENAME = "prompt.txt"
STDOUT_LOG = "stdout.log"
STDERR_LOG = "stderr.log"
# A LOCAL_RUN worker that knows its model usage writes this sidecar into its
# own worker dir before exiting; the runner reads it back when the worker
# finishes cleanly and folds it into ``status.json`` (and the per-worker
# ``WorkerStatus.usage``) in the exact ``{usage, cost_usd, model, provider}``
# shape ``muse_cli.orchestrator_api`` consumes. See ``_read_usage_sidecar``.
USAGE_FILENAME = "usage.json"

# Token bucket field names in the canonical (``CanonicalUsage``) spelling. Kept
# explicit so a stray key in a worker's sidecar can't leak into the token math.
_USAGE_TOKEN_FIELDS = (
    "input_tokens",
    "output_tokens",
    "cache_read_tokens",
    "cache_write_tokens",
    "reasoning_tokens",
)

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
    # Optional usage/cost block in the ``{usage, cost_usd, model, provider}``
    # shape ``muse_cli.orchestrator_api`` consumes. Populated from a worker's
    # ``usage.json`` sidecar when a LOCAL_RUN worker finishes cleanly; ``None``
    # for workers that report no usage (the additive default).
    usage: Optional[dict[str, Any]] = None

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


def usage_path(repo: Path, job_id: str, worker_id: str) -> Path:
    """Path to a worker's usage sidecar (``usage.json``) in its worker dir.

    A LOCAL_RUN worker writes its machine-readable usage block here (via
    ``agent.conversation_loop.build_usage_record``) before exiting; the runner
    reads it back when the worker finishes cleanly.
    """

    return worker_dir(repo, job_id, worker_id) / USAGE_FILENAME


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


def _needs_inline_placement(worker: WorkerPlan) -> bool:
    """True when a worker must run inline even if a runtime adapter is injected.

    The :class:`~muse_cli.runtime_adapter.RuntimeAdapter` contract takes only
    ``command`` + ``timeout``; an adapter's working directory and environment
    are single-valued, construction-time concerns. A worker that carries its own
    ``cwd``, an ``env`` overlay, or a worktree-derived ``cwd`` therefore cannot
    be honored faithfully by a shared, injected adapter — routing it there would
    silently run the command in the adapter's directory/environment instead of
    the worker's. Such workers stay on :meth:`ParallelRunner._run_subprocess`,
    the only path that applies per-worker placement, so the adapter path is used
    only where it is genuinely equivalent.
    """

    return bool(worker.cwd or worker.env or worker.use_worktree)


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
        budget_soft_limit: Optional[float] = None,
        budget_hard_limit: Optional[float] = None,
        runtime_adapter: Optional[RuntimeAdapter] = None,
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
        # Per-job budget enforcement (Sprint 10). Both ``None`` => no
        # enforcement (the behavior-preserving default). When a hard limit is
        # set, the runner stops launching further workers once the accumulated
        # worker cost reaches it; a soft limit is surfaced but never blocks the
        # runner here (owner confirmation lives at the orchestrator layer).
        if budget_soft_limit is not None and budget_soft_limit < 0:
            raise OrchestratorError("budget_soft_limit must be >= 0")
        if budget_hard_limit is not None and budget_hard_limit < 0:
            raise OrchestratorError("budget_hard_limit must be >= 0")
        if (
            budget_soft_limit is not None
            and budget_hard_limit is not None
            and budget_soft_limit > budget_hard_limit
        ):
            raise OrchestratorError("budget_soft_limit must be <= budget_hard_limit")
        self._budget_soft_limit = budget_soft_limit
        self._budget_hard_limit = budget_hard_limit
        self._budget_lock = threading.Lock()
        self._spent_usd = 0.0
        self._costed_workers: set[str] = set()
        self._budget_event: Optional[dict[str, Any]] = None
        # Optional runtime adapter (Sprint 13). ``None`` (default) keeps the
        # existing inline-subprocess LOCAL_RUN path byte-for-byte; when set, a
        # LOCAL_RUN worker's command runs through ``adapter.run(...)`` and its
        # RuntimeResult is mapped onto the same WorkerStatus fields. Purely
        # additive — no other mode and no other behavior is affected.
        self._runtime_adapter = runtime_adapter
        # Last computed reschedule plan (Sprint 13). ``None`` until
        # :meth:`compute_reschedule_plan` runs; the plan is *observational* — it
        # is never auto-executed (re-leasing lost work is a documented
        # follow-up).
        self._reschedule_plan: Optional[list[Reschedule]] = None

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
                # Hard budget reached by a prior worker's cost → stop launching
                # the rest. Each remaining worker is recorded as stopped (never
                # run), so the halt is auditable in status.json.
                stop = self._budget_stop_decision()
                if stop is not None:
                    self._record_budget_event(stop)
                    self._mark_cancelled(
                        worker.worker_id, reason=f"stopped: {stop.detail}"
                    )
                    continue
                self._execute_worker(worker)
        else:
            self._run_concurrent()

        self._write_status_snapshot()
        return dict(self.statuses)

    def _run_concurrent(self) -> None:
        """Run workers in a bounded pool, gating each *launch* on the budget.

        A worker is only started while the accrued cost is still within the
        hard budget, so a pre-exhausted hard budget (e.g. ``budget_hard_limit
        =0.0``) starts nothing — exactly like the sequential path, and unlike a
        submit-everything-up-front pool that would race ``concurrency`` workers
        out before the first completion. The max-concurrency guarantee is
        unchanged (the pool still runs at most ``concurrency`` at once); only
        *when* a pending worker is queued differs.
        """

        pending = list(self.plan.workers)
        next_index = 0
        futures: dict[Future[None], WorkerPlan] = {}

        with ThreadPoolExecutor(max_workers=self.plan.concurrency) as pool:

            def _try_launch_one() -> bool:
                """Launch the next pending worker, skipping those a cancel or an
                exhausted budget rules out (recorded as stopped). Returns True
                once a worker is actually submitted, False when none remain."""
                nonlocal next_index
                while next_index < len(pending):
                    worker = pending[next_index]
                    next_index += 1
                    if self._is_cancelled():
                        self._mark_cancelled(worker.worker_id)
                        continue
                    stop = self._budget_stop_decision()
                    if stop is not None:
                        self._record_budget_event(stop)
                        self._mark_cancelled(
                            worker.worker_id, reason=f"stopped: {stop.detail}"
                        )
                        continue
                    futures[pool.submit(self._execute_worker, worker)] = worker
                    return True
                return False

            # Prime the pool (budget-gated): a pre-exhausted budget submits none.
            for _ in range(self.plan.concurrency):
                if not _try_launch_one():
                    break
            # As each worker finishes, fold in its cost (via _update) and try to
            # launch the next pending worker — which re-checks the budget, so a
            # mid-run overrun stops the remaining workers before they start.
            while futures:
                done_set, _ = wait(list(futures), return_when=FIRST_COMPLETED)
                for future in done_set:
                    worker = futures.pop(future)
                    # Surface unexpected exceptions through the worker status
                    # (per-worker errors are written inline; a raise here would
                    # be a programmer bug).
                    exc = future.exception()
                    if exc is not None:
                        self._update(
                            worker.worker_id,
                            state=WorkerState.FAILED,
                            error=f"runner exception: {exc!r}",
                            ended_at=_now_iso(),
                        )
                    _try_launch_one()

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
            self._lease_store.upsert(lease)  # type: ignore[union-attr]  # ty: ignore[unresolved-attribute]  # dynamic config/plugin path
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

        # LOCAL_RUN. With no runtime adapter (the default) this is the existing
        # inline-subprocess path, unchanged. When an adapter is injected, a
        # *plain* local-run worker runs through it and its RuntimeResult is
        # mapped onto the same WorkerStatus fields (observably equivalent for
        # LocalRuntimeAdapter). A worker that carries per-worker placement — its
        # own cwd, an env overlay, or a worktree-derived cwd — stays on the
        # inline path, the only one that honors those: a shared injected adapter
        # has a single construction-time cwd/env and cannot apply them per
        # worker, so routing such a worker through it would silently run the
        # command in the wrong directory/environment.
        if self._runtime_adapter is None or _needs_inline_placement(worker):
            self._run_subprocess(worker, worker_root)
        else:
            self._run_via_adapter(worker, worker_root, self._runtime_adapter)

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
                        # On clean exit, fold in any usage the worker reported
                        # via its ``usage.json`` sidecar. Best-effort: a missing
                        # / malformed sidecar yields ``None`` and the cost meter
                        # stays untouched (additive default). Only successful
                        # runs are trusted to have written a complete record.
                        usage_block = (
                            _read_usage_sidecar(worker_root) if rc == 0 else None
                        )
                        self._update(
                            worker.worker_id,
                            state=WorkerState.COMPLETED if rc == 0 else WorkerState.FAILED,
                            return_code=rc,
                            ended_at=_now_iso(),
                            error=None if rc == 0 else f"exit code {rc}",
                            usage=usage_block,
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

    def _run_via_adapter(
        self, worker: WorkerPlan, worker_root: Path, adapter: RuntimeAdapter
    ) -> None:
        """Run a LOCAL_RUN worker through an injected :class:`RuntimeAdapter`.

        This is the adapter-backed twin of :meth:`_run_subprocess`. It maps the
        adapter's :class:`~muse_cli.runtime_adapter.RuntimeResult` onto the
        same :class:`WorkerStatus` fields the inline path uses, so for a
        :class:`~muse_cli.runtime_adapter.LocalRuntimeAdapter` the observable
        outcome (terminal state, return code, captured stream paths, lease
        lifecycle) matches the default path. The adapter owns *where* the
        command runs (its ``cwd``/``env``/streams are construction-time
        concerns); the runner only hands it the command + timeout and records
        the result.

        Cancellation here is **bounded, not prompt**, and that is the one
        deliberate difference from the inline loop. ``adapter.run`` blocks until
        the command finishes (or its own ``timeout`` fires), and the
        :class:`~muse_cli.runtime_adapter.RuntimeAdapter` contract exposes no
        terminate hook, so a cancel is observed only at the boundaries: a worker
        cancelled *before* launch is recorded as cancelled without running, and a
        cancel that lands *while the command is in flight* is honored once
        ``run`` returns — at most ``timeout_seconds`` later, since the adapter
        kills its own child at the deadline. The inline path, by contrast, polls
        and kills the child mid-flight. Prompt mid-flight cancellation for
        adapter-backed workers needs a cancel/terminate member on the adapter
        Protocol and is a documented follow-up (tracked with the ssh/docker
        adapter work); until then the bounded latency above applies. Workers
        that need either prompt cancellation or per-worker cwd/env/worktree are
        already kept on the inline path by ``_needs_inline_placement``.
        """

        # Honor an already-requested cancel before doing any work, mirroring the
        # _execute_worker entry guard (the inline path's poll loop catches this
        # on its first iteration).
        if self._is_cancelled():
            self._mark_cancelled(worker.worker_id, reason="cancelled by orchestrator")
            return

        self._update(
            worker.worker_id,
            state=WorkerState.RUNNING,
            started_at=_now_iso(),
        )
        self._record_acquire(worker)

        try:
            result: RuntimeResult = adapter.run(
                list(worker.command or []), timeout=float(worker.timeout_seconds)
            )
        except FileNotFoundError as exc:
            self._update(
                worker.worker_id,
                state=WorkerState.FAILED,
                ended_at=_now_iso(),
                error=f"command not found: {exc}",
            )
            self._record_lost(worker.worker_id)
            return
        except OSError as exc:
            self._update(
                worker.worker_id,
                state=WorkerState.FAILED,
                ended_at=_now_iso(),
                error=f"os error: {exc}",
            )
            self._record_lost(worker.worker_id)
            return

        stdout_path = str(result.stdout_path)
        stderr_path = str(result.stderr_path)

        # A cancel that arrived while the command ran takes precedence over a
        # natural exit — same precedence the inline loop gives the cancel check.
        if self._is_cancelled():
            self._update(
                worker.worker_id,
                state=WorkerState.CANCELLED,
                ended_at=_now_iso(),
                error="cancelled by orchestrator",
                return_code=result.returncode,
                stdout_path=stdout_path,
                stderr_path=stderr_path,
            )
            self._record_lost(worker.worker_id)
            return

        if result.timed_out:
            self._update(
                worker.worker_id,
                state=WorkerState.TIMED_OUT,
                ended_at=_now_iso(),
                error=f"exceeded timeout {worker.timeout_seconds}s",
                return_code=result.returncode,
                stdout_path=stdout_path,
                stderr_path=stderr_path,
            )
            self._record_lost(worker.worker_id)
            return

        rc = result.returncode
        # On clean exit, fold in any usage the worker reported via its
        # ``usage.json`` sidecar — identical to the inline path's contract.
        usage_block = _read_usage_sidecar(worker_root) if rc == 0 else None
        self._update(
            worker.worker_id,
            state=WorkerState.COMPLETED if rc == 0 else WorkerState.FAILED,
            return_code=rc,
            ended_at=_now_iso(),
            error=None if rc == 0 else f"exit code {rc}",
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            usage=usage_block,
        )
        if rc == 0:
            self._record_complete(worker.worker_id)
        else:
            self._record_lost(worker.worker_id)

    # ── reschedule plan (observational; never auto-executed) ─────

    def compute_reschedule_plan(
        self, now: Optional[float] = None
    ) -> list[Reschedule]:
        """Compute (and record) a reschedule plan for lost-but-retryable leases.

        Folds the frozen :func:`muse_cli.lease_scheduler.reschedule_plan` over
        the lease store's host registry and leases: each ``EXPIRED`` + idempotent
        lease yields a :class:`~muse_cli.lease_scheduler.Reschedule` proposal
        onto the least-loaded registered host. Stale ``RUNNING`` leases past
        their deadline are first folded to ``EXPIRED`` via the store's own
        ``expire_stale`` (the frozen kernel rule) so a lost-but-not-yet-reaped
        lease is considered.

        This **decides; it does not act** — no retry is launched and no lease is
        re-leased here (that is a documented follow-up). The returned plan is
        also stored on :attr:`reschedule_plan` for later inspection. Returns an
        empty list when there is no lease store, no registered host, or nothing
        retryable (the additive default).
        """

        store = self._lease_store
        if store is None:
            self._reschedule_plan = []
            return []
        when = time.time() if now is None else float(now)
        # Best-effort: a locked/broken store must never raise out of an
        # observational helper. On any failure, record an empty plan.
        try:
            # Fold stale RUNNING leases to EXPIRED first (kernel rule), so a
            # lost lease whose worker never reported done is reschedulable.
            store.expire_stale(when)
            plan = lease_scheduler.reschedule_plan(
                when, hosts=store.hosts(), leases=store.all_leases()
            )
        except Exception:
            plan = []
        self._reschedule_plan = plan
        return plan

    @property
    def reschedule_plan(self) -> Optional[list[Reschedule]]:
        """The last plan from :meth:`compute_reschedule_plan` (``None`` if never run)."""

        return self._reschedule_plan

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
        # Fold a completed worker's reported cost into the running budget meter.
        # ``usage`` is attached exactly once (on clean completion), so counting
        # here — outside the status lock to avoid lock ordering — meters each
        # worker at most once (the dedupe set is belt-and-braces).
        if "usage" in fields:
            self._note_cost(worker_id, fields.get("usage"))
        if self.on_status is not None:
            try:
                self.on_status(snapshot)
            except Exception:
                # Status callbacks must never break execution.
                pass

    def _mark_cancelled(
        self, worker_id: str, *, reason: str = "cancelled before start"
    ) -> None:
        with self._status_lock:
            status = self.statuses[worker_id]
            if status.state in (WorkerState.PENDING,):
                status.state = WorkerState.CANCELLED
                status.ended_at = _now_iso()
                status.error = reason
            self._write_status_snapshot_locked()

    # ── budget enforcement (Sprint 10) ───────────────────────────

    def _note_cost(self, worker_id: str, usage_block: Optional[dict[str, Any]]) -> None:
        """Add a completed worker's reported ``cost_usd`` to the meter, once.

        A worker that reported no usage (or a non-positive / malformed cost)
        leaves the meter untouched — the additive, behavior-preserving default.
        """

        if not isinstance(usage_block, dict):
            return
        cost = usage_block.get("cost_usd")
        if isinstance(cost, bool) or not isinstance(cost, (int, float)) or cost <= 0:
            return
        with self._budget_lock:
            if worker_id in self._costed_workers:
                return
            self._costed_workers.add(worker_id)
            self._spent_usd += float(cost)

    def _budget_stop_decision(self) -> Optional[BudgetDecision]:
        """Return the hard-stop budget decision when the meter is exhausted.

        ``None`` when no budget is configured or the spend is still within the
        hard limit (so the runner keeps launching workers).
        """

        if self._budget_soft_limit is None and self._budget_hard_limit is None:
            return None
        with self._budget_lock:
            spent = self._spent_usd
        decision = evaluate_budget(
            spent,
            soft_limit=self._budget_soft_limit,
            hard_limit=self._budget_hard_limit,
            meter="cost",
        )
        return decision if decision.should_stop else None

    def _record_budget_event(self, decision: BudgetDecision) -> None:
        """Persist the budget hard-stop into ``status.json`` exactly once."""

        with self._status_lock:
            if self._budget_event is not None:
                return
            self._budget_event = {
                "stopped": True,
                "meter": decision.meter,
                "spent": decision.spent,
                "soft_limit": decision.soft_limit,
                "hard_limit": decision.hard_limit,
                "detail": decision.detail,
            }
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
            "workers": [s.as_dict() for s in self.statuses.values()],
        }
        if self._budget_event is not None:
            payload["budget"] = dict(self._budget_event)
        if initial:
            payload["created_at"] = payload["updated_at"]
        else:
            existing = _load_existing_created_at(path)
            if existing:
                payload["created_at"] = existing
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _sanitize_usage_block(raw: Any) -> Optional[dict[str, Any]]:
    """Validate a worker-reported usage mapping into the consumer's shape.

    Accepts the dict produced by ``agent.conversation_loop.build_usage_record``
    and returns a clean ``{usage, cost_usd, model, provider}`` block — exactly
    what ``muse_cli.orchestrator_api._extract_usage_report`` reads. Junk is
    dropped rather than raised on: a malformed sidecar must never fail a run or
    poison the cost meter. Returns ``None`` when there is no usable signal (no
    positive token bucket and no positive cost).
    """

    if not isinstance(raw, dict):
        return None

    tokens: dict[str, int] = {}
    raw_usage = raw.get("usage")
    if isinstance(raw_usage, dict):
        for field_name in _USAGE_TOKEN_FIELDS:
            value = raw_usage.get(field_name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                continue
            count = int(value)
            if count > 0:
                tokens[field_name] = count

    cost_usd = raw.get("cost_usd")
    if isinstance(cost_usd, bool) or not isinstance(cost_usd, (int, float)):
        cost_usd = None
    elif float(cost_usd) < 0:
        cost_usd = None
    else:
        cost_usd = float(cost_usd)

    has_positive_cost = cost_usd is not None and cost_usd > 0
    if not tokens and not has_positive_cost:
        return None

    block: dict[str, Any] = {}
    if tokens:
        block["usage"] = tokens
    block["cost_usd"] = cost_usd if cost_usd is not None else 0.0
    model = raw.get("model")
    if isinstance(model, str) and model.strip():
        block["model"] = model.strip()
    provider = raw.get("provider")
    if isinstance(provider, str) and provider.strip():
        block["provider"] = provider.strip()
    return block


def _read_usage_sidecar(worker_root: Path) -> Optional[dict[str, Any]]:
    """Read + sanitize a worker's ``usage.json`` sidecar, or ``None``.

    Best-effort: a missing file, unreadable bytes, or malformed JSON all yield
    ``None`` so a worker that does not report usage (or writes garbage) simply
    leaves the cost meter untouched — the additive, behavior-preserving default.
    """

    path = worker_root / USAGE_FILENAME
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return _sanitize_usage_block(raw)


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


def write_usage_sidecar(
    repo: Path,
    job_id: str,
    worker_id: str,
    record: Optional[dict[str, Any]],
) -> Optional[Path]:
    """Atomically write a worker's ``usage.json`` sidecar — the producer
    counterpart to the consumer pair :func:`_read_usage_sidecar` /
    :func:`iter_worker_usage`.

    ``record`` is the canonical ``{usage, cost_usd, model, provider}`` block
    produced by :func:`agent.conversation_loop.build_usage_record`. Pass that
    function's return value straight through: a no-op turn (no tokens, no cost)
    yields ``None`` and this writes nothing and returns ``None``, so the cost
    meter never moves. Building the record on the caller side (a worker that ran
    the agent already holds ``build_usage_record``) keeps this module free of the
    agent runtime — the consumer side only ever reads JSON. The supported emit
    pattern is one line::

        from agent.conversation_loop import build_usage_record
        write_usage_sidecar(repo, job_id, worker_id, build_usage_record(result))

    The block lands at :func:`usage_path` so the runner folds it into
    ``status.json`` and a ``JobStore``-holding caller drains it via
    :func:`iter_worker_usage`. The write goes through a temp file + :func:`os.replace`
    so a concurrent reader never sees a torn sidecar; ``record`` should already be
    in report shape (the reader still sanitizes defensively).

    Returns the written path, or ``None`` for a ``None`` record. This is the
    *emit* seam only — wiring a concrete in-repo agent-worker to call it, and
    auto-draining the standalone runner into a ``JobStore``, remain the documented
    follow-ups noted on :func:`iter_worker_usage`.
    """

    if record is None:
        return None

    path = usage_path(Path(repo), job_id, worker_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    os.replace(tmp, path)
    return path


def iter_worker_usage(repo: Path, job_id: str) -> list[tuple[str, dict[str, Any]]]:
    """Yield ``(worker_id, usage_block)`` for every worker that reported usage.

    This is the bridge between the standalone runner and the per-job cost
    aggregate. ``ParallelRunner`` is *not* wired to a ``JobStore`` — it only
    persists artifacts to disk — so after a run, a caller that *does* hold a
    ``JobStore`` (e.g. the orchestrator API / dispatcher) drains the reported
    usage and folds it in. Each ``usage_block`` is already in the exact report
    shape ``muse_cli.orchestrator_api._extract_usage_report`` reads — i.e. a
    body you hand straight to :meth:`JobStore.update_worker`, which detects the
    ``usage`` / ``cost_usd`` keys and routes them into
    :meth:`JobStore.accumulate_cost`::

        runner = ParallelRunner(repo, plan); runner.run()
        for worker_id, block in iter_worker_usage(repo, plan.job_id):
            await store.update_worker(job_id, worker_id, block)

    Note the block's ``usage`` sub-key is a plain token-bucket *dict*; the
    ``update_worker`` seam converts it to the ``CanonicalUsage``-shaped object
    ``JobCost.add_usage`` expects, so prefer ``update_worker`` over calling
    ``accumulate_cost(**block)`` directly (the latter would need a usage object,
    not a dict). Returns an empty list when the job has no status file or no
    worker reported usage (the additive default — nothing to accumulate).
    """

    snapshot = load_status(repo, job_id)
    if not snapshot:
        return []
    out: list[tuple[str, dict[str, Any]]] = []
    for worker in snapshot.get("workers", []):
        if not isinstance(worker, dict):
            continue
        block = _sanitize_usage_block(worker.get("usage"))
        if block is None:
            continue
        worker_id = worker.get("worker_id")
        if isinstance(worker_id, str) and worker_id:
            out.append((worker_id, block))
    return out


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
    "USAGE_FILENAME",
    "WorkerPlan",
    "WorkerState",
    "WorkerStatus",
    "cancel_flag_path",
    "cleanup_job_worktrees",
    "iter_worker_usage",
    "job_dir",
    "list_jobs",
    "load_status",
    "parse_command",
    "request_cancel",
    "status_path",
    "usage_path",
    "worker_dir",
    "write_usage_sidecar",
]
