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
    ApprovalCorruptionError,
    ApprovalExpiredError,
    ApprovalGrantError,
    ApprovalNotFoundError,
    ApprovalSchemaVersionError,
    ApprovalState,
    ApprovalStateError,
    ApprovalVerifier,
    BoundApproval,
    decide_bound_approval,
    list_bound_approvals,
    stage_bound_approval,
    supersede_bound_approval,
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


def test_subject_hashing_rejects_stringified_key_collision(tmp_path: Path) -> None:
    db_path = tmp_path / "grants.db"

    accepted = _stage(db_path, subject={"1": "x"})
    with pytest.raises(ValueError, match="string keys"):
        _stage(db_path, subject={1: "x"})

    assert list_bound_approvals(db_path=db_path) == (accepted,)


@pytest.mark.parametrize(
    "subject",
    [
        {"nested": {1: "x"}},
        {"nested": [object()]},
        {"nested": float("nan")},
        {"nested": float("inf")},
        ("tuple",),
    ],
)
def test_subject_hashing_rejects_nested_ambiguous_values(
    tmp_path: Path, subject: object
) -> None:
    with pytest.raises(ValueError, match="subject"):
        _stage(tmp_path / "grants.db", subject=subject)


@pytest.mark.parametrize(
    "ttl_seconds",
    [True, False, 0, -1, float("nan"), float("inf"), float("-inf"), "60", None],
)
def test_stage_rejects_non_real_non_finite_or_non_positive_ttl(
    tmp_path: Path, ttl_seconds: object
) -> None:
    db_path = tmp_path / "grants.db"

    with pytest.raises(ValueError, match="ttl_seconds"):
        _stage(db_path, ttl_seconds=ttl_seconds)

    assert list_bound_approvals(db_path=db_path) == ()


def test_stage_rejects_ttl_below_clock_resolution_before_db_write(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    db_path = tmp_path / "grants.db"
    monkeypatch.setattr(grants.time, "time", lambda: 1e20)

    with pytest.raises(ValueError, match="ttl_seconds"):
        _stage(db_path, ttl_seconds=1)

    assert not db_path.exists()


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


def test_legacy_v0_database_migrates_without_losing_valid_grant(tmp_path: Path) -> None:
    db_path = tmp_path / "grants.db"
    subject_hash = hashlib.sha256(b'{"legacy":true}').hexdigest()
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE bound_approvals (
                approval_id TEXT PRIMARY KEY,
                actor_id TEXT NOT NULL,
                action TEXT NOT NULL,
                realm_id TEXT NOT NULL,
                correlation_id TEXT NOT NULL,
                subject_hash TEXT NOT NULL,
                state TEXT NOT NULL,
                issued_at REAL NOT NULL,
                expires_at REAL NOT NULL,
                decided_at REAL,
                decided_by TEXT,
                consumed_at REAL,
                provenance TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            INSERT INTO bound_approvals VALUES (
                'legacy-id', 'legacy-actor', 'legacy.action', 'legacy-realm',
                'legacy-correlation', ?, 'pending', 100, 200,
                NULL, NULL, NULL, 'bound-approval-v1'
            )
            """,
            (subject_hash,),
        )

    migrated = list_bound_approvals(db_path=db_path)

    assert len(migrated) == 1
    assert migrated[0].approval_id == "legacy-id"
    assert migrated[0].subject_hash == subject_hash
    with sqlite3.connect(db_path) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 1
        columns = {
            row[1] for row in conn.execute("PRAGMA table_info(bound_approvals)")
        }
    assert "superseded_by" in columns


def test_future_schema_version_fails_closed(tmp_path: Path) -> None:
    db_path = tmp_path / "grants.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA user_version=2")

    with pytest.raises(ApprovalSchemaVersionError):
        list_bound_approvals(db_path=db_path)


def test_claimed_v1_schema_missing_required_column_is_corruption(tmp_path: Path) -> None:
    db_path = tmp_path / "grants.db"
    subject_hash = hashlib.sha256(b"null").hexdigest()
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE bound_approvals (
                approval_id TEXT PRIMARY KEY, actor_id TEXT, action TEXT,
                realm_id TEXT, correlation_id TEXT, subject_hash TEXT,
                state TEXT, issued_at REAL, expires_at REAL, decided_at REAL,
                decided_by TEXT, consumed_at REAL, provenance TEXT
            )
            """
        )
        conn.execute(
            """
            INSERT INTO bound_approvals VALUES (
                'malformed', 'actor', 'action', 'realm', 'correlation', ?,
                'pending', 100, 200, NULL, NULL, NULL, 'bound-approval-v1'
            )
            """,
            (subject_hash,),
        )
        conn.execute("PRAGMA user_version=1")

    with pytest.raises(ApprovalCorruptionError):
        list_bound_approvals(db_path=db_path)


def test_empty_claimed_v1_schema_is_validated_exactly(tmp_path: Path) -> None:
    db_path = tmp_path / "grants.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE bound_approvals (
                approval_id TEXT PRIMARY KEY,
                actor_id TEXT,
                action TEXT,
                realm_id TEXT,
                correlation_id TEXT,
                subject_hash TEXT,
                state TEXT,
                issued_at REAL,
                expires_at REAL,
                decided_at REAL,
                decided_by TEXT,
                consumed_at REAL,
                provenance TEXT,
                superseded_by TEXT
            )
            """
        )
        conn.execute("PRAGMA user_version=1")

    with pytest.raises(ApprovalCorruptionError):
        list_bound_approvals(db_path=db_path)


def test_malformed_legacy_v0_layout_maps_to_domain_corruption(tmp_path: Path) -> None:
    db_path = tmp_path / "grants.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE bound_approvals (approval_id TEXT PRIMARY KEY)")

    with pytest.raises(ApprovalCorruptionError):
        list_bound_approvals(db_path=db_path)


def test_schema_version_is_read_under_write_lock(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    original_connect = sqlite3.connect
    raw_connection = original_connect(tmp_path / "grants.db")
    version_read_lock_states: list[bool] = []

    class ObservedConnection:
        @property
        def row_factory(self) -> object:
            return raw_connection.row_factory

        @row_factory.setter
        def row_factory(self, value: object) -> None:
            raw_connection.row_factory = value  # ty: ignore[invalid-assignment]

        def execute(self, sql: str, parameters: Any = ()) -> sqlite3.Cursor:
            if sql.strip() == "PRAGMA user_version":
                version_read_lock_states.append(raw_connection.in_transaction)
            return raw_connection.execute(sql, parameters)

        def commit(self) -> None:
            raw_connection.commit()

        def rollback(self) -> None:
            raw_connection.rollback()

        def close(self) -> None:
            raw_connection.close()

    observed = ObservedConnection()
    monkeypatch.setattr(grants.sqlite3, "connect", lambda *args, **kwargs: observed)

    assert list_bound_approvals(db_path=tmp_path / "grants.db") == ()
    assert version_read_lock_states == [True]


def test_concurrent_initializers_converge_on_one_valid_schema(tmp_path: Path) -> None:
    db_path = tmp_path / "grants.db"
    barrier = Barrier(4)

    def initialize() -> tuple[BoundApproval, ...]:
        barrier.wait()
        return list_bound_approvals(db_path=db_path)

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = tuple(pool.map(lambda _: initialize(), range(4)))

    assert results == ((), (), (), ())
    with sqlite3.connect(db_path) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 1


@pytest.mark.parametrize("entrypoint", ["list", "decide", "consume"])
def test_unknown_provenance_fails_closed_for_every_authority_path(
    tmp_path: Path, entrypoint: str
) -> None:
    db_path = tmp_path / "grants.db"
    record = _grant(db_path) if entrypoint == "consume" else _stage(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA ignore_check_constraints=ON")
        conn.execute(
            "UPDATE bound_approvals SET provenance = 'unknown-v9' WHERE approval_id = ?",
            (record.approval_id,),
        )

    with pytest.raises(ApprovalCorruptionError):
        if entrypoint == "list":
            list_bound_approvals(db_path=db_path)
        elif entrypoint == "decide":
            decide_bound_approval(
                record.approval_id,
                approve=True,
                decided_by="reviewer",
                db_path=db_path,
            )
        else:
            _consume(db_path, record.approval_id)


@pytest.mark.parametrize(
    "mutation",
    [
        "actor_id = ''",
        "expires_at = issued_at",
        "state = 'granted', decided_at = NULL, decided_by = NULL",
        "state = 'granted', decided_at = issued_at, decided_by = x'01'",
        "state = 'consumed', consumed_at = NULL",
    ],
)
def test_runtime_invariants_detect_corrupt_persisted_rows(
    tmp_path: Path, mutation: str
) -> None:
    db_path = tmp_path / "grants.db"
    pending = _stage(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA ignore_check_constraints=ON")
        conn.execute(
            f"UPDATE bound_approvals SET {mutation} WHERE approval_id = ?",
            (pending.approval_id,),
        )

    with pytest.raises(ApprovalCorruptionError):
        list_bound_approvals(db_path=db_path)


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


def test_same_outcome_retry_requires_original_decider(tmp_path: Path) -> None:
    db_path = tmp_path / "grants.db"
    pending = _stage(db_path)
    decided = decide_bound_approval(
        pending.approval_id,
        approve=True,
        decided_by="reviewer-a",
        db_path=db_path,
    )

    with pytest.raises(ApprovalStateError):
        decide_bound_approval(
            pending.approval_id,
            approve=True,
            decided_by="reviewer-b",
            db_path=db_path,
        )

    assert list_bound_approvals(db_path=db_path) == (decided,)


def test_supersession_is_atomic_and_idempotent_for_same_replacement(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "grants.db"
    original = _stage(db_path, approval_id="original")
    replacement = _stage(db_path, approval_id="replacement")

    superseded = supersede_bound_approval(
        original.approval_id,
        superseded_by=replacement.approval_id,
        db_path=db_path,
    )

    assert superseded.state is ApprovalState.SUPERSEDED
    assert superseded.superseded_by == replacement.approval_id
    assert supersede_bound_approval(
        original.approval_id,
        superseded_by=replacement.approval_id,
        db_path=db_path,
    ) == superseded
    records = {item.approval_id: item for item in list_bound_approvals(db_path=db_path)}
    assert records[replacement.approval_id].state is ApprovalState.PENDING
    with pytest.raises(ApprovalStateError):
        _consume(db_path, original.approval_id)


def test_supersession_rejects_different_or_mismatched_replacement(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "grants.db"
    original = _stage(db_path, approval_id="original")
    replacement = _stage(db_path, approval_id="replacement")
    other = _stage(db_path, approval_id="other", actor_id="actor-other")

    with pytest.raises(ApprovalBindingMismatchError):
        supersede_bound_approval(
            original.approval_id,
            superseded_by=other.approval_id,
            db_path=db_path,
        )
    supersede_bound_approval(
        original.approval_id,
        superseded_by=replacement.approval_id,
        db_path=db_path,
    )
    with pytest.raises(ApprovalStateError):
        supersede_bound_approval(
            original.approval_id,
            superseded_by=other.approval_id,
            db_path=db_path,
        )


def test_only_pending_approval_can_be_superseded(tmp_path: Path) -> None:
    db_path = tmp_path / "grants.db"
    granted = _grant(db_path, approval_id="granted")
    replacement = _stage(db_path, approval_id="replacement")

    with pytest.raises(ApprovalStateError):
        supersede_bound_approval(
            granted.approval_id,
            superseded_by=replacement.approval_id,
            db_path=db_path,
        )


@pytest.mark.parametrize("relationship", ["dangling", "mismatched"])
@pytest.mark.parametrize("entrypoint", ["list", "decide", "consume", "supersede"])
def test_tampered_supersession_relationship_fails_closed(
    tmp_path: Path, relationship: str, entrypoint: str
) -> None:
    db_path = tmp_path / "grants.db"
    original = _stage(db_path, approval_id="original")
    replacement = _stage(db_path, approval_id="replacement")
    mismatched = _stage(db_path, approval_id="mismatched", actor_id="other-actor")
    supersede_bound_approval(
        original.approval_id,
        superseded_by=replacement.approval_id,
        db_path=db_path,
    )
    tampered_target = (
        "missing-replacement"
        if relationship == "dangling"
        else mismatched.approval_id
    )
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE bound_approvals SET superseded_by = ? WHERE approval_id = ?",
            (tampered_target, original.approval_id),
        )

    with pytest.raises(ApprovalCorruptionError):
        if entrypoint == "list":
            list_bound_approvals(db_path=db_path)
        elif entrypoint == "decide":
            decide_bound_approval(
                original.approval_id,
                approve=True,
                decided_by="reviewer",
                db_path=db_path,
            )
        elif entrypoint == "consume":
            _consume(db_path, original.approval_id)
        else:
            supersede_bound_approval(
                original.approval_id,
                superseded_by=tampered_target,
                db_path=db_path,
            )


@pytest.mark.parametrize("failure_marker", ["journal_mode=WAL", "CREATE TABLE"])
def test_connection_closes_when_initialization_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, failure_marker: str
) -> None:
    original_connect = sqlite3.connect
    raw_connection = original_connect(tmp_path / "grants.db")

    class FailingConnection:
        closed = False

        @property
        def row_factory(self) -> object:
            return raw_connection.row_factory

        @row_factory.setter
        def row_factory(self, value: object) -> None:
            raw_connection.row_factory = value  # ty: ignore[invalid-assignment]

        def execute(self, sql: str, parameters: Any = ()) -> sqlite3.Cursor:
            if failure_marker in sql:
                raise sqlite3.OperationalError("injected initialization failure")
            return raw_connection.execute(sql, parameters)

        def commit(self) -> None:
            raw_connection.commit()

        def rollback(self) -> None:
            raw_connection.rollback()

        def close(self) -> None:
            self.closed = True
            raw_connection.close()

    failing = FailingConnection()
    monkeypatch.setattr(grants.sqlite3, "connect", lambda *args, **kwargs: failing)

    expected_error = (
        sqlite3.OperationalError
        if failure_marker == "journal_mode=WAL"
        else ApprovalCorruptionError
    )
    with pytest.raises(expected_error):
        list_bound_approvals(db_path=tmp_path / "grants.db")

    assert failing.closed


@pytest.mark.parametrize("approve", [1, 0, "yes", "", None])
def test_decision_rejects_non_bool_without_mutation(
    tmp_path: Path, approve: object
) -> None:
    db_path = tmp_path / "grants.db"
    pending = _stage(db_path)

    with pytest.raises(ValueError, match="approve"):
        decide_bound_approval(
            pending.approval_id,
            approve=approve,  # ty: ignore[invalid-argument-type]
            decided_by="reviewer",
            db_path=db_path,
        )

    assert list_bound_approvals(db_path=db_path) == (pending,)


def test_decision_uses_one_logical_clock_instant(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    db_path = tmp_path / "grants.db"
    monkeypatch.setattr(grants.time, "time", lambda: 100.0)
    pending = _stage(db_path, ttl_seconds=10)
    clock = iter((109.9, 110.1))
    monkeypatch.setattr(grants.time, "time", lambda: next(clock))

    decided = decide_bound_approval(
        pending.approval_id,
        approve=True,
        decided_by="reviewer",
        db_path=db_path,
    )

    assert decided.decided_at == 109.9
    assert next(clock) == 110.1


def test_pending_approval_cannot_be_consumed(tmp_path: Path) -> None:
    db_path = tmp_path / "grants.db"
    pending = _stage(db_path)

    with pytest.raises(ApprovalStateError):
        _consume(db_path, pending.approval_id)

    assert list_bound_approvals(db_path=db_path) == (pending,)


def test_consume_uses_one_logical_clock_instant(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    db_path = tmp_path / "grants.db"
    monkeypatch.setattr(grants.time, "time", lambda: 100.0)
    pending = _stage(db_path, ttl_seconds=10)
    monkeypatch.setattr(grants.time, "time", lambda: 105.0)
    granted = decide_bound_approval(
        pending.approval_id,
        approve=True,
        decided_by="reviewer",
        db_path=db_path,
    )
    clock = iter((109.9, 110.1))
    monkeypatch.setattr(grants.time, "time", lambda: next(clock))

    consumed = _consume(db_path, granted.approval_id)

    assert consumed.consumed_at == 109.9
    assert next(clock) == 110.1


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


def test_expiry_boundary_is_exclusive(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    db_path = tmp_path / "grants.db"
    monkeypatch.setattr(grants.time, "time", lambda: 100.0)
    pending = _stage(db_path, approval_id="pending-boundary", ttl_seconds=10)
    granted = _grant(db_path, approval_id="granted-boundary", ttl_seconds=10)
    monkeypatch.setattr(grants.time, "time", lambda: 110.0)

    with pytest.raises(ApprovalExpiredError):
        decide_bound_approval(
            pending.approval_id,
            approve=True,
            decided_by="reviewer",
            db_path=db_path,
        )
    with pytest.raises(ApprovalExpiredError):
        _consume(db_path, granted.approval_id)


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
    assert issubclass(ApprovalCorruptionError, ApprovalGrantError)
    assert issubclass(ApprovalSchemaVersionError, ApprovalCorruptionError)


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
