"""Durable, tuple-bound one-time approval grants.

The facade stores only a canonical digest of the protected subject. Every
write is serialized with ``BEGIN IMMEDIATE`` so decision and consumption
transitions remain atomic across processes and threads.
"""

from __future__ import annotations

import contextlib
import enum
import hashlib
import json
import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Protocol, runtime_checkable

from hermes_constants import get_hermes_home

__all__ = [
    "ApprovalBindingMismatchError",
    "ApprovalConflictError",
    "ApprovalExpiredError",
    "ApprovalGrantError",
    "ApprovalNotFoundError",
    "ApprovalState",
    "ApprovalStateError",
    "ApprovalVerifier",
    "BoundApproval",
    "decide_bound_approval",
    "list_bound_approvals",
    "stage_bound_approval",
    "validate_and_consume_approval",
]

_PROVENANCE = "bound-approval-v1"
_BUSY_TIMEOUT_MS = 5_000
_SCHEMA = """
CREATE TABLE IF NOT EXISTS bound_approvals (
    approval_id TEXT PRIMARY KEY,
    actor_id TEXT NOT NULL,
    action TEXT NOT NULL,
    realm_id TEXT NOT NULL,
    correlation_id TEXT NOT NULL,
    subject_hash TEXT NOT NULL CHECK(length(subject_hash) = 64),
    state TEXT NOT NULL CHECK(state IN (
        'pending', 'granted', 'rejected', 'expired', 'consumed', 'superseded'
    )),
    issued_at REAL NOT NULL,
    expires_at REAL NOT NULL,
    decided_at REAL,
    decided_by TEXT,
    consumed_at REAL,
    provenance TEXT NOT NULL
)
"""


class ApprovalGrantError(RuntimeError):
    """Base error for the bound approval domain."""


class ApprovalNotFoundError(ApprovalGrantError):
    """Raised when an approval id does not exist."""


class ApprovalConflictError(ApprovalGrantError):
    """Raised when an approval id conflicts with another binding."""


class ApprovalBindingMismatchError(ApprovalGrantError):
    """Raised when presented binding data does not match the grant."""


class ApprovalStateError(ApprovalGrantError):
    """Raised when a lifecycle transition is not allowed."""


class ApprovalExpiredError(ApprovalStateError):
    """Raised when an approval has expired."""


class ApprovalState(str, enum.Enum):
    """Lifecycle states for a bound approval."""

    PENDING = "pending"
    GRANTED = "granted"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CONSUMED = "consumed"
    SUPERSEDED = "superseded"


@dataclass(frozen=True)
class BoundApproval:
    """Immutable, safely serializable bound approval record."""

    approval_id: str
    actor_id: str
    action: str
    realm_id: str
    correlation_id: str
    subject_hash: str
    state: ApprovalState
    issued_at: float
    expires_at: float
    decided_at: float | None = None
    decided_by: str | None = None
    consumed_at: float | None = None
    provenance: str = _PROVENANCE

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-safe representation containing no source subject."""

        return {
            "approval_id": self.approval_id,
            "actor_id": self.actor_id,
            "action": self.action,
            "realm_id": self.realm_id,
            "correlation_id": self.correlation_id,
            "subject_hash": self.subject_hash,
            "state": self.state.value,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "decided_at": self.decided_at,
            "decided_by": self.decided_by,
            "consumed_at": self.consumed_at,
            "provenance": self.provenance,
        }


@runtime_checkable
class ApprovalVerifier(Protocol):
    """Dependency-injection seam for one-time bound approval verification."""

    def validate_and_consume_approval(
        self,
        approval_id: str,
        actor_id: str,
        action: str,
        realm_id: str,
        correlation_id: str,
        subject: object,
        *,
        db_path: Path | str | None = None,
    ) -> BoundApproval:
        """Validate the exact binding and atomically consume its grant."""
        ...


def _database_path(db_path: Path | str | None) -> Path:
    if db_path is not None:
        return Path(db_path)
    return get_hermes_home() / "approvals" / "grants.db"


def _connect(db_path: Path | str | None) -> sqlite3.Connection:
    path = _database_path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=_BUSY_TIMEOUT_MS / 1_000)
    connection.row_factory = sqlite3.Row
    connection.execute(f"PRAGMA busy_timeout={_BUSY_TIMEOUT_MS}")
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute(_SCHEMA)
    return connection


@contextlib.contextmanager
def _write_transaction(
    db_path: Path | str | None,
) -> Iterator[sqlite3.Connection]:
    connection = _connect(db_path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        yield connection
    except BaseException:
        connection.rollback()
        raise
    else:
        connection.commit()
    finally:
        connection.close()


def _canonical_subject_hash(subject: object) -> str:
    try:
        canonical = json.dumps(
            subject,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("subject must be canonically JSON serializable") from exc
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _required_text(name: str, value: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _from_row(row: sqlite3.Row) -> BoundApproval:
    return BoundApproval(
        approval_id=row["approval_id"],
        actor_id=row["actor_id"],
        action=row["action"],
        realm_id=row["realm_id"],
        correlation_id=row["correlation_id"],
        subject_hash=row["subject_hash"],
        state=ApprovalState(row["state"]),
        issued_at=row["issued_at"],
        expires_at=row["expires_at"],
        decided_at=row["decided_at"],
        decided_by=row["decided_by"],
        consumed_at=row["consumed_at"],
        provenance=row["provenance"],
    )


def _select(connection: sqlite3.Connection, approval_id: str) -> sqlite3.Row:
    row = connection.execute(
        "SELECT * FROM bound_approvals WHERE approval_id = ?", (approval_id,)
    ).fetchone()
    if row is None:
        raise ApprovalNotFoundError(f"approval not found: {approval_id}")
    return row


def _binding(record: BoundApproval) -> tuple[str, str, str, str, str]:
    return (
        record.actor_id,
        record.action,
        record.realm_id,
        record.correlation_id,
        record.subject_hash,
    )


def _presented_binding(
    actor_id: str,
    action: str,
    realm_id: str,
    correlation_id: str,
    subject: object,
) -> tuple[str, str, str, str, str]:
    return (
        _required_text("actor_id", actor_id),
        _required_text("action", action),
        _required_text("realm_id", realm_id),
        _required_text("correlation_id", correlation_id),
        _canonical_subject_hash(subject),
    )


def _mark_expired(
    connection: sqlite3.Connection, record: BoundApproval, now: float
) -> BoundApproval:
    if record.state not in {ApprovalState.PENDING, ApprovalState.GRANTED}:
        return record
    if now < record.expires_at:
        return record
    connection.execute(
        "UPDATE bound_approvals SET state = ? WHERE approval_id = ?",
        (ApprovalState.EXPIRED.value, record.approval_id),
    )
    return _from_row(_select(connection, record.approval_id))


def stage_bound_approval(
    actor_id: str,
    action: str,
    realm_id: str,
    correlation_id: str,
    subject: object,
    *,
    ttl_seconds: float = 600,
    approval_id: str | None = None,
    db_path: Path | str | None = None,
) -> BoundApproval:
    """Stage a pending approval bound to an exact caller tuple."""

    if isinstance(ttl_seconds, bool) or ttl_seconds <= 0:
        raise ValueError("ttl_seconds must be positive")
    binding = _presented_binding(
        actor_id, action, realm_id, correlation_id, subject
    )
    supplied_id = approval_id is not None
    resolved_id = approval_id or f"approval_{uuid.uuid4().hex}"
    _required_text("approval_id", resolved_id)
    now = time.time()
    with _write_transaction(db_path) as connection:
        existing_row = connection.execute(
            "SELECT * FROM bound_approvals WHERE approval_id = ?", (resolved_id,)
        ).fetchone()
        if existing_row is not None:
            existing = _from_row(existing_row)
            if supplied_id and _binding(existing) == binding:
                return existing
            raise ApprovalConflictError(
                f"approval id is already bound: {resolved_id}"
            )
        connection.execute(
            """
            INSERT INTO bound_approvals (
                approval_id, actor_id, action, realm_id, correlation_id,
                subject_hash, state, issued_at, expires_at, provenance
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                resolved_id,
                *binding,
                ApprovalState.PENDING.value,
                now,
                now + float(ttl_seconds),
                _PROVENANCE,
            ),
        )
        return _from_row(_select(connection, resolved_id))


def decide_bound_approval(
    approval_id: str,
    *,
    approve: bool,
    decided_by: str,
    db_path: Path | str | None = None,
) -> BoundApproval:
    """Grant or reject a pending approval exactly once."""

    _required_text("approval_id", approval_id)
    _required_text("decided_by", decided_by)
    desired = ApprovalState.GRANTED if approve else ApprovalState.REJECTED
    expired: BoundApproval | None = None
    with _write_transaction(db_path) as connection:
        record = _mark_expired(
            connection, _from_row(_select(connection, approval_id)), time.time()
        )
        if record.state is ApprovalState.EXPIRED:
            expired = record
        elif record.state is desired:
            return record
        elif record.state is not ApprovalState.PENDING:
            raise ApprovalStateError(
                f"approval {approval_id} cannot be decided from {record.state.value}"
            )
        else:
            now = time.time()
            connection.execute(
                """
                UPDATE bound_approvals
                SET state = ?, decided_at = ?, decided_by = ?
                WHERE approval_id = ? AND state = ?
                """,
                (
                    desired.value,
                    now,
                    decided_by,
                    approval_id,
                    ApprovalState.PENDING.value,
                ),
            )
            return _from_row(_select(connection, approval_id))
    assert expired is not None
    raise ApprovalExpiredError(f"approval expired: {approval_id}")


def validate_and_consume_approval(
    approval_id: str,
    actor_id: str,
    action: str,
    realm_id: str,
    correlation_id: str,
    subject: object,
    *,
    db_path: Path | str | None = None,
) -> BoundApproval:
    """Validate an exact binding and atomically consume its one-time grant."""

    _required_text("approval_id", approval_id)
    presented = _presented_binding(
        actor_id, action, realm_id, correlation_id, subject
    )
    expired: BoundApproval | None = None
    with _write_transaction(db_path) as connection:
        record = _from_row(_select(connection, approval_id))
        if _binding(record) != presented:
            raise ApprovalBindingMismatchError(
                f"approval binding mismatch: {approval_id}"
            )
        record = _mark_expired(connection, record, time.time())
        if record.state is ApprovalState.EXPIRED:
            expired = record
        elif record.state is ApprovalState.CONSUMED:
            return record
        elif record.state is not ApprovalState.GRANTED:
            raise ApprovalStateError(
                f"approval {approval_id} cannot be consumed from {record.state.value}"
            )
        else:
            connection.execute(
                """
                UPDATE bound_approvals
                SET state = ?, consumed_at = ?
                WHERE approval_id = ? AND state = ?
                """,
                (
                    ApprovalState.CONSUMED.value,
                    time.time(),
                    approval_id,
                    ApprovalState.GRANTED.value,
                ),
            )
            return _from_row(_select(connection, approval_id))
    assert expired is not None
    raise ApprovalExpiredError(f"approval expired: {approval_id}")


def list_bound_approvals(
    *,
    state: ApprovalState | str | None = None,
    db_path: Path | str | None = None,
) -> tuple[BoundApproval, ...]:
    """List approvals in issue order, optionally filtered by state."""

    selected_state = ApprovalState(state) if state is not None else None
    with _write_transaction(db_path) as connection:
        now = time.time()
        connection.execute(
            """
            UPDATE bound_approvals
            SET state = ?
            WHERE state IN (?, ?) AND expires_at <= ?
            """,
            (
                ApprovalState.EXPIRED.value,
                ApprovalState.PENDING.value,
                ApprovalState.GRANTED.value,
                now,
            ),
        )
        if selected_state is None:
            rows = connection.execute(
                "SELECT * FROM bound_approvals ORDER BY issued_at, approval_id"
            ).fetchall()
        else:
            rows = connection.execute(
                """
                SELECT * FROM bound_approvals
                WHERE state = ? ORDER BY issued_at, approval_id
                """,
                (selected_state.value,),
            ).fetchall()
        return tuple(_from_row(row) for row in rows)
