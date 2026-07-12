from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
from threading import Barrier
from typing import Any, cast

import pytest
from pydantic import ValidationError

import plugins.muse_universe.store as store_module
from plugins.muse_universe.models import CommandResult, UniverseCommand
from plugins.muse_universe.store import (
    CommandIdConflictError,
    ConflictError,
    UniverseStore,
)


def entity(
    store: UniverseStore,
    entity_type: str,
    entity_id: str,
    realm_id: str | None = None,
) -> dict[str, Any]:
    projection = store.entity(entity_type, entity_id, realm_id=realm_id)
    assert projection is not None
    return projection


def test_append_projects_and_replays(
    tmp_path, command_factory: Callable[..., UniverseCommand]
) -> None:
    store = UniverseStore(tmp_path / "universe.db")

    first = store.append(command_factory(), "realm.created")

    assert first.stream_version == 1
    assert entity(store, "realm", "rlm_local")["name"] == "Local Realm"
    replayed = UniverseStore(tmp_path / "universe.db")
    assert replayed.snapshot("rlm_local")["realms"][0]["version"] == 1


def test_duplicate_command_is_idempotent(
    tmp_path, command_factory: Callable[..., UniverseCommand]
) -> None:
    store = UniverseStore(tmp_path / "universe.db")

    first = store.append(command_factory(), "realm.created")
    replay = store.append(command_factory(), "realm.created")

    assert first.event_id == replay.event_id
    assert first.idempotent_replay is False
    assert replay.idempotent_replay is True
    assert len(store.events_since("rlm_local", 0)) == 1


def test_streams_entities_and_command_ids_are_realm_scoped(
    tmp_path, command_factory: Callable[..., UniverseCommand]
) -> None:
    store = UniverseStore(tmp_path / "universe.db")

    local = store.append(command_factory(), "realm.created")
    other = store.append(
        command_factory(
            realm_id="rlm_other",
            payload={"name": "Other Realm", "mode": "local"},
        ),
        "realm.created",
    )

    assert local.stream_version == other.stream_version == 1
    assert len(store.events_since("rlm_local", 0)) == 1
    assert len(store.events_since("rlm_other", 0)) == 1
    assert entity(store, "realm", "rlm_local", "rlm_local")["name"] == "Local Realm"
    assert entity(store, "realm", "rlm_local", "rlm_other")["name"] == "Other Realm"
    with pytest.raises(LookupError):
        store.entity("realm", "rlm_local")


def test_reused_command_id_with_different_content_is_rejected(
    tmp_path, command_factory: Callable[..., UniverseCommand]
) -> None:
    store = UniverseStore(tmp_path / "universe.db")
    store.append(command_factory(), "realm.created")

    with pytest.raises(CommandIdConflictError):
        store.append(
            command_factory(payload={"name": "Changed", "mode": "local"}),
            "realm.created",
        )

    assert len(store.events_since("rlm_local", 0)) == 1
    assert entity(store, "realm", "rlm_local")["name"] == "Local Realm"


def test_stale_version_conflicts_without_partial_write(
    tmp_path, command_factory: Callable[..., UniverseCommand]
) -> None:
    store = UniverseStore(tmp_path / "universe.db")
    store.append(command_factory(), "realm.created")

    with pytest.raises(ConflictError) as exc:
        store.append(
            command_factory(command_id="cmd_2", expected_version=0),
            "realm.updated",
        )

    assert exc.value.current_version == 1
    assert len(store.events_since("rlm_local", 0)) == 1
    assert entity(store, "realm", "rlm_local")["version"] == 1


def test_transaction_appends_related_events_atomically(
    tmp_path, command_factory: Callable[..., UniverseCommand]
) -> None:
    store = UniverseStore(tmp_path / "universe.db")
    realm = command_factory()
    player = command_factory(
        command_id="cmd_player",
        command_type="player.create",
        stream_type="player",
        stream_id="ply_1",
        payload={"id": "ply_1", "display_name": "Player"},
    )

    with store.transaction() as transaction:
        results = transaction.append_related(
            ((realm, "realm.created"), (player, "player.created"))
        )

    assert [result.event.stream_type for result in results] == ["realm", "player"]
    assert store.entity("realm", "rlm_local", "rlm_local") is not None
    assert store.entity("player", "ply_1", "rlm_local") is not None


def test_related_append_rolls_back_every_projection_on_conflict(
    tmp_path, command_factory: Callable[..., UniverseCommand]
) -> None:
    store = UniverseStore(tmp_path / "universe.db")
    store.append(command_factory(), "realm.created")
    player = command_factory(
        command_id="cmd_player",
        command_type="player.create",
        stream_type="player",
        stream_id="ply_1",
        payload={"id": "ply_1", "display_name": "Player"},
    )
    stale_realm = command_factory(
        command_id="cmd_stale",
        expected_version=0,
        payload={"name": "Changed", "mode": "local"},
    )

    with pytest.raises(ConflictError):
        with store.transaction() as transaction:
            transaction.append_related(
                ((player, "player.created"), (stale_realm, "realm.updated"))
            )

    assert store.entity("player", "ply_1", "rlm_local") is None
    assert entity(store, "realm", "rlm_local", "rlm_local")["version"] == 1


def test_public_projection_and_command_result_reads_need_no_private_connection(
    tmp_path, command_factory: Callable[..., UniverseCommand]
) -> None:
    store = UniverseStore(tmp_path / "universe.db")
    created = store.append(command_factory(), "realm.created")

    assert store.command_result("rlm_local", "cmd_1") == created
    assert store.entities("rlm_local", "realm") == [
        entity(store, "realm", "rlm_local", "rlm_local")
    ]


def test_delete_retains_tombstone_and_event_history(
    tmp_path, command_factory: Callable[..., UniverseCommand]
) -> None:
    store = UniverseStore(tmp_path / "universe.db")
    store.append(command_factory(), "realm.created")

    deleted = store.append(
        command_factory(
            command_id="cmd_2",
            command_type="realm.delete",
            expected_version=1,
            payload={},
        ),
        "realm.deleted",
    )

    assert deleted.entity["deleted"] is True
    assert entity(store, "realm", "rlm_local")["deleted"] is True
    assert len(store.events_since("rlm_local", 0)) == 2


def test_payload_cannot_override_canonical_projection_metadata(
    tmp_path, command_factory: Callable[..., UniverseCommand]
) -> None:
    store = UniverseStore(tmp_path / "universe.db")

    result = store.append(
        command_factory(
            payload={
                "id": "forged-id",
                "entity_type": "forged-type",
                "realm_id": "forged-realm",
                "version": 999,
                "updated_at": "forged-time",
                "simulation": True,
            }
        ),
        "realm.created",
    )

    assert result.entity["id"] == result.event.stream_id
    assert result.entity["entity_type"] == result.event.stream_type
    assert result.entity["realm_id"] == result.event.realm_id
    assert result.entity["version"] == result.event.stream_version
    assert result.entity["updated_at"] == result.event.occurred_at
    assert result.entity["simulation"] == result.event.simulation


def test_same_store_serializes_two_thread_version_race(
    tmp_path, command_factory: Callable[..., UniverseCommand]
) -> None:
    store = UniverseStore(tmp_path / "universe.db")
    barrier = Barrier(2)

    def append(command_id: str):
        barrier.wait()
        try:
            return store.append(
                command_factory(command_id=command_id),
                "realm.created",
            )
        except ConflictError as exc:
            return exc

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(append, ("cmd_a", "cmd_b")))

    assert sum(isinstance(value, CommandResult) for value in outcomes) == 1
    conflicts = [value for value in outcomes if isinstance(value, ConflictError)]
    assert len(conflicts) == 1
    assert conflicts[0].current_version == 1
    assert len(store.events_since("rlm_local", 0)) == 1
    assert entity(store, "realm", "rlm_local")["version"] == 1


def test_unexpected_result_serialization_error_rolls_back_all_tables(
    tmp_path,
    command_factory: Callable[..., UniverseCommand],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database = tmp_path / "universe.db"
    store = UniverseStore(database)
    canonical_json = store_module._canonical_json

    def fail_on_result(value: Any) -> str:
        if isinstance(value, dict) and set(value) == {
            "entity",
            "event",
            "idempotent_replay",
        }:
            raise RuntimeError("forced result serialization failure")
        return canonical_json(value)

    monkeypatch.setattr(store_module, "_canonical_json", fail_on_result)

    with pytest.raises(RuntimeError, match="forced result serialization failure"):
        store.append(command_factory(), "realm.created")

    with sqlite3.connect(database) as connection:
        counts = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("events", "entities", "command_results")
        }
    assert counts == {"events": 0, "entities": 0, "command_results": 0}


def test_command_result_is_frozen(
    tmp_path, command_factory: Callable[..., UniverseCommand]
) -> None:
    result = UniverseStore(tmp_path / "universe.db").append(
        command_factory(), "realm.created"
    )

    with pytest.raises(ValidationError):
        result.idempotent_replay = True


def test_contracts_are_deeply_immutable(
    tmp_path, command_factory: Callable[..., UniverseCommand]
) -> None:
    store = UniverseStore(tmp_path / "universe.db")
    command = command_factory(
        payload={"nested": {"items": [{"name": "original"}]}},
        provenance={
            "source": "owner",
            "evidence": ["evidence-1"],
            "confidence": 1.0,
        },
    )
    created = store.append(command, "realm.created")
    updated = store.append(
        command_factory(
            command_id="cmd_2",
            expected_version=1,
            payload={"status": "updated"},
        ),
        "realm.updated",
    )

    with pytest.raises(TypeError):
        command.payload["nested"]["items"][0]["name"] = "changed"
    with pytest.raises(TypeError):
        created.event.payload["nested"]["items"][0]["name"] = "changed"
    with pytest.raises(TypeError):
        updated.event.rollback["nested"]["items"][0]["name"] = "changed"
    with pytest.raises(TypeError):
        created.entity["nested"]["items"][0]["name"] = "changed"
    with pytest.raises(TypeError):
        cast(Any, command.provenance.evidence)[0] = "changed"


@pytest.mark.parametrize(
    "secret_key",
    [
        "owner_phrase",
        "authorization",
        "api_key",
        "provider_key",
        "password",
        "bearer_token",
        "access_token",
        "refresh_token",
        "credentials",
        "cookie",
        "client_secret",
        "private_key",
    ],
)
def test_secret_like_keys_are_rejected_recursively_without_value_disclosure(
    tmp_path,
    command_factory: Callable[..., UniverseCommand],
    secret_key: str,
) -> None:
    store = UniverseStore(tmp_path / "universe.db")
    secret_value = "must-not-appear-in-errors"

    with pytest.raises(ValueError) as exc:
        store.append(
            command_factory(payload={"nested": {secret_key: secret_value}}),
            "realm.created",
        )

    assert secret_value not in str(exc.value)
    assert store.events_since("rlm_local", 0) == []
    assert store.entity("realm", "rlm_local", realm_id="rlm_local") is None


def test_public_signatures_and_policy_metadata_remain_representable(
    tmp_path, command_factory: Callable[..., UniverseCommand]
) -> None:
    store = UniverseStore(tmp_path / "universe.db")

    result = store.append(
        command_factory(
            payload={
                "public_key": "public-material",
                "signature": "public-signature",
                "policy_metadata": {"token_budget": 1000},
            },
            provenance={
                "source": "signed-record",
                "confidence": 1.0,
                "signature": "provenance-signature",
            },
        ),
        "realm.created",
    )

    assert result.entity["signature"] == "public-signature"
    assert result.event.provenance.signature == "provenance-signature"


def test_schema_check_detects_stale_without_mutating_and_is_deterministic() -> None:
    root = Path(__file__).parents[2]
    schema_dir = root / "plugins" / "muse_universe" / "schemas"
    script = root / "plugins" / "muse_universe" / "scripts" / "export_schemas.py"
    before = {path.name: path.read_bytes() for path in schema_dir.glob("*.json")}

    completed = subprocess.run(
        [sys.executable, str(script), "--check"],
        cwd=root,
        capture_output=True,
        check=False,
        text=True,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    after = {path.name: path.read_bytes() for path in schema_dir.glob("*.json")}
    assert after == before
    assert set(after) == {
        "command_result.schema.json",
        "universe_command.schema.json",
        "universe_event.schema.json",
    }
    for content in after.values():
        parsed = json.loads(content.decode("utf-8"))
        assert content.decode("utf-8") == json.dumps(
            parsed, ensure_ascii=False, indent=2, sort_keys=True
        ) + "\n"

    stale_path = schema_dir / "universe_command.schema.json"
    original = stale_path.read_bytes()
    stale = original + b"\n"
    try:
        stale_path.write_bytes(stale)
        stale_check = subprocess.run(
            [sys.executable, str(script), "--check"],
            cwd=root,
            capture_output=True,
            check=False,
            text=True,
        )
        assert stale_check.returncode != 0
        assert stale_path.read_bytes() == stale
    finally:
        stale_path.write_bytes(original)
