"""Fleet node taxonomy — read-only telemetry facades over runtime entities."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class NodeKind(str, Enum):
    ADMIRALTY = "admiralty"
    FLAGSHIP = "flagship"
    TACTICAL = "tactical"
    INTELLIGENCE = "intelligence"
    SHIP = "ship"


class NodeStatus(str, Enum):
    ACTIVE = "active"
    IDLE = "idle"
    BLOCKED = "blocked"
    OWNER_GATED = "owner_gated"
    UNAVAILABLE = "unavailable"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class FleetNode:
    """Base fleet telemetry node. Subclasses represent fixed command slots."""

    id: str
    kind: NodeKind
    label: str
    parent_id: Optional[str] = None
    status: NodeStatus = NodeStatus.IDLE
    active_jobs: int = 0
    last_event_ts: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def touch(self, *, status: Optional[NodeStatus] = None, **meta: Any) -> None:
        self.last_event_ts = _utc_now_iso()
        if status is not None:
            self.status = status
        if meta:
            self.metadata.update(meta)

    def to_dict(self, *, children: Optional[list[str]] = None) -> dict[str, Any]:
        out: dict[str, Any] = {
            "id": self.id,
            "kind": self.kind.value,
            "label": self.label,
            "status": self.status.value,
            "active_jobs": self.active_jobs,
            "last_event_ts": self.last_event_ts,
        }
        if self.parent_id:
            out["parent_id"] = self.parent_id
        if children:
            out["children"] = children
        if self.metadata:
            out["metadata"] = dict(self.metadata)
        return out


@dataclass
class AdmiraltyNode(FleetNode):
    """M.U.S.E — gateway routing, Memory Tree, Admiralty registry root."""

    def __init__(self) -> None:
        super().__init__(
            id="admiralty",
            kind=NodeKind.ADMIRALTY,
            label="M.U.S.E Admiralty",
            parent_id=None,
        )


@dataclass
class FlagshipNode(FleetNode):
    """Jarvis-Prime — Operator / Strategy / Builder mode command."""

    def __init__(self) -> None:
        super().__init__(
            id="flagship",
            kind=NodeKind.FLAGSHIP,
            label="Jarvis-Prime Flagship",
            parent_id="admiralty",
        )


@dataclass
class TacticalVesselNode(FleetNode):
    """Hermes — CLI, tools, gateway agent execution shell."""

    def __init__(self) -> None:
        super().__init__(
            id="tactical",
            kind=NodeKind.TACTICAL,
            label="M.U.S.E. Tactical Cruiser",
            parent_id="flagship",
        )


@dataclass
class IntelligenceFleetNode(FleetNode):
    """AOS Enterprise Council — multi-perspective audit and judgment."""

    def __init__(self) -> None:
        super().__init__(
            id="intelligence",
            kind=NodeKind.INTELLIGENCE,
            label="AOS Intelligence Frigate",
            parent_id="flagship",
        )


@dataclass
class FleetShip(FleetNode):
    """A dispatched worker or kanban assignee under a fleet command node."""

    def __init__(
        self,
        ship_id: str,
        label: str,
        *,
        parent_id: str,
        task_class: str = "",
        job_id: str = "",
    ) -> None:
        super().__init__(
            id=ship_id,
            kind=NodeKind.SHIP,
            label=label,
            parent_id=parent_id,
            status=NodeStatus.ACTIVE,
        )
        self.metadata["task_class"] = task_class
        self.metadata["job_id"] = job_id
