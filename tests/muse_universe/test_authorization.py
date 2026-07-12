from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from typing import Any

import pytest

from plugins.muse_universe.authorization import AuthorizationError
from plugins.muse_universe.service import UniverseService
from plugins.muse_universe.store import CommandIdConflictError


def _asset_payload(asset_id: str = "ast_1") -> dict[str, object]:
    return {
        "id": asset_id,
        "content_hash": "sha256:" + "a" * 64,
        "license": "MUSE-ORIGINAL-1.0",
        "provenance": {"source": "owner", "evidence": ["source:1"]},
        "verification": {"status": "passed", "evidence": ["scan:1"]},
        "moderation": {"status": "approved", "case_id": "mod_1"},
    }


def _invite_and_accept(
    service: UniverseService,
    *,
    player_id: str = "ply_guest",
    scopes: list[str] | None = None,
) -> None:
    service.execute(
        "membership.invite",
        "ply_owner",
        "rlm_local",
        {
            "id": f"mem_{player_id}",
            "player_id": player_id,
            "civilization_id": "civ_owner",
            "scopes": scopes or ["presence:write"],
        },
        0,
        f"cmd_invite_{player_id}",
    )
    service.execute(
        "membership.accept",
        player_id,
        "rlm_local",
        {"id": f"mem_{player_id}"},
        1,
        f"cmd_accept_{player_id}",
    )


def test_rank_never_grants_capability_scope(service: UniverseService) -> None:
    service.create_local_realm("ply_owner")
    service.execute(
        "player.create",
        "ply_owner",
        "rlm_local",
        {"id": "ply_guest", "display_name": "Guest", "rank": 9999},
        0,
        "cmd_guest",
    )
    with pytest.raises(AuthorizationError, match="scope"):
        service.execute(
            "vessel.module.install",
            "ply_guest",
            "rlm_local",
            {"vessel_id": "vsl_owner", "module_id": "mod_release_dock"},
            1,
            "cmd_escalate",
        )


def test_payload_roles_scopes_and_membership_are_never_authoritative(
    service: UniverseService,
) -> None:
    service.create_local_realm("ply_owner")
    with pytest.raises(AuthorizationError, match="scope"):
        service.execute(
            "station.create",
            "ply_forged",
            "rlm_local",
            {
                "id": "stn_forged",
                "station_type": "neural_shipyard",
                "owner_id": "ply_forged",
                "rooms": ["command_bridge"],
                "roles": ["owner"],
                "scopes": ["station:write"],
                "membership": {"status": "active"},
            },
            0,
            "cmd_forged",
        )


def test_active_realm_membership_grants_only_recorded_scopes(
    service: UniverseService,
) -> None:
    service.create_local_realm("ply_owner")
    service.execute(
        "civilization.create",
        "ply_owner",
        "rlm_local",
        {
            "id": "civ_owner",
            "name": "Owner Civ",
            "charter": "Build safely",
            "governance": {"quorum": 1},
        },
        0,
        "cmd_civ",
    )
    _invite_and_accept(service)
    service.execute(
        "presence.update",
        "ply_guest",
        "rlm_local",
        {
            "id": "ply_guest",
            "sequence": 1,
            "status": "online",
            "visibility": "realm",
        },
        0,
        "cmd_presence",
    )
    with pytest.raises(AuthorizationError, match="scope"):
        service.execute(
            "fleet.create",
            "ply_guest",
            "rlm_local",
            {"id": "flt_1", "owner_id": "ply_guest", "members": []},
            0,
            "cmd_fleet",
        )


def test_removed_membership_and_realm_mismatch_fail_closed(
    service: UniverseService,
) -> None:
    service.create_local_realm("ply_owner")
    service.execute(
        "civilization.create",
        "ply_owner",
        "rlm_local",
        {
            "id": "civ_owner",
            "name": "Owner Civ",
            "charter": "Build safely",
            "governance": {"quorum": 1},
        },
        0,
        "cmd_civ",
    )
    _invite_and_accept(service, player_id="ply_removed")
    service.execute(
        "membership.accept",
        "ply_removed",
        "rlm_local",
        {"id": "mem_ply_removed", "status": "removed"},
        2,
        "cmd_remove",
    )
    with pytest.raises(AuthorizationError, match="active membership"):
        service.execute(
            "presence.update",
            "ply_removed",
            "rlm_local",
            {"id": "ply_removed", "sequence": 1, "status": "online"},
            0,
            "cmd_removed_presence",
        )

    service.create_local_realm("ply_other", realm_id="rlm_other")
    with pytest.raises(AuthorizationError, match="realm"):
        service.execute(
            "presence.update",
            "ply_removed",
            "rlm_other",
            {"id": "ply_removed", "sequence": 1, "status": "online"},
            0,
            "cmd_wrong_realm",
        )


def test_sensitive_request_uses_exact_trusted_approval_binding(
    service: UniverseService, approval_verifier
) -> None:
    service.create_local_realm("ply_owner")
    approval_verifier.allow("apr_release")
    with pytest.raises(Exception, match="release"):
        service.execute(
            "release.promote",
            "ply_owner",
            "rlm_local",
            {"release_id": "rel_missing", "target": "production"},
            0,
            "cmd_release",
            approval_id="apr_release",
        )
    assert approval_verifier.calls == []

    approval_verifier.allow("apr_asset")
    service.execute(
        "asset.register",
        "ply_owner",
        "rlm_local",
        _asset_payload(),
        0,
        "cmd_asset",
        approval_id="apr_asset",
    )
    approval_verifier.calls.clear()
    service.execute(
        "release.stage",
        "ply_owner",
        "rlm_local",
        {
            "id": "rel_1",
            "artifact_id": "ast_1",
            "content_hash": "sha256:" + "a" * 64,
            "target": "production",
            "verification": {"status": "passed", "evidence": ["test:1"]},
            "rollback": {"release_id": "rel_previous"},
        },
        0,
        "cmd_stage",
    )
    service.execute(
        "release.promote",
        "ply_owner",
        "rlm_local",
        {"release_id": "rel_1", "target": "production"},
        1,
        "cmd_release",
        approval_id="apr_release",
    )
    binding = approval_verifier.calls[0]
    assert binding["action"] == "release.promote"
    assert binding["actor_id"] == "ply_owner"
    assert binding["realm_id"] == "rlm_local"
    assert binding["correlation_id"] == "cmd_release"
    assert binding["subject"] == {
        "command_id": "cmd_release",
        "command_type": "release.promote",
        "actor_id": "ply_owner",
        "realm_id": "rlm_local",
        "expected_version": 1,
        "payload": {"release_id": "rel_1", "target": "production"},
        "simulation": False,
    }


def test_approval_metadata_and_owner_phrase_are_rejected_from_payload(
    service: UniverseService,
) -> None:
    service.create_local_realm("ply_owner")
    for forbidden in ("approval_id", "approval_metadata", "owner_phrase"):
        with pytest.raises(ValueError, match="payload"):
            service.execute(
                "asset.register",
                "ply_owner",
                "rlm_local",
                {
                    "id": f"ast_{forbidden}",
                    "content_hash": "sha256:" + "a" * 64,
                    "license": "MUSE-ORIGINAL-1.0",
                    "provenance": {"source": "owner", "evidence": ["src:1"]},
                    "verification": {"status": "passed"},
                    "moderation": {"status": "approved"},
                    forbidden: "do-not-trust",
                },
                0,
                f"cmd_{forbidden}",
            )


def test_simulation_cannot_promote_release(service: UniverseService) -> None:
    service.create_local_realm("ply_owner")
    with pytest.raises(AuthorizationError, match="simulation"):
        service.execute(
            "release.promote",
            "ply_owner",
            "rlm_local",
            {"release_id": "rel_1", "target": "production"},
            0,
            "cmd_release",
            simulation=True,
        )


def test_unsupported_command_fails_closed(service: UniverseService) -> None:
    service.create_local_realm("ply_owner")
    with pytest.raises(AuthorizationError, match="unsupported"):
        service.execute(
            "admin.godmode",
            "ply_owner",
            "rlm_local",
            {"id": "anything"},
            0,
            "cmd_unknown",
        )


def test_consumed_approval_retries_only_the_same_exact_request(tmp_path) -> None:
    from hermes_cli.approval_grants import decide_bound_approval, stage_bound_approval
    from plugins.muse_universe.store import UniverseStore

    service = UniverseService(UniverseStore(tmp_path / "retry.db"))
    service.create_local_realm("ply_owner")
    asset_payload = _asset_payload()
    asset_subject = {
        "command_id": "cmd_asset",
        "command_type": "asset.register",
        "actor_id": "ply_owner",
        "realm_id": "rlm_local",
        "expected_version": 0,
        "payload": asset_payload,
        "simulation": False,
    }
    asset_approval = stage_bound_approval(
        "ply_owner",
        "asset.register",
        "rlm_local",
        "cmd_asset",
        asset_subject,
        approval_id="approval_asset_retry",
    )
    decide_bound_approval(asset_approval.approval_id, approve=True, decided_by="owner")
    service.execute(
        "asset.register",
        "ply_owner",
        "rlm_local",
        asset_payload,
        0,
        "cmd_asset",
        approval_id=asset_approval.approval_id,
    )
    service.execute(
        "release.stage",
        "ply_owner",
        "rlm_local",
        {
            "id": "rel_1",
            "artifact_id": "ast_1",
            "content_hash": "sha256:" + "a" * 64,
            "target": "production",
            "verification": {"status": "passed", "evidence": ["test:1"]},
            "rollback": {"release_id": "rel_previous"},
        },
        0,
        "cmd_stage",
    )
    payload = {"release_id": "rel_1", "target": "production"}
    subject = {
        "command_id": "cmd_promote",
        "command_type": "release.promote",
        "actor_id": "ply_owner",
        "realm_id": "rlm_local",
        "expected_version": 1,
        "payload": payload,
        "simulation": False,
    }
    staged = stage_bound_approval(
        "ply_owner",
        "release.promote",
        "rlm_local",
        "cmd_promote",
        subject,
        approval_id="approval_release_retry",
    )
    decide_bound_approval(staged.approval_id, approve=True, decided_by="owner")
    first = service.execute(
        "release.promote",
        "ply_owner",
        "rlm_local",
        payload,
        1,
        "cmd_promote",
        approval_id=staged.approval_id,
    )
    replay = service.execute(
        "release.promote",
        "ply_owner",
        "rlm_local",
        payload,
        1,
        "cmd_promote",
        approval_id=staged.approval_id,
    )
    assert replay.event_id == first.event_id
    assert replay.idempotent_replay is True
    assert replay.event.causation_id == "cmd_promote"
    assert replay.event.correlation_id == "cmd_promote"

    with pytest.raises(CommandIdConflictError):
        service.execute(
            "release.promote",
            "ply_owner",
            "rlm_local",
            payload,
            2,
            "cmd_promote",
            approval_id=staged.approval_id,
        )


def test_stale_sensitive_race_does_not_consume_losing_approval(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from hermes_cli.approval_grants import (
        ApprovalState,
        decide_bound_approval,
        list_bound_approvals,
        stage_bound_approval,
        validate_and_consume_approval,
    )
    from plugins.muse_universe.store import ConflictError, UniverseStore

    approval_db = tmp_path / "approvals.db"

    class ScopedVerifier:
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
        ):
            del db_path
            return validate_and_consume_approval(
                approval_id,
                actor_id,
                action,
                realm_id,
                correlation_id,
                subject,
                db_path=approval_db,
            )

    store = UniverseStore(tmp_path / "universe.db")
    service = UniverseService(store, approval_verifier=ScopedVerifier())
    service.create_local_realm("ply_owner")
    payload: dict[str, Any] = {
        "id": "wrk_race",
        "provider": "external",
        "project_id": "proj_1",
        "cost_usd": 1.0,
        "expiry_utc": "2099-01-01T00:00:00+00:00",
        "checkpoint": "chk_1",
        "signed_preview": "sha256:" + "b" * 64,
    }

    def grant(command_id: str, expected_version: int, approval_id: str) -> str:
        subject = {
            "command_id": command_id,
            "command_type": "workspace.lease",
            "actor_id": "ply_owner",
            "realm_id": "rlm_local",
            "expected_version": expected_version,
            "payload": payload,
            "simulation": False,
        }
        staged = stage_bound_approval(
            "ply_owner",
            "workspace.lease",
            "rlm_local",
            command_id,
            subject,
            approval_id=approval_id,
            db_path=approval_db,
        )
        decide_bound_approval(
            staged.approval_id,
            approve=True,
            decided_by="owner",
            db_path=approval_db,
        )
        return staged.approval_id

    approvals = (
        grant("cmd_lease_a", 0, "approval_lease_a"),
        grant("cmd_lease_b", 0, "approval_lease_b"),
    )
    barrier = Barrier(2)
    original_command_result = store.command_result

    def synchronized_command_result(realm_id: str, command_id: str):
        if command_id in {"cmd_lease_a", "cmd_lease_b"}:
            result = original_command_result(realm_id, command_id)
            barrier.wait()
            return result
        return original_command_result(realm_id, command_id)

    monkeypatch.setattr(store, "command_result", synchronized_command_result)

    def lease(index: int):
        try:
            return service.execute(
                "workspace.lease",
                "ply_owner",
                "rlm_local",
                payload,
                0,
                f"cmd_lease_{'a' if index == 0 else 'b'}",
                approval_id=approvals[index],
            )
        except Exception as exc:  # noqa: BLE001 - race outcome is asserted below
            return exc

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = tuple(pool.map(lease, range(2)))

    assert sum(not isinstance(result, Exception) for result in results) == 1
    assert sum(isinstance(result, ConflictError) for result in results) == 1
    records = {record.approval_id: record for record in list_bound_approvals(db_path=approval_db)}
    loser = next(index for index, result in enumerate(results) if isinstance(result, ConflictError))
    winner = 1 - loser
    assert records[approvals[winner]].state is ApprovalState.CONSUMED
    assert records[approvals[loser]].state is ApprovalState.GRANTED

    corrected_id = "cmd_lease_corrected"
    corrected_approval = grant(corrected_id, 1, "approval_lease_corrected")
    corrected = service.execute(
        "workspace.lease",
        "ply_owner",
        "rlm_local",
        payload,
        1,
        corrected_id,
        approval_id=corrected_approval,
    )
    assert corrected.stream_version == 2
