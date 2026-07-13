from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol

from .catalog import MANDATORY_VESSEL_ROOMS, VESSEL_CLASSES
from .models import AuthorizationDecision, ProvenanceRecord, UniverseCommand

if TYPE_CHECKING:
    from .service import UniverseService


_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
_SYMBOL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,127}$")
_PRIVATE_PATH = re.compile(
    r"(?ix)(?:"
    r"(?<![a-z0-9])file:(?://)?"
    r"|(?<![a-z0-9])[a-z]:[\\/]"
    r"|(?<![a-z0-9])\\\\[^\\/\s]+[\\/]"
    r"|(?<![a-z0-9:])//[^/\s]+/"
    r"|(?<![a-z0-9])~[\\/]"
    r"|(?<![a-z0-9])\$\{?home\}?[\\/]"
    r"|(?<![a-z0-9])/(?:home|root|users|private|etc|var|tmp|opt|srv)(?:/|$)"
    r")"
)
_HEALTH_STATES = frozenset(
    {"available", "degraded", "error", "running", "stopped", "unknown"}
)
_RUNTIME_STATES = frozenset(
    {"degraded", "error", "restarting", "running", "starting", "stopped", "stopping"}
)
_SAFE_METADATA_FIELDS = frozenset(
    {
        "active",
        "active_agent_count",
        "description",
        "distribution_name",
        "distribution_source",
        "distribution_version",
        "gateway_running",
        "gateway_state",
        "is_default",
        "model",
        "provider",
        "skill_count",
    }
)


@dataclass(frozen=True)
class AgentRecord:
    """Secret-free agent information used to derive one vessel binding."""

    agent_id: str
    display_name: str
    vessel_class: str
    capabilities: tuple[str, ...]
    health: str = "available"
    metadata: Mapping[str, object] = field(default_factory=dict)


class AgentAdapter(Protocol):
    def discover(self) -> tuple[AgentRecord, ...]: ...


@dataclass(frozen=True)
class ReconciliationReport:
    realm_id: str
    discovered: int = 0
    created: int = 0
    updated: int = 0
    deactivated: int = 0
    quarantined: int = 0
    created_vessel_ids: tuple[str, ...] = ()
    updated_vessel_ids: tuple[str, ...] = ()
    deactivated_vessel_ids: tuple[str, ...] = ()
    quarantined_vessel_ids: tuple[str, ...] = ()


class HermesAgentAdapter:
    """Discover runnable profiles using only public, safe Hermes metadata."""

    def discover(self) -> tuple[AgentRecord, ...]:
        from gateway import status
        from hermes_cli import profiles

        active_profile = profiles.get_active_profile_name()
        runtime = status.read_runtime_status() or {}
        running_pid_present = status.get_running_pid(cleanup_stale=False) is not None
        current_gateway_running = status.is_gateway_running(cleanup_stale=False)

        runtime_state = _runtime_state(runtime.get("gateway_state"))
        active_agent_count = _non_negative_int(runtime.get("active_agents"))
        records: list[AgentRecord] = []
        for profile in profiles.list_profiles():
            is_active = profile.name == active_profile
            gateway_running = bool(
                profile.gateway_running
                or (
                    is_active
                    and (current_gateway_running or running_pid_present)
                )
            )
            health = _profile_health(
                is_active=is_active,
                gateway_running=gateway_running,
                runtime_state=runtime_state,
                active_agent_count=active_agent_count,
            )
            capabilities: list[str] = []
            if profile.model or profile.provider:
                capabilities.append("model:invoke")
            if profile.skill_count > 0:
                capabilities.append("skills:load")
            if gateway_running:
                capabilities.append("gateway:serve")

            metadata = {
                "active": is_active,
                "active_agent_count": active_agent_count if is_active else 0,
                "description": profile.description,
                "distribution_name": profile.distribution_name,
                "distribution_source": profile.distribution_source,
                "distribution_version": profile.distribution_version,
                "gateway_running": gateway_running,
                "gateway_state": runtime_state if is_active else "stopped",
                "is_default": profile.is_default,
                "model": profile.model,
                "provider": profile.provider,
                "skill_count": max(0, int(profile.skill_count)),
            }
            records.append(
                AgentRecord(
                    agent_id=profile.name,
                    display_name=_profile_display_name(profile.name),
                    vessel_class=_default_vessel_class(profile.name),
                    capabilities=tuple(capabilities),
                    health=health,
                    metadata=metadata,
                )
            )
        return tuple(sorted(records, key=lambda record: record.agent_id))


def stable_vessel_id(realm_id: str, agent_id: str) -> str:
    """Return the realm-local stable vessel id for an agent."""

    realm = _required_identifier(realm_id, "realm_id")
    agent = _required_identifier(agent_id, "agent_id")
    digest = hashlib.sha256(
        realm.encode("utf-8") + b"\0" + agent.encode("utf-8")
    ).hexdigest()
    return f"vsl_{digest[:20]}"


def reconcile_agents(
    service: UniverseService,
    adapter: AgentAdapter | None = None,
    *,
    realm_id: str = "rlm_local",
) -> ReconciliationReport:
    """Reconcile real runnable agents to one active vessel per realm."""

    realm_id = _required_identifier(realm_id, "realm_id")
    realm = service.store.entity("realm", realm_id, realm_id)
    if realm is None:
        raise ValueError(f"realm {realm_id!r} does not exist")
    owner_id = _required_identifier(realm.get("owner_id"), "realm owner_id")
    simulation = realm.get("mode") == "simulation"

    discovered = (adapter or HermesAgentAdapter()).discover()
    agents: dict[str, AgentRecord] = {}
    for record in discovered:
        agent_id = _required_identifier(record.agent_id, "agent_id")
        if agent_id in agents:
            raise ValueError(f"duplicate discovered agent_id {agent_id!r}")
        agents[agent_id] = record

    created: list[str] = []
    updated: list[str] = []
    quarantined: list[str] = []
    deactivated: list[str] = []

    vessels = _vessels_by_id(service, realm_id)
    for agent_id in sorted(agents):
        record = agents[agent_id]
        vessel_id = stable_vessel_id(realm_id, agent_id)
        desired_binding = _active_binding(record)
        desired_class = _safe_vessel_class(record.vessel_class)
        desired_name = f"{_safe_display_name(record.display_name, agent_id)} Vessel"
        current = vessels.get(vessel_id)
        if current is None:
            service.execute(
                "vessel.create",
                owner_id,
                realm_id,
                _new_vessel_payload(
                    vessel_id=vessel_id,
                    owner_id=owner_id,
                    name=desired_name,
                    vessel_class=desired_class,
                    binding=desired_binding,
                ),
                0,
                _command_id("create", realm_id, vessel_id, 0, desired_binding),
                simulation=simulation,
            )
            created.append(vessel_id)
            vessels = _vessels_by_id(service, realm_id)
            continue

        current_agent_id = _binding_agent_id(current)
        if current_agent_id not in {None, agent_id}:
            raise ValueError(
                f"stable vessel {vessel_id!r} is bound to a different agent"
            )
        desired_payload = {
            "agent_binding": desired_binding,
            "name": desired_name,
            "vessel_class": desired_class,
        }
        if any(current.get(key) != value for key, value in desired_payload.items()):
            _append_lifecycle(
                service,
                realm_id=realm_id,
                owner_id=owner_id,
                vessel=current,
                operation="reconcile",
                payload=desired_payload,
            )
            updated.append(vessel_id)
            vessels = _vessels_by_id(service, realm_id)

    # Quarantine every duplicate active manifestation. The stable vessel is the
    # canonical survivor for discovered profiles; legacy removed bindings retain
    # the lexicographically first record until the deactivation pass below.
    active_groups = _active_groups(vessels.values())
    for agent_id in sorted(active_groups):
        group = active_groups[agent_id]
        if len(group) < 2:
            continue
        canonical_id = stable_vessel_id(realm_id, agent_id)
        keep_id = canonical_id if canonical_id in group else min(group)
        for vessel_id in sorted(group):
            if vessel_id == keep_id:
                continue
            vessel = vessels[vessel_id]
            binding = _lifecycle_binding(
                vessel,
                status="quarantined",
                health="degraded",
                reason="duplicate_active_binding",
                canonical_vessel_id=keep_id,
            )
            _append_lifecycle(
                service,
                realm_id=realm_id,
                owner_id=owner_id,
                vessel=vessel,
                operation="quarantine",
                payload={"agent_binding": binding},
            )
            quarantined.append(vessel_id)
            vessels = _vessels_by_id(service, realm_id)

    # A removed profile is retained as an auditable, inactive vessel instead of
    # being deleted. Quarantined duplicates are already inactive and remain so.
    for vessel_id, vessel in sorted(vessels.items()):
        agent_id = _binding_agent_id(vessel)
        if agent_id is None or agent_id in agents or not _binding_is_active(vessel):
            continue
        binding = _lifecycle_binding(
            vessel,
            status="inactive",
            health="removed",
            reason="profile_removed",
        )
        _append_lifecycle(
            service,
            realm_id=realm_id,
            owner_id=owner_id,
            vessel=vessel,
            operation="deactivate",
            payload={"agent_binding": binding},
        )
        deactivated.append(vessel_id)

    return ReconciliationReport(
        realm_id=realm_id,
        discovered=len(agents),
        created=len(created),
        updated=len(updated),
        deactivated=len(deactivated),
        quarantined=len(quarantined),
        created_vessel_ids=tuple(created),
        updated_vessel_ids=tuple(updated),
        deactivated_vessel_ids=tuple(deactivated),
        quarantined_vessel_ids=tuple(quarantined),
    )


def _vessels_by_id(
    service: UniverseService, realm_id: str
) -> dict[str, dict[str, Any]]:
    return {
        str(vessel["id"]): vessel
        for vessel in service.store.entities(realm_id, "vessel")
        if isinstance(vessel.get("id"), str)
    }


def _active_groups(
    vessels: Iterable[dict[str, Any]],
) -> dict[str, dict[str, dict[str, Any]]]:
    groups: dict[str, dict[str, dict[str, Any]]] = {}
    for vessel in vessels:
        if not isinstance(vessel, dict) or not _binding_is_active(vessel):
            continue
        agent_id = _binding_agent_id(vessel)
        vessel_id = vessel.get("id")
        if agent_id is None or not isinstance(vessel_id, str):
            continue
        groups.setdefault(agent_id, {})[vessel_id] = vessel
    return groups


def _new_vessel_payload(
    *,
    vessel_id: str,
    owner_id: str,
    name: str,
    vessel_class: str,
    binding: dict[str, Any],
) -> dict[str, Any]:
    return {
        "id": vessel_id,
        "owner_id": owner_id,
        "name": name,
        "vessel_class": vessel_class,
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
        "agent_binding": binding,
    }


def _append_lifecycle(
    service: UniverseService,
    *,
    realm_id: str,
    owner_id: str,
    vessel: Mapping[str, Any],
    operation: str,
    payload: Mapping[str, Any],
) -> None:
    vessel_id = _required_identifier(vessel.get("id"), "vessel_id")
    version = vessel.get("version")
    if type(version) is not int or version < 1:
        raise ValueError(f"vessel {vessel_id!r} has an invalid version")
    command_id = _command_id(operation, realm_id, vessel_id, version, payload)
    command = UniverseCommand(
        command_id=command_id,
        command_type=f"vessel.agent.{operation}",
        realm_id=realm_id,
        actor_id=owner_id,
        stream_type="vessel",
        stream_id=vessel_id,
        expected_version=version,
        payload=dict(payload),
        authorization=AuthorizationDecision(
            allowed=True,
            reason="internal agent-vessel reconciliation",
            scopes=("vessel:reconcile",),
        ),
        provenance=ProvenanceRecord(
            source="hermes_profile_reconciliation",
            evidence=(f"vessel:{vessel_id}",),
            confidence=1.0,
        ),
        causation_id=command_id,
        correlation_id=command_id,
        simulation=bool(vessel.get("simulation")),
    )
    service.store.append(command, f"vessel.agent_{operation}d")


def _active_binding(record: AgentRecord) -> dict[str, Any]:
    agent_id = _required_identifier(record.agent_id, "agent_id")
    return {
        "agent_id": agent_id,
        "status": "active",
        "active": True,
        "capabilities": list(_safe_capabilities(record.capabilities)),
        "health": _safe_health(record.health),
        "metadata": _safe_metadata(record.metadata),
    }


def _lifecycle_binding(
    vessel: Mapping[str, Any],
    *,
    status: str,
    health: str,
    reason: str,
    canonical_vessel_id: str | None = None,
) -> dict[str, Any]:
    current = vessel.get("agent_binding")
    binding = current if isinstance(current, Mapping) else {}
    agent_id = _required_identifier(binding.get("agent_id"), "agent_binding.agent_id")
    result: dict[str, Any] = {
        "agent_id": agent_id,
        "status": status,
        "active": False,
        "capabilities": list(_safe_capabilities(binding.get("capabilities", ()))),
        "health": health,
        "metadata": _safe_metadata(binding.get("metadata", {})),
        "lifecycle_reason": reason,
    }
    if canonical_vessel_id is not None:
        result["canonical_vessel_id"] = _required_identifier(
            canonical_vessel_id, "canonical_vessel_id"
        )
    return result


def _binding_agent_id(vessel: Mapping[str, Any]) -> str | None:
    binding = vessel.get("agent_binding")
    if not isinstance(binding, Mapping):
        return None
    value = binding.get("agent_id")
    if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
        return None
    return value


def _binding_is_active(vessel: Mapping[str, Any]) -> bool:
    binding = vessel.get("agent_binding")
    if not isinstance(binding, Mapping):
        return False
    status = binding.get("status")
    if status is None:
        return binding.get("active") is True
    return status == "active" and binding.get("active") is not False


def _safe_capabilities(values: object) -> tuple[str, ...]:
    if not isinstance(values, (list, tuple, set, frozenset)):
        return ()
    capabilities = {
        value
        for value in values
        if isinstance(value, str)
        and _SYMBOL.fullmatch(value)
        and _is_safe_serialized_string(value)
    }
    return tuple(sorted(capabilities))


def _safe_metadata(values: object) -> dict[str, object]:
    if not isinstance(values, Mapping):
        return {}
    safe: dict[str, object] = {}
    for key in sorted(_SAFE_METADATA_FIELDS):
        value = values.get(key)
        if key not in values:
            continue
        if key in {"active", "gateway_running", "is_default"}:
            if isinstance(value, bool):
                safe[key] = value
        elif key in {"active_agent_count", "skill_count"}:
            if type(value) is int and value >= 0:
                safe[key] = value
        elif value is None:
            safe[key] = None
        elif (
            isinstance(value, str)
            and len(value) <= 512
            and _is_safe_serialized_string(value)
        ):
            safe[key] = value
    return safe


def _safe_health(value: object) -> str:
    if isinstance(value, str) and value.casefold() in _HEALTH_STATES:
        return value.casefold()
    return "unknown"


def _safe_vessel_class(value: object) -> str:
    return value if isinstance(value, str) and value in VESSEL_CLASSES else "scout"


def _safe_display_name(value: object, fallback: str) -> str:
    if (
        isinstance(value, str)
        and value.strip()
        and len(value.strip()) <= 128
        and value.isprintable()
        and _is_safe_serialized_string(value)
    ):
        return value.strip()
    return fallback


def _required_identifier(value: object, field_name: str) -> str:
    if (
        not isinstance(value, str)
        or not _IDENTIFIER.fullmatch(value)
        or not _is_safe_serialized_string(value)
    ):
        raise ValueError(f"{field_name} must be a safe identifier")
    return value


def _command_id(
    operation: str,
    realm_id: str,
    vessel_id: str,
    version: int,
    payload: Mapping[str, Any],
) -> str:
    encoded = json.dumps(
        payload,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    material = f"{operation}\0{realm_id}\0{vessel_id}\0{version}\0{encoded}"
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:32]
    return f"cmd_reconcile_{operation}_{digest}"


def _looks_secretish(value: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]+", "_", value.casefold()).strip("_")
    segments = normalized.split("_") if normalized else []
    segment_set = set(segments)
    if segment_set & {"bearer", "credential", "credentials", "passwd", "password", "secret"}:
        return True
    joined = "_".join(segments)
    if any(
        marker in joined
        for marker in (
            "access_token",
            "api_key",
            "oauth_token",
            "private_key",
            "provider_key",
        )
    ):
        return True
    if re.search(r"(?i)(?:^|[^a-z0-9])sk-[a-z0-9_-]{8,}", value):
        return True
    if re.search(
        r"(?i)\b(?:access[_ -]?token|api[_ -]?key|oauth[_ -]?token|"
        r"provider[_ -]?key|token)\s*[:=]\s*\S+",
        value,
    ):
        return True
    if re.search(r"(?i)-----BEGIN(?: [A-Z0-9]+)* PRIVATE KEY-----", value):
        return True
    if re.search(r"(?i)\bgh[pousr]_[a-z0-9]{20,}\b", value):
        return True
    return bool(re.search(r"^[a-z][a-z0-9+.-]*://[^/@\s]+:[^/@\s]+@", value))


def _looks_private_path(value: str) -> bool:
    return bool(_PRIVATE_PATH.search(value))


def _is_safe_serialized_string(value: str) -> bool:
    return not _looks_secretish(value) and not _looks_private_path(value)


def _runtime_state(value: object) -> str:
    if isinstance(value, str) and value.casefold() in _RUNTIME_STATES:
        return value.casefold()
    return "stopped"


def _non_negative_int(value: object) -> int:
    return value if type(value) is int and value >= 0 else 0


def _profile_health(
    *,
    is_active: bool,
    gateway_running: bool,
    runtime_state: str,
    active_agent_count: int,
) -> str:
    if is_active and runtime_state in {"degraded", "error"}:
        return "degraded"
    if gateway_running or (is_active and active_agent_count > 0):
        return "running"
    return "available"


def _profile_display_name(name: str) -> str:
    return "Default" if name == "default" else name.replace("_", " ").replace("-", " ").title()


def _default_vessel_class(agent_id: str) -> str:
    digest = hashlib.sha256(agent_id.encode("utf-8")).digest()
    return VESSEL_CLASSES[int.from_bytes(digest[:2], "big") % len(VESSEL_CLASSES)]
