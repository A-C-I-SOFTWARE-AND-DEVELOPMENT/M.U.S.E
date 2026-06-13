"""Event constants and pub/sub broker for the orchestrator API.

This module is the canonical source of truth for the event vocabulary
emitted by ``hermes_cli.orchestrator_api`` to its WebSocket subscribers.
Pulling these out of the API module lets cockpit clients (Android,
Flutter, the TUI) import the same string constants without depending on
FastAPI being installed in the client's environment.

The broker is a tiny, dependency-free async pub/sub. It:

* fans events to per-job subscriber queues,
* keeps a bounded history per job so a late subscriber can replay
  events it missed (the API's WebSocket handler uses this to deliver
  the ``job.created`` envelope a client may have already missed),
* drops events for slow subscribers rather than blocking the whole
  fan-out (the subscriber will see the missed state reflected the
  next time it polls the REST API).

It is not a general-purpose message bus and is deliberately kept
small — one process, one event loop, in-memory state.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Event vocabulary
# ---------------------------------------------------------------------------

# Lifecycle
EVENT_JOB_CREATED = "job.created"
EVENT_JOB_FAILED = "job.failed"
EVENT_PHASE_CHANGED = "phase.changed"
EVENT_ERROR = "error"

# Approvals (human-in-the-loop gates)
EVENT_APPROVAL_REQUESTED = "approval.requested"
EVENT_APPROVAL_GRANTED = "approval.granted"
EVENT_APPROVAL_REJECTED = "approval.rejected"

# Worker lifecycle
EVENT_WORKER_STARTED = "worker.started"
EVENT_WORKER_HEARTBEAT = "worker.heartbeat"
EVENT_WORKER_BLOCKED = "worker.blocked"
EVENT_WORKER_COMPLETED = "worker.completed"

# Cost — one per folded model-call delta (Sprint 10 aggregate; event-sourced
# so restart-replay can rebuild the cost meter instead of resetting it to 0).
EVENT_COST_ACCUMULATED = "cost.accumulated"

# Evidence / scoring
EVENT_EVIDENCE_UPDATED = "evidence.updated"
EVENT_SCORING_COMPLETED = "scoring.completed"

# Validation / publish
EVENT_VALIDATION_COMPLETED = "validation.completed"
EVENT_PUBLISH_READY = "publish.ready"

ALL_EVENTS: Tuple[str, ...] = (
    EVENT_JOB_CREATED,
    EVENT_JOB_FAILED,
    EVENT_PHASE_CHANGED,
    EVENT_ERROR,
    EVENT_APPROVAL_REQUESTED,
    EVENT_APPROVAL_GRANTED,
    EVENT_APPROVAL_REJECTED,
    EVENT_WORKER_STARTED,
    EVENT_WORKER_HEARTBEAT,
    EVENT_WORKER_BLOCKED,
    EVENT_WORKER_COMPLETED,
    EVENT_COST_ACCUMULATED,
    EVENT_EVIDENCE_UPDATED,
    EVENT_SCORING_COMPLETED,
    EVENT_VALIDATION_COMPLETED,
    EVENT_PUBLISH_READY,
)

# Phases used by ``phase.changed`` envelopes. Workers move a job through
# this sequence; the cockpit colours the progress bar by phase.
PHASE_INTAKE = "intake"
PHASE_PLANNING = "planning"
PHASE_EXECUTING = "executing"
PHASE_VALIDATING = "validating"
PHASE_AWAITING_APPROVAL = "awaiting_approval"
PHASE_PUBLISH_READY = "publish_ready"
PHASE_COMPLETED = "completed"
PHASE_FAILED = "failed"
PHASE_CANCELLED = "cancelled"

ALL_PHASES: Tuple[str, ...] = (
    PHASE_INTAKE,
    PHASE_PLANNING,
    PHASE_EXECUTING,
    PHASE_VALIDATING,
    PHASE_AWAITING_APPROVAL,
    PHASE_PUBLISH_READY,
    PHASE_COMPLETED,
    PHASE_FAILED,
    PHASE_CANCELLED,
)


# ---------------------------------------------------------------------------
# Envelope helper
# ---------------------------------------------------------------------------


def make_envelope(
    event: str,
    job_id: str,
    data: Optional[Dict[str, Any]] = None,
    *,
    ts: Optional[float] = None,
) -> Dict[str, Any]:
    """Build the JSON envelope that the WebSocket sends to subscribers.

    The shape is stable: ``{event, job_id, ts, data}``. Clients pin to
    this layout, so add new keys instead of renaming the existing ones.

    Raises:
        ValueError: if ``event`` is not in :data:`ALL_EVENTS`. Enforcing
            this at envelope-construction time means a typo in a publish
            call fails loudly instead of silently shipping a payload no
            client knows how to parse.
    """
    if event not in ALL_EVENTS:
        raise ValueError(f"unknown event: {event!r}")
    return {
        "event": event,
        "job_id": job_id,
        "ts": ts if ts is not None else time.time(),
        "data": dict(data or {}),
    }


# ---------------------------------------------------------------------------
# EventBroker
# ---------------------------------------------------------------------------


class EventBroker:
    """Per-job async pub/sub with bounded history.

    Subscribers receive a fresh ``asyncio.Queue``. The broker keeps the
    last ``history`` envelopes per job so the WebSocket can replay them
    to a late subscriber. Each subscriber queue has a fixed capacity;
    when it fills, new events for that subscriber are dropped (with a
    warning) so a slow client cannot stall the fan-out for everyone.
    """

    DEFAULT_HISTORY = 256
    DEFAULT_QUEUE = 256

    def __init__(
        self,
        *,
        history: int = DEFAULT_HISTORY,
        queue_size: int = DEFAULT_QUEUE,
    ) -> None:
        if history < 0:
            raise ValueError("history must be >= 0")
        if queue_size <= 0:
            raise ValueError("queue_size must be > 0")
        self._history: Dict[str, List[Dict[str, Any]]] = {}
        self._subscribers: Dict[str, Set["asyncio.Queue[Dict[str, Any]]"]] = {}
        self._lock = asyncio.Lock()
        self._history_limit = history
        self._queue_size = queue_size

    async def publish(
        self,
        event: str,
        job_id: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        envelope = make_envelope(event, job_id, data)
        async with self._lock:
            buf = self._history.setdefault(job_id, [])
            buf.append(envelope)
            overflow = len(buf) - self._history_limit
            if overflow > 0:
                del buf[:overflow]
            subs = list(self._subscribers.get(job_id, ()))
        for queue in subs:
            try:
                queue.put_nowait(envelope)
            except asyncio.QueueFull:
                logger.warning(
                    "orchestrator_events: dropping %s for slow subscriber on job %s",
                    event,
                    job_id,
                )
        return envelope

    async def subscribe(self, job_id: str) -> "asyncio.Queue[Dict[str, Any]]":
        queue: "asyncio.Queue[Dict[str, Any]]" = asyncio.Queue(maxsize=self._queue_size)
        async with self._lock:
            self._subscribers.setdefault(job_id, set()).add(queue)
        return queue

    async def unsubscribe(
        self,
        job_id: str,
        queue: "asyncio.Queue[Dict[str, Any]]",
    ) -> None:
        async with self._lock:
            subs = self._subscribers.get(job_id)
            if subs is None:
                return
            subs.discard(queue)
            if not subs:
                self._subscribers.pop(job_id, None)

    async def history(self, job_id: str) -> List[Dict[str, Any]]:
        async with self._lock:
            return list(self._history.get(job_id, ()))

    async def clear(self, job_id: Optional[str] = None) -> None:
        async with self._lock:
            if job_id is None:
                self._history.clear()
            else:
                self._history.pop(job_id, None)

    def subscriber_count(self, job_id: str) -> int:
        return len(self._subscribers.get(job_id, ()))

    def known_jobs(self) -> List[str]:
        return list(self._history.keys())


# ---------------------------------------------------------------------------
# Convenience publishers — keep the call sites readable in orchestrator_api
# ---------------------------------------------------------------------------


async def publish_phase_changed(
    broker: EventBroker,
    job_id: str,
    *,
    from_phase: Optional[str],
    to_phase: str,
    reason: Optional[str] = None,
) -> Dict[str, Any]:
    if to_phase not in ALL_PHASES:
        raise ValueError(f"unknown phase: {to_phase!r}")
    data: Dict[str, Any] = {"from": from_phase, "to": to_phase}
    if reason is not None:
        data["reason"] = reason
    return await broker.publish(EVENT_PHASE_CHANGED, job_id, data)


async def publish_approval_requested(
    broker: EventBroker,
    job_id: str,
    *,
    kind: str,
    summary: str,
    payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    data: Dict[str, Any] = {"kind": kind, "summary": summary}
    if payload is not None:
        data["payload"] = payload
    return await broker.publish(EVENT_APPROVAL_REQUESTED, job_id, data)


async def publish_worker_heartbeat(
    broker: EventBroker,
    job_id: str,
    *,
    worker: str,
    progress: Optional[float] = None,
    note: Optional[str] = None,
) -> Dict[str, Any]:
    data: Dict[str, Any] = {"worker": worker}
    if progress is not None:
        data["progress"] = progress
    if note is not None:
        data["note"] = note
    return await broker.publish(EVENT_WORKER_HEARTBEAT, job_id, data)


async def publish_error(
    broker: EventBroker,
    job_id: str,
    *,
    message: str,
    fatal: bool = False,
    detail: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    data: Dict[str, Any] = {"message": message, "fatal": bool(fatal)}
    if detail is not None:
        data["detail"] = detail
    return await broker.publish(EVENT_ERROR, job_id, data)


__all__ = [
    "ALL_EVENTS",
    "ALL_PHASES",
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
    "PHASE_AWAITING_APPROVAL",
    "PHASE_CANCELLED",
    "PHASE_COMPLETED",
    "PHASE_EXECUTING",
    "PHASE_FAILED",
    "PHASE_INTAKE",
    "PHASE_PLANNING",
    "PHASE_PUBLISH_READY",
    "PHASE_VALIDATING",
    "make_envelope",
    "publish_approval_requested",
    "publish_error",
    "publish_phase_changed",
    "publish_worker_heartbeat",
]
