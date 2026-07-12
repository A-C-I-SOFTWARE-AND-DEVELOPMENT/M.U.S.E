from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Sequence
from uuid import uuid4

from .models import CommandResult, UniverseCommand, UniverseEvent, utc_now
from .reducers import reduce_entity
from .validation import validate_finite_numbers, validate_no_secret_fields


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


class AmbiguousEntityError(LookupError):
    def __init__(self, entity_type: str, entity_id: str) -> None:
        super().__init__(
            f"entity {entity_type!r}/{entity_id!r} exists in multiple realms; "
            "realm_id is required"
        )


class UniverseTransaction:
    """Authoritative projection reads and related appends in one write transaction."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def command_result(self, realm_id: str, command_id: str) -> CommandResult | None:
        row = self._connection.execute(
            "SELECT result_json FROM command_results WHERE realm_id = ? AND command_id = ?",
            (realm_id, command_id),
        ).fetchone()
        if row is None:
            return None
        result = CommandResult.model_validate_json(row["result_json"])
        _validate_result(result)
        return result

    def entity(
        self,
        entity_type: str,
        entity_id: str,
        realm_id: str | None = None,
    ) -> dict[str, Any] | None:
        if realm_id is None:
            rows = self._connection.execute(
                """
                SELECT entity_json FROM entities
                WHERE entity_type = ? AND entity_id = ? ORDER BY realm_id LIMIT 2
                """,
                (entity_type, entity_id),
            ).fetchall()
            if len(rows) > 1:
                raise AmbiguousEntityError(entity_type, entity_id)
            return None if not rows else json.loads(rows[0]["entity_json"])
        row = self._connection.execute(
            """
            SELECT entity_json FROM entities
            WHERE realm_id = ? AND entity_type = ? AND entity_id = ?
            """,
            (realm_id, entity_type, entity_id),
        ).fetchone()
        return None if row is None else json.loads(row["entity_json"])

    def entities(
        self, realm_id: str | None, entity_type: str
    ) -> list[dict[str, Any]]:
        if realm_id is None:
            rows = self._connection.execute(
                """
                SELECT entity_json FROM entities
                WHERE entity_type = ? ORDER BY realm_id, entity_id
                """,
                (entity_type,),
            ).fetchall()
        else:
            rows = self._connection.execute(
                """
                SELECT entity_json FROM entities
                WHERE realm_id = ? AND entity_type = ? ORDER BY entity_id
                """,
                (realm_id, entity_type),
            ).fetchall()
        return [json.loads(row["entity_json"]) for row in rows]

    def snapshot(self, realm_id: str) -> dict[str, list[dict[str, Any]]]:
        rows = self._connection.execute(
            """
            SELECT entity_type, entity_json FROM entities
            WHERE realm_id = ? ORDER BY entity_type, entity_id
            """,
            (realm_id,),
        ).fetchall()
        snapshot: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            snapshot.setdefault(f"{row['entity_type']}s", []).append(
                json.loads(row["entity_json"])
            )
        return snapshot

    def append(self, command: UniverseCommand, event_type: str) -> CommandResult:
        return _append_in_transaction(self._connection, command, event_type)

    def assert_stream_version(
        self,
        realm_id: str,
        stream_type: str,
        stream_id: str,
        expected_version: int,
    ) -> None:
        row = self._connection.execute(
            """
            SELECT version FROM entities
            WHERE realm_id = ? AND entity_type = ? AND entity_id = ?
            """,
            (realm_id, stream_type, stream_id),
        ).fetchone()
        current_version = 0 if row is None else int(row["version"])
        if expected_version != current_version:
            raise ConflictError(expected_version, current_version)

    def append_related(
        self, items: Sequence[tuple[UniverseCommand, str]]
    ) -> tuple[CommandResult, ...]:
        return tuple(self.append(command, event_type) for command, event_type in items)


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
                    UNIQUE (realm_id, stream_type, stream_id, stream_version)
                );

                CREATE INDEX IF NOT EXISTS events_realm_sequence
                    ON events (realm_id, sequence);

                CREATE INDEX IF NOT EXISTS events_realm_stream_sequence
                    ON events (realm_id, stream_type, stream_id, sequence);

                CREATE TABLE IF NOT EXISTS entities (
                    entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    realm_id TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    entity_json TEXT NOT NULL,
                    PRIMARY KEY (realm_id, entity_type, entity_id)
                );

                CREATE TABLE IF NOT EXISTS command_results (
                    realm_id TEXT NOT NULL,
                    command_id TEXT NOT NULL,
                    command_fingerprint TEXT NOT NULL,
                    event_id TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    PRIMARY KEY (realm_id, command_id),
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
        with self.transaction() as transaction:
            return transaction.append(command, event_type)

    @contextmanager
    def transaction(self) -> Iterator[UniverseTransaction]:
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield UniverseTransaction(connection)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def command_result(self, realm_id: str, command_id: str) -> CommandResult | None:
        with self._connection() as connection:
            return UniverseTransaction(connection).command_result(realm_id, command_id)

    def entities(
        self, realm_id: str | None, entity_type: str
    ) -> list[dict[str, Any]]:
        with self._connection() as connection:
            return UniverseTransaction(connection).entities(realm_id, entity_type)

    def entity(
        self,
        entity_type: str,
        entity_id: str,
        realm_id: str | None = None,
    ) -> dict[str, Any] | None:
        with self._connection() as connection:
            if realm_id is not None:
                row = connection.execute(
                    """
                    SELECT entity_json FROM entities
                    WHERE realm_id = ? AND entity_type = ? AND entity_id = ?
                    """,
                    (realm_id, entity_type, entity_id),
                ).fetchone()
                return None if row is None else json.loads(row["entity_json"])

            rows = connection.execute(
                """
                SELECT entity_json FROM entities
                WHERE entity_type = ? AND entity_id = ?
                ORDER BY realm_id
                LIMIT 2
                """,
                (entity_type, entity_id),
            ).fetchall()
        if len(rows) > 1:
            raise AmbiguousEntityError(entity_type, entity_id)
        return None if not rows else json.loads(rows[0]["entity_json"])

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


def _append_in_transaction(
    connection: sqlite3.Connection,
    command: UniverseCommand,
    event_type: str,
) -> CommandResult:
    _validate_command(command)
    fingerprint = _command_fingerprint(command, event_type)
    stored = connection.execute(
        """
        SELECT command_fingerprint, result_json
        FROM command_results
        WHERE realm_id = ? AND command_id = ?
        """,
        (command.realm_id, command.command_id),
    ).fetchone()
    if stored is not None:
        if stored["command_fingerprint"] != fingerprint:
            raise CommandIdConflictError(command.command_id)
        result = CommandResult.model_validate_json(stored["result_json"])
        _validate_result(result)
        return result.model_copy(update={"idempotent_replay": True})

    current_row = connection.execute(
        """
        SELECT version, entity_json
        FROM entities
        WHERE realm_id = ? AND entity_type = ? AND entity_id = ?
        """,
        (command.realm_id, command.stream_type, command.stream_id),
    ).fetchone()
    current_version = 0 if current_row is None else int(current_row["version"])
    if command.expected_version != current_version:
        raise ConflictError(command.expected_version, current_version)

    current = None if current_row is None else json.loads(current_row["entity_json"])
    validate_no_secret_fields(current or {}, path="rollback")
    sequence = int(
        connection.execute("SELECT COALESCE(MAX(sequence), 0) + 1 FROM events").fetchone()[0]
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
    validate_no_secret_fields(entity, path="entity")
    result = CommandResult(event=event, entity=entity)
    _validate_result(result)

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
        ON CONFLICT(realm_id, entity_type, entity_id) DO UPDATE SET
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
            realm_id, command_id, command_fingerprint, event_id, result_json
        ) VALUES (?, ?, ?, ?, ?)
        """,
        (
            command.realm_id,
            command.command_id,
            fingerprint,
            event.event_id,
            _canonical_json(result.model_dump(mode="json")),
        ),
    )
    return result


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        allow_nan=False,
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


def _validate_command(command: UniverseCommand) -> None:
    validate_finite_numbers(command.model_dump(mode="python"), path="command")
    validate_no_secret_fields(command.payload, path="payload")
    validate_no_secret_fields(
        command.authorization.model_dump(mode="json"), path="authorization"
    )
    validate_no_secret_fields(
        command.provenance.model_dump(mode="json"), path="provenance"
    )


def _validate_result(result: CommandResult) -> None:
    validate_finite_numbers(result.model_dump(mode="python"), path="result")
    validate_no_secret_fields(result.event.payload, path="event.payload")
    validate_no_secret_fields(
        result.event.authorization.model_dump(mode="json"),
        path="event.authorization",
    )
    validate_no_secret_fields(
        result.event.provenance.model_dump(mode="json"),
        path="event.provenance",
    )
    validate_no_secret_fields(result.event.rollback, path="event.rollback")
    validate_no_secret_fields(result.entity, path="result.entity")
