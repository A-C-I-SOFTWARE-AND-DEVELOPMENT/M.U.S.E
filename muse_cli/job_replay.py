"""Deterministic job-state reconstruction from the event stream (Sprint 4).

The orchestrator emits a stable event vocabulary (:mod:`muse_cli.orchestrator_events`)
and stores each job's events, but nothing reconstructs job *state* from those
events — state is loaded from a snapshot file. This module adds the missing
fold: given the ordered event envelopes for one job, rebuild a
:class:`JobSnapshot`.

The reducer is **pure and deterministic**:

* replaying the same events always yields the same snapshot;
* a truncated prefix of the events yields a consistent *partial* snapshot;
* unknown event types and missing payload keys are tolerated, never raise.

This is what lets a job's state survive a process restart by *replay* — the
Sprint 14 "restart mid-job → replay" gate — instead of relying solely on a
snapshot file. It is additive: it changes no emission or storage behavior.

Each envelope is the shape produced by
:func:`muse_cli.orchestrator_events.make_envelope`::

    {"event": "...", "job_id": "...", "ts": 0.0, "data": {...}}

A known wrinkle, faithful to the current emitters: ``reject``/``cancel`` do
not always emit a ``phase.changed``, so terminal phase is derived from
``job.failed`` (with ``reason == "cancelled"`` mapped to the cancelled phase).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any, Optional

from muse_cli.orchestrator_events import (
    EVENT_APPROVAL_GRANTED,
    EVENT_APPROVAL_REJECTED,
    EVENT_APPROVAL_REQUESTED,
    EVENT_ERROR,
    EVENT_JOB_CREATED,
    EVENT_JOB_FAILED,
    EVENT_PHASE_CHANGED,
    EVENT_PUBLISH_READY,
    EVENT_VALIDATION_COMPLETED,
    EVENT_WORKER_BLOCKED,
    EVENT_WORKER_COMPLETED,
    EVENT_WORKER_HEARTBEAT,
    EVENT_WORKER_STARTED,
    PHASE_CANCELLED,
    PHASE_COMPLETED,
    PHASE_FAILED,
    PHASE_INTAKE,
)

__all__ = ["JobSnapshot", "rebuild_snapshot"]


# phase -> status, mirroring the statuses orchestrator_api.JobStore.update sets.
_PHASE_STATUS: dict[str, str] = {
    "intake": "pending",
    "planning": "running",
    "executing": "running",
    "validating": "validating",
    "awaiting_approval": "awaiting_approval",
    "publish_ready": "publish_ready",
    "completed": "completed",
    "failed": "failed",
    "cancelled": "cancelled",
}

_TERMINAL_PHASES: frozenset[str] = frozenset(
    {PHASE_COMPLETED, PHASE_FAILED, PHASE_CANCELLED}
)

# Keys a publish plan may carry a pull-request URL under (emitters vary).
_PR_URL_KEYS: tuple[str, ...] = ("pr_url", "url", "html_url", "pull_request_url")


@dataclass
class JobSnapshot:
    """Reconstructed job state. Mirrors the load-bearing fields of ``Job``."""

    job_id: str
    name: Optional[str] = None
    spec: dict[str, Any] = field(default_factory=dict)
    status: str = "pending"
    phase: str = PHASE_INTAKE
    workers: dict[str, str] = field(default_factory=dict)
    approvals: dict[str, str] = field(default_factory=dict)
    validation: Optional[dict[str, Any]] = None
    publish_plan: Optional[dict[str, Any]] = None
    pr_url: Optional[str] = None
    error: Optional[str] = None
    failed: bool = False
    event_count: int = 0
    last_ts: Optional[float] = None

    @property
    def is_terminal(self) -> bool:
        return self.phase in _TERMINAL_PHASES

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "name": self.name,
            "spec": self.spec,
            "status": self.status,
            "phase": self.phase,
            "workers": dict(self.workers),
            "approvals": dict(self.approvals),
            "validation": self.validation,
            "publish_plan": self.publish_plan,
            "pr_url": self.pr_url,
            "error": self.error,
            "failed": self.failed,
            "event_count": self.event_count,
            "last_ts": self.last_ts,
        }


def _pr_url_from_plan(plan: Mapping[str, Any]) -> Optional[str]:
    for key in _PR_URL_KEYS:
        value = plan.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def rebuild_snapshot(
    events: Iterable[Mapping[str, Any]], *, job_id: Optional[str] = None
) -> JobSnapshot:
    """Fold ordered event envelopes into a :class:`JobSnapshot`.

    ``job_id`` may be passed explicitly; otherwise it is taken from the first
    envelope that carries one. Events are applied in iteration order, so pass
    them oldest→newest (the order the broker and event log store them).
    """

    snapshot = JobSnapshot(job_id=job_id or "")

    for envelope in events:
        if not isinstance(envelope, Mapping):
            continue
        event = envelope.get("event")
        data = envelope.get("data")
        if not isinstance(data, Mapping):
            data = {}

        if not snapshot.job_id:
            envelope_job = envelope.get("job_id")
            if isinstance(envelope_job, str) and envelope_job:
                snapshot.job_id = envelope_job

        ts = envelope.get("ts")
        if isinstance(ts, (int, float)):
            snapshot.last_ts = float(ts)
        snapshot.event_count += 1

        if event == EVENT_JOB_CREATED:
            name = data.get("name")
            if isinstance(name, str):
                snapshot.name = name
            spec = data.get("spec")
            if isinstance(spec, Mapping):
                snapshot.spec = dict(spec)
            snapshot.phase = PHASE_INTAKE
            snapshot.status = _PHASE_STATUS[PHASE_INTAKE]

        elif event == EVENT_PHASE_CHANGED:
            to_phase = data.get("to")
            if isinstance(to_phase, str) and to_phase:
                snapshot.phase = to_phase
                snapshot.status = _PHASE_STATUS.get(to_phase, snapshot.status)

        elif event == EVENT_WORKER_STARTED:
            worker = data.get("worker")
            if isinstance(worker, str) and worker:
                snapshot.workers[worker] = "running"

        elif event == EVENT_WORKER_HEARTBEAT:
            worker = data.get("worker")
            if isinstance(worker, str) and worker:
                snapshot.workers.setdefault(worker, "running")
                snapshot.workers[worker] = "running"

        elif event == EVENT_WORKER_BLOCKED:
            worker = data.get("worker")
            if isinstance(worker, str) and worker:
                snapshot.workers[worker] = "blocked"

        elif event == EVENT_WORKER_COMPLETED:
            worker = data.get("worker")
            if isinstance(worker, str) and worker:
                snapshot.workers[worker] = "completed"

        elif event == EVENT_APPROVAL_REQUESTED:
            approval_id = data.get("approval_id") or data.get("id")
            if isinstance(approval_id, str) and approval_id:
                snapshot.approvals[approval_id] = "pending"

        elif event == EVENT_APPROVAL_GRANTED:
            approval_id = data.get("approval_id") or data.get("id")
            if isinstance(approval_id, str) and approval_id:
                snapshot.approvals[approval_id] = "granted"

        elif event == EVENT_APPROVAL_REJECTED:
            approval_id = data.get("approval_id") or data.get("id")
            if isinstance(approval_id, str) and approval_id:
                snapshot.approvals[approval_id] = "rejected"

        elif event == EVENT_VALIDATION_COMPLETED:
            result = data.get("result")
            snapshot.validation = dict(result) if isinstance(result, Mapping) else {}

        elif event == EVENT_PUBLISH_READY:
            plan = data.get("plan")
            if isinstance(plan, Mapping):
                snapshot.publish_plan = dict(plan)
                pr_url = _pr_url_from_plan(plan)
                if pr_url:
                    snapshot.pr_url = pr_url

        elif event == EVENT_JOB_FAILED:
            snapshot.failed = True
            reason = data.get("reason")
            if isinstance(reason, str) and reason:
                snapshot.error = reason
            if reason == "cancelled":
                snapshot.phase = PHASE_CANCELLED
                snapshot.status = _PHASE_STATUS[PHASE_CANCELLED]
            else:
                snapshot.phase = PHASE_FAILED
                snapshot.status = _PHASE_STATUS[PHASE_FAILED]

        elif event == EVENT_ERROR:
            message = data.get("message") or data.get("error")
            if isinstance(message, str) and message:
                snapshot.error = message

        # Unknown / non-state events (heartbeat extras, evidence.updated,
        # scoring.completed, phase.changed without "to") are tolerated: counted
        # but not folded into state.

    return snapshot
