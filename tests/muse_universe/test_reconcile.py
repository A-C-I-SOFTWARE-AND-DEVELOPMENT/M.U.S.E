from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from hermes_cli.profiles import ProfileInfo

from plugins.muse_universe.catalog import MANDATORY_VESSEL_ROOMS
from plugins.muse_universe.reconcile import (
    AgentRecord,
    HermesAgentAdapter,
    reconcile_agents,
    stable_vessel_id,
)


class FakeAgentAdapter:
    def __init__(self, agents: list[AgentRecord]) -> None:
        self._agents = agents

    def discover(self) -> tuple[AgentRecord, ...]:
        return tuple(self._agents)


def _vessel_payload(vessel_id: str, agent_id: str) -> dict[str, object]:
    return {
        "id": vessel_id,
        "owner_id": "ply_owner",
        "name": f"{agent_id} vessel",
        "vessel_class": "scout",
        "rooms": list(MANDATORY_VESSEL_ROOMS),
        "attachment_points": ["sensor_spine", "utility_bay", "release_dock"],
        "budgets": {
            "power": 100.0,
            "heat": 100.0,
            "compute": 100.0,
            "context": 100.0,
        },
        "installed_modules": [],
        "allowed_licenses": ["MUSE-ORIGINAL-1.0"],
        "path_reachable": True,
        "agent_binding": {
            "agent_id": agent_id,
            "status": "active",
            "active": True,
            "capabilities": ["web"],
            "health": "available",
        },
    }


def test_stable_vessel_id_is_realm_scoped_sha256() -> None:
    expected = "vsl_" + hashlib.sha256(
        b"rlm_local\0research"
    ).hexdigest()[:20]

    assert stable_vessel_id("rlm_local", "research") == expected
    assert stable_vessel_id("rlm_other", "research") != expected


def test_each_runnable_agent_has_one_active_vessel(service) -> None:
    service.create_local_realm("ply_owner")
    adapter = FakeAgentAdapter(
        [
            AgentRecord("research", "Research", "scout", ("web", "vision")),
            AgentRecord("forge", "Forge", "forge", ("terminal", "patch")),
        ]
    )

    report = reconcile_agents(service, adapter)

    assert report.created == 2
    assert report.updated == 0
    vessels = service.snapshot("ply_owner", "rlm_local")["vessels"]
    active = [
        vessel
        for vessel in vessels
        if vessel["agent_binding"]["status"] == "active"
    ]
    assert {vessel["agent_binding"]["agent_id"] for vessel in active} == {
        "research",
        "forge",
    }
    assert {vessel["id"] for vessel in active} == {
        stable_vessel_id("rlm_local", "research"),
        stable_vessel_id("rlm_local", "forge"),
    }

    report2 = reconcile_agents(service, adapter)

    assert report2.created == 0
    assert report2.updated == 0
    assert report2.deactivated == 0
    assert report2.quarantined == 0


def test_capability_and_health_drift_updates_existing_binding(service) -> None:
    service.create_local_realm("ply_owner")
    reconcile_agents(
        service,
        FakeAgentAdapter(
            [AgentRecord("research", "Research", "scout", ("web",), "available")]
        ),
    )

    report = reconcile_agents(
        service,
        FakeAgentAdapter(
            [
                AgentRecord(
                    "research",
                    "Research",
                    "scout",
                    ("vision", "web", "vision"),
                    "degraded",
                )
            ]
        ),
    )

    assert report.updated == 1
    vessel = service.store.entity(
        "vessel", stable_vessel_id("rlm_local", "research"), "rlm_local"
    )
    assert vessel is not None
    assert vessel["agent_binding"]["capabilities"] == ["vision", "web"]
    assert vessel["agent_binding"]["health"] == "degraded"
    assert vessel["version"] == 2


def test_duplicate_active_binding_is_quarantined_with_rollback(service) -> None:
    service.create_local_realm("ply_owner")
    canonical = stable_vessel_id("rlm_local", "research")
    service.execute(
        "vessel.create",
        "ply_owner",
        "rlm_local",
        _vessel_payload(canonical, "research"),
        0,
        "cmd_seed_canonical",
    )
    duplicate = "vsl_duplicate_research"
    service.execute(
        "vessel.create",
        "ply_owner",
        "rlm_local",
        _vessel_payload(duplicate, "research"),
        0,
        "cmd_seed_duplicate",
    )

    report = reconcile_agents(
        service,
        FakeAgentAdapter(
            [AgentRecord("research", "Research", "scout", ("web",))]
        ),
    )

    assert report.quarantined == 1
    assert report.quarantined_vessel_ids == (duplicate,)
    canonical_vessel = service.store.entity("vessel", canonical, "rlm_local")
    duplicate_vessel = service.store.entity("vessel", duplicate, "rlm_local")
    assert canonical_vessel is not None
    assert duplicate_vessel is not None
    assert canonical_vessel["agent_binding"]["status"] == "active"
    assert duplicate_vessel["agent_binding"]["status"] == "quarantined"
    events = service.store.events_since("rlm_local", 0)
    quarantine = next(
        event for event in events if event.event_type == "vessel.agent_quarantined"
    )
    assert quarantine.stream_id == duplicate
    assert quarantine.rollback["agent_binding"]["status"] == "active"


def test_removed_profile_is_deactivated_and_can_be_reactivated(service) -> None:
    service.create_local_realm("ply_owner")
    populated = FakeAgentAdapter(
        [AgentRecord("research", "Research", "scout", ("web",))]
    )
    reconcile_agents(service, populated)

    removed = reconcile_agents(service, FakeAgentAdapter([]))

    assert removed.deactivated == 1
    vessel_id = stable_vessel_id("rlm_local", "research")
    vessel = service.store.entity("vessel", vessel_id, "rlm_local")
    assert vessel is not None
    assert vessel["agent_binding"]["status"] == "inactive"
    assert vessel["agent_binding"]["health"] == "removed"
    assert reconcile_agents(service, FakeAgentAdapter([])).deactivated == 0

    restored = reconcile_agents(service, populated)

    assert restored.updated == 1
    vessel = service.store.entity("vessel", vessel_id, "rlm_local")
    assert vessel is not None
    assert vessel["agent_binding"]["status"] == "active"


def test_reconciliation_drops_secret_shaped_adapter_metadata(service) -> None:
    service.create_local_realm("ply_owner")
    adapter = FakeAgentAdapter(
        [
            AgentRecord(
                "research",
                "Research",
                "scout",
                ("web", "api_key=do-not-copy", "bearer:do-not-copy"),
                metadata={
                    "model": "safe-model",
                    "provider": "safe-provider",
                    "api_key": "do-not-copy",
                    "path": "C:/private/profile",
                    "request_headers": {"Authorization": "do-not-copy"},
                },
            )
        ]
    )

    reconcile_agents(service, adapter)

    vessel = service.store.entity(
        "vessel", stable_vessel_id("rlm_local", "research"), "rlm_local"
    )
    assert vessel is not None
    serialized = json.dumps(vessel, sort_keys=True)
    assert "do-not-copy" not in serialized
    assert "api_key" not in serialized
    assert "request_headers" not in serialized
    assert "C:/private/profile" not in serialized
    assert vessel["agent_binding"]["capabilities"] == ["web"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("description", "Profile files at C:/Users/alice/.hermes/config.yaml"),
        ("provider", r"provider cache at \\server\private\profile.yaml"),
        ("model", "loaded from /home/alice/.config/hermes/model.yaml"),
        ("distribution_source", "file:///home/alice/private/profile.yaml"),
        ("distribution_name", "Bearer abcdefghijklmnopqrstuvwxyz"),
        ("distribution_version", "token=ghp_abcdefghijklmnopqrstuvwxyz"),
        ("gateway_state", "token=ghp_abcdefghijklmnopqrstuvwxyz"),
        ("description", "-----BEGIN PRIVATE KEY----- do-not-copy"),
    ],
)
def test_reconciliation_filters_unsafe_values_from_every_allowed_metadata_field(
    service, field: str, value: str
) -> None:
    service.create_local_realm("ply_owner")

    reconcile_agents(
        service,
        FakeAgentAdapter(
            [
                AgentRecord(
                    "research",
                    "Research",
                    "scout",
                    ("web",),
                    metadata={
                        "description": "Safe research profile",
                        "provider": "safe-provider",
                        field: value,
                    },
                )
            ]
        ),
    )

    vessel = service.store.entity(
        "vessel", stable_vessel_id("rlm_local", "research"), "rlm_local"
    )
    assert vessel is not None
    metadata = vessel["agent_binding"]["metadata"]
    assert value not in metadata.values()
    assert value not in json.dumps(vessel, sort_keys=True)


def test_reconciliation_filters_unsafe_display_names_and_capability_values(
    service,
) -> None:
    service.create_local_realm("ply_owner")

    reconcile_agents(
        service,
        FakeAgentAdapter(
            [
                AgentRecord(
                    "research",
                    "Profile at C:/Users/alice/.hermes/config.yaml",
                    "scout",
                    ("web", "file:/home/alice/private/tool"),
                )
            ]
        ),
    )

    vessel = service.store.entity(
        "vessel", stable_vessel_id("rlm_local", "research"), "rlm_local"
    )
    assert vessel is not None
    assert vessel["name"] == "research Vessel"
    assert vessel["agent_binding"]["capabilities"] == ["web"]


def test_reconciliation_preserves_safe_opaque_metadata_values(service) -> None:
    service.create_local_realm("ply_owner")
    metadata = {
        "description": "Research profile",
        "provider": "registry:openrouter/stable",
        "model": "org/model-v1",
        "distribution_source": "registry:profiles/stable",
    }

    reconcile_agents(
        service,
        FakeAgentAdapter(
            [
                AgentRecord(
                    "research",
                    "Research",
                    "scout",
                    ("web",),
                    metadata=metadata,
                )
            ]
        ),
    )

    vessel = service.store.entity(
        "vessel", stable_vessel_id("rlm_local", "research"), "rlm_local"
    )
    assert vessel is not None
    assert vessel["agent_binding"]["metadata"] == metadata


def test_default_adapter_uses_safe_profile_and_current_runtime_metadata(
    monkeypatch, tmp_path: Path
) -> None:
    from gateway import status
    from hermes_cli import profiles

    profile_rows = [
        ProfileInfo(
            name="default",
            path=tmp_path / ".hermes",
            is_default=True,
            gateway_running=True,
            model="model-a",
            provider="provider-a",
            has_env=True,
            skill_count=3,
            description="Research profile",
        ),
        ProfileInfo(
            name="forge",
            path=tmp_path / ".hermes" / "profiles" / "forge",
            is_default=False,
            gateway_running=False,
            model=None,
            provider=None,
            skill_count=0,
        ),
    ]
    monkeypatch.setattr(profiles, "list_profiles", lambda: profile_rows)
    monkeypatch.setattr(profiles, "get_active_profile_name", lambda: "default")
    monkeypatch.setattr(
        status,
        "read_runtime_status",
        lambda: {
            "gateway_state": "running",
            "active_agents": 2,
            "pid": 999,
            "argv": ["--provider-key", "do-not-copy"],
            "platforms": {"chat": {"error_message": "do-not-copy"}},
        },
    )
    monkeypatch.setattr(status, "get_running_pid", lambda **_kwargs: 999)
    monkeypatch.setattr(status, "is_gateway_running", lambda **_kwargs: True)

    records = HermesAgentAdapter().discover()

    assert {record.agent_id for record in records} == {"default", "forge"}
    active = next(record for record in records if record.agent_id == "default")
    assert active.health == "running"
    assert active.metadata == {
        "active": True,
        "active_agent_count": 2,
        "description": "Research profile",
        "distribution_name": None,
        "distribution_source": None,
        "distribution_version": None,
        "gateway_running": True,
        "gateway_state": "running",
        "is_default": True,
        "model": "model-a",
        "provider": "provider-a",
        "skill_count": 3,
    }
    serialized = json.dumps(dict(active.metadata), sort_keys=True)
    assert "do-not-copy" not in serialized
    assert "pid" not in serialized
    assert "argv" not in serialized
    assert str(profile_rows[0].path) not in serialized
