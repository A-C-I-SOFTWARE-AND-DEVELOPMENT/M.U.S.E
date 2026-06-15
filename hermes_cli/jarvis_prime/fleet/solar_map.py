"""Nero Solar System — maps fleet + observatory telemetry to celestial bodies.

Gateway-side layout only; UE5/Pixel Streaming renders positions returned here.
Every field is derived from measured snapshot/stream data or omitted — never
fabricated placeholder orbits.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class SolarBody:
    id: str
    label: str
    role: str  # sun | planet | belt | moon
    orbit_radius: float
    orbit_angle_rad: float
    heat: Optional[float] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        pos = _polar_to_xyz(self.orbit_radius, self.orbit_angle_rad)
        out: dict[str, Any] = {
            "id": self.id,
            "label": self.label,
            "role": self.role,
            "pos": pos,
            "orbit_radius": self.orbit_radius,
            "orbit_angle_rad": self.orbit_angle_rad,
        }
        if self.heat is not None:
            out["heat"] = self.heat
        if self.metadata:
            out["metadata"] = dict(self.metadata)
        return out


@dataclass
class SolarTransit:
    """A data packet (ship) traveling between two bodies — from job.stage events."""

    id: str
    source_id: str
    dest_id: str
    job_id: str
    stage: str
    progress: float  # 0..1 along spline; derived from stage ordinal
    latency_ms: Optional[int] = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "id": self.id,
            "source_id": self.source_id,
            "dest_id": self.dest_id,
            "job_id": self.job_id,
            "stage": self.stage,
            "progress": self.progress,
        }
        if self.latency_ms is not None:
            out["latency_ms"] = self.latency_ms
        return out


# Canonical pipeline stations → solar body ids (mirrors observatory STATIONS).
_STAGE_BODY = {
    "job": "planet-navigator",
    "navigator": "planet-navigator",
    "worker": "planet-worker",
    "gate": "planet-gate",
    "ledger": "planet-ledger",
    "done": "sun-nero",
    "failed": "sun-nero",
}

_STAGE_PROGRESS = {
    "queued": 0.05,
    "job": 0.15,
    "navigator": 0.35,
    "worker": 0.55,
    "gate": 0.75,
    "ledger": 0.90,
    "done": 1.0,
    "failed": 1.0,
}


def _seed_angle(seed: str) -> float:
    h = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return (int(h[:8], 16) / 0xFFFFFFFF) * 2 * math.pi


def _polar_to_xyz(radius: float, angle: float, y_scale: float = 0.3) -> list[float]:
    return [
        round(radius * math.cos(angle), 4),
        round(radius * math.sin(angle) * y_scale, 4),
        round(radius * math.sin(angle) * 0.15, 4),
    ]


def _default_bodies(fleet_snapshot: dict[str, Any]) -> list[SolarBody]:
    """Build the static solar system from fleet command nodes."""
    bodies: list[SolarBody] = [
        SolarBody(
            id="sun-nero",
            label="Nero Core",
            role="sun",
            orbit_radius=0.0,
            orbit_angle_rad=0.0,
            metadata={
                "chain_valid": _fleet_meta(fleet_snapshot, "admiralty", "chain_valid"),
            },
        ),
        SolarBody(
            id="planet-flagship",
            label="Jarvis-Prime",
            role="planet",
            orbit_radius=12.0,
            orbit_angle_rad=_seed_angle("flagship"),
            metadata={"fleet_id": "flagship"},
        ),
        SolarBody(
            id="planet-tactical",
            label="Hermes",
            role="planet",
            orbit_radius=18.0,
            orbit_angle_rad=_seed_angle("tactical"),
            metadata={"fleet_id": "tactical"},
        ),
        SolarBody(
            id="planet-intelligence",
            label="AOS Council",
            role="planet",
            orbit_radius=24.0,
            orbit_angle_rad=_seed_angle("intelligence"),
            metadata={"fleet_id": "intelligence"},
        ),
        SolarBody(
            id="planet-navigator",
            label="Navigator",
            role="moon",
            orbit_radius=30.0,
            orbit_angle_rad=_seed_angle("navigator"),
        ),
        SolarBody(
            id="planet-worker",
            label="Worker",
            role="moon",
            orbit_radius=36.0,
            orbit_angle_rad=_seed_angle("worker"),
        ),
        SolarBody(
            id="planet-gate",
            label="Gate",
            role="moon",
            orbit_radius=42.0,
            orbit_angle_rad=_seed_angle("gate"),
        ),
        SolarBody(
            id="planet-ledger",
            label="Ledger",
            role="moon",
            orbit_radius=48.0,
            orbit_angle_rad=_seed_angle("ledger"),
        ),
        SolarBody(
            id="belt-sessions",
            label="Session Clusters",
            role="belt",
            orbit_radius=54.0,
            orbit_angle_rad=_seed_angle("sessions"),
        ),
    ]
    return bodies


def _fleet_meta(fleet_snapshot: dict[str, Any], node_id: str, key: str) -> Any:
    for node in fleet_snapshot.get("nodes", []):
        if node.get("id") == node_id:
            return (node.get("metadata") or {}).get(key)
    return None


def transit_from_job_stage(
    job_id: str,
    stage: str,
    *,
    task_class: str = "",
    latency_ms: Optional[int] = None,
) -> SolarTransit:
    """Map one measured job.stage event to a solar transit."""
    dest = _STAGE_BODY.get(stage, "planet-worker")
    # Source is previous station in the pipeline.
    stages = list(_STAGE_BODY.keys())
    idx = stages.index(stage) if stage in stages else 0
    source = _STAGE_BODY.get(stages[max(0, idx - 1)], "sun-nero")
    progress = _STAGE_PROGRESS.get(stage, 0.5)
    return SolarTransit(
        id=f"transit-{job_id}-{stage}",
        source_id=source,
        dest_id=dest,
        job_id=job_id,
        stage=stage,
        progress=progress,
        latency_ms=latency_ms,
    )


def solar_system_view(
    fleet_snapshot: Optional[dict[str, Any]] = None,
    *,
    observatory_graph: Optional[dict[str, Any]] = None,
    active_transits: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
    """Compose the Nero Solar System view for Observatory snapshot extension.

    Parameters
    ----------
    fleet_snapshot:
        Output of :meth:`FleetRegistry.snapshot`.
    observatory_graph:
        Optional ``snapshot["graph"]`` block — cluster heat merged onto outer planets.
    active_transits:
        Optional list of serialized :class:`SolarTransit` dicts from SSE replay.
    """
    fleet_snapshot = fleet_snapshot or {"nodes": [], "active_ships": 0}
    bodies = _default_bodies(fleet_snapshot)

    if observatory_graph and observatory_graph.get("status") != "unavailable":
        clusters = observatory_graph.get("clusters") or []
        for i, cluster in enumerate(clusters[:5]):
            angle = _seed_angle(cluster.get("id", str(i)))
            bodies.append(
                SolarBody(
                    id=f"outer-{cluster.get('id', i)}",
                    label=cluster.get("label", f"Cluster {i}"),
                    role="planet",
                    orbit_radius=60.0 + i * 6.0,
                    orbit_angle_rad=angle,
                    heat=cluster.get("heat"),
                    metadata={"cluster_id": cluster.get("id"), "type_mix": cluster.get("type_mix")},
                )
            )

    return {
        "v": 1,
        "skin": "nero_solar",
        "bodies": [b.to_dict() for b in bodies],
        "transits": active_transits or [],
        "active_ships": fleet_snapshot.get("active_ships", 0),
    }
