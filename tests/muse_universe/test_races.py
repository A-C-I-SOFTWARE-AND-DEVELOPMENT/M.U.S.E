from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from plugins.muse_universe.models import CommandResult, UniverseCommand
from plugins.muse_universe.service import UniverseService, ValidationError
from plugins.muse_universe.store import ConflictError, UniverseStore


def test_two_thread_expected_version_race_has_exactly_one_winner(
    tmp_path,
    command_factory: Callable[..., UniverseCommand],
) -> None:
    store = UniverseStore(tmp_path / "expected-version-race.db")
    barrier = Barrier(2)

    def append(command_id: str) -> CommandResult | ConflictError:
        barrier.wait()
        try:
            return store.append(
                command_factory(command_id=command_id, expected_version=0),
                "realm.created",
            )
        except ConflictError as exc:
            return exc

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(append, ("cmd_race_a", "cmd_race_b")))

    winners = [outcome for outcome in outcomes if isinstance(outcome, CommandResult)]
    conflicts = [outcome for outcome in outcomes if isinstance(outcome, ConflictError)]
    assert len(winners) == 1
    assert len(conflicts) == 1
    assert conflicts[0].expected_version == 0
    assert conflicts[0].current_version == 1
    assert winners[0].stream_version == 1
    assert len(store.events_since("rlm_local", 0)) == 1
    projection = store.entity("realm", "rlm_local", realm_id="rlm_local")
    assert projection is not None
    assert projection["version"] == 1


def test_concurrent_exact_duplicate_command_is_one_idempotent_effect(
    tmp_path,
    command_factory: Callable[..., UniverseCommand],
) -> None:
    store = UniverseStore(tmp_path / "duplicate-command-race.db")
    barrier = Barrier(2)

    def append(_index: int) -> CommandResult:
        barrier.wait()
        return store.append(command_factory(), "realm.created")

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(append, range(2)))

    assert outcomes[0].event_id == outcomes[1].event_id
    assert sorted(outcome.idempotent_replay for outcome in outcomes) == [False, True]
    assert len(store.events_since("rlm_local", 0)) == 1
    assert store.command_result("rlm_local", "cmd_1") is not None


def test_stale_write_rolls_back_event_projection_and_command_result(
    tmp_path,
    command_factory: Callable[..., UniverseCommand],
) -> None:
    store = UniverseStore(tmp_path / "stale-write.db")
    store.append(command_factory(), "realm.created")
    before_events = [
        event.model_dump(mode="json")
        for event in store.events_since("rlm_local", 0)
    ]
    before_projection = store.entity(
        "realm", "rlm_local", realm_id="rlm_local"
    )

    try:
        store.append(
            command_factory(
                command_id="cmd_stale",
                expected_version=0,
                payload={"name": "Stale overwrite", "mode": "local"},
            ),
            "realm.updated",
        )
    except ConflictError as exc:
        assert exc.expected_version == 0
        assert exc.current_version == 1
    else:
        raise AssertionError("stale write unexpectedly succeeded")

    assert [
        event.model_dump(mode="json")
        for event in store.events_since("rlm_local", 0)
    ] == before_events
    assert store.entity(
        "realm", "rlm_local", realm_id="rlm_local"
    ) == before_projection
    assert store.command_result("rlm_local", "cmd_stale") is None


def test_concurrent_creator_transfers_cannot_double_spend(
    service: UniverseService,
) -> None:
    service.create_local_realm("ply_owner")
    service.execute(
        "creator_ledger.record",
        "ply_owner",
        "rlm_local",
        {
            "id": "cr_seed",
            "asset_id": "ast_1",
            "owner_id": "ply_owner",
            "quantity": 1,
        },
        0,
        "cmd_seed_balance",
    )
    barrier = Barrier(2)

    def transfer(index: int) -> CommandResult | ValidationError:
        barrier.wait()
        try:
            return service.execute(
                "creator_ledger.transfer",
                "ply_owner",
                "rlm_local",
                {
                    "id": f"cr_transfer_{index}",
                    "asset_id": "ast_1",
                    "from_id": "ply_owner",
                    "to_id": f"ply_buyer_{index}",
                    "quantity": 1,
                },
                0,
                f"cmd_transfer_{index}",
            )
        except ValidationError as exc:
            return exc

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(transfer, range(2)))

    assert sum(isinstance(outcome, CommandResult) for outcome in outcomes) == 1
    failures = [outcome for outcome in outcomes if isinstance(outcome, ValidationError)]
    assert len(failures) == 1
    assert "insufficient balance" in str(failures[0])
    transfer_events = [
        event
        for event in service.store.events_since("rlm_local", 0)
        if event.event_type == "creator.transferred"
    ]
    assert len(transfer_events) == 1
    owner_balance = sum(
        side["quantity"]
        for entry in service.snapshot("ply_owner", "rlm_local")["creator_ledgers"]
        if entry.get("asset_id") == "ast_1"
        for side in entry.get("entries", [])
        if side.get("owner_id") == "ply_owner"
    )
    assert owner_balance == 0


def test_concurrent_equal_ids_in_distinct_realms_do_not_conflict(
    service: UniverseService,
) -> None:
    service.create_local_realm("ply_alpha", realm_id="rlm_alpha")
    service.create_local_realm("ply_beta", realm_id="rlm_beta")
    barrier = Barrier(2)

    def create_player(realm_id: str, owner_id: str) -> CommandResult:
        barrier.wait()
        return service.execute(
            "player.create",
            owner_id,
            realm_id,
            {"id": "ply_shared", "display_name": realm_id},
            0,
            "cmd_shared",
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = (
            executor.submit(create_player, "rlm_alpha", "ply_alpha"),
            executor.submit(create_player, "rlm_beta", "ply_beta"),
        )
        outcomes = [future.result() for future in futures]

    assert {outcome.event.realm_id for outcome in outcomes} == {
        "rlm_alpha",
        "rlm_beta",
    }
    assert all(outcome.stream_version == 1 for outcome in outcomes)
    assert service.store.command_result("rlm_alpha", "cmd_shared") is not None
    assert service.store.command_result("rlm_beta", "cmd_shared") is not None
