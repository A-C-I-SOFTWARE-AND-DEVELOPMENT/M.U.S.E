"""Fleet Admiralty registry — aggregates measured telemetry from runtime seams."""

from __future__ import annotations

import threading
from typing import Any, Optional

from hermes_cli.jarvis_prime.fleet.nodes import (
    AdmiraltyNode,
    FlagshipNode,
    FleetShip,
    IntelligenceFleetNode,
    NodeStatus,
    TacticalVesselNode,
)

_REGISTRY: Optional["FleetRegistry"] = None
_LOCK = threading.Lock()


class FleetRegistry:
    """Central registry for fleet command nodes and active ships.

    Thread-safe for gateway/agent concurrent updates. Does not mutate
    orchestrator state — records telemetry only.
    """

    def __init__(self) -> None:
        self.admiralty = AdmiraltyNode()
        self.flagship = FlagshipNode()
        self.tactical = TacticalVesselNode()
        self.intelligence = IntelligenceFleetNode()
        self._ships: dict[str, FleetShip] = {}
        self._lock = threading.Lock()

    def _command_nodes(self) -> tuple[AdmiraltyNode, FlagshipNode, TacticalVesselNode, IntelligenceFleetNode]:
        return self.admiralty, self.flagship, self.tactical, self.intelligence

    def _refresh_chain_status(self) -> None:
        """Pull AXIOM chain validity into Admiralty metadata (measured only)."""
        try:
            from hermes_cli.jarvis_prime.axiom_bridge import get_bridge

            audit = get_bridge().audit()
            chain_valid = audit.get("chain_valid")
            self.admiralty.metadata["chain_valid"] = chain_valid
            if chain_valid is False:
                self.admiralty.status = NodeStatus.BLOCKED
            elif self.admiralty.status == NodeStatus.BLOCKED:
                self.admiralty.status = NodeStatus.IDLE
        except Exception:
            self.admiralty.metadata["chain_valid"] = None

    def register_ship(
        self,
        ship_id: str,
        label: str,
        *,
        parent_id: str = "tactical",
        task_class: str = "",
        job_id: str = "",
    ) -> FleetShip:
        with self._lock:
            ship = FleetShip(
                ship_id,
                label,
                parent_id=parent_id,
                task_class=task_class,
                job_id=job_id,
            )
            self._ships[ship_id] = ship
            parent = self._node_by_id(parent_id)
            if parent is not None:
                parent.active_jobs = sum(
                    1 for s in self._ships.values() if s.parent_id == parent_id
                )
                parent.touch(status=NodeStatus.ACTIVE)
            self.admiralty.touch()
            return ship

    def release_ship(self, ship_id: str) -> None:
        with self._lock:
            ship = self._ships.pop(ship_id, None)
            if ship is None:
                return
            parent = self._node_by_id(ship.parent_id)
            if parent is not None:
                parent.active_jobs = sum(
                    1 for s in self._ships.values() if s.parent_id == ship.parent_id
                )
                if parent.active_jobs == 0:
                    parent.status = NodeStatus.IDLE
            self.admiralty.touch()

    def record_job_stage(
        self,
        job_id: str,
        stage: str,
        *,
        task_class: str = "",
        parent_id: str = "tactical",
    ) -> None:
        """Mirror an orchestrator stage transition into fleet telemetry."""
        ship_id = f"ship-{job_id}"
        with self._lock:
            ship = self._ships.get(ship_id)
            if ship is None:
                ship = self.register_ship(
                    ship_id,
                    label=f"Job {job_id[:8]}",
                    parent_id=parent_id,
                    task_class=task_class,
                    job_id=job_id,
                )
            ship.touch(status=NodeStatus.ACTIVE, stage=stage, task_class=task_class)
            if stage in ("done", "failed", "cancelled"):
                self.release_ship(ship_id)

    def record_aos_audit(self, *, audit_id: str, status: str = "running") -> None:
        """Record an AOS council audit on the intelligence frigate."""
        with self._lock:
            self.intelligence.touch(
                status=NodeStatus.ACTIVE if status == "running" else NodeStatus.IDLE,
                audit_id=audit_id,
            )
            self.flagship.touch(status=NodeStatus.ACTIVE)

    def record_mode(self, mode: str) -> None:
        """Record Jarvis-Prime mode activation on the flagship."""
        with self._lock:
            self.flagship.touch(status=NodeStatus.ACTIVE, mode=mode)

    def record_tool_actuation(self, tool_name: str) -> None:
        """Record Hermes tool execution on the tactical cruiser."""
        with self._lock:
            self.tactical.touch(status=NodeStatus.ACTIVE, last_tool=tool_name)

    def _node_by_id(self, node_id: str) -> Any:
        for node in self._command_nodes():
            if node.id == node_id:
                return node
        return None

    def snapshot(self) -> dict[str, Any]:
        """Full fleet telemetry snapshot for Observatory / cockpit consumers."""
        with self._lock:
            self._refresh_chain_status()
            nodes = []
            for node in self._command_nodes():
                children = []
                if node.id == "admiralty":
                    children = ["flagship"]
                elif node.id == "flagship":
                    children = ["tactical", "intelligence"]
                elif node.id in ("tactical", "intelligence"):
                    children = [
                        s.id for s in self._ships.values() if s.parent_id == node.id
                    ]
                nodes.append(node.to_dict(children=children or None))
            for ship in self._ships.values():
                nodes.append(ship.to_dict())
            return {
                "v": 1,
                "nodes": nodes,
                "active_ships": len(self._ships),
            }


def get_registry() -> FleetRegistry:
    global _REGISTRY
    with _LOCK:
        if _REGISTRY is None:
            _REGISTRY = FleetRegistry()
        return _REGISTRY


def reset_registry() -> None:
    """Test helper — discard the process-global registry."""
    global _REGISTRY
    with _LOCK:
        _REGISTRY = None
