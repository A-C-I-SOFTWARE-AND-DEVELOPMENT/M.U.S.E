from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator
from uuid import uuid4

from .models import CommandResult, UniverseCommand, UniverseEvent, utc_now
from .reducers import reduce_entity


class ConflictError(RuntimeError):
    def __init__(self, expected_version: int, current_version: int) -> None:
        self.expected_version = expected_version
        self.current_version = current_version
        super().__init__(
            f"expected stream version {expected_version}, current version is "
            f"{current_version}"
        )


class CommandIdConflictError(ValueError):
    def __init__(self, command_id: str) -> None:
        self.command_id = command_id
        super().__init__(f"command_id {command_id!r} was reused with different content")


class UniverseStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS events (
                    sequence INTEGER PRIMARY KEY,
                    event_id TEXT NOT NULL UNIQUE,
                    realm_id TEXT NOT NULL,
                    stream_type TEXT NOT NULL,
                    stream_id TEXT NOT NULL,
                    stream_version INTEGER NOT NULL,
                    event_json TEXT NOT NULL,
                    UNIQUE (stream_type, stream_id, stream_version)
                );

                CREATE INDEX IF NOT EXISTS events_realm_sequence
                    ON events (realm_id, sequence);

                CREATE TABLE IF NOT EXISTS entities (
                    entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    realm_id TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    entity_json TEXT NOT NULL,
                    PRIMARY KEY (entity_type, entity_id)
                );

                CREATE TABLE IF NOT EXISTS command_results (
                    command_id TEXT PRIMARY KEY,
                    command_fingerprint TEXT NOT NULL,
                    event_id TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    FOREIGN KEY (event_id) REFERENCES events(event_id)
                );
                """
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=5.0, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=5000")
        return connection

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            yield connection
        finally:
            connection.close()

    def append(self, command: UniverseCommand, event_type: str) -> CommandResult:
        fingerprint = _command_fingerprint(command, event_type)
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            stored = connection.execute(
                """
                SELECT command_fingerprint, result_json
                FROM command_results
                WHERE command_id = ?
                """,
                (command.command_id,),
            ).fetchone()
            if stored is not None:
                if stored["command_fingerprint"] != fingerprint:
                    raise CommandIdConflictError(command.command_id)
                result = CommandResult.model_validate_json(stored["result_json"])
                connection.commit()
                return result.model_copy(update={"idempotent_replay": True})

            current_row = connection.execute(
                """
                SELECT version, entity_json
                FROM entities
                WHERE entity_type = ? AND entity_id = ?
                """,
                (command.stream_type, command.stream_id),
            ).fetchone()
            current_version = 0 if current_row is None else int(current_row["version"])
            if command.expected_version != current_version:
                raise ConflictError(command.expected_version, current_version)

            current = (
                None
                if current_row is None
                else json.loads(current_row["entity_json"])
            )
            sequence = int(
                connection.execute(
                    "SELECT COALESCE(MAX(sequence), 0) + 1 FROM events"
                ).fetchone()[0]
            )
            event = UniverseEvent(
                sequence=sequence,
                event_id=str(uuid4()),
                event_type=event_type,
                realm_id=command.realm_id,
                actor_id=command.actor_id,
                stream_type=command.stream_type,
                stream_id=command.stream_id,
                stream_version=current_version + 1,
                authorization=command.authorization,
                causation_id=command.causation_id,
                correlation_id=command.correlation_id,
                occurred_at=utc_now(),
                payload=command.payload,
                provenance=command.provenance,
                simulation=command.simulation,
                rollback=current or {},
            )
            entity = reduce_entity(current, event)
            result = CommandResult(event=event, entity=entity)

            connection.execute(
                """
                INSERT INTO events (
                    sequence, event_id, realm_id, stream_type, stream_id,
                    stream_version, event_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.sequence,
                    event.event_id,
                    event.realm_id,
                    event.stream_type,
                    event.stream_id,
                    event.stream_version,
                    _canonical_json(event.model_dump(mode="json")),
                ),
            )
            connection.execute(
                """
                INSERT INTO entities (
                    entity_type, entity_id, realm_id, version, entity_json
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(entity_type, entity_id) DO UPDATE SET
                    realm_id = excluded.realm_id,
                    version = excluded.version,
                    entity_json = excluded.entity_json
                """,
                (
                    event.stream_type,
                    event.stream_id,
                    event.realm_id,
                    event.stream_version,
                    _canonical_json(entity),
                ),
            )
            connection.execute(
                """
                INSERT INTO command_results (
                    command_id, command_fingerprint, event_id, result_json
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    command.command_id,
                    fingerprint,
                    event.event_id,
                    _canonical_json(result.model_dump(mode="json")),
                ),
            )
            connection.commit()
            return result
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def entity(self, entity_type: str, entity_id: str) -> dict[str, Any] | None:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT entity_json FROM entities
                WHERE entity_type = ? AND entity_id = ?
                """,
                (entity_type, entity_id),
            ).fetchone()
        return None if row is None else json.loads(row["entity_json"])

    def events_since(self, realm_id: str, sequence: int) -> list[UniverseEvent]:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT event_json FROM events
                WHERE realm_id = ? AND sequence > ?
                ORDER BY sequence
                """,
                (realm_id, sequence),
            ).fetchall()
        return [UniverseEvent.model_validate_json(row["event_json"]) for row in rows]

    def snapshot(self, realm_id: str) -> dict[str, list[dict[str, Any]]]:
        projections: dict[tuple[str, str], dict[str, Any]] = {}
        for event in self.events_since(realm_id, 0):
            key = (event.stream_type, event.stream_id)
            projections[key] = reduce_entity(projections.get(key), event)

        snapshot: dict[str, list[dict[str, Any]]] = {}
        for (entity_type, _), entity in sorted(projections.items()):
            snapshot.setdefault(f"{entity_type}s", []).append(entity)
        return snapshot


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _command_fingerprint(command: UniverseCommand, event_type: str) -> str:
    content = {
        "command": command.model_dump(mode="json"),
        "event_type": event_type,
    }
    return hashlib.sha256(_canonical_json(content).encode("utf-8")).hexdigest()
