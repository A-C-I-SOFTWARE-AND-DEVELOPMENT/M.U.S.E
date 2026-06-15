"""Nero-Fleet command hierarchy — telemetry overlay for the M.U.S.E operating layer.

Maps the naval fleet metaphor (Admiralty → Flagship → Cruiser/Frigate → Ships)
onto existing runtime entities without changing orchestrator on-disk schemas.
Visual clients (Observatory, Pixel Streaming cockpit) consume
:func:`snapshot` and :func:`solar_system_view` for measured state only.
"""

from hermes_cli.jarvis_prime.fleet.nodes import (
    AdmiraltyNode,
    FleetNode,
    FleetShip,
    FlagshipNode,
    IntelligenceFleetNode,
    NodeKind,
    NodeStatus,
    TacticalVesselNode,
)
from hermes_cli.jarvis_prime.fleet.registry import FleetRegistry, get_registry
from hermes_cli.jarvis_prime.fleet.solar_map import SolarBody, SolarTransit, solar_system_view

__all__ = [
    "AdmiraltyNode",
    "FleetNode",
    "FleetRegistry",
    "FleetShip",
    "FlagshipNode",
    "IntelligenceFleetNode",
    "NodeKind",
    "NodeStatus",
    "SolarBody",
    "SolarTransit",
    "TacticalVesselNode",
    "get_registry",
    "solar_system_view",
]
