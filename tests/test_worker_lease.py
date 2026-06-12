"""Tests for the worker lease state machine (Sprint 13)."""

from __future__ import annotations

import pytest

from muse_cli.worker_lease import (
    LeaseStatus,
    WorkerLease,
    acquire,
    can_complete,
    can_retry,
    cancel,
    complete,
    expire_if_stale,
    heartbeat,
    is_expired,
)


def _pending(idempotent: bool = True) -> WorkerLease:
    return WorkerLease(
        lease_id="lease_1",
        job_id="job_1",
        worker_id="claude-code",
        host_id="host_a",
        idempotent=idempotent,
    )


def _running(now: float = 100.0, ttl: float = 30.0) -> WorkerLease:
    return acquire(_pending(), now=now, ttl=ttl)


def test_acquire_from_pending():
    lease = acquire(_pending(), now=100.0, ttl=30.0)
    assert lease.status is LeaseStatus.RUNNING
    assert lease.acquired_at == 100.0
    assert lease.heartbeat_at == 100.0
    assert lease.expires_at == 130.0


def test_acquire_non_pending_raises():
    with pytest.raises(ValueError):
        acquire(_running(), now=200.0, ttl=30.0)


def test_acquire_bad_ttl_raises():
    with pytest.raises(ValueError):
        acquire(_pending(), now=100.0, ttl=0.0)


def test_is_expired():
    lease = _running(now=100.0, ttl=30.0)  # expires at 130
    assert is_expired(lease, now=125.0) is False
    assert is_expired(lease, now=130.0) is False  # inclusive boundary, not yet past
    assert is_expired(lease, now=131.0) is True
    # non-running leases are never "expired" in this sense
    assert is_expired(_pending(), now=999.0) is False


def test_heartbeat_extends_deadline():
    lease = _running(now=100.0, ttl=30.0)
    beat = heartbeat(lease, now=120.0, ttl=30.0)
    assert beat.heartbeat_at == 120.0
    assert beat.expires_at == 150.0
    assert beat.status is LeaseStatus.RUNNING


def test_heartbeat_after_expiry_loses_lease():
    lease = _running(now=100.0, ttl=30.0)  # expires 130
    beat = heartbeat(lease, now=140.0, ttl=30.0)
    assert beat.status is LeaseStatus.EXPIRED


def test_heartbeat_non_running_raises():
    with pytest.raises(ValueError):
        heartbeat(_pending(), now=100.0, ttl=30.0)


def test_expire_if_stale():
    lease = _running(now=100.0, ttl=30.0)
    assert expire_if_stale(lease, now=120.0).status is LeaseStatus.RUNNING  # fresh
    assert expire_if_stale(lease, now=200.0).status is LeaseStatus.EXPIRED  # stale
    # no-op on terminal
    done = complete(lease, now=110.0)
    assert expire_if_stale(done, now=9999.0).status is LeaseStatus.COMPLETED


def test_can_complete():
    lease = _running(now=100.0, ttl=30.0)
    assert can_complete(lease, now=120.0) is True
    assert can_complete(lease, now=200.0) is False  # lapsed
    assert can_complete(_pending(), now=100.0) is False


def test_complete_live_lease():
    lease = _running(now=100.0, ttl=30.0)
    done = complete(lease, now=115.0)
    assert done.status is LeaseStatus.COMPLETED
    assert done.heartbeat_at == 115.0
    assert done.is_terminal


def test_duplicate_completion_after_expiry_rejected():
    lease = _running(now=100.0, ttl=30.0)  # expires 130
    # worker reports done at 140, after the lease lapsed -> rejected
    with pytest.raises(ValueError):
        complete(lease, now=140.0)


def test_complete_non_running_raises():
    with pytest.raises(ValueError):
        complete(_pending(), now=100.0)


def test_cancel_non_terminal():
    assert cancel(_pending()).status is LeaseStatus.CANCELLED
    assert cancel(_running()).status is LeaseStatus.CANCELLED


def test_cancel_terminal_raises():
    done = complete(_running(now=100.0, ttl=30.0), now=110.0)
    with pytest.raises(ValueError):
        cancel(done)


def test_can_retry_only_expired_idempotent():
    expired_idem = expire_if_stale(_running(now=100.0, ttl=30.0), now=200.0)
    assert expired_idem.status is LeaseStatus.EXPIRED
    assert can_retry(expired_idem) is True

    expired_non_idem = expire_if_stale(
        acquire(_pending(idempotent=False), now=100.0, ttl=30.0), now=200.0
    )
    assert can_retry(expired_non_idem) is False

    assert can_retry(_running()) is False  # not expired


def test_is_terminal_property():
    assert _pending().is_terminal is False
    assert _running().is_terminal is False
    assert complete(_running(now=100.0, ttl=30.0), now=110.0).is_terminal is True
