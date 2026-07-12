"""Tests for durable, tuple-bound one-time approval grants."""

from __future__ import annotations

import hashlib
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from typing import Any

import pytest

import hermes_cli.approval_grants as grants
from hermes_cli.approval_grants import (
    ApprovalBindingMismatchError,
    ApprovalConflictError,
    ApprovalExpiredError,
    ApprovalGrantError,
    ApprovalNotFoundError,
    ApprovalState,
    ApprovalStateError,
    ApprovalVerifier,
    BoundApproval,
    decide_bound_approval,
    list_bound_approvals,
    stage_bound_approval,
    validate_and_consume_approval,
)
from hermes_constants import reset_hermes_home_override, set_hermes_home_override


ACTOR = "actor-7"
ACTION = "plugin.command.execute"
REALM = "realm-alpha"
CORRELATION = "corr-42"
SUBJECT = {"resource": "artifact-9", "revision": 3}


def _stage(db_path: Path, **overrides: object) -> BoundApproval:
    values: dict[str, Any] = {
        "actor_id": ACTOR,
        "action": ACTION,
        "realm_id": REALM,
        "correlation_id": CORRELATION,
        "subject": SUBJECT,
        "db_path": db_path,
    }
    values.update(overrides)
    return stage_bound_approval(**values)


def _grant(db_path: Path, **overrides: object) -> BoundApproval:
    staged = _stage(db_path, **overrides)
    return decide_bound_approval(
        staged.approval_id,
        approve=True,
        decided_by="cockpit-user",
        db_path=db_path,
    )


def _consume(db_path: Path, approval_id: str, **overrides: object) -> BoundApproval:
    values: dict[str, Any] = {
        "approval_id": approval_id,
        "actor_id": ACTOR,
        "action": ACTION,
        "realm_id": REALM,
        "correlation_id": CORRELATION,
        "subject": SUBJECT,
        "db_path": db_path,
    }
    values.update(overrides)
    return validate_and_consume_approval(**values)


def test_stage_persists_canonical_hash_and_lists_immutable_record(tmp_path: Path) -> None:
    db_path = tmp_path / "grants.db"

    staged = _stage(db_path, subject={"revision": 3, "resource": "artifact-9"})

    assert staged.state is ApprovalState.PENDING
    assert staged.subject_hash == hashlib.sha256(
        b'{"resource":"artifact-9","revision":3}'
    ).hexdigest()
    assert staged.provenance == "bound-approval-v1"
    assert list_bound_approvals(db_path=db_path) == (staged,)
    with pytest.raises(AttributeError):
        staged.state = ApprovalState.GRANTED  # ty: ignore[invalid-assignment]


def test_storage_and_serialization_never_expose_raw_subject(tmp_path: Path) -> None:
    db_path = tmp_path / "grants.db"
    secret_marker = "raw-subject-must-not-survive"

    staged = _stage(db_path, subject={"marker": secret_marker})

    assert secret_marker.encode() not in db_path.read_bytes()
    assert "subject" not in staged.to_dict()
    assert staged.to_dict()["subject_hash"] == staged.subject_hash


def test_default_path_is_profile_aware(tmp_path: Path) -> None:
    profile_home = tmp_path / "profiles" / "reviewer"
    token = set_hermes_home_override(profile_home)
    try:
        staged = stage_bound_approval(
            ACTOR, ACTION, REALM, CORRELATION, SUBJECT
        )
    finally:
        reset_hermes_home_override(token)

    expected = profile_home / "approvals" / "grants.db"
    assert expected.is_file()
    assert list_bound_approvals(db_path=expected) == (staged,)


def test_caller_supplied_id_is_idempotent_for_same_binding(tmp_path: Path) -> None:
    db_path = tmp_path / "grants.db"

    first = _stage(db_path, approval_id="approval-fixed")
    second = _stage(db_path, approval_id="approval-fixed")

    assert second == first
    assert list_bound_approvals(db_path=db_path) == (first,)


@pytest.mark.parametrize(
    ("field", "different"),
    [
        ("actor_id", "actor-other"),
        ("action", "plugin.command.other"),
        ("realm_id", "realm-other"),
        ("correlation_id", "corr-other"),
        ("subject", {"resource": "artifact-other"}),
    ],
)
def test_caller_supplied_id_rejects_binding_mismatch(
    tmp_path: Path, field: str, different: object
) -> None:
    db_path = tmp_path / "grants.db"
    original = _stage(db_path, approval_id="approval-fixed")

    with pytest.raises(ApprovalConflictError):
        _stage(db_path, approval_id="approval-fixed", **{field: different})

    assert list_bound_approvals(db_path=db_path) == (original,)


def test_decision_grants_or_rejects_pending_request(tmp_path: Path) -> None:
    db_path = tmp_path / "grants.db"
    granted_pending = _stage(db_path, approval_id="grant-me")
    rejected_pending = _stage(db_path, approval_id="reject-me")

    granted = decide_bound_approval(
        granted_pending.approval_id,
        approve=True,
        decided_by="reviewer-a",
        db_path=db_path,
    )
    rejected = decide_bound_approval(
        rejected_pending.approval_id,
        approve=False,
        decided_by="reviewer-b",
        db_path=db_path,
    )

    assert granted.state is ApprovalState.GRANTED
    assert granted.decided_by == "reviewer-a"
    assert granted.decided_at is not None
    assert rejected.state is ApprovalState.REJECTED
    assert rejected.decided_by == "reviewer-b"
    with pytest.raises(ApprovalStateError):
        _consume(db_path, rejected.approval_id)


def test_same_decision_is_idempotent_but_opposite_decision_fails(tmp_path: Path) -> None:
    db_path = tmp_path / "grants.db"
    pending = _stage(db_path)
    granted = decide_bound_approval(
        pending.approval_id,
        approve=True,
        decided_by="reviewer-a",
        db_path=db_path,
    )

    assert decide_bound_approval(
        pending.approval_id,
        approve=True,
        decided_by="reviewer-a",
        db_path=db_path,
    ) == granted
    with pytest.raises(ApprovalStateError):
        decide_bound_approval(
            pending.approval_id,
            approve=False,
            decided_by="reviewer-a",
            db_path=db_path,
        )


def test_pending_and_granted_requests_expire(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    db_path = tmp_path / "grants.db"
    monkeypatch.setattr(grants.time, "time", lambda: 100.0)
    pending = _stage(db_path, approval_id="pending", ttl_seconds=10)
    granted = _grant(db_path, approval_id="granted", ttl_seconds=10)
    monkeypatch.setattr(grants.time, "time", lambda: 111.0)

    with pytest.raises(ApprovalExpiredError):
        decide_bound_approval(
            pending.approval_id,
            approve=True,
            decided_by="reviewer",
            db_path=db_path,
        )
    with pytest.raises(ApprovalExpiredError):
        _consume(db_path, granted.approval_id)

    expired = list_bound_approvals(state=ApprovalState.EXPIRED, db_path=db_path)
    assert {item.approval_id for item in expired} == {"pending", "granted"}


@pytest.mark.parametrize(
    ("field", "different"),
    [
        ("actor_id", "actor-other"),
        ("action", "plugin.command.other"),
        ("realm_id", "realm-other"),
        ("correlation_id", "corr-other"),
        ("subject", {"resource": "artifact-other"}),
    ],
)
def test_consume_fails_closed_for_every_binding_mismatch(
    tmp_path: Path, field: str, different: object
) -> None:
    db_path = tmp_path / "grants.db"
    granted = _grant(db_path)

    with pytest.raises(ApprovalBindingMismatchError):
        _consume(db_path, granted.approval_id, **{field: different})

    persisted = list_bound_approvals(db_path=db_path)[0]
    assert persisted.state is ApprovalState.GRANTED
    assert persisted.consumed_at is None


def test_consume_is_one_time_with_same_tuple_idempotent_retry(tmp_path: Path) -> None:
    db_path = tmp_path / "grants.db"
    granted = _grant(db_path)

    consumed = _consume(db_path, granted.approval_id)
    retried = _consume(db_path, granted.approval_id)

    assert consumed.state is ApprovalState.CONSUMED
    assert retried == consumed
    with pytest.raises(ApprovalBindingMismatchError):
        _consume(db_path, granted.approval_id, actor_id="actor-other")


def test_two_thread_consume_race_is_atomic_and_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "grants.db"
    granted = _grant(db_path)
    barrier = Barrier(2)

    def consume() -> BoundApproval:
        barrier.wait()
        return _consume(db_path, granted.approval_id)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = tuple(pool.map(lambda _: consume(), range(2)))

    assert results[0] == results[1]
    assert results[0].state is ApprovalState.CONSUMED
    persisted = list_bound_approvals(db_path=db_path)
    assert persisted == (results[0],)


def test_failed_consume_rolls_back_without_mutating_grant(tmp_path: Path) -> None:
    db_path = tmp_path / "grants.db"
    granted = _grant(db_path)

    with pytest.raises(ApprovalBindingMismatchError):
        _consume(db_path, granted.approval_id, action="plugin.command.wrong")

    with sqlite3.connect(db_path) as conn:
        state, consumed_at = conn.execute(
            "SELECT state, consumed_at FROM bound_approvals WHERE approval_id = ?",
            (granted.approval_id,),
        ).fetchone()
    assert state == ApprovalState.GRANTED.value
    assert consumed_at is None
    assert _consume(db_path, granted.approval_id).state is ApprovalState.CONSUMED


def test_unknown_id_raises_stable_domain_error(tmp_path: Path) -> None:
    db_path = tmp_path / "grants.db"

    with pytest.raises(ApprovalNotFoundError):
        decide_bound_approval(
            "missing",
            approve=True,
            decided_by="reviewer",
            db_path=db_path,
        )
    assert issubclass(ApprovalNotFoundError, ApprovalGrantError)
    assert issubclass(ApprovalConflictError, ApprovalGrantError)
    assert issubclass(ApprovalBindingMismatchError, ApprovalGrantError)
    assert issubclass(ApprovalStateError, ApprovalGrantError)
    assert issubclass(ApprovalExpiredError, ApprovalStateError)


def test_approval_verifier_is_structural_protocol() -> None:
    class FakeVerifier:
        def validate_and_consume_approval(
            self,
            approval_id: str,
            actor_id: str,
            action: str,
            realm_id: str,
            correlation_id: str,
            subject: object,
            *,
            db_path: Path | None = None,
        ) -> BoundApproval:
            raise NotImplementedError

    assert isinstance(FakeVerifier(), ApprovalVerifier)
