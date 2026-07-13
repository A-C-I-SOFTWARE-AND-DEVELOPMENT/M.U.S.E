from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from plugins.muse_universe.authorization import AuthorizationError
from plugins.muse_universe.models import (
    AuthorizationDecision,
    ProvenanceRecord,
    UniverseCommand,
)
from plugins.muse_universe.service import UniverseService, ValidationError


def _create_civilization(
    service: UniverseService,
    civilization_id: str,
    *,
    command_id: str | None = None,
) -> None:
    service.execute(
        "civilization.create",
        "ply_owner",
        "rlm_local",
        {
            "id": civilization_id,
            "name": civilization_id,
            "charter": "Operate safely",
            "governance": {"quorum": 1},
        },
        0,
        command_id or f"cmd_create_{civilization_id}",
    )


def _invite_and_accept(
    service: UniverseService,
    player_id: str,
    civilization_id: str,
    scopes: list[str],
) -> str:
    membership_id = f"mem_{player_id}"
    service.execute(
        "membership.invite",
        "ply_owner",
        "rlm_local",
        {
            "id": membership_id,
            "player_id": player_id,
            "civilization_id": civilization_id,
            "scopes": scopes,
        },
        0,
        f"cmd_invite_{player_id}",
    )
    service.execute(
        "membership.accept",
        player_id,
        "rlm_local",
        {"id": membership_id},
        1,
        f"cmd_accept_{player_id}",
    )
    return membership_id


def test_forged_membership_roles_and_scopes_never_authorize(
    service: UniverseService,
) -> None:
    service.create_local_realm("ply_owner")

    with pytest.raises(AuthorizationError, match="active membership|scope"):
        service.execute(
            "station.create",
            "ply_forged",
            "rlm_local",
            {
                "id": "stn_forged",
                "station_type": "neural_shipyard",
                "owner_id": "ply_forged",
                "rooms": ["command_bridge"],
                "membership": {"status": "active", "realm_id": "rlm_local"},
                "roles": ["owner"],
                "scopes": ["*", "station:write"],
                "rank": 9999,
            },
            0,
            "cmd_forged_station",
        )

    assert service.store.entity(
        "station", "stn_forged", realm_id="rlm_local"
    ) is None
    assert [event.event_type for event in service.store.events_since("rlm_local", 0)] == [
        "realm.created"
    ]


def test_removed_member_is_denied_even_when_payload_claims_active_status(
    service: UniverseService,
) -> None:
    service.create_local_realm("ply_owner")
    _create_civilization(service, "civ_owner")
    membership_id = _invite_and_accept(
        service, "ply_removed", "civ_owner", ["presence:write"]
    )
    service.execute(
        "membership.accept",
        "ply_removed",
        "rlm_local",
        {"id": membership_id, "status": "removed"},
        2,
        "cmd_remove_member",
    )

    with pytest.raises(AuthorizationError, match="active membership"):
        service.execute(
            "presence.update",
            "ply_removed",
            "rlm_local",
            {
                "id": "ply_removed",
                "sequence": 1,
                "status": "online",
                "membership": {"status": "active"},
            },
            0,
            "cmd_removed_presence",
        )

    assert service.store.entity(
        "presence", "ply_removed", realm_id="rlm_local"
    ) is None


def test_membership_in_one_realm_does_not_authorize_another_realm(
    service: UniverseService,
) -> None:
    service.create_local_realm("ply_owner")
    _create_civilization(service, "civ_owner")
    _invite_and_accept(service, "ply_guest", "civ_owner", ["presence:write"])
    service.create_local_realm("ply_other", realm_id="rlm_other")

    with pytest.raises(AuthorizationError, match="realm mismatch"):
        service.execute(
            "presence.update",
            "ply_guest",
            "rlm_other",
            {"id": "ply_guest", "sequence": 1, "status": "online"},
            0,
            "cmd_cross_realm_presence",
        )

    assert service.store.events_since("rlm_other", 0)[0].event_type == "realm.created"
    assert len(service.store.events_since("rlm_other", 0)) == 1


def test_active_membership_without_required_scope_fails_closed(
    service: UniverseService,
) -> None:
    service.create_local_realm("ply_owner")
    _create_civilization(service, "civ_owner")
    _invite_and_accept(service, "ply_guest", "civ_owner", ["presence:write"])

    with pytest.raises(AuthorizationError, match="fleet:write"):
        service.execute(
            "fleet.create",
            "ply_guest",
            "rlm_local",
            {"id": "flt_forbidden", "owner_id": "ply_guest", "members": []},
            0,
            "cmd_forbidden_fleet",
        )

    assert service.store.entity(
        "fleet", "flt_forbidden", realm_id="rlm_local"
    ) is None


def test_gameplay_rank_cannot_escalate_capability_scope(
    service: UniverseService,
) -> None:
    service.create_local_realm("ply_owner")
    _create_civilization(service, "civ_owner")
    _invite_and_accept(service, "ply_ranked", "civ_owner", ["presence:write"])
    player = service.execute(
        "player.create",
        "ply_owner",
        "rlm_local",
        {"id": "ply_ranked", "display_name": "Ranked", "rank": 9999},
        0,
        "cmd_ranked_player",
    ).entity
    assert player["rank"] == 9999

    with pytest.raises(AuthorizationError, match="vessel:configure"):
        service.execute(
            "vessel.module.install",
            "ply_ranked",
            "rlm_local",
            {
                "vessel_id": "vsl_owner",
                "module_id": "mod_release_dock",
                "attachment_type": "release_dock",
            },
            1,
            "cmd_rank_escalation",
        )


def test_duplicate_governance_vote_is_rejected_without_partial_write(
    service: UniverseService,
) -> None:
    service.create_local_realm("ply_owner")
    _create_civilization(service, "civ_owner")
    service.execute(
        "governance.propose",
        "ply_owner",
        "rlm_local",
        {
            "id": "prop_1",
            "civilization_id": "civ_owner",
            "title": "One actor, one vote",
            "action": {"type": "station.create"},
            "deadline_utc": (
                datetime.now(timezone.utc) + timedelta(hours=1)
            ).isoformat(),
        },
        0,
        "cmd_proposal",
    )
    service.execute(
        "governance.vote",
        "ply_owner",
        "rlm_local",
        {"proposal_id": "prop_1", "choice": "yes"},
        1,
        "cmd_vote_yes",
    )

    before = service.store.events_since("rlm_local", 0)
    with pytest.raises(ValidationError, match="duplicate"):
        service.execute(
            "governance.vote",
            "ply_owner",
            "rlm_local",
            {"proposal_id": "prop_1", "choice": "no"},
            2,
            "cmd_vote_twice",
        )

    proposal = service.store.entity("proposal", "prop_1", realm_id="rlm_local")
    assert proposal is not None
    assert proposal["version"] == 2
    assert proposal["votes"] == [{"actor_id": "ply_owner", "choice": "yes"}]
    assert service.store.events_since("rlm_local", 0) == before


def test_operational_and_creator_ledgers_reject_cross_family_fields(
    service: UniverseService,
) -> None:
    service.create_local_realm("ply_owner")

    with pytest.raises(ValidationError, match="operational ledger"):
        service.execute(
            "operational_ledger.record",
            "ply_owner",
            "rlm_local",
            {
                "id": "op_mixed",
                "provider": "local",
                "compute_seconds": 1,
                "cost_usd": 0.0,
                "asset_id": "ast_1",
                "quantity": 1,
            },
            0,
            "cmd_op_mixed",
        )
    with pytest.raises(ValidationError, match="creator ledger"):
        service.execute(
            "creator_ledger.record",
            "ply_owner",
            "rlm_local",
            {
                "id": "cr_mixed",
                "asset_id": "ast_1",
                "owner_id": "ply_owner",
                "quantity": 1,
                "provider": "external",
                "cost_usd": 2.0,
            },
            0,
            "cmd_cr_mixed",
        )

    snapshot = service.snapshot("ply_owner", "rlm_local")
    assert snapshot.get("operational_ledgers", []) == []
    assert snapshot.get("creator_ledgers", []) == []


def test_unregistered_blueprint_and_missing_license_fail_closed_before_approval(
    service: UniverseService,
    approval_verifier,
) -> None:
    service.create_local_realm("ply_owner")
    approval_verifier.allow("apr_unsigned_blueprint")
    with pytest.raises(ValidationError, match="asset does not exist"):
        service.execute(
            "blueprint.publish",
            "ply_owner",
            "rlm_local",
            {
                "id": "bp_unsigned",
                "asset_id": "ast_unregistered",
                "visibility": "public",
            },
            0,
            "cmd_unsigned_blueprint",
            approval_id="apr_unsigned_blueprint",
        )

    approval_verifier.allow("apr_missing_license")
    with pytest.raises(ValidationError, match="license"):
        service.execute(
            "asset.register",
            "ply_owner",
            "rlm_local",
            {
                "id": "ast_missing_license",
                "content_hash": "sha256:" + "a" * 64,
                "provenance": {"source": "owner", "evidence": ["source:1"]},
                "verification": {"status": "passed", "evidence": ["scan:1"]},
                "moderation": {"status": "approved", "case_id": "mod_1"},
            },
            0,
            "cmd_missing_license",
            approval_id="apr_missing_license",
        )

    assert approval_verifier.calls == []
    assert service.store.entity(
        "blueprint", "bp_unsigned", realm_id="rlm_local"
    ) is None
    assert service.store.entity(
        "asset", "ast_missing_license", realm_id="rlm_local"
    ) is None


def test_real_command_cannot_promote_a_simulation_release_projection(
    service: UniverseService,
    approval_verifier,
) -> None:
    service.create_local_realm("ply_owner")
    service.store.append(
        UniverseCommand(
            command_id="seed_simulation_release",
            command_type="release.stage",
            realm_id="rlm_local",
            actor_id="ply_owner",
            stream_type="release",
            stream_id="rel_simulation",
            expected_version=0,
            payload={
                "id": "rel_simulation",
                "artifact_id": "ast_1",
                "content_hash": "sha256:" + "a" * 64,
                "target": "production",
                "status": "staged",
                "verification": {"status": "passed", "evidence": ["test:1"]},
                "rollback": {"release_id": "rel_previous"},
            },
            authorization=AuthorizationDecision(
                allowed=True, reason="test seed", scopes=("*",)
            ),
            provenance=ProvenanceRecord(source="test", confidence=1.0),
            causation_id="seed_simulation_release",
            correlation_id="seed_simulation_release",
            simulation=True,
        ),
        "release.staged",
    )
    approval_verifier.allow("apr_real_promotion")

    with pytest.raises(AuthorizationError, match="simulation"):
        service.execute(
            "release.promote",
            "ply_owner",
            "rlm_local",
            {"release_id": "rel_simulation", "target": "production"},
            1,
            "cmd_real_promotion",
            approval_id="apr_real_promotion",
            simulation=False,
        )

    release = service.store.entity(
        "release", "rel_simulation", realm_id="rlm_local"
    )
    assert release is not None
    assert release["status"] == "staged"
    assert release["simulation"] is True
    assert approval_verifier.calls == []


@pytest.mark.parametrize(
    "secret_key",
    [
        "owner_phrase",
        "authorization",
        "api_key",
        "providerKey",
        "password",
        "bearer_token",
        "access_token",
        "refresh-token",
        "credentials",
        "cookie",
        "client_secret",
        "private_key",
    ],
)
def test_secret_like_payload_keys_are_rejected_without_value_disclosure(
    service: UniverseService,
    secret_key: str,
) -> None:
    service.create_local_realm("ply_owner")
    sentinel = "SENTINEL-MUST-NEVER-LEAK"

    with pytest.raises(ValueError) as exc:
        service.execute(
            "player.create",
            "ply_owner",
            "rlm_local",
            {
                "id": f"ply_secret_{secret_key}",
                "display_name": "Secret carrier",
                "nested": {secret_key: sentinel},
            },
            0,
            f"cmd_secret_{secret_key}",
        )

    assert sentinel not in str(exc.value)
    serialized_events = "\n".join(
        event.model_dump_json() for event in service.store.events_since("rlm_local", 0)
    )
    assert sentinel not in serialized_events
    assert len(service.store.events_since("rlm_local", 0)) == 1
    assert service.store.command_result("rlm_local", f"cmd_secret_{secret_key}") is None


def test_presence_reads_enforce_private_crew_and_public_minimization(
    service: UniverseService,
) -> None:
    service.presence_min_interval = 0
    service.create_local_realm("ply_owner")
    for civilization_id in ("civ_alpha", "civ_beta"):
        _create_civilization(service, civilization_id)
    _invite_and_accept(
        service, "ply_private", "civ_alpha", ["presence:write"]
    )
    _invite_and_accept(service, "ply_crew", "civ_alpha", ["presence:write"])
    _invite_and_accept(service, "ply_other", "civ_beta", ["presence:write"])

    for player_id, visibility, position in (
        ("ply_private", "private", [1, 2, 3]),
        ("ply_crew", "crew", [4, 5, 6]),
        ("ply_other", "public", [7, 8, 9]),
    ):
        service.execute(
            "presence.update",
            player_id,
            "rlm_local",
            {
                "id": player_id,
                "sequence": 1,
                "status": "online",
                "visibility": visibility,
                "mode": "walk",
                "position": position,
            },
            0,
            f"cmd_presence_{player_id}",
        )

    with pytest.raises(AuthorizationError, match="caller"):
        service.snapshot(None, "rlm_local")

    alpha_view = service.snapshot("ply_private", "rlm_local")["presences"]
    assert {presence["id"] for presence in alpha_view} == {
        "ply_private",
        "ply_crew",
        "ply_other",
    }
    private = next(item for item in alpha_view if item["id"] == "ply_private")
    assert "position" not in private
    crew = next(item for item in alpha_view if item["id"] == "ply_crew")
    assert set(crew) == {"id", "status", "visibility", "mode"}

    beta_view = service.snapshot("ply_other", "rlm_local")["presences"]
    assert {presence["id"] for presence in beta_view} == {"ply_other"}
    assert set(beta_view[0]) == {"id", "status", "visibility", "mode"}
    assert service.entity(
        "ply_other", "presence", "ply_private", "rlm_local"
    ) is None


def test_moderation_report_and_block_preserve_authoritative_state(
    service: UniverseService,
) -> None:
    service.create_local_realm("ply_owner")
    report = service.execute(
        "moderation.report",
        "ply_owner",
        "rlm_local",
        {"id": "mod_case_1", "target_id": "ply_target", "reason": "abuse"},
        0,
        "cmd_report",
    )
    block = service.execute(
        "moderation.block",
        "ply_owner",
        "rlm_local",
        {"id": "blk_1", "target_id": "ply_target", "reason": "safety"},
        0,
        "cmd_block",
    )

    assert report.event.event_type == "moderation.reported"
    assert report.entity["reporter_id"] == "ply_owner"
    assert report.entity["status"] == "open"
    assert block.event.event_type == "moderation.blocked"
    assert block.entity["blocker_id"] == "ply_owner"
    assert block.entity["active"] is True


def test_same_ids_and_command_ids_remain_realm_isolated(
    service: UniverseService,
) -> None:
    service.create_local_realm("ply_alpha", realm_id="rlm_alpha")
    service.create_local_realm("ply_beta", realm_id="rlm_beta")

    alpha = service.execute(
        "player.create",
        "ply_alpha",
        "rlm_alpha",
        {"id": "ply_shared", "display_name": "Alpha"},
        0,
        "cmd_shared_player",
    )
    beta = service.execute(
        "player.create",
        "ply_beta",
        "rlm_beta",
        {"id": "ply_shared", "display_name": "Beta"},
        0,
        "cmd_shared_player",
    )

    assert alpha.entity["realm_id"] == "rlm_alpha"
    assert beta.entity["realm_id"] == "rlm_beta"
    assert service.store.entity(
        "player", "ply_shared", realm_id="rlm_alpha"
    )["display_name"] == "Alpha"
    assert service.store.entity(
        "player", "ply_shared", realm_id="rlm_beta"
    )["display_name"] == "Beta"
    with pytest.raises(LookupError, match="multiple realms"):
        service.store.entity("player", "ply_shared")
    assert {
        event.realm_id for event in service.store.events_since("rlm_alpha", 0)
    } == {"rlm_alpha"}
    assert {
        event.realm_id for event in service.store.events_since("rlm_beta", 0)
    } == {"rlm_beta"}
