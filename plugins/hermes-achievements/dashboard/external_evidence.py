"""Presentation-only external evidence ledger for Hermes achievements."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from collections.abc import Mapping, Sequence
from contextlib import closing
from datetime import datetime
from pathlib import Path
from typing import Any

from hermes_constants import get_hermes_home


_AUTHORITY_KEYS = frozenset(
    {
        "achievement_id",
        "approval",
        "approvals",
        "capabilities",
        "metrics",
        "role",
        "roles",
        "scope",
        "scopes",
        "tier",
        "tool",
        "tools",
        "unlocked",
    }
)
_REQUIRED_TOP_LEVEL = frozenset(
    {
        "version",
        "kind",
        "producer",
        "mission_id",
        "source_type",
        "source_id",
        "mode",
        "evidence_references",
        "provenance",
    }
)


def external_evidence_path() -> Path:
    return (
        get_hermes_home()
        / "plugins"
        / "hermes-achievements"
        / "external_evidence.sqlite3"
    )


def record_external_evidence(envelope: Mapping[str, Any]) -> dict[str, str]:
    normalized = _validate_envelope(envelope)
    encoded = _canonical_json(normalized)
    dedupe_key = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    record_id = f"external_{dedupe_key[:24]}"
    path = external_evidence_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(_connect(path)) as connection:
        connection.execute("BEGIN IMMEDIATE")
        try:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO external_evidence (
                    record_id, dedupe_key, envelope_json, recorded_at
                ) VALUES (?, ?, ?, ?)
                """,
                (record_id, dedupe_key, encoded, time.time()),
            )
            status = "accepted" if cursor.rowcount == 1 else "duplicate"
            connection.commit()
        except Exception:
            connection.rollback()
            raise
    return {"status": status, "record_id": record_id, "dedupe_key": dedupe_key}


def list_external_evidence() -> list[dict[str, Any]]:
    path = external_evidence_path()
    if not path.is_file():
        return []
    with closing(_connect(path)) as connection:
        rows = connection.execute(
            """
            SELECT record_id, dedupe_key, envelope_json, recorded_at
            FROM external_evidence ORDER BY recorded_at, record_id
            """
        ).fetchall()
    records: list[dict[str, Any]] = []
    for row in rows:
        records.append(
            {
                **json.loads(row["envelope_json"]),
                "record_id": row["record_id"],
                "dedupe_key": row["dedupe_key"],
                "recorded_at": row["recorded_at"],
            }
        )
    return records


def _connect(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path, timeout=5.0, isolation_level=None)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA busy_timeout=5000")
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS external_evidence (
            record_id TEXT PRIMARY KEY,
            dedupe_key TEXT NOT NULL UNIQUE,
            envelope_json TEXT NOT NULL,
            recorded_at REAL NOT NULL
        )
        """
    )
    return connection


def _validate_envelope(envelope: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(envelope, Mapping):
        raise ValueError("external evidence envelope must be a mapping")
    _reject_authority_shape(envelope)
    allowed = _REQUIRED_TOP_LEVEL | {"simulation_label"}
    if set(envelope) - allowed or _REQUIRED_TOP_LEVEL - set(envelope):
        raise ValueError("external evidence envelope fields are invalid")
    if type(envelope.get("version")) is not int or envelope["version"] != 1:
        raise ValueError("external evidence version must be 1")
    if envelope.get("kind") != "mission.completed":
        raise ValueError("external evidence kind is invalid")
    if envelope.get("producer") != "muse_universe":
        raise ValueError("external evidence producer is invalid")
    for field in ("mission_id", "source_type", "source_id"):
        _required_text(envelope.get(field), field)
    mode = envelope.get("mode")
    if mode not in {"real", "simulation"}:
        raise ValueError("external evidence mode is invalid")
    if mode == "simulation" and envelope.get("simulation_label") != "simulation":
        raise ValueError("simulation evidence requires an explicit label")
    if mode == "real" and "simulation_label" in envelope:
        raise ValueError("real evidence cannot carry a simulation label")
    references = envelope.get("evidence_references")
    if (
        not isinstance(references, Sequence)
        or isinstance(references, (str, bytes, bytearray))
        or not references
        or any(not isinstance(item, str) or not item for item in references)
    ):
        raise ValueError("external evidence references are required")
    provenance = envelope.get("provenance")
    if not isinstance(provenance, Mapping) or set(provenance) != {
        "realm_id",
        "command_id",
        "occurred_at",
    }:
        raise ValueError("external evidence provenance is invalid")
    _required_text(provenance.get("realm_id"), "provenance.realm_id")
    _required_text(provenance.get("command_id"), "provenance.command_id")
    occurred_at = _required_text(
        provenance.get("occurred_at"), "provenance.occurred_at"
    )
    try:
        parsed = datetime.fromisoformat(occurred_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("external evidence occurred_at is invalid") from exc
    if parsed.tzinfo is None:
        raise ValueError("external evidence occurred_at must include a timezone")
    return json.loads(_canonical_json(dict(envelope)))


def _reject_authority_shape(value: Any) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            normalized = str(key).casefold().replace("-", "_")
            if normalized in _AUTHORITY_KEYS:
                raise ValueError("authority-shaped external evidence is forbidden")
            _reject_authority_shape(item)
    elif isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray)
    ):
        for item in value:
            _reject_authority_shape(item)


def _required_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} is required")
    return value.strip()


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
