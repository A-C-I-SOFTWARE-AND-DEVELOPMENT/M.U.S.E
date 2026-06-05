"""Worker lease state machine (Sprint 13 core).

Durable-lease semantics for multi-host worker execution, as a pure,
clock-injected state machine — no wall-clock dependence, so transitions are
deterministic and testable. Encodes the plan's failure rules:

* a lost heartbeat (now past ``expires_at``) **expires** the lease;
* an **expired** lease may be **retried** only if the work is idempotent;
* a **duplicate completion after expiry** is rejected (``can_complete`` is
  False once expired/terminal);
* terminal leases are immutable.

Persistence, the host registry, and heartbeat scheduling are wiring left for
a follow-up; this is the state kernel and its tests. Every transition
returns a new frozen :class:`WorkerLease`; invalid transitions raise
``ValueError`` so a caller can't silently drive a lease into a bad state.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, replace
from typing import Optional

__all__ = [
    "LeaseStatus",
    "WorkerLease",
    "acquire",
    "heartbeat",
    "expire_if_stale",
    "complete",
    "cancel",
    "is_expired",
    "can_retry",
    "can_complete",
]


class LeaseStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


_TERMINAL: frozenset[LeaseStatus] = frozenset(
    {LeaseStatus.COMPLETED, LeaseStatus.EXPIRED, LeaseStatus.CANCELLED}
)


@dataclass(frozen=True)
class WorkerLease:
    """One worker's claim on a job on a host, with a heartbeat deadline."""

    lease_id: str
    job_id: str
    worker_id: str
    host_id: str
    status: LeaseStatus = LeaseStatus.PENDING
    acquired_at: Optional[float] = None
    heartbeat_at: Optional[float] = None
    expires_at: Optional[float] = None
    idempotent: bool = True
    """Whether the work can be safely retried after a lost lease."""

    @property
    def is_terminal(self) -> bool:
        return self.status in _TERMINAL


def acquire(lease: WorkerLease, *, now: float, ttl: float) -> WorkerLease:
    """Claim a ``PENDING`` lease, starting the heartbeat clock."""

    if lease.status is not LeaseStatus.PENDING:
        raise ValueError(f"cannot acquire lease in status {lease.status.value}")
    if ttl <= 0:
        raise ValueError("ttl must be > 0")
    return replace(
        lease,
        status=LeaseStatus.RUNNING,
        acquired_at=now,
        heartbeat_at=now,
        expires_at=now + ttl,
    )


def is_expired(lease: WorkerLease, *, now: float) -> bool:
    """True when a ``RUNNING`` lease is past its heartbeat deadline."""

    return (
        lease.status is LeaseStatus.RUNNING
        and lease.expires_at is not None
        and now > lease.expires_at
    )


def heartbeat(lease: WorkerLease, *, now: float, ttl: float) -> WorkerLease:
    """Refresh a ``RUNNING`` lease's deadline — unless it already lapsed.

    A heartbeat that arrives after ``expires_at`` is too late: the lease has
    been lost, so it transitions to ``EXPIRED`` rather than being revived.
    """

    if lease.status is not LeaseStatus.RUNNING:
        raise ValueError(f"cannot heartbeat lease in status {lease.status.value}")
    if ttl <= 0:
        raise ValueError("ttl must be > 0")
    if is_expired(lease, now=now):
        return replace(lease, status=LeaseStatus.EXPIRED)
    return replace(lease, heartbeat_at=now, expires_at=now + ttl)


def expire_if_stale(lease: WorkerLease, *, now: float) -> WorkerLease:
    """Transition a stale ``RUNNING`` lease to ``EXPIRED``; otherwise no-op."""

    if is_expired(lease, now=now):
        return replace(lease, status=LeaseStatus.EXPIRED)
    return lease


def can_complete(lease: WorkerLease, *, now: float) -> bool:
    """True only if a completion now would be accepted (running, not lapsed)."""

    return lease.status is LeaseStatus.RUNNING and not is_expired(lease, now=now)


def complete(lease: WorkerLease, *, now: float) -> WorkerLease:
    """Mark a live ``RUNNING`` lease ``COMPLETED``.

    Rejects a duplicate/late completion: a lease that already lapsed (a lost
    lease whose worker reports done after expiry) cannot be completed.
    """

    if not can_complete(lease, now=now):
        raise ValueError(
            f"cannot complete lease in status {lease.status.value} (expired or terminal)"
        )
    return replace(lease, status=LeaseStatus.COMPLETED, heartbeat_at=now)


def cancel(lease: WorkerLease) -> WorkerLease:
    """Cancel a non-terminal lease."""

    if lease.is_terminal:
        raise ValueError(f"cannot cancel lease in status {lease.status.value}")
    return replace(lease, status=LeaseStatus.CANCELLED)


def can_retry(lease: WorkerLease) -> bool:
    """True when an expired lease's work may be re-leased (idempotent only)."""

    return lease.status is LeaseStatus.EXPIRED and lease.idempotent
