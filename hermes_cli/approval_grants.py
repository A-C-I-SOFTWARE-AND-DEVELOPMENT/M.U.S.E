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
import math
import numbers
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
    "ApprovalCorruptionError",
    "ApprovalExpiredError",
    "ApprovalGrantError",
    "ApprovalNotFoundError",
    "ApprovalSchemaVersionError",
    "ApprovalState",
    "ApprovalStateError",
    "ApprovalVerifier",
    "BoundApproval",
    "decide_bound_approval",
    "list_bound_approvals",
    "stage_bound_approval",
    "supersede_bound_approval",
    "validate_and_consume_approval",
]

_PROVENANCE = "bound-approval-v1"
_SCHEMA_VERSION = 1
_BUSY_TIMEOUT_MS = 5_000
_MAX_SUPERSESSION_HOPS = 10_000
_LEGACY_V0_COLUMNS = (
    "approval_id",
    "actor_id",
    "action",
    "realm_id",
    "correlation_id",
    "subject_hash",
    "state",
    "issued_at",
    "expires_at",
    "decided_at",
    "decided_by",
    "consumed_at",
    "provenance",
)
_SCHEMA_V1 = """
CREATE TABLE IF NOT EXISTS bound_approvals (
    approval_id TEXT PRIMARY KEY CHECK(length(approval_id) > 0),
    actor_id TEXT NOT NULL CHECK(length(actor_id) > 0),
    action TEXT NOT NULL CHECK(length(action) > 0),
    realm_id TEXT NOT NULL CHECK(length(realm_id) > 0),
    correlation_id TEXT NOT NULL CHECK(length(correlation_id) > 0),
    subject_hash TEXT NOT NULL CHECK(
        length(subject_hash) = 64
        AND subject_hash NOT GLOB '*[^0-9a-f]*'
    ),
    state TEXT NOT NULL CHECK(state IN (
        'pending', 'granted', 'rejected', 'expired', 'consumed', 'superseded'
    )),
    issued_at REAL NOT NULL,
    expires_at REAL NOT NULL CHECK(expires_at > issued_at),
    decided_at REAL,
    decided_by TEXT CHECK(decided_by IS NULL OR length(decided_by) > 0),
    consumed_at REAL,
    provenance TEXT NOT NULL CHECK(provenance = 'bound-approval-v1'),
    superseded_by TEXT,
    CHECK(decided_at IS NULL OR (
        decided_at >= issued_at AND decided_at < expires_at
    )),
    CHECK(
        (state = 'pending' AND decided_at IS NULL AND decided_by IS NULL
            AND consumed_at IS NULL AND superseded_by IS NULL)
        OR (state IN ('granted', 'rejected') AND decided_at IS NOT NULL
            AND decided_by IS NOT NULL AND consumed_at IS NULL
            AND superseded_by IS NULL)
        OR (state = 'expired' AND consumed_at IS NULL
            AND superseded_by IS NULL
            AND ((decided_at IS NULL AND decided_by IS NULL)
                OR (decided_at IS NOT NULL AND decided_by IS NOT NULL)))
        OR (state = 'consumed' AND decided_at IS NOT NULL
            AND decided_by IS NOT NULL AND consumed_at IS NOT NULL
            AND consumed_at >= decided_at AND consumed_at < expires_at
            AND superseded_by IS NULL)
        OR (state = 'superseded' AND decided_at IS NULL
            AND decided_by IS NULL AND consumed_at IS NULL
            AND length(superseded_by) > 0 AND superseded_by != approval_id)
    )
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


class ApprovalCorruptionError(ApprovalGrantError):
    """Raised when persisted approval data violates trusted invariants."""


class ApprovalSchemaVersionError(ApprovalCorruptionError):
    """Raised when a database schema version is unsupported."""


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
    superseded_by: str | None = None

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
            "superseded_by": self.superseded_by,
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
    try:
        connection.row_factory = sqlite3.Row
        connection.execute(f"PRAGMA busy_timeout={_BUSY_TIMEOUT_MS}")
        _enable_wal(connection)
        _initialize_schema(connection)
        return connection
    except BaseException:
        connection.close()
        raise


def _enable_wal(connection: sqlite3.Connection) -> None:
    deadline = time.monotonic() + (_BUSY_TIMEOUT_MS / 1_000)
    while True:
        try:
            connection.execute("PRAGMA journal_mode=WAL")
            return
        except sqlite3.OperationalError as exc:
            if "locked" not in str(exc).lower() or time.monotonic() >= deadline:
                raise
            time.sleep(0.01)


def _initialize_schema(connection: sqlite3.Connection) -> None:
    try:
        connection.execute("BEGIN IMMEDIATE")
        version = int(connection.execute("PRAGMA user_version").fetchone()[0])
        if version > _SCHEMA_VERSION:
            raise ApprovalSchemaVersionError(
                f"unsupported approval schema version: {version}"
            )
        if version == 0:
            exists = connection.execute(
                """
                SELECT 1 FROM sqlite_master
                WHERE type = 'table' AND name = 'bound_approvals'
                """
            ).fetchone()
            if exists is not None:
                columns = tuple(
                    row[1]
                    for row in connection.execute(
                        "PRAGMA table_info(bound_approvals)"
                    )
                )
                if columns != _LEGACY_V0_COLUMNS:
                    raise ApprovalCorruptionError(
                        "legacy approval schema has an invalid layout"
                    )
                connection.execute(
                    "ALTER TABLE bound_approvals RENAME TO bound_approvals_v0"
                )
            connection.execute(_SCHEMA_V1)
            if exists is not None:
                connection.execute(
                    """
                    INSERT INTO bound_approvals (
                        approval_id, actor_id, action, realm_id, correlation_id,
                        subject_hash, state, issued_at, expires_at, decided_at,
                        decided_by, consumed_at, provenance, superseded_by
                    )
                    SELECT approval_id, actor_id, action, realm_id, correlation_id,
                        subject_hash, state, issued_at, expires_at, decided_at,
                        decided_by, consumed_at, provenance, NULL
                    FROM bound_approvals_v0
                    """
                )
                connection.execute("DROP TABLE bound_approvals_v0")
            connection.execute(f"PRAGMA user_version={_SCHEMA_VERSION}")
        _validate_current_schema(connection)
        connection.commit()
    except ApprovalGrantError:
        connection.rollback()
        raise
    except sqlite3.DatabaseError as exc:
        connection.rollback()
        raise ApprovalCorruptionError(
            "approval schema initialization failed"
        ) from exc
    except BaseException:
        connection.rollback()
        raise


def _normalize_schema_sql(sql: str) -> str:
    normalized = "".join(sql.lower().split())
    return normalized.replace("ifnotexists", "")


def _validate_current_schema(connection: sqlite3.Connection) -> None:
    row = connection.execute(
        """
        SELECT sql FROM sqlite_master
        WHERE type = 'table' AND name = 'bound_approvals'
        """
    ).fetchone()
    if row is None or not isinstance(row[0], str):
        raise ApprovalCorruptionError("approval schema table is missing")
    if _normalize_schema_sql(row[0]) != _normalize_schema_sql(_SCHEMA_V1):
        raise ApprovalCorruptionError("approval schema structure is invalid")


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
    _validate_subject(subject)
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


def _validate_subject(value: object) -> None:
    """Require an unambiguous recursive JSON value domain."""

    if value is None or type(value) in {bool, int, str}:
        return
    if type(value) is float:
        if math.isfinite(value):
            return
        raise ValueError("subject numbers must be finite")
    if type(value) is list:
        for item in value:
            _validate_subject(item)
        return
    if type(value) is dict:
        for key, item in value.items():
            if type(key) is not str:
                raise ValueError("subject mappings must use string keys")
            _validate_subject(item)
        return
    raise ValueError("subject contains an unsupported value type")


def _positive_finite_ttl(ttl_seconds: object) -> float:
    if isinstance(ttl_seconds, bool) or not isinstance(ttl_seconds, numbers.Real):
        raise ValueError("ttl_seconds must be a real finite positive number")
    try:
        value = float(ttl_seconds)
    except (OverflowError, TypeError, ValueError) as exc:
        raise ValueError("ttl_seconds must be a real finite positive number") from exc
    if not math.isfinite(value) or value <= 0:
        raise ValueError("ttl_seconds must be a real finite positive number")
    return value


def _required_text(name: str, value: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _from_row(row: sqlite3.Row) -> BoundApproval:
    try:
        state = ApprovalState(row["state"])
        record = BoundApproval(
            approval_id=row["approval_id"],
            actor_id=row["actor_id"],
            action=row["action"],
            realm_id=row["realm_id"],
            correlation_id=row["correlation_id"],
            subject_hash=row["subject_hash"],
            state=state,
            issued_at=row["issued_at"],
            expires_at=row["expires_at"],
            decided_at=row["decided_at"],
            decided_by=row["decided_by"],
            consumed_at=row["consumed_at"],
            provenance=row["provenance"],
            superseded_by=row["superseded_by"],
        )
    except (IndexError, KeyError, TypeError, ValueError) as exc:
        raise ApprovalCorruptionError("invalid persisted approval record") from exc
    _validate_record(record)
    return record


def _finite_timestamp(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, numbers.Real):
        raise ApprovalCorruptionError(f"invalid {name}")
    converted = float(value)
    if not math.isfinite(converted):
        raise ApprovalCorruptionError(f"invalid {name}")
    return converted


def _validate_record(record: BoundApproval) -> None:
    for name in (
        "approval_id",
        "actor_id",
        "action",
        "realm_id",
        "correlation_id",
    ):
        value = getattr(record, name)
        if not isinstance(value, str) or not value:
            raise ApprovalCorruptionError(f"invalid persisted {name}")
    if (
        not isinstance(record.subject_hash, str)
        or len(record.subject_hash) != 64
        or any(char not in "0123456789abcdef" for char in record.subject_hash)
    ):
        raise ApprovalCorruptionError("invalid persisted subject_hash")
    if record.provenance != _PROVENANCE:
        raise ApprovalCorruptionError("unknown approval provenance")

    issued_at = _finite_timestamp("issued_at", record.issued_at)
    expires_at = _finite_timestamp("expires_at", record.expires_at)
    if expires_at <= issued_at:
        raise ApprovalCorruptionError("approval expiry must follow issuance")
    decided_at = (
        None
        if record.decided_at is None
        else _finite_timestamp("decided_at", record.decided_at)
    )
    consumed_at = (
        None
        if record.consumed_at is None
        else _finite_timestamp("consumed_at", record.consumed_at)
    )
    if decided_at is not None and not issued_at <= decided_at < expires_at:
        raise ApprovalCorruptionError("decision timestamp is out of order")
    decision_pair = (
        decided_at is not None
        and isinstance(record.decided_by, str)
        and bool(record.decided_by)
    )
    decision_absent = decided_at is None and record.decided_by is None

    if record.state is ApprovalState.PENDING:
        valid = decision_absent and consumed_at is None and record.superseded_by is None
    elif record.state in {ApprovalState.GRANTED, ApprovalState.REJECTED}:
        valid = decision_pair and consumed_at is None and record.superseded_by is None
    elif record.state is ApprovalState.EXPIRED:
        valid = (
            (decision_pair or decision_absent)
            and consumed_at is None
            and record.superseded_by is None
        )
    elif record.state is ApprovalState.CONSUMED:
        valid = (
            decision_pair
            and consumed_at is not None
            and decided_at is not None
            and decided_at <= consumed_at < expires_at
            and record.superseded_by is None
        )
    else:
        valid = (
            decision_absent
            and consumed_at is None
            and isinstance(record.superseded_by, str)
            and bool(record.superseded_by)
            and record.superseded_by != record.approval_id
        )
    if not valid:
        raise ApprovalCorruptionError("persisted lifecycle metadata is inconsistent")


def _select(connection: sqlite3.Connection, approval_id: str) -> sqlite3.Row:
    row = connection.execute(
        "SELECT * FROM bound_approvals WHERE approval_id = ?", (approval_id,)
    ).fetchone()
    if row is None:
        raise ApprovalNotFoundError(f"approval not found: {approval_id}")
    return row


def _load_record(
    connection: sqlite3.Connection,
    approval_id: str,
) -> BoundApproval:
    record = _from_row(_select(connection, approval_id))
    _validate_supersession_chain(connection, record)
    return record


def _validate_supersession_chain(
    connection: sqlite3.Connection,
    record: BoundApproval,
) -> None:
    seen = {record.approval_id}
    current = record
    hops = 0
    while current.state is ApprovalState.SUPERSEDED:
        if hops >= _MAX_SUPERSESSION_HOPS:
            raise ApprovalCorruptionError("supersession chain exceeds hop limit")
        replacement_id = current.superseded_by
        assert replacement_id is not None
        if replacement_id in seen:
            raise ApprovalCorruptionError("supersession relationship contains a cycle")
        row = connection.execute(
            "SELECT * FROM bound_approvals WHERE approval_id = ?", (replacement_id,)
        ).fetchone()
        if row is None:
            raise ApprovalCorruptionError("supersession replacement is missing")
        replacement = _from_row(row)
        if _binding(current) != _binding(replacement):
            raise ApprovalCorruptionError(
                "supersession replacement binding is invalid"
            )
        seen.add(replacement_id)
        current = replacement
        hops += 1


def _validate_supersession_graph(records: dict[str, BoundApproval]) -> None:
    edge_depths: dict[str, int] = {}
    for start_id in records:
        if start_id in edge_depths:
            continue
        path: list[str] = []
        path_positions: dict[str, int] = {}
        current_id = start_id
        while current_id not in edge_depths:
            if current_id in path_positions:
                raise ApprovalCorruptionError(
                    "supersession relationship contains a cycle"
                )
            current = records[current_id]
            if current.state is not ApprovalState.SUPERSEDED:
                edge_depths[current_id] = 0
                break
            path_positions[current_id] = len(path)
            path.append(current_id)
            replacement_id = current.superseded_by
            assert replacement_id is not None
            replacement = records.get(replacement_id)
            if replacement is None:
                raise ApprovalCorruptionError("supersession replacement is missing")
            if _binding(current) != _binding(replacement):
                raise ApprovalCorruptionError(
                    "supersession replacement binding is invalid"
                )
            current_id = replacement_id
        depth = edge_depths[current_id]
        for path_id in reversed(path):
            depth += 1
            if depth > _MAX_SUPERSESSION_HOPS:
                raise ApprovalCorruptionError("supersession chain exceeds hop limit")
            edge_depths[path_id] = depth


def _load_validated_graph(
    connection: sqlite3.Connection,
) -> tuple[BoundApproval, ...]:
    rows = connection.execute(
        "SELECT * FROM bound_approvals ORDER BY issued_at, approval_id"
    ).fetchall()
    records = tuple(_from_row(row) for row in rows)
    _validate_supersession_graph(
        {record.approval_id: record for record in records}
    )
    return records


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
    return _load_record(connection, record.approval_id)


def _validated_expiry(issued_at: float, ttl: float) -> float:
    expires_at = issued_at + ttl
    if not math.isfinite(expires_at) or expires_at <= issued_at:
        raise ValueError("ttl_seconds is below clock resolution")
    return expires_at


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

    ttl = _positive_finite_ttl(ttl_seconds)
    binding = _presented_binding(
        actor_id, action, realm_id, correlation_id, subject
    )
    supplied_id = approval_id is not None
    resolved_id = approval_id or f"approval_{uuid.uuid4().hex}"
    _required_text("approval_id", resolved_id)
    _validated_expiry(time.time(), ttl)
    with _write_transaction(db_path) as connection:
        existing_row = connection.execute(
            "SELECT * FROM bound_approvals WHERE approval_id = ?", (resolved_id,)
        ).fetchone()
        if existing_row is not None:
            existing = _load_record(connection, resolved_id)
            if supplied_id and _binding(existing) == binding:
                return existing
            raise ApprovalConflictError(
                f"approval id is already bound: {resolved_id}"
            )
        now = time.time()
        expires_at = _validated_expiry(now, ttl)
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
                expires_at,
                _PROVENANCE,
            ),
        )
        return _load_record(connection, resolved_id)


def decide_bound_approval(
    approval_id: str,
    *,
    approve: bool,
    decided_by: str,
    db_path: Path | str | None = None,
) -> BoundApproval:
    """Grant or reject a pending approval exactly once."""

    if type(approve) is not bool:
        raise ValueError("approve must be a bool")
    _required_text("approval_id", approval_id)
    _required_text("decided_by", decided_by)
    desired = ApprovalState.GRANTED if approve else ApprovalState.REJECTED
    expired: BoundApproval | None = None
    with _write_transaction(db_path) as connection:
        now = time.time()
        record = _mark_expired(connection, _load_record(connection, approval_id), now)
        if record.state is ApprovalState.EXPIRED:
            expired = record
        elif record.state is desired:
            if record.decided_by != decided_by:
                raise ApprovalStateError(
                    f"approval {approval_id} was decided by another identity"
                )
            return record
        elif record.state is not ApprovalState.PENDING:
            raise ApprovalStateError(
                f"approval {approval_id} cannot be decided from {record.state.value}"
            )
        else:
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
            return _load_record(connection, approval_id)
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
        now = time.time()
        record = _load_record(connection, approval_id)
        if _binding(record) != presented:
            raise ApprovalBindingMismatchError(
                f"approval binding mismatch: {approval_id}"
            )
        record = _mark_expired(connection, record, now)
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
                    now,
                    approval_id,
                    ApprovalState.GRANTED.value,
                ),
            )
            return _load_record(connection, approval_id)
    assert expired is not None
    raise ApprovalExpiredError(f"approval expired: {approval_id}")


def supersede_bound_approval(
    approval_id: str,
    *,
    superseded_by: str,
    db_path: Path | str | None = None,
) -> BoundApproval:
    """Atomically supersede a pending approval with another bound request."""

    _required_text("approval_id", approval_id)
    _required_text("superseded_by", superseded_by)
    if approval_id == superseded_by:
        raise ValueError("an approval cannot supersede itself")

    expired_id: str | None = None
    with _write_transaction(db_path) as connection:
        now = time.time()
        original = _mark_expired(
            connection, _load_record(connection, approval_id), now
        )
        if original.state is ApprovalState.EXPIRED:
            expired_id = approval_id
        elif original.state is ApprovalState.SUPERSEDED:
            if original.superseded_by != superseded_by:
                raise ApprovalStateError(
                    f"approval {approval_id} was superseded by another request"
                )
            return original
        elif original.state is not ApprovalState.PENDING:
            raise ApprovalStateError(
                f"approval {approval_id} cannot be superseded from "
                f"{original.state.value}"
            )
        else:
            replacement = _mark_expired(
                connection,
                _load_record(connection, superseded_by),
                now,
            )
            if replacement.state is ApprovalState.EXPIRED:
                expired_id = superseded_by
            elif replacement.state is not ApprovalState.PENDING:
                raise ApprovalStateError(
                    f"replacement {superseded_by} is not pending"
                )
            elif _binding(original) != _binding(replacement):
                raise ApprovalBindingMismatchError(
                    "replacement approval has a different binding"
                )
            else:
                connection.execute(
                    """
                    UPDATE bound_approvals
                    SET state = ?, superseded_by = ?
                    WHERE approval_id = ? AND state = ?
                    """,
                    (
                        ApprovalState.SUPERSEDED.value,
                        superseded_by,
                        approval_id,
                        ApprovalState.PENDING.value,
                    ),
                )
                records = _load_validated_graph(connection)
                return next(
                    record
                    for record in records
                    if record.approval_id == approval_id
                )
    assert expired_id is not None
    raise ApprovalExpiredError(f"approval expired: {expired_id}")


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
        records = _load_validated_graph(connection)
        if selected_state is None:
            return records
        return tuple(record for record in records if record.state is selected_state)
