"""Open-world RPG production blueprint — the studio's executable build plan.

This is the muse verifiable-arena capability map *as code*, not a doc: a
machine-readable blueprint (``data/open_world_rpg_blueprint.json``) describing
the 27 reviewed capability domains, the phased roadmap, the critical path, the
cross-domain dependency graph, and the engine recommendation — plus typed
accessors the :class:`~agent.studio.orchestrator.StudioOrchestrator` consumes to
*scaffold and plan* a Skyrim-CLASS production.

Original-IP only: genre techniques and reusable game SYSTEMS — no Bethesda
assets, names, world, or lore.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

_BLUEPRINT_PATH = (
    Path(__file__).resolve().parent / "resources" / "open_world_rpg_blueprint.json"
)

_PRIORITY_ORDER = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}


@dataclass(frozen=True)
class CapabilityDomain:
    """One reviewed capability domain (e.g. ``world_streaming``)."""

    key: str
    lane: str
    priority: str  # P0 (foundational) .. P3 (polish)
    confidence: float
    summary: str
    capabilities: tuple[str, ...]
    dependencies: tuple[str, ...]
    effort_band: str
    milestones: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key, "lane": self.lane, "priority": self.priority,
            "confidence": self.confidence, "summary": self.summary,
            "capabilities": list(self.capabilities),
            "dependencies": list(self.dependencies),
            "effort_band": self.effort_band, "milestones": list(self.milestones),
        }


@dataclass(frozen=True)
class RoadmapPhase:
    """One phase of the build roadmap, ending in a concrete vertical slice."""

    phase: str
    goal: str
    domains: tuple[str, ...]
    vertical_slice: str
    exit_criteria: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "phase": self.phase, "goal": self.goal, "domains": list(self.domains),
            "vertical_slice": self.vertical_slice, "exit_criteria": self.exit_criteria,
        }


@dataclass(frozen=True)
class DependencyEdge:
    """A critical "src must exist before dst" edge across domains."""

    src: str
    dst: str
    why: str

    def to_dict(self) -> dict[str, Any]:
        return {"from": self.src, "to": self.dst, "why": self.why}


@dataclass(frozen=True)
class OpenWorldRpgBlueprint:
    """The full, queryable capability map / build plan."""

    name: str
    engine_recommended: str
    engine_rationale: str
    effort_summary: str
    domains: tuple[CapabilityDomain, ...]
    phases: tuple[RoadmapPhase, ...]
    critical_path: tuple[str, ...]
    dependency_edges: tuple[DependencyEdge, ...]
    top_unknowns: tuple[str, ...]

    def domain(self, key: str) -> Optional[CapabilityDomain]:
        for d in self.domains:
            if d.key == key:
                return d
        return None

    def by_priority(self, priority: str) -> list[CapabilityDomain]:
        return [d for d in self.domains if d.priority == priority]

    @property
    def p0_domains(self) -> list[CapabilityDomain]:
        """Foundational domains, in declared order (the critical substrate)."""
        return self.by_priority("P0")

    def ordered_domains(self) -> list[CapabilityDomain]:
        """All domains sorted by priority (P0 first), then key."""
        return sorted(
            self.domains,
            key=lambda d: (_PRIORITY_ORDER.get(d.priority, 9), d.key),
        )

    def as_plan(self) -> dict[str, Any]:
        """The whole blueprint as a JSON-serializable plan dict."""
        return {
            "name": self.name,
            "engine": {"recommended": self.engine_recommended,
                       "rationale": self.engine_rationale},
            "effort_summary": self.effort_summary,
            "phases": [p.to_dict() for p in self.phases],
            "critical_path": list(self.critical_path),
            "dependency_edges": [e.to_dict() for e in self.dependency_edges],
            "top_unknowns": list(self.top_unknowns),
            "domains": [d.to_dict() for d in self.domains],
        }


def load_open_world_rpg_blueprint(path: Optional[Path] = None) -> OpenWorldRpgBlueprint:
    """Load the shipped open-world RPG blueprint resource (or an override path)."""
    data = json.loads(Path(path or _BLUEPRINT_PATH).read_text(encoding="utf-8"))
    domains = tuple(
        CapabilityDomain(
            key=d["key"],
            lane=d.get("lane", ""),
            priority=d.get("priority", "P3"),
            confidence=float(d.get("confidence") or 0.0),
            summary=d.get("summary", ""),
            capabilities=tuple(d.get("capabilities") or ()),
            dependencies=tuple(d.get("dependencies") or ()),
            effort_band=d.get("effort_band", ""),
            milestones=tuple(d.get("milestones") or ()),
        )
        for d in data.get("domains", [])
    )
    phases = tuple(
        RoadmapPhase(
            phase=p.get("phase", ""),
            goal=p.get("goal", ""),
            domains=tuple(p.get("domains") or ()),
            vertical_slice=p.get("vertical_slice", ""),
            exit_criteria=p.get("exit_criteria", ""),
        )
        for p in data.get("phases", [])
    )
    edges = tuple(
        DependencyEdge(src=e.get("from", ""), dst=e.get("to", ""), why=e.get("why", ""))
        for e in data.get("dependency_edges", [])
    )
    engine = data.get("engine", {}) or {}
    return OpenWorldRpgBlueprint(
        name=data.get("name", "open-world RPG"),
        engine_recommended=engine.get("recommended", ""),
        engine_rationale=engine.get("rationale", ""),
        effort_summary=data.get("effort_summary", ""),
        domains=domains,
        phases=phases,
        critical_path=tuple(data.get("critical_path") or ()),
        dependency_edges=edges,
        top_unknowns=tuple(data.get("top_unknowns") or ()),
    )


__all__ = [
    "CapabilityDomain",
    "RoadmapPhase",
    "DependencyEdge",
    "OpenWorldRpgBlueprint",
    "load_open_world_rpg_blueprint",
]
