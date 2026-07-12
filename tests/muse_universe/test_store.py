from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import sys
from threading import Barrier
from typing import Any

import pytest
from pydantic import ValidationError

from plugins.muse_universe.models import CommandResult, UniverseCommand
from plugins.muse_universe.store import (
    CommandIdConflictError,
    ConflictError,
    UniverseStore,
)


def entity(store: UniverseStore, entity_type: str, entity_id: str) -> dict[str, Any]:
    projection = store.entity(entity_type, entity_id)
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


def test_command_result_is_frozen(
    tmp_path, command_factory: Callable[..., UniverseCommand]
) -> None:
    result = UniverseStore(tmp_path / "universe.db").append(
        command_factory(), "realm.created"
    )

    with pytest.raises(ValidationError):
        result.idempotent_replay = True


def test_schema_check_is_deterministic_and_does_not_mutate_files() -> None:
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
