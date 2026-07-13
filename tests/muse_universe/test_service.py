from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import hashlib
from threading import Barrier

import pytest

from plugins.muse_universe.authorization import AuthorizationError
from plugins.muse_universe.catalog import (
    ATLAS_CROWN,
    COOP_ROLES,
    MODULES,
    OPTIONAL_CLASS_ROOMS,
    PLAYER_MODES,
    REQUIRED_ROOMS,
    STATIONS,
    VESSEL_CLASSES,
)
from plugins.muse_universe.service import (
    COMMANDS,
    VALIDATORS,
    UniverseService,
    ValidationError,
)
from plugins.muse_universe.models import (
    AuthorizationDecision,
    ProvenanceRecord,
    UniverseCommand,
)


def _public_metadata() -> dict[str, object]:
    return {
        "content_hash": "sha256:" + "a" * 64,
        "license": "MUSE-ORIGINAL-1.0",
        "provenance": {"source": "owner", "evidence": ["source:1"]},
        "verification": {"status": "passed", "evidence": ["scan:1"]},
        "moderation": {"status": "approved", "case_id": "mod_1"},
    }


def _vessel_payload(vessel_id: str = "vsl_owner") -> dict[str, object]:
    return {
        "id": vessel_id,
        "owner_id": "ply_owner",
        "vessel_class": "flagship",
        "rooms": [room for room in REQUIRED_ROOMS if room != "governance_chamber"],
        "attachment_points": ["sensor_spine", "release_dock", "utility_bay"],
        "budgets": {"power": 100.0, "heat": 100.0, "compute": 100.0, "context": 100.0},
        "installed_modules": [],
        "path_reachable": True,
        "allowed_licenses": ["MUSE-ORIGINAL-1.0"],
    }


def _expected_internal_command_id(purpose: str, external_command_id: str) -> str:
    digest = hashlib.sha256(external_command_id.encode("utf-8")).hexdigest()
    return f"__muse_internal__:{purpose}:{digest}"


def test_catalog_preserves_cross_runtime_contract_and_is_immutable(
    service: UniverseService,
) -> None:
    assert ATLAS_CROWN["id"] == "atlas_crown"
    assert tuple(station["id"] for station in STATIONS) == (
        "neural_shipyard",
        "deep_observatory",
        "fabrication_foundry",
        "cinema_array",
        "game_foundry",
        "memory_archive",
        "quarantine_moon",
        "relay_embassy",
        "academy_station",
        "blueprint_exchange",
        "release_dock",
    )
    assert VESSEL_CLASSES == (
        "scout",
        "surveyor",
        "forge",
        "director",
        "carrier",
        "diplomat",
        "sentinel",
        "courier",
        "flagship",
    )
    assert PLAYER_MODES == ("walk", "pilot", "fleet", "director")
    assert "governance_chamber" in REQUIRED_ROOMS
    assert len(REQUIRED_ROOMS) == 9
    assert "render_chamber" in OPTIONAL_CLASS_ROOMS
    assert "captain" in COOP_ROLES
    assert set(MODULES["mod_sensor_research"]) >= {
        "id",
        "type",
        "attachment_types",
        "requires",
        "conflicts",
        "capabilities",
        "power",
        "heat",
        "compute",
        "context",
        "cost_class",
        "trust_exposure",
        "license",
    }
    with pytest.raises(TypeError):
        MODULES["mod_sensor_research"]["power"] = 0

    first = service.catalog()
    first["player_modes"].append("forged")
    assert "forged" not in service.catalog()["player_modes"]


def test_every_explicit_command_has_its_own_validator() -> None:
    assert set(VALIDATORS) == set(COMMANDS)
    assert len(set(VALIDATORS.values())) == len(COMMANDS)
    validators = {
        command: getattr(UniverseService, name, None)
        for command, name in VALIDATORS.items()
    }
    assert all(callable(validator) for validator in validators.values())
    assert len(set(validators.values())) == len(COMMANDS)
    assert all(
        validator is getattr(UniverseService, VALIDATORS[command])
        for command, validator in validators.items()
    )


def test_station_create_rejects_atlas_crown_as_network_station(
    service: UniverseService,
) -> None:
    service.create_local_realm("ply_owner")
    with pytest.raises(ValidationError, match="network"):
        service.execute(
            "station.create",
            "ply_owner",
            "rlm_local",
            {
                "id": "stn_atlas",
                "station_type": "atlas_crown",
                "owner_id": "ply_owner",
                "rooms": ["governance_chamber"],
            },
            0,
            "cmd_atlas_station",
        )


def test_operational_and_creator_ledgers_never_mix(
    service: UniverseService,
) -> None:
    service.create_local_realm("ply_owner")
    service.execute(
        "operational_ledger.record",
        "ply_owner",
        "rlm_local",
        {"id": "op_1", "provider": "local", "compute_seconds": 2, "cost_usd": 0.0},
        0,
        "cmd_op",
    )
    service.execute(
        "creator_ledger.record",
        "ply_owner",
        "rlm_local",
        {"id": "cr_1", "asset_id": "ast_1", "owner_id": "ply_owner", "quantity": 1},
        0,
        "cmd_cr",
    )
    snapshot = service.snapshot("ply_owner", "rlm_local")
    assert snapshot["operational_ledgers"][0]["id"] == "op_1"
    assert snapshot["creator_ledgers"][0]["id"] == "cr_1"
    with pytest.raises(ValidationError, match="operational"):
        service.execute(
            "creator_ledger.record",
            "ply_owner",
            "rlm_local",
            {"id": "cr_bad", "asset_id": "ast_1", "quantity": 1, "cost_usd": 5},
            0,
            "cmd_cr_bad",
        )


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf"), True])
def test_workspace_cost_rejects_non_finite_and_boolean_values_before_approval(
    service: UniverseService, approval_verifier, value: object
) -> None:
    service.create_local_realm("ply_owner")
    approval_verifier.allow("apr_workspace_numeric")

    with pytest.raises((AuthorizationError, ValidationError), match="numeric|finite"):
        service.execute(
            "workspace.lease",
            "ply_owner",
            "rlm_local",
            {
                "id": "wrk_numeric",
                "provider": "external",
                "project_id": "proj_1",
                "cost_usd": value,
                "expiry_utc": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
                "checkpoint": "chk_1",
                "signed_preview": "sha256:" + "b" * 64,
            },
            0,
            "cmd_workspace_numeric",
            approval_id="apr_workspace_numeric",
        )

    assert approval_verifier.calls == []


def test_nested_non_finite_payload_is_rejected_before_sensitive_approval(
    service: UniverseService, approval_verifier
) -> None:
    service.create_local_realm("ply_owner")
    approval_verifier.allow("apr_workspace_nested_numeric")

    with pytest.raises(ValueError, match="non-finite"):
        service.execute(
            "workspace.lease",
            "ply_owner",
            "rlm_local",
            {
                "id": "wrk_nested_numeric",
                "provider": "external",
                "project_id": "proj_1",
                "cost_usd": 1.0,
                "expiry_utc": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
                "checkpoint": "chk_1",
                "signed_preview": "sha256:" + "b" * 64,
                "telemetry": {"ratio": float("nan")},
            },
            0,
            "cmd_workspace_nested_numeric",
            approval_id="apr_workspace_nested_numeric",
        )

    assert approval_verifier.calls == []


@pytest.mark.parametrize(
    "quantity",
    [float("nan"), float("inf"), float("-inf"), True, 0, -1],
)
def test_creator_quantities_are_finite_positive_numbers(
    service: UniverseService, quantity: object
) -> None:
    service.create_local_realm("ply_owner")

    with pytest.raises(ValidationError, match="numeric|finite|positive"):
        service.execute(
            "creator_ledger.record",
            "ply_owner",
            "rlm_local",
            {
                "id": "cr_numeric",
                "asset_id": "ast_1",
                "owner_id": "ply_owner",
                "quantity": quantity,
            },
            0,
            "cmd_creator_numeric",
        )


def test_creator_transfer_non_finite_quantity_cannot_bypass_balance(
    service: UniverseService,
) -> None:
    service.create_local_realm("ply_owner")
    service.execute(
        "creator_ledger.record",
        "ply_owner",
        "rlm_local",
        {"id": "cr_seed", "asset_id": "ast_1", "owner_id": "ply_owner", "quantity": 1},
        0,
        "cmd_seed",
    )

    with pytest.raises(ValidationError, match="finite"):
        service.execute(
            "creator_ledger.transfer",
            "ply_owner",
            "rlm_local",
            {
                "id": "cr_transfer_nan",
                "asset_id": "ast_1",
                "from_id": "ply_owner",
                "to_id": "ply_other",
                "quantity": float("nan"),
            },
            0,
            "cmd_transfer_nan",
        )


def test_public_blueprint_requires_rights_verification_and_moderation(
    service: UniverseService, approval_verifier
) -> None:
    service.create_local_realm("ply_owner")
    with pytest.raises(ValidationError, match="asset"):
        service.execute(
            "blueprint.publish",
            "ply_owner",
            "rlm_local",
            {
                "id": "bp_1",
                "asset_id": "ast_missing",
                "visibility": "public",
            },
            0,
            "cmd_bp",
        )
    approval_verifier.allow("apr_asset")
    service.execute(
        "asset.register",
        "ply_owner",
        "rlm_local",
        {"id": "ast_1", **_public_metadata()},
        0,
        "cmd_asset",
        approval_id="apr_asset",
    )
    with pytest.raises(AuthorizationError, match="approval"):
        service.execute(
            "blueprint.publish",
            "ply_owner",
            "rlm_local",
            {"id": "bp_2", "asset_id": "ast_1", "visibility": "public"},
            0,
            "cmd_bp_2",
        )


def test_creator_assets_always_require_rights_and_provenance(
    service: UniverseService,
) -> None:
    service.create_local_realm("ply_owner")
    for missing in ("license", "content_hash", "provenance", "verification", "moderation"):
        payload = {"id": f"ast_{missing}", **_public_metadata()}
        payload.pop(missing)
        with pytest.raises(ValidationError, match=missing):
            service.execute(
                "asset.register",
                "ply_owner",
                "rlm_local",
                payload,
                0,
                f"cmd_{missing}",
            )


def test_asset_registration_requires_bound_owner_approval(
    service: UniverseService,
) -> None:
    service.create_local_realm("ply_owner")
    with pytest.raises(AuthorizationError, match="approval"):
        service.execute(
            "asset.register",
            "ply_owner",
            "rlm_local",
            {"id": "ast_1", **_public_metadata()},
            0,
            "cmd_asset",
        )


def test_registered_asset_rights_are_immutable(
    service: UniverseService, approval_verifier
) -> None:
    service.create_local_realm("ply_owner")
    approval_verifier.allow("apr_asset_initial")
    service.execute(
        "asset.register",
        "ply_owner",
        "rlm_local",
        {"id": "ast_immutable", **_public_metadata()},
        0,
        "cmd_asset_initial",
        approval_id="apr_asset_initial",
    )
    approval_verifier.allow("apr_asset_replace")
    with pytest.raises(ValidationError, match="immutable"):
        service.execute(
            "asset.register",
            "ply_owner",
            "rlm_local",
            {
                "id": "ast_immutable",
                **{
                    **_public_metadata(),
                    "content_hash": "sha256:" + "b" * 64,
                },
            },
            1,
            "cmd_asset_replace",
            approval_id="apr_asset_replace",
        )


def test_publication_uses_stored_asset_rights_not_forged_payload(
    service: UniverseService, approval_verifier
) -> None:
    service.create_local_realm("ply_owner")
    approval_verifier.allow("apr_asset")
    asset = service.execute(
        "asset.register",
        "ply_owner",
        "rlm_local",
        {"id": "ast_1", **_public_metadata()},
        0,
        "cmd_asset",
        approval_id="apr_asset",
    ).entity
    assert asset["owner_id"] == "ply_owner"
    approval_verifier.allow("apr_blueprint")
    with pytest.raises(ValidationError, match="stored rights"):
        service.execute(
            "blueprint.publish",
            "ply_owner",
            "rlm_local",
            {
                "id": "bp_forged",
                "asset_id": "ast_1",
                "visibility": "public",
                "license": "FORGED",
                "content_hash": "sha256:" + "b" * 64,
                "provenance": {"source": "forged", "evidence": ["forged"]},
                "verification": {"status": "passed"},
                "moderation": {"status": "approved"},
            },
            0,
            "cmd_blueprint_forged",
            approval_id="apr_blueprint",
        )


@pytest.mark.parametrize(
    ("command_type", "payload"),
    [
        (
            "blueprint.publish",
            {"id": "bp_missing", "asset_id": "ast_missing", "visibility": "private"},
        ),
        (
            "gallery.publish",
            {"id": "gal_missing", "asset_id": "ast_missing", "visibility": "private"},
        ),
        (
            "release.stage",
            {
                "id": "rel_missing",
                "artifact_id": "ast_missing",
                "content_hash": "sha256:" + "a" * 64,
                "target": "preview",
                "verification": {"status": "passed", "evidence": ["test:1"]},
                "rollback": {"release_id": "rel_previous"},
            },
        ),
    ],
)
def test_publication_and_release_reject_nonexistent_assets(
    service: UniverseService, command_type: str, payload: dict[str, object]
) -> None:
    service.create_local_realm("ply_owner")
    with pytest.raises(ValidationError, match="asset"):
        service.execute(
            command_type,
            "ply_owner",
            "rlm_local",
            payload,
            0,
            f"cmd_{command_type}_missing",
        )


def test_cross_owner_asset_publication_is_rejected(
    service: UniverseService, approval_verifier
) -> None:
    service.create_local_realm("ply_owner")
    approval_verifier.allow("apr_asset")
    service.execute(
        "asset.register",
        "ply_owner",
        "rlm_local",
        {"id": "ast_owner", **_public_metadata()},
        0,
        "cmd_asset_owner",
        approval_id="apr_asset",
    )
    service.execute(
        "civilization.create",
        "ply_owner",
        "rlm_local",
        {"id": "civ_1", "name": "Civ", "charter": "Safe", "governance": {"quorum": 1}},
        0,
        "cmd_civ",
    )
    service.execute(
        "membership.invite",
        "ply_owner",
        "rlm_local",
        {
            "id": "mem_guest",
            "player_id": "ply_guest",
            "civilization_id": "civ_1",
            "scopes": ["blueprint:publish"],
        },
        0,
        "cmd_invite",
    )
    service.execute(
        "membership.accept",
        "ply_guest",
        "rlm_local",
        {"id": "mem_guest"},
        1,
        "cmd_accept",
    )
    with pytest.raises(AuthorizationError, match="owner"):
        service.execute(
            "blueprint.publish",
            "ply_guest",
            "rlm_local",
            {"id": "bp_stolen", "asset_id": "ast_owner", "visibility": "private"},
            0,
            "cmd_bp_stolen",
        )


def test_presence_enforces_identity_sequence_rate_and_privacy(tmp_path) -> None:
    from plugins.muse_universe.store import UniverseStore

    now = [100.0]
    service = UniverseService(UniverseStore(tmp_path / "presence.db"), clock=lambda: now[0])
    service.create_local_realm("ply_owner")
    service.execute(
        "presence.update",
        "ply_owner",
        "rlm_local",
        {"id": "ply_owner", "sequence": 1, "status": "online", "visibility": "private"},
        0,
        "cmd_presence_1",
    )
    with pytest.raises(ValidationError, match="rate"):
        service.execute(
            "presence.update",
            "ply_owner",
            "rlm_local",
            {"id": "ply_owner", "sequence": 2, "status": "online"},
            1,
            "cmd_presence_fast",
        )
    now[0] += 1.0
    with pytest.raises(ValidationError, match="sequence"):
        service.execute(
            "presence.update",
            "ply_owner",
            "rlm_local",
            {"id": "ply_owner", "sequence": 1, "status": "online"},
            1,
            "cmd_presence_replay",
        )
    with pytest.raises(ValidationError, match="authoritative"):
        service.execute(
            "presence.update",
            "ply_owner",
            "rlm_local",
            {"id": "ply_owner", "sequence": 2, "inventory": ["admin-key"]},
            1,
            "cmd_presence_inventory",
        )


def test_presence_snapshot_is_caller_aware_and_public_is_minimal(
    service: UniverseService,
) -> None:
    service.presence_min_interval = 0
    service.create_local_realm("ply_owner")
    for civilization_id in ("civ_1", "civ_2"):
        service.execute(
            "civilization.create",
            "ply_owner",
            "rlm_local",
            {
                "id": civilization_id,
                "name": civilization_id,
                "charter": "Safe",
                "governance": {"quorum": 1},
            },
            0,
            f"cmd_{civilization_id}",
        )
    for player_id, civilization_id in (
        ("ply_private", "civ_1"),
        ("ply_crew", "civ_1"),
        ("ply_other", "civ_2"),
    ):
        service.execute(
            "membership.invite",
            "ply_owner",
            "rlm_local",
            {
                "id": f"mem_{player_id}",
                "player_id": player_id,
                "civilization_id": civilization_id,
                "scopes": ["presence:write"],
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
    service.execute(
        "presence.update",
        "ply_private",
        "rlm_local",
        {
            "id": "ply_private",
            "sequence": 1,
            "status": "online",
            "visibility": "private",
            "position": [1, 2, 3],
        },
        0,
        "cmd_private",
    )
    service.execute(
        "presence.update",
        "ply_crew",
        "rlm_local",
        {
            "id": "ply_crew",
            "sequence": 1,
            "status": "online",
            "visibility": "crew",
            "position": [4, 5, 6],
        },
        0,
        "cmd_crew",
    )
    service.execute(
        "presence.update",
        "ply_other",
        "rlm_local",
        {
            "id": "ply_other",
            "sequence": 1,
            "status": "online",
            "visibility": "public",
            "position": [7, 8, 9],
        },
        0,
        "cmd_public",
    )

    with pytest.raises(AuthorizationError, match="caller"):
        service.snapshot(None, "rlm_local")

    crew_view = service.snapshot("ply_private", "rlm_local")["presences"]
    assert {presence["id"] for presence in crew_view} == {
        "ply_private",
        "ply_crew",
        "ply_other",
    }
    other_view = service.snapshot("ply_other", "rlm_local")["presences"]
    assert "ply_private" not in {presence["id"] for presence in other_view}
    assert "ply_crew" not in {presence["id"] for presence in other_view}
    public = next(presence for presence in other_view if presence["id"] == "ply_other")
    assert set(public) == {"id", "status", "visibility", "mode"}
    owner_view = service.snapshot("ply_owner", "rlm_local")["presences"]
    assert {presence["id"] for presence in owner_view} == {
        "ply_private",
        "ply_crew",
        "ply_other",
    }
    assert service.snapshot_for("ply_private", "rlm_local") == service.snapshot(
        "ply_private", "rlm_local"
    )
    with pytest.raises(AuthorizationError, match="caller"):
        service.entity(None, "presence", "ply_private", "rlm_local")
    assert (
        service.entity("ply_other", "presence", "ply_private", "rlm_local")
        is None
    )
    crew_presence = service.entity(
        "ply_private", "presence", "ply_crew", "rlm_local"
    )
    assert crew_presence is not None
    assert set(crew_presence) == {"id", "status", "visibility", "mode"}
    owner_presence = service.entity(
        "ply_owner", "presence", "ply_private", "rlm_local"
    )
    assert owner_presence is not None
    assert "sequence" in owner_presence


def test_governance_rejects_duplicate_and_late_votes(
    service: UniverseService,
) -> None:
    service.create_local_realm("ply_owner")
    service.execute(
        "civilization.create",
        "ply_owner",
        "rlm_local",
        {"id": "civ_1", "name": "Civ", "charter": "Safe", "governance": {"quorum": 1}},
        0,
        "cmd_civ",
    )
    deadline = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    service.execute(
        "governance.propose",
        "ply_owner",
        "rlm_local",
        {
            "id": "prop_1",
            "civilization_id": "civ_1",
            "title": "Build",
            "action": {"type": "station.create"},
            "deadline_utc": deadline,
        },
        0,
        "cmd_prop",
    )
    service.execute(
        "governance.vote",
        "ply_owner",
        "rlm_local",
        {"proposal_id": "prop_1", "choice": "yes"},
        1,
        "cmd_vote",
    )
    with pytest.raises(ValidationError, match="duplicate"):
        service.execute(
            "governance.vote",
            "ply_owner",
            "rlm_local",
            {"proposal_id": "prop_1", "choice": "no"},
            2,
            "cmd_vote_again",
        )


def test_governance_vote_requires_membership_in_the_proposal_civilization(
    service: UniverseService,
) -> None:
    service.create_local_realm("ply_owner")
    for civilization_id in ("civ_1", "civ_2"):
        service.execute(
            "civilization.create",
            "ply_owner",
            "rlm_local",
            {
                "id": civilization_id,
                "name": civilization_id,
                "charter": "Safe",
                "governance": {"quorum": 1},
            },
            0,
            f"cmd_{civilization_id}",
        )
    service.execute(
        "membership.invite",
        "ply_owner",
        "rlm_local",
        {
            "id": "mem_voter",
            "player_id": "ply_voter",
            "civilization_id": "civ_2",
            "scopes": ["governance:vote"],
        },
        0,
        "cmd_invite_voter",
    )
    service.execute(
        "membership.accept",
        "ply_voter",
        "rlm_local",
        {"id": "mem_voter"},
        1,
        "cmd_accept_voter",
    )
    service.execute(
        "governance.propose",
        "ply_owner",
        "rlm_local",
        {
            "id": "prop_1",
            "civilization_id": "civ_1",
            "title": "Build",
            "action": {"type": "station.create"},
            "deadline_utc": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        },
        0,
        "cmd_prop",
    )
    with pytest.raises(AuthorizationError, match="civilization"):
        service.execute(
            "governance.vote",
            "ply_voter",
            "rlm_local",
            {"proposal_id": "prop_1", "choice": "yes"},
            1,
            "cmd_wrong_civ_vote",
        )


def test_governance_propose_and_execute_require_exact_civilization_membership(
    service: UniverseService,
) -> None:
    service.create_local_realm("ply_owner")
    for civilization_id in ("civ_1", "civ_2"):
        service.execute(
            "civilization.create",
            "ply_owner",
            "rlm_local",
            {
                "id": civilization_id,
                "name": civilization_id,
                "charter": "Safe",
                "governance": {"quorum": 1},
            },
            0,
            f"cmd_{civilization_id}",
        )
    service.execute(
        "membership.invite",
        "ply_owner",
        "rlm_local",
        {
            "id": "mem_governor",
            "player_id": "ply_governor",
            "civilization_id": "civ_2",
            "scopes": ["governance:propose", "governance:execute"],
        },
        0,
        "cmd_invite_governor",
    )
    service.execute(
        "membership.accept",
        "ply_governor",
        "rlm_local",
        {"id": "mem_governor"},
        1,
        "cmd_accept_governor",
    )
    proposal = {
        "id": "prop_1",
        "civilization_id": "civ_1",
        "title": "Build",
        "action": {"type": "station.create"},
        "deadline_utc": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
    }
    with pytest.raises(AuthorizationError, match="civilization"):
        service.execute(
            "governance.propose",
            "ply_governor",
            "rlm_local",
            proposal,
            0,
            "cmd_wrong_civ_proposal",
        )
    service.execute(
        "governance.propose",
        "ply_owner",
        "rlm_local",
        proposal,
        0,
        "cmd_owner_proposal",
    )
    with pytest.raises(AuthorizationError, match="civilization"):
        service.execute(
            "governance.execute",
            "ply_governor",
            "rlm_local",
            {"proposal_id": "prop_1"},
            1,
            "cmd_wrong_civ_execute",
        )


def test_world_freeze_regeneration_and_shared_building_budgets(
    service: UniverseService,
) -> None:
    service.create_local_realm("ply_owner")
    service.execute(
        "world.create",
        "ply_owner",
        "rlm_local",
        {
            "id": "wld_1",
            "owner_id": "ply_owner",
            "regions": ["north", "south"],
            "performance_budget": {"triangles": 1000, "draw_calls": 20},
            "navigation": {"minimum_clearance": 2.0},
        },
        0,
        "cmd_world",
    )
    service.execute(
        "world.region.freeze",
        "ply_owner",
        "rlm_local",
        {"world_id": "wld_1", "region_id": "north"},
        1,
        "cmd_freeze",
    )
    with pytest.raises(ValidationError, match="frozen"):
        service.execute(
            "world.region.regenerate",
            "ply_owner",
            "rlm_local",
            {"world_id": "wld_1", "region_id": "north", "recipe": {"density": 0.8}},
            2,
            "cmd_regen",
        )
    with pytest.raises(ValidationError, match="performance"):
        service.execute(
            "building.place",
            "ply_owner",
            "rlm_local",
            {
                "id": "bld_1",
                "world_id": "wld_1",
                "owner_id": "ply_owner",
                "expected_world_version": 2,
                "region_id": "south",
                "collision_valid": True,
                "navigation_clearance": 2.0,
                "performance_cost": {"triangles": 1001, "draw_calls": 1},
            },
            0,
            "cmd_build",
        )


def test_shared_building_requires_active_civilization_ownership_scope(
    service: UniverseService,
) -> None:
    service.create_local_realm("ply_owner")
    service.execute(
        "civilization.create",
        "ply_owner",
        "rlm_local",
        {"id": "civ_1", "name": "Civ", "charter": "Shared", "governance": {"quorum": 1}},
        0,
        "cmd_civ",
    )
    service.execute(
        "membership.invite",
        "ply_owner",
        "rlm_local",
        {"id": "mem_builder", "player_id": "ply_builder", "civilization_id": "civ_1", "scopes": ["building:write"]},
        0,
        "cmd_invite_builder",
    )
    service.execute(
        "membership.accept",
        "ply_builder",
        "rlm_local",
        {"id": "mem_builder"},
        1,
        "cmd_accept_builder",
    )
    service.execute(
        "world.create",
        "ply_owner",
        "rlm_local",
        {
            "id": "wld_shared",
            "owner_id": "ply_owner",
            "regions": ["shared"],
            "performance_budget": {"triangles": 1000, "draw_calls": 20},
            "navigation": {"minimum_clearance": 2.0},
        },
        0,
        "cmd_shared_world",
    )
    result = service.execute(
        "building.place",
        "ply_builder",
        "rlm_local",
        {
                "id": "bld_shared",
                "world_id": "wld_shared",
                "owner_id": "civ_1",
                "expected_world_version": 1,
                "region_id": "shared",
                "transform": {"position": [2, 2, 2]},
                "collision": {"radius": 1.0},
                "navigation_clearance": 2.0,
            "performance_cost": {"triangles": 100, "draw_calls": 2},
        },
        0,
        "cmd_shared_build",
    )
    assert result.entity["owner_id"] == "civ_1"


@pytest.mark.parametrize(
    ("world_simulation", "placement_simulation"),
    [(True, False), (False, True)],
)
def test_building_placement_cannot_cross_world_projection_mode(
    service: UniverseService,
    world_simulation: bool,
    placement_simulation: bool,
) -> None:
    service.create_local_realm("ply_owner")
    service.execute(
        "world.create",
        "ply_owner",
        "rlm_local",
        {
            "id": "wld_mode",
            "owner_id": "ply_owner",
            "regions": ["buildable"],
            "performance_budget": {"triangles": 100, "draw_calls": 10},
            "navigation": {"minimum_clearance": 1.0},
        },
        0,
        "cmd_world_mode",
        simulation=world_simulation,
    )

    with pytest.raises(AuthorizationError, match="simulation"):
        service.execute(
            "building.place",
            "ply_owner",
            "rlm_local",
            {
                "id": "bld_mode",
                "world_id": "wld_mode",
                "owner_id": "ply_owner",
                "expected_world_version": 1,
                "region_id": "buildable",
                "transform": {"position": [2, 2, 2]},
                "collision": {"radius": 1.0},
                "navigation_clearance": 1.0,
                "performance_cost": {"triangles": 1, "draw_calls": 1},
            },
            0,
            "cmd_build_mode",
            simulation=placement_simulation,
        )

    world = service.entity("ply_owner", "world", "wld_mode", "rlm_local")
    assert world is not None
    assert world["simulation"] is world_simulation
    assert world["version"] == 1


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("budget", float("nan")),
        ("budget", float("inf")),
        ("bounds", float("inf")),
        ("bounds", float("nan")),
    ],
)
def test_world_geometry_and_budgets_reject_non_finite_values(
    service: UniverseService, field: str, value: float
) -> None:
    service.create_local_realm("ply_owner")
    payload: dict[str, object] = {
        "id": "wld_numeric",
        "owner_id": "ply_owner",
        "regions": ["buildable"],
        "performance_budget": {"triangles": 100, "draw_calls": 10},
        "navigation": {"minimum_clearance": 1.0},
    }
    if field == "budget":
        payload["performance_budget"] = {"triangles": value, "draw_calls": 10}
    else:
        payload["bounds"] = {"min": [0, 0, 0], "max": [value, 10, 10]}

    with pytest.raises(ValidationError, match="finite"):
        service.execute(
            "world.create",
            "ply_owner",
            "rlm_local",
            payload,
            0,
            "cmd_world_numeric",
        )


def test_building_cost_cannot_be_negative(
    service: UniverseService,
) -> None:
    service.create_local_realm("ply_owner")
    service.execute(
        "world.create",
        "ply_owner",
        "rlm_local",
        {
            "id": "wld_cost",
            "owner_id": "ply_owner",
            "regions": ["buildable"],
            "performance_budget": {"triangles": 100, "draw_calls": 10},
            "navigation": {"minimum_clearance": 1.0},
        },
        0,
        "cmd_world_cost",
    )

    with pytest.raises(ValidationError, match="cost"):
        service.execute(
            "building.place",
            "ply_owner",
            "rlm_local",
            {
                "id": "bld_negative_cost",
                "world_id": "wld_cost",
                "owner_id": "ply_owner",
                "expected_world_version": 1,
                "region_id": "buildable",
                "transform": {"position": [2, 2, 2]},
                "collision": {"radius": 1.0},
                "navigation_clearance": 1.0,
                "performance_cost": {"triangles": -1, "draw_calls": 1},
            },
            0,
            "cmd_build_negative_cost",
        )


def test_building_related_command_id_cannot_be_preempted_by_user_input(
    service: UniverseService,
) -> None:
    service.create_local_realm("ply_owner")
    external_command_id = "cmd_build_reserved"
    related_command_id = _expected_internal_command_id(
        "building-world", external_command_id
    )
    with pytest.raises(ValidationError, match="reserved"):
        service.execute(
            "player.create",
            "ply_owner",
            "rlm_local",
            {"id": "ply_preempt", "display_name": "Preempt"},
            0,
            related_command_id,
        )

    service.execute(
        "world.create",
        "ply_owner",
        "rlm_local",
        {
            "id": "wld_reserved",
            "owner_id": "ply_owner",
            "regions": ["buildable"],
            "performance_budget": {"triangles": 100, "draw_calls": 10},
            "navigation": {"minimum_clearance": 1.0},
        },
        0,
        "cmd_world_reserved",
    )
    service.execute(
        "building.place",
        "ply_owner",
        "rlm_local",
        {
            "id": "bld_reserved",
            "world_id": "wld_reserved",
            "owner_id": "ply_owner",
            "expected_world_version": 1,
            "region_id": "buildable",
            "transform": {"position": [2, 2, 2]},
            "collision": {"radius": 1.0},
            "navigation_clearance": 1.0,
            "performance_cost": {"triangles": 1, "draw_calls": 1},
        },
        0,
        external_command_id,
    )

    related = service.store.command_result("rlm_local", related_command_id)
    assert related is not None
    assert related.event.stream_type == "world"
    assert related.event.correlation_id == external_command_id


def test_vessel_module_checks_compatibility_budgets_path_license_and_approval(
    service: UniverseService, approval_verifier
) -> None:
    service.create_local_realm("ply_owner")
    service.execute(
        "vessel.create",
        "ply_owner",
        "rlm_local",
        _vessel_payload(),
        0,
        "cmd_vessel",
    )
    approval_verifier.allow("apr_module")
    service.execute(
        "vessel.module.install",
        "ply_owner",
        "rlm_local",
        {"vessel_id": "vsl_owner", "module_id": "mod_sensor_research", "attachment_type": "sensor_spine"},
        1,
        "cmd_module",
        approval_id="apr_module",
    )
    vessel = service.entity("ply_owner", "vessel", "vsl_owner", "rlm_local")
    assert vessel is not None
    assert vessel["installed_modules"] == ["mod_sensor_research"]

    service.execute(
        "vessel.create",
        "ply_owner",
        "rlm_local",
        {**_vessel_payload("vsl_blocked"), "path_reachable": False},
        0,
        "cmd_blocked_vessel",
    )
    with pytest.raises(ValidationError, match="path"):
        service.execute(
            "vessel.module.install",
            "ply_owner",
            "rlm_local",
            {"vessel_id": "vsl_blocked", "module_id": "mod_sensor_research", "attachment_type": "sensor_spine"},
            1,
            "cmd_blocked_module",
            approval_id="apr_module",
        )


def test_vessel_creation_rejects_client_installed_modules(
    service: UniverseService,
) -> None:
    service.create_local_realm("ply_owner")
    with pytest.raises(ValidationError, match="installed_modules"):
        service.execute(
            "vessel.create",
            "ply_owner",
            "rlm_local",
            {**_vessel_payload(), "installed_modules": ["mod_sensor_research"]},
            0,
            "cmd_vessel_with_module",
        )


@pytest.mark.parametrize(
    ("command_type", "payload"),
    [
        (
            "operational_ledger.record",
            {
                "id": "op_sim",
                "provider": "local",
                "compute_seconds": 1,
                "cost_usd": 0.0,
            },
        ),
        (
            "asset.register",
            {"id": "ast_sim", **_public_metadata()},
        ),
        (
            "release.stage",
            {
                "id": "rel_sim",
                "artifact_id": "ast_sim",
                "content_hash": "sha256:" + "a" * 64,
                "target": "production",
                "verification": {"status": "passed", "evidence": ["test:1"]},
                "rollback": {"release_id": "rel_previous"},
            },
        ),
        (
            "creator_ledger.record",
            {
                "id": "cr_sim",
                "asset_id": "ast_1",
                "owner_id": "ply_owner",
                "quantity": 1,
            },
        ),
        (
            "creator_ledger.transfer",
            {
                "id": "cr_sim_transfer",
                "asset_id": "ast_1",
                "from_id": "ply_owner",
                "to_id": "ply_other",
                "quantity": 1,
            },
        ),
    ],
)
def test_simulation_cannot_execute_real_effect_commands(
    service: UniverseService, command_type: str, payload: dict[str, object]
) -> None:
    service.create_local_realm("ply_owner")
    with pytest.raises(AuthorizationError, match="simulation"):
        service.execute(
            command_type,
            "ply_owner",
            "rlm_local",
            payload,
            0,
            f"cmd_{command_type}",
            simulation=True,
        )


def test_simulation_cannot_install_capability_module(
    service: UniverseService, approval_verifier
) -> None:
    service.create_local_realm("ply_owner")
    service.execute(
        "vessel.create",
        "ply_owner",
        "rlm_local",
        _vessel_payload("vsl_sim"),
        0,
        "cmd_sim_vessel",
        simulation=True,
    )
    approval_verifier.allow("apr_sim_module")
    with pytest.raises(AuthorizationError, match="simulation"):
        service.execute(
            "vessel.module.install",
            "ply_owner",
            "rlm_local",
            {
                "vessel_id": "vsl_sim",
                "module_id": "mod_sensor_research",
                "attachment_type": "sensor_spine",
            },
            1,
            "cmd_sim_module",
            approval_id="apr_sim_module",
            simulation=True,
        )


def test_real_promotion_rejects_simulation_release_projection(
    service: UniverseService, approval_verifier
) -> None:
    service.create_local_realm("ply_owner")
    service.store.append(
        UniverseCommand(
            command_id="seed_sim_release",
            command_type="release.stage",
            realm_id="rlm_local",
            actor_id="ply_owner",
            stream_type="release",
            stream_id="rel_sim",
            expected_version=0,
            payload={
                "id": "rel_sim",
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
            causation_id="seed_sim_release",
            correlation_id="seed_sim_release",
            simulation=True,
        ),
        "release.staged",
    )
    approval_verifier.allow("apr_real_promote")
    with pytest.raises(AuthorizationError, match="simulation"):
        service.execute(
            "release.promote",
            "ply_owner",
            "rlm_local",
            {"release_id": "rel_sim", "target": "production"},
            1,
            "cmd_real_promote",
            approval_id="apr_real_promote",
        )


def test_mission_state_machine_stores_only_real_or_labeled_simulation_evidence(
    service: UniverseService,
) -> None:
    service.create_local_realm("ply_owner")
    service.execute(
        "mission.create",
        "ply_owner",
        "rlm_local",
        {"id": "mis_1", "source_type": "kanban", "source_id": "task_1", "mode": "real"},
        0,
        "cmd_mission",
    )
    with pytest.raises(ValidationError, match="transition"):
        service.execute(
            "mission.transition",
            "ply_owner",
            "rlm_local",
            {"mission_id": "mis_1", "to_state": "completed", "evidence": ["run:1"]},
            1,
            "cmd_skip",
        )
    service.execute(
        "mission.transition",
        "ply_owner",
        "rlm_local",
        {"mission_id": "mis_1", "to_state": "planned"},
        1,
        "cmd_plan",
    )
    service.execute(
        "mission.transition",
        "ply_owner",
        "rlm_local",
        {"mission_id": "mis_1", "to_state": "active"},
        2,
        "cmd_start",
    )
    result = service.execute(
        "mission.transition",
        "ply_owner",
        "rlm_local",
        {"mission_id": "mis_1", "to_state": "completed", "evidence": ["test:passed"]},
        3,
        "cmd_complete",
    )
    assert result.entity["evidence"] == ("test:passed",)


def test_forged_achievement_is_ignored_and_progression_never_gates_operations(
    tmp_path,
) -> None:
    from plugins.muse_universe.achievements import AchievementBridge
    from plugins.muse_universe.store import UniverseStore

    class EvidenceAdapter:
        def record(self, evidence: dict[str, object]) -> dict[str, str]:
            assert evidence["mission_id"] == "mis_1"
            return {
                "status": "accepted",
                "record_id": "external_1",
                "dedupe_key": "a" * 64,
            }

    service = UniverseService(
        UniverseStore(tmp_path / "achievements.db"),
        achievement_bridge=AchievementBridge(adapter=EvidenceAdapter(), enabled=True),
        progression_enabled=False,
    )
    service.create_local_realm("ply_owner")
    player = service.execute(
        "player.create",
        "ply_owner",
        "rlm_local",
        {"id": "ply_1", "display_name": "Player", "achievements": ["owner"], "tier": 999},
        0,
        "cmd_player",
    ).entity
    assert "achievements" not in player
    service.execute(
        "operational_ledger.record",
        "ply_owner",
        "rlm_local",
        {"id": "op_1", "provider": "local", "compute_seconds": 1, "cost_usd": 0.0},
        0,
        "cmd_operational",
    )


def test_evidence_bridge_persists_returned_reference_on_completed_mission(
    tmp_path,
) -> None:
    from plugins.muse_universe.achievements import AchievementBridge
    from plugins.muse_universe.store import UniverseStore

    calls: list[dict[str, object]] = []

    class EvidenceAdapter:
        def record(self, evidence: dict[str, object]) -> dict[str, str]:
            durable = store.entity("mission", "mis_1", "rlm_local")
            assert durable is not None
            assert durable["state"] == "completed"
            calls.append(evidence)
            return {
                "status": "accepted",
                "record_id": "external_1",
                "dedupe_key": "a" * 64,
            }

    store = UniverseStore(tmp_path / "evidence.db")
    service = UniverseService(
        store,
        achievement_bridge=AchievementBridge(adapter=EvidenceAdapter()),
    )
    service.create_local_realm("ply_owner")
    service.execute(
        "mission.create",
        "ply_owner",
        "rlm_local",
        {"id": "mis_1", "source_type": "kanban", "source_id": "task_1", "mode": "real"},
        0,
        "cmd_mission",
    )
    for expected_version, command_id, to_state in (
        (1, "cmd_plan", "planned"),
        (2, "cmd_start", "active"),
    ):
        service.execute(
            "mission.transition",
            "ply_owner",
            "rlm_local",
            {"mission_id": "mis_1", "to_state": to_state},
            expected_version,
            command_id,
        )
    receipt_command_id = _expected_internal_command_id(
        "achievement-evidence", "cmd_complete"
    )
    with pytest.raises(ValidationError, match="reserved"):
        service.execute(
            "player.create",
            "ply_owner",
            "rlm_local",
            {"id": "ply_receipt_preempt", "display_name": "Preempt"},
            0,
            receipt_command_id,
        )
    result = service.execute(
        "mission.transition",
        "ply_owner",
        "rlm_local",
        {"mission_id": "mis_1", "to_state": "completed", "evidence": ["test:passed"]},
        3,
        "cmd_complete",
    )
    assert "achievement_evidence_receipt" not in result.event.payload
    assert calls == [
        {
            "version": 1,
            "kind": "mission.completed",
            "producer": "muse_universe",
            "mission_id": "mis_1",
            "source_type": "kanban",
            "source_id": "task_1",
            "mode": "real",
            "evidence_references": ["test:passed"],
            "provenance": {
                "realm_id": "rlm_local",
                "command_id": "cmd_complete",
                "occurred_at": result.event.occurred_at,
            },
        }
    ]
    stored = service.entity("ply_owner", "mission", "mis_1", "rlm_local")
    assert stored is not None
    assert stored["achievement_evidence_receipt"] == {
        "status": "accepted",
        "record_id": "external_1",
        "dedupe_key": "a" * 64,
    }
    receipt_result = store.command_result("rlm_local", receipt_command_id)
    assert receipt_result is not None
    assert receipt_result.event.event_type == "mission.achievement_evidence_recorded"

    replay = service.execute(
        "mission.transition",
        "ply_owner",
        "rlm_local",
        {"mission_id": "mis_1", "to_state": "completed", "evidence": ["test:passed"]},
        3,
        "cmd_complete",
    )
    assert replay.idempotent_replay
    assert len(calls) == 1
    assert store.command_result("rlm_local", receipt_command_id) == receipt_result


def test_concurrent_exact_command_replay_returns_stored_result_before_revalidation(
    service: UniverseService, monkeypatch: pytest.MonkeyPatch
) -> None:
    service.create_local_realm("ply_owner")
    service.execute(
        "mission.create",
        "ply_owner",
        "rlm_local",
        {"id": "mis_race", "source_type": "kanban", "source_id": "task_race", "mode": "real"},
        0,
        "cmd_mission_race",
    )
    for expected_version, command_id, to_state in (
        (1, "cmd_plan_race", "planned"),
        (2, "cmd_start_race", "active"),
    ):
        service.execute(
            "mission.transition",
            "ply_owner",
            "rlm_local",
            {"mission_id": "mis_race", "to_state": to_state},
            expected_version,
            command_id,
        )

    barrier = Barrier(2)
    original_command_result = service.store.command_result

    def synchronized_command_result(realm_id: str, command_id: str):
        if command_id == "cmd_complete_race":
            result = original_command_result(realm_id, command_id)
            barrier.wait()
            return result
        return original_command_result(realm_id, command_id)

    monkeypatch.setattr(service.store, "command_result", synchronized_command_result)

    def complete():
        try:
            return service.execute(
                "mission.transition",
                "ply_owner",
                "rlm_local",
                {
                    "mission_id": "mis_race",
                    "to_state": "completed",
                    "evidence": ["test:race"],
                },
                3,
                "cmd_complete_race",
            )
        except Exception as exc:  # noqa: BLE001 - race result is asserted below
            return exc

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _index: complete(), range(2)))

    assert all(not isinstance(result, Exception) for result in results)
    assert sum(result.idempotent_replay for result in results) == 1
    assert results[0].event_id == results[1].event_id


def test_creator_transfer_and_refund_preserve_both_sides(
    service: UniverseService, approval_verifier
) -> None:
    service.create_local_realm("ply_owner")
    service.execute(
        "creator_ledger.record",
        "ply_owner",
        "rlm_local",
        {"id": "cr_seed", "asset_id": "ast_1", "owner_id": "ply_owner", "quantity": 5},
        0,
        "cmd_seed",
    )
    transfer = service.execute(
        "creator_ledger.transfer",
        "ply_owner",
        "rlm_local",
        {"id": "cr_transfer", "asset_id": "ast_1", "from_id": "ply_owner", "to_id": "ply_buyer", "quantity": 2},
        0,
        "cmd_transfer",
    ).entity
    assert transfer["entries"] == (
        {"owner_id": "ply_owner", "quantity": -2},
        {"owner_id": "ply_buyer", "quantity": 2},
    )
    approval_verifier.allow("apr_refund")
    refund = service.execute(
        "marketplace.refund",
        "ply_owner",
        "rlm_local",
        {"id": "cr_refund", "transfer_id": "cr_transfer", "reason": "requested"},
        0,
        "cmd_refund",
        approval_id="apr_refund",
    ).entity
    assert refund["entries"] == (
        {"owner_id": "ply_buyer", "quantity": -2},
        {"owner_id": "ply_owner", "quantity": 2},
    )
    approval_verifier.allow("apr_refund_again")
    with pytest.raises(ValidationError, match="already refunded"):
        service.execute(
            "marketplace.refund",
            "ply_owner",
            "rlm_local",
            {"id": "cr_refund_again", "transfer_id": "cr_transfer", "reason": "duplicate"},
            0,
            "cmd_refund_again",
            approval_id="apr_refund_again",
        )


def test_concurrent_creator_transfers_cannot_double_spend(
    service: UniverseService, monkeypatch: pytest.MonkeyPatch
) -> None:
    service.create_local_realm("ply_owner")
    service.execute(
        "creator_ledger.record",
        "ply_owner",
        "rlm_local",
        {"id": "cr_seed", "asset_id": "ast_1", "owner_id": "ply_owner", "quantity": 1},
        0,
        "cmd_seed",
    )
    barrier = Barrier(2)
    append_barrier = Barrier(2)
    original_append = service.store.append

    def delayed_append(*args, **kwargs):
        append_barrier.wait()
        return original_append(*args, **kwargs)

    monkeypatch.setattr(service.store, "append", delayed_append)

    def transfer(index: int):
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
        except Exception as exc:  # noqa: BLE001 - race result is asserted by type
            return exc

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(transfer, range(2)))

    assert sum(not isinstance(result, Exception) for result in results) == 1
    assert sum(isinstance(result, ValidationError) for result in results) == 1
    owner_balance = sum(
        side["quantity"]
        for entry in service.snapshot("ply_owner", "rlm_local")["creator_ledgers"]
        if entry.get("asset_id") == "ast_1"
        for side in entry.get("entries", [])
        if side.get("owner_id") == "ply_owner"
    )
    assert owner_balance == 0


def test_concurrent_refunds_cannot_refund_one_transfer_twice(
    service: UniverseService, approval_verifier, monkeypatch: pytest.MonkeyPatch
) -> None:
    service.create_local_realm("ply_owner")
    service.execute(
        "creator_ledger.record",
        "ply_owner",
        "rlm_local",
        {"id": "cr_seed", "asset_id": "ast_1", "owner_id": "ply_owner", "quantity": 1},
        0,
        "cmd_seed",
    )
    service.execute(
        "creator_ledger.transfer",
        "ply_owner",
        "rlm_local",
        {
            "id": "cr_transfer",
            "asset_id": "ast_1",
            "from_id": "ply_owner",
            "to_id": "ply_buyer",
            "quantity": 1,
        },
        0,
        "cmd_transfer",
    )
    for index in range(2):
        approval_verifier.allow(f"apr_refund_{index}")
    barrier = Barrier(2)
    append_barrier = Barrier(2)
    original_append = service.store.append

    def delayed_append(*args, **kwargs):
        append_barrier.wait()
        return original_append(*args, **kwargs)

    monkeypatch.setattr(service.store, "append", delayed_append)

    def refund(index: int):
        barrier.wait()
        try:
            return service.execute(
                "marketplace.refund",
                "ply_owner",
                "rlm_local",
                {
                    "id": f"cr_refund_{index}",
                    "transfer_id": "cr_transfer",
                    "reason": "requested",
                },
                0,
                f"cmd_refund_{index}",
                approval_id=f"apr_refund_{index}",
            )
        except Exception as exc:  # noqa: BLE001 - race result is asserted by type
            return exc

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(refund, range(2)))

    assert sum(not isinstance(result, Exception) for result in results) == 1
    assert sum(isinstance(result, ValidationError) for result in results) == 1


def test_all_creator_commands_reject_operational_fields(
    service: UniverseService, approval_verifier
) -> None:
    service.create_local_realm("ply_owner")
    service.execute(
        "creator_ledger.record",
        "ply_owner",
        "rlm_local",
        {"id": "cr_seed", "asset_id": "ast_1", "owner_id": "ply_owner", "quantity": 2},
        0,
        "cmd_seed",
    )
    with pytest.raises(ValidationError, match="operational"):
        service.execute(
            "creator_ledger.transfer",
            "ply_owner",
            "rlm_local",
            {
                "id": "cr_bad_transfer",
                "asset_id": "ast_1",
                "from_id": "ply_owner",
                "to_id": "ply_buyer",
                "quantity": 1,
                "provider": "external",
            },
            0,
            "cmd_bad_transfer",
        )
    service.execute(
        "creator_ledger.transfer",
        "ply_owner",
        "rlm_local",
        {
            "id": "cr_transfer",
            "asset_id": "ast_1",
            "from_id": "ply_owner",
            "to_id": "ply_buyer",
            "quantity": 1,
        },
        0,
        "cmd_transfer",
    )
    approval_verifier.allow("apr_bad_refund")
    with pytest.raises(ValidationError, match="operational"):
        service.execute(
            "marketplace.refund",
            "ply_owner",
            "rlm_local",
            {
                "id": "cr_bad_refund",
                "transfer_id": "cr_transfer",
                "reason": "requested",
                "cost_usd": 1,
            },
            0,
            "cmd_bad_refund",
            approval_id="apr_bad_refund",
        )


def test_concurrent_buildings_atomically_advance_world_and_budget(
    service: UniverseService,
) -> None:
    service.create_local_realm("ply_owner")
    service.execute(
        "world.create",
        "ply_owner",
        "rlm_local",
        {
            "id": "wld_race",
            "owner_id": "ply_owner",
            "regions": ["shared"],
            "bounds": {"min": [0, 0, 0], "max": [100, 100, 100]},
            "performance_budget": {"triangles": 100, "draw_calls": 10},
            "navigation": {"minimum_clearance": 2.0},
        },
        0,
        "cmd_world_race",
    )
    barrier = Barrier(2)

    def place(index: int):
        barrier.wait()
        try:
            return service.execute(
                "building.place",
                "ply_owner",
                "rlm_local",
                {
                    "id": f"bld_{index}",
                    "world_id": "wld_race",
                    "owner_id": "ply_owner",
                    "expected_world_version": 1,
                    "region_id": "shared",
                    "transform": {"position": [10 + index * 20, 10, 10]},
                    "collision": {"radius": 5},
                    "collision_valid": True,
                    "navigation_clearance": 2.0,
                    "performance_cost": {"triangles": 60, "draw_calls": 2},
                },
                0,
                f"cmd_build_{index}",
            )
        except Exception as exc:  # noqa: BLE001 - race result is asserted by type
            return exc

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(place, range(2)))

    assert sum(not isinstance(result, Exception) for result in results) == 1
    assert sum(isinstance(result, (ValidationError, Exception)) for result in results) == 1
    world = service.entity("ply_owner", "world", "wld_race", "rlm_local")
    assert world is not None
    assert world["version"] == 2
    assert world["performance_used"]["triangles"] == 60


def test_public_age_region_hook_external_workspace_logistics_and_cinematic_qc(
    tmp_path, approval_verifier
) -> None:
    from plugins.muse_universe.store import UniverseStore

    rejected: list[str] = []

    def policy(actor_id: str, realm: dict[str, object], payload: dict[str, object]) -> bool:
        rejected.append(actor_id)
        return payload.get("region") != "blocked"

    service = UniverseService(
        UniverseStore(tmp_path / "policies.db"),
        approval_verifier=approval_verifier,
        public_policy_hook=policy,
    )
    service.create_local_realm("ply_owner", mode="public", visibility="public")
    approval_verifier.allow("apr_policy_asset")
    service.execute(
        "asset.register",
        "ply_owner",
        "rlm_local",
        {"id": "ast_policy", **_public_metadata()},
        0,
        "cmd_policy_asset",
        approval_id="apr_policy_asset",
    )
    rejected.clear()
    with pytest.raises(ValidationError, match="age/region"):
        service.execute(
            "gallery.publish",
            "ply_owner",
            "rlm_local",
            {
                "id": "gal_1",
                "asset_id": "ast_policy",
                "visibility": "public",
                "region": "blocked",
            },
            0,
            "cmd_gallery",
        )
    assert rejected == ["ply_owner"]

    with pytest.raises(AuthorizationError, match="approval"):
        service.execute(
            "workspace.lease",
            "ply_owner",
            "rlm_local",
            {
                "id": "wrk_1",
                "provider": "external",
                "project_id": "proj_1",
                "cost_usd": 1.0,
                "expiry_utc": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
                "checkpoint": "chk_1",
                "signed_preview": "sha256:" + "b" * 64,
            },
            0,
            "cmd_workspace",
        )
    with pytest.raises(ValidationError, match="logistics"):
        service.execute(
            "logistics.update",
            "ply_owner",
            "rlm_local",
            {"id": "log_1", "kind": "game", "resource": "fuel", "quantity": -1},
            0,
            "cmd_logistics",
        )

    service.execute(
        "cinematic_shot.create",
        "ply_owner",
        "rlm_local",
        {
            "id": "shot_1",
            "scene_id": "scene_1",
            "cameras": [{"id": "cam_l"}, {"id": "cam_r"}],
            "lens": {"focal_length_mm": 50},
            "stereo": {"interaxial_mm": 65, "convergence_m": 8},
            "render_config": {"version": "1", "resolution": [4096, 2160]},
        },
        0,
        "cmd_shot",
    )
    with pytest.raises(ValidationError, match="QC"):
        service.execute(
            "cinematic_shot.qc",
            "ply_owner",
            "rlm_local",
            {"shot_id": "shot_1", "status": "passed", "checks": {"alignment": "failed"}, "evidence": ["frame:1"]},
            1,
            "cmd_qc",
        )
