from __future__ import annotations

from datetime import datetime, timedelta, timezone

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
    snapshot = service.snapshot("rlm_local")
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


def test_public_blueprint_requires_rights_verification_and_moderation(
    service: UniverseService,
) -> None:
    service.create_local_realm("ply_owner")
    with pytest.raises(ValidationError, match="license"):
        service.execute(
            "blueprint.publish",
            "ply_owner",
            "rlm_local",
            {
                "id": "bp_1",
                "visibility": "public",
                "content_hash": "sha256:" + "a" * 64,
                "verification": {"status": "passed"},
            },
            0,
            "cmd_bp",
        )
    with pytest.raises(AuthorizationError, match="approval"):
        service.execute(
            "blueprint.publish",
            "ply_owner",
            "rlm_local",
            {"id": "bp_2", "visibility": "public", **_public_metadata()},
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
            "collision_valid": True,
            "navigation_clearance": 2.0,
            "performance_cost": {"triangles": 100, "draw_calls": 2},
        },
        0,
        "cmd_shared_build",
    )
    assert result.entity["owner_id"] == "civ_1"


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
    vessel = service.entity("vessel", "vsl_owner", "rlm_local")
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
            return {"session_id": "mis_1", "title": "Mission evidence", "value": "test:passed"}

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

    class EvidenceAdapter:
        def record(self, evidence: dict[str, object]) -> dict[str, str]:
            return {
                "session_id": str(evidence["mission_id"]),
                "title": "Mission evidence",
                "value": "test:passed",
            }

    service = UniverseService(
        UniverseStore(tmp_path / "evidence.db"),
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
    result = service.execute(
        "mission.transition",
        "ply_owner",
        "rlm_local",
        {"mission_id": "mis_1", "to_state": "completed", "evidence": ["test:passed"]},
        3,
        "cmd_complete",
    )
    assert result.event.payload["achievement_evidence"]["session_id"] == "mis_1"
    stored = service.entity("mission", "mis_1", "rlm_local")
    assert stored is not None
    assert stored["achievement_evidence"]["value"] == "test:passed"


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
    with pytest.raises(ValidationError, match="age/region"):
        service.execute(
            "gallery.publish",
            "ply_owner",
            "rlm_local",
            {"id": "gal_1", "visibility": "public", "region": "blocked", **_public_metadata()},
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
