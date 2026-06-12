"""Tests for the lease reschedule policy (Sprint 13, multi-host substrate).

Pure + deterministic: no store, no clock, no I/O. We construct leases via the
frozen kernel (:mod:`muse_cli.worker_lease`) and host records, then assert the
policy's decisions.
"""

from __future__ import annotations

from muse_cli.lease_scheduler import (
    Reschedule,
    host_load,
    pick_target_host,
    reschedule_plan,
)
from muse_cli.worker_lease import (
    LeaseStatus,
    WorkerLease,
    acquire,
    expire_if_stale,
)
from muse_cli.worker_lease_store import HostRecord


# ─── helpers ──────────────────────────────────────────────────────────


def _pending(
    lease_id: str, *, host_id: str = "host_a", idempotent: bool = True
) -> WorkerLease:
    return WorkerLease(
        lease_id=lease_id,
        job_id="job_1",
        worker_id="claude-code",
        host_id=host_id,
        idempotent=idempotent,
    )


def _running(
    lease_id: str,
    *,
    host_id: str = "host_a",
    idempotent: bool = True,
    now: float = 100.0,
    ttl: float = 30.0,
) -> WorkerLease:
    return acquire(
        _pending(lease_id, host_id=host_id, idempotent=idempotent), now=now, ttl=ttl
    )


def _expired(
    lease_id: str,
    *,
    host_id: str = "host_a",
    idempotent: bool = True,
) -> WorkerLease:
    # Acquire at 100 (ttl 30 -> expires 130), then fold past the deadline.
    running = _running(lease_id, host_id=host_id, idempotent=idempotent)
    expired = expire_if_stale(running, now=200.0)
    assert expired.status is LeaseStatus.EXPIRED
    return expired


def _hosts(*ids: str) -> list[HostRecord]:
    return [HostRecord(host_id=hid) for hid in ids]


# ─── host_load ────────────────────────────────────────────────────────


def test_host_load_counts_only_running():
    leases = [
        _running("a", host_id="h1"),
        _running("b", host_id="h1"),
        _running("c", host_id="h2"),
        _expired("d", host_id="h1"),  # expired -> not counted
    ]
    load = host_load(leases)
    assert load["h1"] == 2
    assert load["h2"] == 1
    assert load["nope"] == 0  # Counter default


# ─── pick_target_host ─────────────────────────────────────────────────


def test_pick_target_host_least_loaded():
    load = host_load([_running("a", host_id="busy"), _running("b", host_id="busy")])
    target = pick_target_host(_hosts("busy", "idle"), load)
    assert target == "idle"


def test_pick_target_host_tie_breaks_by_id():
    # Both hosts have zero load; the lower host_id wins deterministically.
    target = pick_target_host(_hosts("zebra", "alpha"), host_load([]))
    assert target == "alpha"


def test_pick_target_host_no_hosts_returns_none():
    assert pick_target_host([], host_load([])) is None


# ─── reschedule_plan ──────────────────────────────────────────────────


def test_reschedules_expired_idempotent_to_a_host():
    leases = [_expired("lost", host_id="host_a")]
    plan = reschedule_plan(1000.0, hosts=_hosts("host_a", "host_b"), leases=leases)
    assert len(plan) == 1
    action = plan[0]
    assert isinstance(action, Reschedule)
    assert action.lease_id == "lost"
    assert action.job_id == "job_1"
    assert action.from_host_id == "host_a"
    assert action.target_host_id in {"host_a", "host_b"}


def test_skips_running_leases():
    leases = [_running("live", host_id="host_a")]
    plan = reschedule_plan(1000.0, hosts=_hosts("host_a"), leases=leases)
    assert plan == []


def test_skips_non_idempotent_expired_leases():
    leases = [_expired("danger", host_id="host_a", idempotent=False)]
    plan = reschedule_plan(1000.0, hosts=_hosts("host_a", "host_b"), leases=leases)
    assert plan == []


def test_mixed_leases_only_retryable_rescheduled():
    leases = [
        _running("live", host_id="host_a"),
        _expired("retry-me", host_id="host_a", idempotent=True),
        _expired("no-retry", host_id="host_a", idempotent=False),
    ]
    plan = reschedule_plan(1000.0, hosts=_hosts("host_a", "host_b"), leases=leases)
    assert [r.lease_id for r in plan] == ["retry-me"]


def test_picks_least_loaded_target():
    # host_busy already runs two live leases; the expired one should be
    # rescheduled onto the idle host.
    leases = [
        _running("live1", host_id="host_busy"),
        _running("live2", host_id="host_busy"),
        _expired("lost", host_id="host_busy"),
    ]
    plan = reschedule_plan(
        1000.0, hosts=_hosts("host_busy", "host_idle"), leases=leases
    )
    assert len(plan) == 1
    assert plan[0].target_host_id == "host_idle"


def test_no_hosts_means_no_plan():
    leases = [_expired("lost", host_id="host_a")]
    assert reschedule_plan(1000.0, hosts=[], leases=leases) == []


def test_deterministic_same_inputs_same_output():
    leases = [
        _expired("e1", host_id="host_a"),
        _expired("e2", host_id="host_a"),
    ]
    hosts = _hosts("host_b", "host_a")  # unsorted on purpose
    plan1 = reschedule_plan(1000.0, hosts=hosts, leases=leases)
    plan2 = reschedule_plan(1000.0, hosts=hosts, leases=leases)
    assert plan1 == plan2
    # Order follows the input order of the expired leases.
    assert [r.lease_id for r in plan1] == ["e1", "e2"]
    # Tie on load (both hosts 0) -> deterministic lowest id target.
    assert {r.target_host_id for r in plan1} == {"host_a"}


def test_plan_does_not_mutate_inputs():
    expired = _expired("lost", host_id="host_a")
    leases = [expired]
    hosts = _hosts("host_a")
    reschedule_plan(1000.0, hosts=hosts, leases=leases)
    # Inputs unchanged (frozen dataclasses, but assert the lease is identical).
    assert leases == [expired]
    assert expired.status is LeaseStatus.EXPIRED
