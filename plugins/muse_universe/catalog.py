from __future__ import annotations

from copy import deepcopy
from typing import Any

from .models import FrozenDict, deep_freeze

ATLAS_CROWN = deep_freeze(
    {
        "id": "atlas_crown",
        "type": "home_landmark",
        "rooms": ("governance_chamber",),
    }
)

_STATION_IDS = (
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
STATIONS = tuple(deep_freeze({"id": station_id}) for station_id in _STATION_IDS)

VESSEL_CLASSES = (
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
PLAYER_MODES = ("walk", "pilot", "fleet", "director")
COOP_ROLES = (
    "captain",
    "pilot",
    "science",
    "engineering",
    "fabrication",
    "security",
    "communications",
    "director",
)

MANDATORY_VESSEL_ROOMS = (
    "command_bridge",
    "neural_chamber",
    "sensor_laboratory",
    "fabrication_bay",
    "memory_vault",
    "drone_hangar",
    "engineering",
    "airlock_security",
)
REQUIRED_ROOMS = (*MANDATORY_VESSEL_ROOMS, "governance_chamber")
OPTIONAL_CLASS_ROOMS = (
    "render_chamber",
    "diagnostic_lab",
    "diplomatic_suite",
    "cargo_refinery",
    "simulation_deck",
    "carrier_hangar",
)

MODULE_CATEGORIES = (
    "sensor",
    "fabrication",
    "memory",
    "compute",
    "shield",
    "crew",
    "communications",
    "release",
)


def _module(
    module_id: str,
    module_type: str,
    attachment_types: tuple[str, ...],
    capabilities: tuple[str, ...],
    *,
    requires: tuple[str, ...] = (),
    conflicts: tuple[str, ...] = (),
    power: float,
    heat: float,
    compute: float,
    context: float,
    cost_class: str = "local_or_provider",
    trust_exposure: str = "bounded",
) -> FrozenDict:
    return deep_freeze(
        {
            "id": module_id,
            "type": module_type,
            "attachment_types": attachment_types,
            "requires": requires,
            "conflicts": conflicts,
            "capabilities": capabilities,
            "power": power,
            "heat": heat,
            "compute": compute,
            "context": context,
            "cost_class": cost_class,
            "trust_exposure": trust_exposure,
            "license": "MUSE-ORIGINAL-1.0",
        }
    )

MODULES = deep_freeze(
    {
        "mod_sensor_research": _module(
            "mod_sensor_research",
            "sensor",
            ("sensor_spine",),
            ("research:read",),
            power=8.0,
            heat=5.0,
            compute=2.0,
            context=1.0,
            trust_exposure="read_only_external",
        ),
        "mod_fabrication_tools": _module(
            "mod_fabrication_tools",
            "fabrication",
            ("utility_bay",),
            ("artifact:write",),
            power=12.0,
            heat=10.0,
            compute=6.0,
            context=2.0,
            trust_exposure="sandboxed_write",
        ),
        "mod_memory_archive": _module(
            "mod_memory_archive",
            "memory",
            ("utility_bay",),
            ("memory:read",),
            power=4.0,
            heat=2.0,
            compute=2.0,
            context=8.0,
            trust_exposure="private_data",
        ),
        "mod_compute_drive": _module(
            "mod_compute_drive",
            "compute",
            ("utility_bay",),
            (),
            power=15.0,
            heat=15.0,
            compute=20.0,
            context=0.0,
            trust_exposure="runtime",
        ),
        "mod_permission_shield": _module(
            "mod_permission_shield",
            "shield",
            ("utility_bay",),
            (),
            power=3.0,
            heat=1.0,
            compute=1.0,
            context=0.0,
            trust_exposure="policy_enforcement",
        ),
        "mod_crew_station": _module(
            "mod_crew_station",
            "crew",
            ("utility_bay",),
            (),
            power=2.0,
            heat=1.0,
            compute=1.0,
            context=1.0,
            trust_exposure="collaboration",
        ),
        "mod_communications_relay": _module(
            "mod_communications_relay",
            "communications",
            ("utility_bay",),
            ("communications:send",),
            power=5.0,
            heat=3.0,
            compute=2.0,
            context=1.0,
            trust_exposure="external_message",
        ),
        "mod_release_dock": _module(
            "mod_release_dock",
            "release",
            ("release_dock",),
            ("release:promote",),
            requires=("mod_permission_shield",),
            power=10.0,
            heat=6.0,
            compute=4.0,
            context=2.0,
            trust_exposure="public_deployment",
        ),
    }
)


def catalog_snapshot() -> dict[str, Any]:
    """Return a mutable client copy without exposing catalog state."""

    return deepcopy(
        {
            "atlas_crown": dict(ATLAS_CROWN),
            "stations": [dict(station) for station in STATIONS],
            "vessel_classes": list(VESSEL_CLASSES),
            "player_modes": list(PLAYER_MODES),
            "coop_roles": list(COOP_ROLES),
            "required_rooms": list(REQUIRED_ROOMS),
            "mandatory_vessel_rooms": list(MANDATORY_VESSEL_ROOMS),
            "optional_class_rooms": list(OPTIONAL_CLASS_ROOMS),
            "module_categories": list(MODULE_CATEGORIES),
            "modules": {key: dict(value) for key, value in MODULES.items()},
        }
    )
