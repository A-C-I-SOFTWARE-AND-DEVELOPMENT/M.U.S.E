"""Reschedule policy for lost worker leases (Sprint 13, multi-host).

The lease kernel (:mod:`muse_cli.worker_lease`) decides when a lease is
``EXPIRED`` and whether it ``can_retry`` (idempotent only); the store
(:mod:`muse_cli.worker_lease_store`) persists leases + a host registry. What
neither does is choose *where to re-run* a lost-but-retryable lease. That is a
**policy**, and this module is exactly that policy — kept pure so it is trivial
to test and reason about:

    plan = reschedule_plan(now, hosts=hosts, leases=leases)

Properties (all enforced + tested):

* **Only expired + idempotent leases are rescheduled.** A still-``RUNNING``
  lease is in flight; a non-idempotent expired lease must not be retried
  (replaying it could double an external side effect). Both are skipped — the
  same rule ``worker_lease.can_retry`` encodes, reused verbatim.
* **Least-loaded host placement.** "Load" is the number of currently
  ``RUNNING`` leases on each *registered* host. The target is the registered
  host with the fewest running leases; ties break by ``host_id`` so the result
  is deterministic.
* **Pure + deterministic.** No clock, no I/O, no randomness — ``now`` is passed
  in (callers fold ``expire_if_stale`` / ``expire_stale`` first, or pass already
  expired leases). Given identical inputs the output list is identical, in a
  stable order (input order of the expired leases).

This module decides; it does not act. A caller (the runner integration, a
documented follow-up) is responsible for taking each :class:`Reschedule` and
actually acquiring a fresh lease on the chosen host via a
:class:`muse_cli.runtime_adapter.RuntimeAdapter`. It never mutates the store
or the leases it is handed.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterable, Optional

from muse_cli.worker_lease import LeaseStatus, WorkerLease, can_retry
from muse_cli.worker_lease_store import HostRecord

__all__ = [
    "Reschedule",
    "host_load",
    "pick_target_host",
    "reschedule_plan",
]


@dataclass(frozen=True)
class Reschedule:
    """A proposal to re-run one lost lease's work on a chosen host.

    Carries the originating lease (so the caller can copy ``job_id`` /
    ``worker_id`` / ``idempotent`` when minting the replacement lease) and the
    target ``host_id`` the policy selected. ``from_host_id`` records where the
    work last ran, which is useful for an audit/ledger entry.
    """

    lease: WorkerLease
    target_host_id: str

    @property
    def lease_id(self) -> str:
        return self.lease.lease_id

    @property
    def job_id(self) -> str:
        return self.lease.job_id

    @property
    def from_host_id(self) -> str:
        return self.lease.host_id


def host_load(leases: Iterable[WorkerLease]) -> Counter[str]:
    """Count currently ``RUNNING`` leases per ``host_id``.

    This is the "load" the scheduler balances against — only in-flight
    (``RUNNING``) leases count toward a host's load; terminal/expired leases do
    not occupy a host. Hosts with zero running leases are simply absent from the
    returned counter (callers default them to 0).
    """

    counts: Counter[str] = Counter()
    for lease in leases:
        if lease.status is LeaseStatus.RUNNING:
            counts[lease.host_id] += 1
    return counts


def pick_target_host(
    hosts: Iterable[HostRecord], load: Counter[str]
) -> Optional[str]:
    """Return the least-loaded registered host id, or ``None`` if no hosts.

    "Least loaded" = fewest currently ``RUNNING`` leases (from ``load``);
    unseen hosts count as 0. Ties break by ``host_id`` ascending so the choice
    is deterministic regardless of registry iteration order.
    """

    candidates = list(hosts)
    if not candidates:
        return None
    # Sort key: (running-lease count, host_id). min() then yields the
    # least-loaded host, deterministically broken by id on ties.
    best = min(candidates, key=lambda h: (load.get(h.host_id, 0), h.host_id))
    return best.host_id


def reschedule_plan(
    now: float,
    *,
    hosts: Iterable[HostRecord],
    leases: Iterable[WorkerLease],
) -> list[Reschedule]:
    """Decide reschedule actions for lost-but-retryable leases.

    For every ``EXPIRED`` + idempotent lease (``worker_lease.can_retry`` is
    True), propose a retry on the least-loaded registered host. Still-running
    and non-idempotent leases are never rescheduled. The ``now`` argument is
    accepted for signature stability / future time-based policy (e.g. backoff)
    and to keep callers passing an explicit clock; the current policy is purely
    status-driven and does not branch on it.

    Returns one :class:`Reschedule` per retryable lease, in the input order of
    those leases. If no host is registered, returns ``[]`` (there is nowhere to
    place work — the caller surfaces that as a stalled job rather than guessing
    a host).
    """

    lease_list = list(leases)
    host_list = list(hosts)

    target = pick_target_host(host_list, host_load(lease_list))
    if target is None:
        return []

    plan: list[Reschedule] = []
    for lease in lease_list:
        if can_retry(lease):
            plan.append(Reschedule(lease=lease, target_host_id=target))
    return plan
