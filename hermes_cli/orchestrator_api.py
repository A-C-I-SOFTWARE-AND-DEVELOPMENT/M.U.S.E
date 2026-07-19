"""Local-only Hermes orchestrator API + WebSocket backend.

Exposes Hermes orchestration jobs through a small FastAPI app so the
Android APK, the TUI, and other local clients can control and observe
jobs without needing to embed Hermes' Python internals.

Design constraints (see ``docs/orchestration/local-api-backend.md``):

* Local-first. Binds to ``127.0.0.1`` by default. The caller has to opt
  in to a public bind, and the app *refuses* to start with no token
  configured in that mode.
* No multi-tenant complexity. There is one shared in-memory job store
  per process. Clients are trusted local processes on the same machine.
* Token auth is optional. Without a token the API is fully open on
  loopback. Set ``HERMES_ORCHESTRATOR_API_TOKEN`` (or pass ``token=`` to
  :func:`create_app`) to require ``Authorization: Bearer <token>`` on
  every request and ``?token=<token>`` on WebSocket connects.
* No heavy framework beyond FastAPI which is already an optional
  ``[web]`` extra of hermes-agent.

The store is intentionally minimal — job state lives in memory, keyed
by job id. Persistent orchestration state is the responsibility of the
worker that handed the job to this API; this module just exposes
control + observability surfaces.
"""

from __future__ import annotations

import asyncio
import hmac
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, cast

try:
    from fastapi import (
        Depends,
        FastAPI,
        HTTPException,
        Request,
        WebSocket,
        WebSocketDisconnect,
        status,
    )
    from fastapi.responses import JSONResponse
    FASTAPI_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only without the extra
    FastAPI = None  # ty: ignore[invalid-assignment]
    HTTPException = Exception  # ty: ignore[invalid-assignment]
    WebSocket = object  # ty: ignore[invalid-assignment]
    WebSocketDisconnect = Exception  # ty: ignore[invalid-assignment]
    FASTAPI_AVAILABLE = False

from hermes_cli import job_event_store
from hermes_cli.job_cost import USAGE_TOKEN_FIELDS, JobCost, _coerce_cost, _coerce_tokens
from hermes_cli.job_replay import JobSnapshot, rebuild_snapshot
from hermes_cli.orchestrator_events import (
    ALL_EVENTS,
    ALL_PHASES,
    EVENT_APPROVAL_GRANTED,
    EVENT_APPROVAL_REJECTED,
    EVENT_APPROVAL_REQUESTED,
    EVENT_COST_ACCUMULATED,
    EVENT_ERROR,
    EVENT_EVIDENCE_UPDATED,
    EVENT_JOB_CREATED,
    EVENT_JOB_FAILED,
    EVENT_PHASE_CHANGED,
    EVENT_PUBLISH_READY,
    EVENT_SCORING_COMPLETED,
    EVENT_VALIDATION_COMPLETED,
    EVENT_WORKER_BLOCKED,
    EVENT_WORKER_COMPLETED,
    EVENT_WORKER_HEARTBEAT,
    EVENT_WORKER_STARTED,
    EventBroker,
    PHASE_AWAITING_APPROVAL,
    PHASE_CANCELLED,
    PHASE_COMPLETED,
    PHASE_EXECUTING,
    PHASE_PUBLISH_READY,
    PHASE_VALIDATING,
    make_envelope,
)

logger = logging.getLogger(__name__)

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765

# Terminal statuses — POST /jobs/{id}/cancel/resume reject these.
_TERMINAL_STATES = frozenset({"completed", "failed", "cancelled"})

_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost", "testclient"})


@dataclass
class Job:
    """In-memory representation of an orchestration job."""

    id: str
    name: str
    spec: Dict[str, Any]
    status: str = "pending"
    phase: str = "intake"
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    evidence: Dict[str, Any] = field(default_factory=dict)
    artifacts: List[Dict[str, Any]] = field(default_factory=list)
    logs: List[Dict[str, Any]] = field(default_factory=list)
    workers: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    approvals: List[Dict[str, Any]] = field(default_factory=list)
    validation: Optional[Dict[str, Any]] = None
    publish_plan: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    events: List[Dict[str, Any]] = field(default_factory=list)
    source: Optional[str] = None
    # Per-job cost / token aggregate (Sprint 10). Starts empty (zero cost,
    # zero tokens), so attaching it changes nothing until usage is recorded.
    cost: JobCost = field(default_factory=JobCost)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "spec": self.spec,
            "status": self.status,
            "phase": self.phase,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "evidence": self.evidence,
            "artifacts": self.artifacts,
            "workers": self.workers,
            "approvals": self.approvals,
            "validation": self.validation,
            "publish_plan": self.publish_plan,
            "error": self.error,
            "source": self.source,
            "cost": self.cost.totals(),
        }

    def budget_status(self) -> Optional[Dict[str, Any]]:
        """Evaluate accumulated cost against any budget configured in ``spec``.

        Reads ``spec["budget"]`` for ``soft_limit`` / ``hard_limit`` (USD) and
        an optional ``meter`` label. Returns ``None`` when no budget is
        configured (the additive default — existing jobs and tests see no
        new behavior), otherwise a serialized
        :class:`~hermes_cli.budget_policy.BudgetDecision`.
        """
        return _budget_status_for(self.spec, self.cost)


def _coerce_limit(value: Any) -> Optional[float]:
    """Parse a budget limit from a spec value, ignoring junk.

    Returns ``None`` for missing / non-numeric / negative limits so a
    malformed ``spec["budget"]`` degrades to "no limit" rather than raising.
    """
    if value is None or isinstance(value, bool):
        return None
    try:
        limit = float(value)
    except (TypeError, ValueError):
        return None
    return limit if limit >= 0 else None


def _budget_status_for(
    spec: Optional[Dict[str, Any]],
    cost: JobCost,
) -> Optional[Dict[str, Any]]:
    """Serialize a budget decision for ``cost`` given a job ``spec``.

    The budget config lives at ``spec["budget"]`` as
    ``{"soft_limit": float, "hard_limit": float, "meter": str}``. Any of the
    three may be omitted. Returns ``None`` when no usable limit is configured;
    otherwise the :class:`~hermes_cli.budget_policy.BudgetDecision` rendered as
    a plain dict (``outcome`` / ``tier`` / ``should_stop`` / ``needs_approval``
    / ``spent`` / limits / ``meter`` / ``detail``).
    """
    budget_cfg = (spec or {}).get("budget")
    if not isinstance(budget_cfg, dict):
        return None
    soft_limit = _coerce_limit(budget_cfg.get("soft_limit"))
    hard_limit = _coerce_limit(budget_cfg.get("hard_limit"))
    if soft_limit is None and hard_limit is None:
        return None
    # If both are set but mis-ordered, fall back to "no budget" rather than
    # raising — a malformed spec must not break the status endpoint.
    if soft_limit is not None and hard_limit is not None and soft_limit > hard_limit:
        return None
    meter = budget_cfg.get("meter")
    meter = meter if isinstance(meter, str) and meter.strip() else "cost"
    decision = cost.budget_decision(
        soft_limit=soft_limit,
        hard_limit=hard_limit,
        meter=meter,
    )
    return {
        "outcome": decision.outcome.value,
        "tier": decision.tier,
        "should_stop": decision.should_stop,
        "needs_approval": decision.needs_approval,
        "spent": decision.spent,
        "soft_limit": decision.soft_limit,
        "hard_limit": decision.hard_limit,
        "meter": decision.meter,
        "detail": decision.detail,
    }


# Token bucket names a worker report may carry, in the canonical
# (``CanonicalUsage``) spelling. A worker that knows its model usage reports
# these under ``payload["usage"]``; the orchestrator folds them into the job's
# cost aggregate. Keeping the set explicit means a stray key in the report
# (``"foo": 1``) can't sneak into the token math.
_USAGE_TOKEN_FIELDS = (
    "input_tokens",
    "output_tokens",
    "cache_read_tokens",
    "cache_write_tokens",
    "reasoning_tokens",
)


@dataclass
class _ReportedUsage:
    """A worker-reported token breakdown.

    Structurally compatible with ``agent.usage_pricing.CanonicalUsage`` and the
    ``UsageLike`` protocol that :meth:`hermes_cli.job_cost.JobCost.add_usage`
    reads — it exposes exactly the five token attributes, so it can be passed
    straight through without importing the pricing module into this hot path.
    """

    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    reasoning_tokens: int = 0


def _extract_usage_report(
    body: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Pull an optional usage/cost block out of a worker report ``body``.

    This is the producer seam documented in ``hermes_cli.job_cost``: a worker
    that knows its per-call token usage / cost reports it on its heartbeat or
    completion payload, and the orchestrator folds it into the job's cost
    aggregate. The recognised shape is::

        {
          "usage": {                # optional — token buckets
            "input_tokens": int, "output_tokens": int,
            "cache_read_tokens": int, "cache_write_tokens": int,
            "reasoning_tokens": int
          },
          "cost_usd": float,        # optional — the call's cost in USD
          "model": str,             # optional — for the by-model breakdown
          "provider": str           # optional
        }

    Returns ``None`` when the body carries no usage signal at all (no ``usage``
    block and no ``cost_usd``), so a plain heartbeat never moves the cost meter
    — the additive, behavior-preserving default. Otherwise returns the kwargs
    for :meth:`JobStore.accumulate_cost` (``usage`` / ``cost_usd`` / ``model``
    / ``provider``). Malformed pieces are dropped rather than raised on: a junk
    report must not break a worker heartbeat.
    """
    raw_usage = body.get("usage")
    has_cost = "cost_usd" in body and body.get("cost_usd") is not None
    if not isinstance(raw_usage, dict) and not has_cost:
        return None

    usage_obj: Optional[_ReportedUsage] = None
    if isinstance(raw_usage, dict):
        tokens: Dict[str, int] = {}
        for field_name in _USAGE_TOKEN_FIELDS:
            value = raw_usage.get(field_name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                continue
            count = int(value)
            if count > 0:
                tokens[field_name] = count
        if tokens:
            usage_obj = _ReportedUsage(**tokens)

    cost_usd = body.get("cost_usd") if has_cost else None
    # Only treat cost as numeric; anything else degrades to "no cost" (tokens,
    # if any, still count). bool is rejected by JobCost downstream, so screen
    # it here too rather than letting a ``True`` become ``1.0``.
    if isinstance(cost_usd, bool) or not isinstance(cost_usd, (int, float)):
        cost_usd = None

    if usage_obj is None and cost_usd is None:
        # Had a ``usage``/``cost_usd`` key but nothing usable in it.
        return None

    result: Dict[str, Any] = {"usage": usage_obj, "cost_usd": cost_usd}
    model = body.get("model")
    if isinstance(model, str) and model.strip():
        result["model"] = model.strip()
    provider = body.get("provider")
    if isinstance(provider, str) and provider.strip():
        result["provider"] = provider.strip()
    return result


#: Opt-in switch for the live dispatch route. Default-OFF: the route exists for
#: discoverability but 403s unless this is set truthy, so booting the API never
#: changes behavior (the dispatcher actually executing a plan + accruing cost is
#: an owner decision). Mirrors the explicit-enable spirit of the other gates.
DISPATCH_ENV = "HERMES_ORCHESTRATOR_DISPATCH"
_TRUTHY = {"1", "true", "yes", "on"}


def dispatch_enabled() -> bool:
    """Return ``True`` only when :data:`DISPATCH_ENV` is set to a truthy value."""
    return os.environ.get(DISPATCH_ENV, "").strip().lower() in _TRUTHY


def _plan_from_spec(job_id: str, spec: Dict[str, Any]) -> Any:
    """Build an :class:`ExecutionPlan` from a stored job ``spec`` dict.

    Recognised spec shape (only ``workers`` is required)::

        {
          "workers": [
            {"worker_id": "w1", "profile": "default", "mode": "local-run",
             "command": ["..."], "prompt": "...", "timeout_seconds": 600,
             "cwd": "...", "env": {...}, "handoff": {...}, "use_worktree": false}
          ],
          "concurrency": 2, "use_worktrees": false,
          "base_ref": null, "allow_dirty": false
        }

    Raises :class:`OrchestratorError` (mapped to HTTP 400 by the route) for a
    malformed spec; the constructed plan is validated before return. Imported
    lazily because :mod:`hermes_cli.orchestrator_dispatch` /
    :mod:`hermes_cli.orchestrator_parallel` import from this module.
    """
    from hermes_cli.orchestrator_parallel import (
        ExecutionMode,
        ExecutionPlan,
        OrchestratorError,
        WorkerPlan,
    )

    raw_workers = spec.get("workers")
    if not isinstance(raw_workers, list) or not raw_workers:
        raise OrchestratorError("spec.workers must be a non-empty list")

    workers: List[Any] = []
    for index, raw in enumerate(raw_workers):
        if not isinstance(raw, dict):
            raise OrchestratorError(f"spec.workers[{index}] must be an object")
        raw = cast(Dict[str, Any], raw)
        mode_raw = str(raw.get("mode", ExecutionMode.LOCAL_RUN.value))
        try:
            mode = ExecutionMode(mode_raw)
        except ValueError as exc:
            raise OrchestratorError(f"unknown worker mode {mode_raw!r}") from exc
        kwargs: Dict[str, Any] = {
            "worker_id": str(raw.get("worker_id") or f"w{index}"),
            "profile": str(raw.get("profile") or "default"),
            "mode": mode,
            "prompt": str(raw.get("prompt", "")),
        }
        command = raw.get("command")
        if isinstance(command, (list, tuple)):
            kwargs["command"] = [str(token) for token in command]
        if isinstance(raw.get("cwd"), str):
            kwargs["cwd"] = raw["cwd"]
        if isinstance(raw.get("env"), dict):
            kwargs["env"] = {str(k): str(v) for k, v in raw["env"].items()}
        if raw.get("timeout_seconds") is not None:
            kwargs["timeout_seconds"] = int(raw["timeout_seconds"])
        if isinstance(raw.get("handoff"), dict):
            kwargs["handoff"] = raw["handoff"]
        if "use_worktree" in raw:
            kwargs["use_worktree"] = bool(raw["use_worktree"])
        workers.append(WorkerPlan(**kwargs))

    plan_kwargs: Dict[str, Any] = {"job_id": job_id, "workers": workers}
    if spec.get("concurrency") is not None:
        plan_kwargs["concurrency"] = int(spec["concurrency"])
    if "use_worktrees" in spec:
        plan_kwargs["use_worktrees"] = bool(spec["use_worktrees"])
    if isinstance(spec.get("base_ref"), str):
        plan_kwargs["base_ref"] = spec["base_ref"]
    if "allow_dirty" in spec:
        plan_kwargs["allow_dirty"] = bool(spec["allow_dirty"])

    plan = ExecutionPlan(**plan_kwargs)
    plan.validate()
    return plan


class JobStore:
    """Thread-safe in-memory job store with per-job event broadcasting.

    The store is shared by every request handler. Event fan-out is
    delegated to :class:`hermes_cli.orchestrator_events.EventBroker`;
    the store keeps a per-job event log on the ``Job`` object for the
    REST log endpoint, while the broker handles live WebSocket
    subscribers.
    """

    def __init__(self, *, broker: Optional[EventBroker] = None) -> None:
        self._jobs: Dict[str, Job] = {}
        self._lock = asyncio.Lock()
        self._broker = broker or EventBroker()

    @property
    def broker(self) -> EventBroker:
        return self._broker

    # ------------------------------------------------------------------
    # Job CRUD
    # ------------------------------------------------------------------
    async def create(
        self,
        name: str,
        spec: Dict[str, Any],
        *,
        source: Optional[str] = None,
    ) -> Job:
        async with self._lock:
            job = Job(
                id=str(uuid.uuid4()),
                name=name,
                spec=dict(spec or {}),
                source=source,
            )
            self._jobs[job.id] = job
        await self.emit_event(
            job.id, EVENT_JOB_CREATED, {"name": job.name, "spec": job.spec}
        )
        return job

    async def get(self, job_id: str) -> Job:
        async with self._lock:
            job = self._jobs.get(job_id)
        if job is None:
            raise KeyError(job_id)
        return job

    async def list(self) -> List[Job]:
        async with self._lock:
            return list(self._jobs.values())

    async def update(self, job_id: str, **changes: Any) -> Job:
        """Apply attribute changes to an existing job."""
        async with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise KeyError(job_id)
            for key, value in changes.items():
                if hasattr(job, key):
                    setattr(job, key, value)
            job.updated_at = time.time()
        return job

    async def record_worker(
        self,
        job_id: str,
        worker: str,
        info: Dict[str, Any],
    ) -> Job:
        """Merge worker state into ``job.workers[worker]``."""
        async with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise KeyError(job_id)
            current = dict(job.workers.get(worker, {}))
            current.update(info)
            current["updated_at"] = time.time()
            job.workers[worker] = current
            job.updated_at = current["updated_at"]
        return job

    async def accumulate_cost(
        self,
        job_id: str,
        *,
        usage: Optional[Any] = None,
        cost_usd: Any = None,
        model: Optional[str] = None,
        provider: Optional[str] = None,
    ) -> Job:
        """Fold one recorded model call into the job's cost aggregate.

        Mirrors :meth:`record_worker`: it locates the job under the store
        lock and updates :attr:`Job.cost` via
        :meth:`hermes_cli.job_cost.JobCost.add_usage`. ``usage`` is any object
        exposing the ``CanonicalUsage`` token attributes;
        ``agent.usage_pricing.CanonicalUsage`` satisfies it directly.

        This is the orchestrator-side aggregation point. Producers (the worker
        dispatcher reporting per-call token usage) are a documented follow-up
        — see the module docstring of ``hermes_cli.job_cost``.
        """
        async with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise KeyError(job_id)
            job.cost.add_usage(
                usage,
                cost_usd=cost_usd,
                model=model,
                provider=provider,
            )
            job.updated_at = time.time()
        # Event-source the folded delta so restart-replay can rebuild the
        # cost meter (the in-memory fold above stays the live truth). Outside
        # the lock — emit_event takes it itself. Token/cost values go through
        # the same coercions add_usage applies, so the durable delta is
        # JSON-serializable and replays to the identical aggregate.
        delta: Dict[str, Any] = {}
        if usage is not None:
            delta["usage"] = {
                name: _coerce_tokens(getattr(usage, name, 0))
                for name in USAGE_TOKEN_FIELDS
            }
        if cost_usd is not None:
            delta["cost_usd"] = _coerce_cost(cost_usd)
        if model:
            delta["model"] = model
        if provider:
            delta["provider"] = provider
        await self.emit_event(job_id, EVENT_COST_ACCUMULATED, delta)
        return job

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------
    async def emit_event(
        self,
        job_id: str,
        event: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Fan an event out via the broker and append it to the job log."""
        envelope = await self._broker.publish(event, job_id, data)
        async with self._lock:
            job = self._jobs.get(job_id)
            if job is not None:
                job.events.append(envelope)
                job.logs.append(envelope)
                job.updated_at = envelope["ts"]
        # Durable tee for restart-replay (Sprint 14). Best-effort and
        # guarded so a persistence failure can NEVER raise into this
        # fast path — the in-memory store above is the live source of
        # truth. ``job_event_store.append`` already swallows every error
        # and no-ops when ``HERMES_JOB_PERSIST`` is disabled; the extra
        # try/except here is belt-and-braces against an import-time or
        # signature surprise.
        try:
            job_event_store.append(job_id, envelope)
        except Exception:  # pragma: no cover - durability must never break emit
            logger.debug("orchestrator_api: job_event_store.append failed", exc_info=True)
        return envelope

    async def subscribe(self, job_id: str) -> "asyncio.Queue[Dict[str, Any]]":
        return await self._broker.subscribe(job_id)

    async def unsubscribe(
        self, job_id: str, queue: "asyncio.Queue[Dict[str, Any]]"
    ) -> None:
        await self._broker.unsubscribe(job_id, queue)

    async def replay(self, job_id: str) -> List[Dict[str, Any]]:
        async with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise KeyError(job_id)
            return list(job.events)

    async def snapshot(self, job_id: str) -> JobSnapshot:
        """Reconstruct a job's state purely from its recorded events.

        Folds the job's event envelopes through the replay reducer
        (:func:`hermes_cli.job_replay.rebuild_snapshot`). This is the basis
        for restart-replay: the same fold rebuilds status / phase / workers /
        approvals from a persisted event stream, so job state can survive
        losing the in-memory copy. An unknown job yields an empty snapshot
        (no raise), mirroring the reducer's tolerance.
        """
        async with self._lock:
            job = self._jobs.get(job_id)
            events = list(job.events) if job is not None else []
        return rebuild_snapshot(events, job_id=job_id)

    # ------------------------------------------------------------------
    # Restart-replay
    # ------------------------------------------------------------------
    def restore_from_disk(self) -> int:
        """Rehydrate jobs from the durable per-job event log on disk.

        For every job id that :func:`hermes_cli.job_event_store.iter_job_ids`
        reports, this reads the persisted envelopes, folds them through
        :func:`hermes_cli.job_replay.rebuild_snapshot`, and reconstructs a
        :class:`Job` in ``self._jobs``. The loaded envelopes are re-seeded onto
        ``job.events`` so the live ``GET /jobs/{id}/snapshot`` route — which
        re-folds ``job.events`` — keeps working after a restart.

        This is **synchronous and meant to run once at startup**, before the
        event loop is serving requests, so it does not take the async
        ``self._lock`` (there are no concurrent mutators yet). Constructing a
        bare ``JobStore()`` does *not* call this — restore is wired only in
        :func:`create_app`, so the in-memory-only tests stay pure.

        :class:`hermes_cli.job_cost.JobCost` is event-sourced via
        ``cost.accumulated`` deltas (one per :meth:`accumulate_cost` call), so
        a restored job's cost meter is rebuilt alongside status / phase /
        workers / approvals / validation / publish plan. Logs that predate
        cost event-sourcing carry no deltas and restore with a zero meter —
        the old documented behavior. A job already in ``self._jobs`` is left
        untouched (the live copy wins).

        Returns the number of jobs newly restored. Best-effort: a malformed or
        unreadable job log is skipped, never raised on.
        """
        restored = 0
        for job_id in job_event_store.iter_job_ids():
            if not job_id or job_id in self._jobs:
                continue
            try:
                envelopes = job_event_store.read(job_id)
            except Exception:  # pragma: no cover - defensive
                continue
            if not envelopes:
                continue
            snapshot = rebuild_snapshot(envelopes, job_id=job_id)
            job = self._job_from_snapshot(snapshot, envelopes)
            self._jobs[job.id] = job
            restored += 1
        return restored

    @staticmethod
    def _job_from_snapshot(
        snapshot: JobSnapshot,
        envelopes: List[Dict[str, Any]],
    ) -> Job:
        """Build a :class:`Job` from a replayed :class:`JobSnapshot`.

        Bridges the two shapes the codebase uses for the same concepts:

        * ``JobSnapshot.workers`` is ``{worker: state}``; ``Job.workers`` is
          ``{worker: {...}}`` — each state is wrapped as ``{"state": state}``
          so the ``/workers`` routes keep their dict shape.
        * ``JobSnapshot.approvals`` is ``{id: state}``; ``Job.approvals`` is a
          ``list[dict]`` — each becomes ``{"id": id, "state": state}``.

        The loaded ``envelopes`` are copied onto ``job.events``/``job.logs`` so
        the live snapshot/log routes re-fold the same stream post-restart.
        ``Job.cost`` is seeded from ``snapshot.cost`` — the aggregate the
        replay fold rebuilt from ``cost.accumulated`` deltas (zero for logs
        that predate cost event-sourcing).
        """
        workers: Dict[str, Dict[str, Any]] = {
            name: {"state": state} for name, state in snapshot.workers.items()
        }
        approvals: List[Dict[str, Any]] = [
            {"id": appr_id, "state": state}
            for appr_id, state in snapshot.approvals.items()
        ]
        events = list(envelopes)
        last_ts = snapshot.last_ts if snapshot.last_ts is not None else time.time()
        job = Job(
            id=snapshot.job_id,
            name=snapshot.name or snapshot.job_id,
            spec=dict(snapshot.spec),
            status=snapshot.status,
            phase=snapshot.phase,
            updated_at=last_ts,
            workers=workers,
            approvals=approvals,
            validation=snapshot.validation,
            publish_plan=snapshot.publish_plan,
            error=snapshot.error,
            events=events,
            logs=list(events),
            cost=snapshot.cost,
        )
        return job


def _is_loopback_host(host: str) -> bool:
    return host in _LOOPBACK_HOSTS


def _find_pending_approval(
    approvals: List[Dict[str, Any]],
    approval_id: Optional[str],
) -> Optional[Dict[str, Any]]:
    """Locate the approval entry an approve/reject call should mutate.

    With an explicit id we look that up by id. Without one we pick the
    oldest entry still in ``state == "pending"`` so a "just do the next
    one" client doesn't have to track ids.
    """
    if approval_id is not None:
        for entry in approvals:
            if entry.get("id") == approval_id:
                if entry.get("state", "pending") == "pending":
                    return entry
                return None
        return None
    for entry in approvals:
        if entry.get("state", "pending") == "pending":
            return entry
    return None


def _summarise_voice(transcript: str, *, max_words: int = 8) -> str:
    """Turn a voice transcript into a short job title.

    Real intake will run the transcript through an LLM; for the bare
    HTTP endpoint we just take the first N words so the job list is
    readable. Punctuation is stripped from the trailing word.
    """
    words = transcript.strip().split()
    if not words:
        return "voice intake"
    snippet = " ".join(words[:max_words])
    return snippet.rstrip(",.;:!?")


def _client_is_local(request_or_ws: Any) -> bool:
    """Both ``Request`` and ``WebSocket`` expose ``.client.host`` the same way."""
    client = getattr(request_or_ws, "client", None)
    host = getattr(client, "host", "") if client else ""
    if not host:
        # No socket peer (e.g. ASGI test transport with no client tuple).
        # Treat as local — tests rely on this and uvicorn fills it in.
        return True
    return _is_loopback_host(host)


def create_app(
    *,
    store: Optional[JobStore] = None,
    token: Optional[str] = None,
    allow_public_bind: bool = False,
) -> "FastAPI":
    """Build the orchestrator FastAPI application.

    Args:
        store: Optional pre-existing :class:`JobStore`. Lets tests inject
            a populated store, and lets the gateway share one store with
            its job dispatcher.
        token: When set, every HTTP request must carry
            ``Authorization: Bearer <token>`` (constant-time compared)
            and every WebSocket must include ``?token=<token>``.
        allow_public_bind: Set to ``True`` only when the caller is
            *deliberately* exposing the API beyond loopback. When
            ``False`` (default) the middleware refuses non-loopback
            clients even if uvicorn happened to bind ``0.0.0.0``.

    Raises:
        RuntimeError: if FastAPI isn't installed.
    """
    if not FASTAPI_AVAILABLE:
        raise RuntimeError(
            "fastapi is required for hermes_cli.orchestrator_api. Install "
            "with: pip install 'hermes-agent[web]' or `pip install fastapi`."
        )

    # Restore from disk only for a store *we* create — never for an injected
    # (test/gateway) store, which owns its own lifecycle. A bare ``JobStore()``
    # built directly by a test stays pure in-memory; restore is wired here and
    # only here. Gated on the persistence switch so ``HERMES_JOB_PERSIST=0``
    # boots a clean store with no replay.
    owns_store = store is None
    store = store or JobStore()
    if owns_store and job_event_store.persistence_enabled():
        try:
            restored = store.restore_from_disk()
            if restored:
                logger.info(
                    "orchestrator_api: restored %d job(s) from disk on startup",
                    restored,
                )
        except Exception:  # pragma: no cover - startup restore must not crash boot
            logger.warning(
                "orchestrator_api: restore_from_disk failed; starting empty",
                exc_info=True,
            )
    app = FastAPI(title="M.U.S.E. Orchestrator API", version="1.0.0")
    app.state.store = store
    app.state.token = token
    app.state.allow_public_bind = allow_public_bind

    # ------------------------------------------------------------------
    # Middleware: loopback + token enforcement
    # ------------------------------------------------------------------
    @app.middleware("http")
    async def _local_only_guard(request: "Request", call_next: Callable[..., Any]):
        if not allow_public_bind and not _client_is_local(request):
            return JSONResponse(
                {"error": "orchestrator API is restricted to loopback"},
                status_code=403,
            )
        if token:
            auth = request.headers.get("authorization", "")
            prefix = "Bearer "
            if not auth.startswith(prefix) or not hmac.compare_digest(
                auth[len(prefix):].encode(), token.encode()
            ):
                # Skip token check on the unauthenticated health probe so
                # supervisors (systemd, Docker healthcheck) work without
                # baking the token into their config.
                if request.url.path != "/health":
                    return JSONResponse(
                        {"error": "missing or invalid bearer token"},
                        status_code=401,
                    )
        return await call_next(request)

    def _ws_authorised(ws: "WebSocket") -> bool:
        if not allow_public_bind and not _client_is_local(ws):
            return False
        if not token:
            return True
        supplied = ws.query_params.get("token", "")
        return hmac.compare_digest(supplied.encode(), token.encode())

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    async def _get_job_or_404(job_id: str) -> Job:
        try:
            return await store.get(job_id)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"job {job_id} not found")

    def _reject_terminal(job: Job, action: str) -> None:
        if job.status in _TERMINAL_STATES:
            raise HTTPException(
                status_code=409,
                detail=f"cannot {action} job in terminal state '{job.status}'",
            )

    # ------------------------------------------------------------------
    # Routes
    # ------------------------------------------------------------------
    @app.get("/health")
    async def health() -> Dict[str, Any]:
        return {
            "status": "ok",
            "service": "hermes-orchestrator-api",
            "version": "1.0.0",
            "auth_required": bool(token),
            "public_bind": bool(allow_public_bind),
        }

    @app.get("/jobs")
    async def list_jobs() -> Dict[str, Any]:
        jobs = await store.list()
        return {"jobs": [j.to_dict() for j in jobs]}

    @app.post("/jobs", status_code=201)
    async def create_job(payload: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="payload must be a JSON object")
        raw_name = payload.get("name", payload.get("title", "untitled"))
        if not isinstance(raw_name, str) or not raw_name.strip():
            raise HTTPException(
                status_code=400, detail="'name' must be a non-empty string"
            )
        name = raw_name
        spec = payload.get("spec", {})
        if spec is None:
            spec = {}
        if not isinstance(spec, dict):
            raise HTTPException(status_code=400, detail="'spec' must be an object")
        job = await store.create(name=name.strip(), spec=spec)
        return job.to_dict()

    @app.get("/jobs/{job_id}")
    async def get_job(job_id: str) -> Dict[str, Any]:
        job = await _get_job_or_404(job_id)
        return job.to_dict()

    @app.get("/jobs/{job_id}/status")
    async def get_job_status(job_id: str) -> Dict[str, Any]:
        job = await _get_job_or_404(job_id)
        return {
            "id": job.id,
            "status": job.status,
            "updated_at": job.updated_at,
            "error": job.error,
            # Per-job cost aggregate + budget evaluation (Sprint 10). ``cost``
            # is always present (zero when nothing was recorded); ``budget`` is
            # ``None`` unless the job spec configures soft/hard limits.
            "cost": job.cost.totals(),
            "budget": job.budget_status(),
        }

    @app.get("/jobs/{job_id}/snapshot")
    async def get_job_snapshot(job_id: str) -> Dict[str, Any]:
        """Reconstruct a job's state purely from its recorded event stream.

        This is the live entry point for :meth:`JobStore.snapshot`, which folds
        the job's event envelopes through the replay reducer
        (:func:`hermes_cli.job_replay.rebuild_snapshot`) to rebuild status /
        phase / workers / approvals / validation / publish plan. Unlike
        ``GET /jobs/{id}/status`` (which reads the mutated in-memory ``Job``),
        this route derives state solely from ``job.events`` — the same fold
        that would rehydrate a job after a restart.

        Restart-replay is wired (Sprint 14): :meth:`JobStore.emit_event` tees
        each envelope to a durable per-job log
        (:mod:`hermes_cli.job_event_store`), and :func:`create_app` calls
        :meth:`JobStore.restore_from_disk` at startup to fold those envelopes
        back through ``rebuild_snapshot`` and re-seed ``job.events``. So this
        route keeps working after a restart. (One caveat: per-job *cost* is not
        event-sourced and resets to zero on restore — see
        :meth:`JobStore.restore_from_disk`.)

        Returns 404 for an unknown job (matching ``/status``) rather than the
        empty snapshot :meth:`JobStore.snapshot` would otherwise yield, so a bad
        id is an explicit client error.
        """
        await _get_job_or_404(job_id)
        snapshot = await store.snapshot(job_id)
        return snapshot.to_dict()

    @app.get("/jobs/{job_id}/artifacts")
    async def get_job_artifacts(job_id: str) -> Dict[str, Any]:
        job = await _get_job_or_404(job_id)
        return {"id": job.id, "artifacts": list(job.artifacts)}

    @app.get("/jobs/{job_id}/logs")
    async def get_job_logs(
        job_id: str,
        since: float = 0.0,
        limit: int = 0,
    ) -> Dict[str, Any]:
        """Return the event log for a job.

        ``since`` filters out envelopes with ``ts <= since`` so a cockpit
        can poll for incremental updates without re-streaming history.
        ``limit`` (when > 0) caps the number of envelopes returned.
        """
        job = await _get_job_or_404(job_id)
        entries = job.logs
        if since:
            entries = [e for e in entries if e.get("ts", 0) > since]
        if limit and limit > 0:
            entries = entries[-limit:]
        return {"id": job.id, "logs": list(entries)}

    @app.post("/jobs/{job_id}/resume")
    async def resume_job(job_id: str) -> Dict[str, Any]:
        job = await _get_job_or_404(job_id)
        _reject_terminal(job, "resume")
        previous_phase = job.phase
        job = await store.update(
            job_id,
            status="running",
            phase=PHASE_EXECUTING,
            error=None,
        )
        await store.emit_event(
            job_id,
            EVENT_PHASE_CHANGED,
            {"from": previous_phase, "to": PHASE_EXECUTING, "reason": "resume"},
        )
        await store.emit_event(job_id, EVENT_WORKER_STARTED, {"reason": "resume"})
        return job.to_dict()

    @app.post("/jobs/{job_id}/cancel")
    async def cancel_job(job_id: str) -> Dict[str, Any]:
        job = await _get_job_or_404(job_id)
        if job.status in _TERMINAL_STATES:
            return job.to_dict()
        previous_phase = job.phase
        job = await store.update(job_id, status="cancelled", phase=PHASE_CANCELLED)
        await store.emit_event(
            job_id,
            EVENT_PHASE_CHANGED,
            {"from": previous_phase, "to": PHASE_CANCELLED, "reason": "cancel"},
        )
        await store.emit_event(job_id, EVENT_JOB_FAILED, {"reason": "cancelled"})
        return job.to_dict()

    @app.post("/jobs/{job_id}/approve")
    async def approve_job(
        job_id: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Approve a pending gate.

        The body may include ``approval_id`` to mark a specific request
        granted, plus an optional ``comment``. Without an id the first
        pending request wins.
        """
        job = await _get_job_or_404(job_id)
        _reject_terminal(job, "approve")
        payload = dict(payload or {})
        approval_id = payload.get("approval_id")
        approvals = list(job.approvals)
        target = _find_pending_approval(approvals, approval_id)
        if target is None:
            raise HTTPException(
                status_code=409, detail="no pending approval to grant"
            )
        target["state"] = "granted"
        target["decided_at"] = time.time()
        if "comment" in payload:
            target["comment"] = payload["comment"]
        next_phase = PHASE_EXECUTING
        job = await store.update(
            job_id,
            approvals=approvals,
            status="running",
            phase=next_phase,
        )
        await store.emit_event(
            job_id,
            EVENT_APPROVAL_GRANTED,
            {"approval_id": target.get("id"), "comment": target.get("comment")},
        )
        return job.to_dict()

    @app.post("/jobs/{job_id}/reject")
    async def reject_job(
        job_id: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Reject a pending gate. Job moves to ``failed``."""
        job = await _get_job_or_404(job_id)
        _reject_terminal(job, "reject")
        payload = dict(payload or {})
        approval_id = payload.get("approval_id")
        approvals = list(job.approvals)
        target = _find_pending_approval(approvals, approval_id)
        if target is None:
            raise HTTPException(
                status_code=409, detail="no pending approval to reject"
            )
        target["state"] = "rejected"
        target["decided_at"] = time.time()
        if "comment" in payload:
            target["comment"] = payload["comment"]
        job = await store.update(
            job_id,
            approvals=approvals,
            status="failed",
            phase=PHASE_CANCELLED,
            error=payload.get("comment") or "approval rejected",
        )
        await store.emit_event(
            job_id,
            EVENT_APPROVAL_REJECTED,
            {"approval_id": target.get("id"), "comment": target.get("comment")},
        )
        await store.emit_event(
            job_id, EVENT_JOB_FAILED, {"reason": "approval rejected"}
        )
        return job.to_dict()

    @app.post("/jobs/{job_id}/validate")
    async def validate_job(job_id: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        job = await _get_job_or_404(job_id)
        _reject_terminal(job, "validate")
        result = dict(payload or {})
        result.setdefault("requested_at", time.time())
        previous_phase = job.phase
        job = await store.update(
            job_id,
            validation=result,
            status="validating",
            phase=PHASE_VALIDATING,
        )
        await store.emit_event(
            job_id,
            EVENT_PHASE_CHANGED,
            {"from": previous_phase, "to": PHASE_VALIDATING, "reason": "validate"},
        )
        await store.emit_event(
            job_id, EVENT_VALIDATION_COMPLETED, {"result": result}
        )
        return job.to_dict()

    @app.post("/jobs/{job_id}/publish-plan")
    async def publish_plan(job_id: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        job = await _get_job_or_404(job_id)
        _reject_terminal(job, "publish")
        plan = dict(payload or {})
        plan.setdefault("prepared_at", time.time())
        previous_phase = job.phase
        job = await store.update(
            job_id,
            publish_plan=plan,
            status="publish_ready",
            phase=PHASE_PUBLISH_READY,
        )
        await store.emit_event(
            job_id,
            EVENT_PHASE_CHANGED,
            {"from": previous_phase, "to": PHASE_PUBLISH_READY, "reason": "publish"},
        )
        await store.emit_event(job_id, EVENT_PUBLISH_READY, {"plan": plan})
        return job.to_dict()

    @app.get("/workers")
    async def list_workers() -> Dict[str, Any]:
        """Aggregate worker state across every active job.

        Each worker entry reflects the last heartbeat or status update
        recorded via :meth:`JobStore.record_worker` (or by clients that
        called ``POST /jobs/{id}/workers/{worker}``).
        """
        jobs = await store.list()
        workers: List[Dict[str, Any]] = []
        for job in jobs:
            for name, info in job.workers.items():
                entry = {"job_id": job.id, "job_name": job.name, "worker": name}
                entry.update(info)
                workers.append(entry)
        return {"workers": workers}

    @app.get("/jobs/{job_id}/workers")
    async def list_job_workers(job_id: str) -> Dict[str, Any]:
        job = await _get_job_or_404(job_id)
        return {"id": job.id, "workers": dict(job.workers)}

    @app.post("/jobs/{job_id}/workers/{worker}")
    async def update_worker(
        job_id: str,
        worker: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Record a worker heartbeat / status update.

        ``state`` is free-form (``"running"``, ``"blocked"``, ``"done"``,
        …). When set to ``"running"`` we also emit ``worker.heartbeat``
        so cockpits can drive a liveness indicator without polling.

        If the report carries a usage/cost block (``usage`` token buckets
        and/or ``cost_usd``, optionally with ``model`` / ``provider``), it is
        folded into the job's cost aggregate via
        :meth:`JobStore.accumulate_cost`. This is the producer seam documented
        in ``hermes_cli.job_cost``: a worker that knows its per-call model
        usage reports it here, and per-job cost accumulates. A report with no
        usage block leaves the cost meter untouched (additive default).
        """
        await _get_job_or_404(job_id)
        body = dict(payload or {})
        if "worker" in body and body["worker"] != worker:
            raise HTTPException(
                status_code=400, detail="payload 'worker' must match path"
            )
        body.setdefault("state", "running")
        job = await store.record_worker(job_id, worker, body)
        usage_report = _extract_usage_report(body)
        if usage_report is not None:
            job = await store.accumulate_cost(job_id, **usage_report)
        state = body.get("state")
        if state == "running":
            await store.emit_event(
                job_id,
                EVENT_WORKER_HEARTBEAT,
                {"worker": worker, **{k: v for k, v in body.items() if k != "state"}},
            )
        elif state == "blocked":
            await store.emit_event(
                job_id,
                EVENT_WORKER_BLOCKED,
                {"worker": worker, "reason": body.get("reason")},
            )
        elif state in ("done", "completed"):
            await store.emit_event(
                job_id,
                EVENT_WORKER_COMPLETED,
                {"worker": worker, "result": body.get("result")},
            )
        return {"id": job.id, "worker": worker, "info": job.workers[worker]}

    @app.post("/jobs/{job_id}/dispatch")
    async def dispatch_job(
        job_id: str, payload: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Execute a job's plan and drain per-worker usage into its cost meter.

        This is the **live caller** of the cost producer→consumer seam: until
        now ``hermes_cli.orchestrator_dispatch.run_plan_into_store`` had no
        caller, so a real server's per-job ``cost`` always read ``0``. This
        route runs the job's plan through a :class:`ParallelRunner` and folds
        each worker's reported usage into the job's :class:`JobCost`, so a
        subsequent ``GET /jobs/{id}/status`` reflects real cost.

        **Owner-gated + opt-in.** It 403s unless
        ``HERMES_ORCHESTRATOR_DISPATCH`` is set truthy, so simply booting the
        API never starts executing plans (default behavior is byte-identical).

        Body (optional): ``{"spec": {...}, "repo": "/path"}``. ``spec`` overrides
        the stored job spec as the plan source; ``repo`` is the root the worker
        artifacts live under (defaults to the process cwd).
        """
        if not dispatch_enabled():
            raise HTTPException(
                status_code=403,
                detail=(
                    "orchestrator dispatch is disabled; set "
                    f"{DISPATCH_ENV}=1 to enable (owner decision)"
                ),
            )
        job = await _get_job_or_404(job_id)
        _reject_terminal(job, "dispatch")
        body = dict(payload or {})
        spec_override = body.get("spec")
        spec = spec_override if isinstance(spec_override, dict) else job.spec
        repo = body.get("repo") or (spec or {}).get("repo") or os.getcwd()

        # Lazy import: orchestrator_dispatch / orchestrator_parallel import from
        # this module, so importing them at module load would be circular.
        from hermes_cli.orchestrator_dispatch import run_plan_into_store
        from hermes_cli.orchestrator_parallel import (
            OrchestratorError,
            per_worker_local_adapter,
        )

        try:
            plan = _plan_from_spec(job_id, spec or {})
            statuses = await run_plan_into_store(
                repo, plan, store, adapter_factory=per_worker_local_adapter
            )
        except OrchestratorError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

        job = await store.get(job_id)
        return {
            "id": job.id,
            "status": job.status,
            "workers": {wid: st.as_dict() for wid, st in statuses.items()},
            "cost": job.cost.totals(),
            "budget": job.budget_status(),
        }

    @app.post("/voice/intake", status_code=201)
    async def voice_intake(payload: Dict[str, Any]) -> Dict[str, Any]:
        """Create a job from a voice transcript.

        Body shape::

            {
              "transcript": "…",
              "name": "optional explicit title",
              "context": {…},      # optional metadata (locale, device, …)
              "spec": {…}          # optional override of the auto spec
            }

        The transcript becomes ``spec.transcript`` (and ``name`` if no
        title is supplied) so a worker downstream can act on it.
        """
        if not isinstance(payload, dict):
            raise HTTPException(
                status_code=400, detail="payload must be a JSON object"
            )
        transcript = payload.get("transcript")
        if not isinstance(transcript, str) or not transcript.strip():
            raise HTTPException(
                status_code=400, detail="'transcript' must be a non-empty string"
            )
        raw_name = payload.get("name") or _summarise_voice(transcript)
        name = raw_name.strip()
        if not name:
            name = "voice intake"
        spec_override = payload.get("spec")
        if spec_override is not None and not isinstance(spec_override, dict):
            raise HTTPException(
                status_code=400, detail="'spec' must be an object"
            )
        spec: Dict[str, Any] = {"transcript": transcript.strip()}
        context = payload.get("context")
        if context is not None:
            if not isinstance(context, dict):
                raise HTTPException(
                    status_code=400, detail="'context' must be an object"
                )
            spec["context"] = context
        if spec_override:
            spec.update(spec_override)
        job = await store.create(name=name, spec=spec, source="voice")
        return job.to_dict()

    # ------------------------------------------------------------------
    # WebSocket — /jobs/{job_id}/events
    # ------------------------------------------------------------------
    @app.websocket("/jobs/{job_id}/events")
    async def job_events(ws: "WebSocket", job_id: str) -> None:
        if not _ws_authorised(ws):
            await ws.close(code=4401)
            return
        try:
            await store.get(job_id)
        except KeyError:
            await ws.close(code=4404)
            return

        await ws.accept()

        # Replay any buffered history first so a late subscriber sees the
        # ``job.created`` event that was emitted before it connected.
        history = await store.replay(job_id)
        for envelope in history:
            await ws.send_json(envelope)

        queue = await store.subscribe(job_id)
        try:
            recv_task = asyncio.create_task(_drain_ws(ws))
            try:
                while True:
                    envelope = await queue.get()
                    await ws.send_json(envelope)
            finally:
                recv_task.cancel()
        except WebSocketDisconnect:
            pass
        except Exception as exc:  # pragma: no cover - belt-and-braces
            logger.warning("orchestrator_api: WS error on job %s: %s", job_id, exc)
        finally:
            await store.unsubscribe(job_id, queue)

    return app


async def _drain_ws(ws: "WebSocket") -> None:
    """Pull (and discard) any client-sent frames so disconnects surface promptly."""
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        return
    except Exception:
        return


def run(
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    *,
    token: Optional[str] = None,
    allow_public_bind: bool = False,
) -> None:
    """Run the orchestrator API under uvicorn.

    The CLI wrapper resolves ``token`` from ``HERMES_ORCHESTRATOR_API_TOKEN``
    when not provided. A public bind without a token is refused so the
    operator can't accidentally publish an unauthenticated control plane.
    """
    try:
        import uvicorn  # local import — avoids hard dep at import time
    except ImportError as exc:  # pragma: no cover - dep error path
        raise RuntimeError(
            "uvicorn is required to run the orchestrator API. Install "
            "with: pip install 'hermes-agent[web]'."
        ) from exc

    if token is None:
        token = os.environ.get("HERMES_ORCHESTRATOR_API_TOKEN") or None

    is_public = host not in {"127.0.0.1", "localhost", "::1"}
    if is_public and not allow_public_bind:
        raise RuntimeError(
            f"refusing to bind orchestrator API to {host!r}: pass "
            "allow_public_bind=True (or --insecure on the CLI) to opt in."
        )
    if is_public and not token:
        raise RuntimeError(
            "refusing to bind orchestrator API to a non-loopback address "
            "without HERMES_ORCHESTRATOR_API_TOKEN set."
        )

    # When bound to loopback we keep allow_public_bind=False so the
    # middleware defensively rejects any client that somehow reaches us
    # off-loopback. Only flip it on for a deliberate public bind.
    app = create_app(token=token, allow_public_bind=is_public and allow_public_bind)
    uvicorn.run(app, host=host, port=port, log_level="info")


__all__ = [
    "ALL_EVENTS",
    "ALL_PHASES",
    "DEFAULT_HOST",
    "DEFAULT_PORT",
    "EVENT_APPROVAL_GRANTED",
    "EVENT_APPROVAL_REJECTED",
    "EVENT_APPROVAL_REQUESTED",
    "EVENT_ERROR",
    "EVENT_EVIDENCE_UPDATED",
    "EVENT_JOB_CREATED",
    "EVENT_JOB_FAILED",
    "EVENT_PHASE_CHANGED",
    "EVENT_PUBLISH_READY",
    "EVENT_SCORING_COMPLETED",
    "EVENT_VALIDATION_COMPLETED",
    "EVENT_WORKER_BLOCKED",
    "EVENT_WORKER_COMPLETED",
    "EVENT_WORKER_HEARTBEAT",
    "EVENT_WORKER_STARTED",
    "EventBroker",
    "Job",
    "JobCost",
    "JobStore",
    "create_app",
    "make_envelope",
    "run",
]
