from __future__ import annotations

from collections.abc import Callable
import json
from pathlib import Path
import re

import pytest

from plugins.muse_universe.models import UniverseCommand, UniverseEvent
from plugins.muse_universe.service import COMMANDS
from plugins.muse_universe.store import CommandIdConflictError, UniverseStore


ROOT = Path(__file__).parents[2]
SCHEMA_DIR = ROOT / "plugins" / "muse_universe" / "schemas"
CONTRACT = ROOT / "docs" / "contracts" / "muse-universe-events-v1.md"

COMMAND_REQUIRED = {
    "command_id",
    "command_type",
    "realm_id",
    "actor_id",
    "stream_type",
    "stream_id",
    "expected_version",
    "payload",
    "authorization",
    "provenance",
    "causation_id",
    "correlation_id",
}
EVENT_REQUIRED = {
    "sequence",
    "event_id",
    "event_type",
    "realm_id",
    "actor_id",
    "stream_type",
    "stream_id",
    "stream_version",
    "authorization",
    "causation_id",
    "correlation_id",
    "occurred_at",
    "payload",
    "provenance",
    "simulation",
    "rollback",
}

FROZEN_V1_COMMAND_EVENTS = {
    "realm.create": ("realm", "realm.created"),
    "player.create": ("player", "player.created"),
    "civilization.create": ("civilization", "civilization.created"),
    "membership.invite": ("membership", "membership.invited"),
    "membership.accept": ("membership", "membership.accepted"),
    "presence.update": ("presence", "presence.updated"),
    "governance.propose": ("proposal", "governance.proposed"),
    "governance.vote": ("proposal", "governance.vote_recorded"),
    "governance.execute": ("proposal", "governance.executed"),
    "civilization.diplomacy": ("treaty", "diplomacy.updated"),
    "moderation.report": ("moderation_case", "moderation.reported"),
    "moderation.block": ("block", "moderation.blocked"),
    "station.create": ("station", "station.created"),
    "world.create": ("world", "world.created"),
    "world.region.freeze": ("world", "world.region_frozen"),
    "world.region.regenerate": ("world", "world.region_regenerated"),
    "building.place": ("building", "building.placed"),
    "vessel.create": ("vessel", "vessel.created"),
    "vessel.module.install": ("vessel", "vessel.module_installed"),
    "vessel.cosmetics.update": ("vessel", "vessel.cosmetics_updated"),
    "fleet.create": ("fleet", "fleet.created"),
    "fleet.assign": ("fleet", "fleet.member_assigned"),
    "mission.create": ("mission", "mission.created"),
    "mission.transition": ("mission", "mission.transitioned"),
    "campaign.create": ("campaign", "campaign.created"),
    "expedition.create": ("expedition", "expedition.created"),
    "blueprint.publish": ("blueprint", "blueprint.published"),
    "exchange.listing.publish": (
        "exchange_listing",
        "exchange.listing_published",
    ),
    "exchange.listing.remove": (
        "exchange_listing",
        "exchange.listing_removed",
    ),
    "marketplace.refund": ("creator_ledger", "marketplace.refunded"),
    "gallery.publish": ("gallery_item", "gallery.published"),
    "asset.register": ("asset", "asset.registered"),
    "operational_ledger.record": (
        "operational_ledger",
        "operational.recorded",
    ),
    "creator_ledger.record": ("creator_ledger", "creator.recorded"),
    "creator_ledger.transfer": ("creator_ledger", "creator.transferred"),
    "logistics.update": ("logistics", "logistics.updated"),
    "workspace.lease": ("workspace_lease", "workspace.leased"),
    "release.stage": ("release", "release.staged"),
    "release.promote": ("release", "release.promoted"),
    "cinematic_shot.create": ("cinematic_shot", "cinematic_shot.created"),
    "cinematic_shot.qc": (
        "cinematic_shot",
        "cinematic_shot.qc_recorded",
    ),
}

FROZEN_COMMAND_V1_EXAMPLE: dict[str, object] = {
    "command_id": "cmd_contract_0001",
    "command_type": "realm.create",
    "realm_id": "rlm_contract",
    "actor_id": "ply_owner",
    "stream_type": "realm",
    "stream_id": "rlm_contract",
    "expected_version": 0,
    "payload": {
        "authority": "server",
        "id": "rlm_contract",
        "mode": "local",
        "owner_id": "ply_owner",
        "retention": "owner_controlled",
        "ruleset": "muse-universe-v1",
        "version_policy": "optimistic",
        "visibility": "private",
    },
    "authorization": {
        "allowed": True,
        "reason": "local owner",
        "scopes": ["*"],
        "owner_gate": "not_required",
    },
    "provenance": {
        "source": "universe_service",
        "evidence": ["command:cmd_contract_0001"],
        "confidence": 1.0,
        "signature": "f" * 64,
    },
    "causation_id": "cmd_contract_0001",
    "correlation_id": "cmd_contract_0001",
    "simulation": False,
}

FROZEN_EVENT_V1_EXAMPLE: dict[str, object] = {
    "sequence": 1,
    "event_id": "00000000-0000-4000-8000-000000000001",
    "schema_version": 1,
    "event_type": "realm.created",
    "realm_id": "rlm_contract",
    "actor_id": "ply_owner",
    "stream_type": "realm",
    "stream_id": "rlm_contract",
    "stream_version": 1,
    "authorization": {
        "allowed": True,
        "reason": "local owner",
        "scopes": ["*"],
        "owner_gate": "not_required",
    },
    "causation_id": "cmd_contract_0001",
    "correlation_id": "cmd_contract_0001",
    "occurred_at": "2026-07-12T00:00:00+00:00",
    "payload": {
        "authority": "server",
        "id": "rlm_contract",
        "mode": "local",
        "owner_id": "ply_owner",
        "retention": "owner_controlled",
        "ruleset": "muse-universe-v1",
        "version_policy": "optimistic",
        "visibility": "private",
    },
    "provenance": {
        "source": "universe_service",
        "evidence": ["command:cmd_contract_0001"],
        "confidence": 1.0,
        "signature": "f" * 64,
    },
    "simulation": False,
    "rollback": {},
}


def _load_schema(name: str) -> dict[str, object]:
    return json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))


def _doc_vector(name: str) -> dict[str, object]:
    text = CONTRACT.read_text(encoding="utf-8")
    pattern = re.compile(
        rf"<!-- test-vector:{re.escape(name)} -->\s*"
        rf"```json\s*(.*?)\s*```\s*"
        rf"<!-- /test-vector:{re.escape(name)} -->",
        re.DOTALL,
    )
    match = pattern.search(text)
    assert match is not None, f"missing contract test vector {name}"
    return json.loads(match.group(1))


def test_event_replay_after_restart_is_deterministic(
    tmp_path,
    command_factory: Callable[..., UniverseCommand],
) -> None:
    database = tmp_path / "deterministic-replay.db"
    store = UniverseStore(database)
    store.append(command_factory(), "realm.created")
    store.append(
        command_factory(
            command_id="cmd_rename",
            expected_version=1,
            payload={"name": "Renamed Realm", "mode": "local"},
        ),
        "realm.updated",
    )
    live_events = [
        event.model_dump(mode="json")
        for event in store.events_since("rlm_local", 0)
    ]
    live_projection = store.entity(
        "realm", "rlm_local", realm_id="rlm_local"
    )
    live_snapshot = store.snapshot("rlm_local")

    restarted = UniverseStore(database)

    assert [
        event.model_dump(mode="json")
        for event in restarted.events_since("rlm_local", 0)
    ] == live_events
    assert restarted.snapshot("rlm_local") == live_snapshot
    assert restarted.snapshot("rlm_local")["realms"] == [live_projection]
    assert restarted.entity(
        "realm", "rlm_local", realm_id="rlm_local"
    ) == live_projection


def test_each_mutation_captures_the_exact_prior_projection_for_rollback(
    tmp_path,
    command_factory: Callable[..., UniverseCommand],
) -> None:
    database = tmp_path / "rollback-chain.db"
    store = UniverseStore(database)
    first = store.append(command_factory(), "realm.created")
    second = store.append(
        command_factory(
            command_id="cmd_update",
            expected_version=1,
            payload={"name": "Updated Realm", "mode": "local"},
        ),
        "realm.updated",
    )
    deleted = store.append(
        command_factory(
            command_id="cmd_delete",
            command_type="realm.delete",
            expected_version=2,
            payload={},
        ),
        "realm.deleted",
    )

    assert first.event.rollback == {}
    assert second.event.rollback == first.entity
    assert deleted.event.rollback == second.entity
    assert deleted.entity["deleted"] is True

    restarted = UniverseStore(database)
    events = restarted.events_since("rlm_local", 0)
    assert events[1].rollback == first.entity
    assert events[2].rollback == second.entity
    assert restarted.snapshot("rlm_local")["realms"][0]["deleted"] is True


def test_exact_command_retry_is_idempotent_across_process_restart(
    tmp_path,
    command_factory: Callable[..., UniverseCommand],
) -> None:
    database = tmp_path / "restart-idempotency.db"
    first_store = UniverseStore(database)
    first = first_store.append(command_factory(), "realm.created")

    restarted = UniverseStore(database)
    replay = restarted.append(command_factory(), "realm.created")

    assert replay.event_id == first.event_id
    assert replay.idempotent_replay is True
    assert len(restarted.events_since("rlm_local", 0)) == 1

    with pytest.raises(CommandIdConflictError):
        restarted.append(
            command_factory(payload={"name": "Different", "mode": "local"}),
            "realm.created",
        )
    assert len(restarted.events_since("rlm_local", 0)) == 1


def test_realm_filtered_cursor_reconnect_never_leaks_other_realms(
    tmp_path,
    command_factory: Callable[..., UniverseCommand],
) -> None:
    store = UniverseStore(tmp_path / "realm-cursors.db")
    local = store.append(command_factory(), "realm.created")
    other = store.append(
        command_factory(
            command_id="cmd_other",
            realm_id="rlm_other",
            stream_id="rlm_other",
            payload={"name": "Other Realm", "mode": "local"},
        ),
        "realm.created",
    )
    local_update = store.append(
        command_factory(
            command_id="cmd_local_update",
            expected_version=1,
            payload={"name": "Local v2", "mode": "local"},
        ),
        "realm.updated",
    )

    assert local.event.sequence < other.event.sequence < local_update.event.sequence
    assert [
        event.sequence
        for event in store.events_since("rlm_local", local.event.sequence)
    ] == [
        local_update.event.sequence
    ]
    assert [event.sequence for event in store.events_since("rlm_other", 0)] == [
        other.event.sequence
    ]
    assert all(
        event.realm_id == "rlm_local"
        for event in store.events_since("rlm_local", 0)
    )


def test_checked_in_json_schemas_freeze_v1_required_fields() -> None:
    command = _load_schema("universe_command.schema.json")
    event = _load_schema("universe_event.schema.json")
    result = _load_schema("command_result.schema.json")

    assert set(command["required"]) == COMMAND_REQUIRED
    assert COMMAND_REQUIRED <= set(command["properties"])
    assert command["properties"]["expected_version"] == {
        "minimum": 0,
        "title": "Expected Version",
        "type": "integer",
    }
    assert set(event["required"]) == EVENT_REQUIRED
    assert EVENT_REQUIRED | {"schema_version"} <= set(event["properties"])
    assert event["properties"]["schema_version"]["default"] == 1
    assert event["properties"]["payload"]["additionalProperties"] is True
    assert event["properties"]["rollback"]["additionalProperties"] is True
    assert set(result["required"]) == {"event", "entity"}
    assert result["properties"]["idempotent_replay"]["default"] is False


def test_frozen_v1_command_event_names_are_stable_but_extensible() -> None:
    assert set(FROZEN_V1_COMMAND_EVENTS) <= set(COMMANDS)
    for command_type, expected in FROZEN_V1_COMMAND_EVENTS.items():
        assert COMMANDS[command_type] == expected
    assert all(
        "." in command_type and "." in event_type
        for command_type, (_stream_type, event_type) in COMMANDS.items()
    )


def test_documented_json_vectors_are_model_valid_and_test_locked() -> None:
    command = UniverseCommand.model_validate(FROZEN_COMMAND_V1_EXAMPLE)
    event = UniverseEvent.model_validate(FROZEN_EVENT_V1_EXAMPLE)

    assert command.model_dump(mode="json") == FROZEN_COMMAND_V1_EXAMPLE
    assert event.model_dump(mode="json") == FROZEN_EVENT_V1_EXAMPLE
    assert _doc_vector("command-v1") == FROZEN_COMMAND_V1_EXAMPLE
    assert _doc_vector("event-v1") == FROZEN_EVENT_V1_EXAMPLE


def test_contract_documents_every_required_compatibility_rule() -> None:
    text = CONTRACT.read_text(encoding="utf-8")
    for heading in (
        "## Authority selection",
        "## Command envelope",
        "## Event envelope",
        "## Naming",
        "## Optimistic concurrency",
        "## Idempotency",
        "## Cursors and reconnect",
        "## Privacy and secret redaction",
        "## Replay and projections",
        "## Rollback metadata",
        "## Migration and compatibility",
        "## Evidence status",
    ):
        assert heading in text
