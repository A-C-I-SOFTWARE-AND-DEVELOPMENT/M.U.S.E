"""Reasoning engine (Layer 4).

Operates over a working set of :class:`~knowledge.models.MemoryNode` objects
(typically the output of the retrieval orchestrator) plus, optionally, the
graph store. It provides:

* multi-hop traversal over the relationship graph,
* contradiction / conflict detection,
* confidence-weighted inference (noisy-OR corroboration),
* structured reasoning expansion that ties the above together.

The in-memory path requires no database, so reasoning is fully runnable and
testable offline; a :class:`~knowledge.graph_store.GraphStore` can be supplied
to widen traversal beyond the working set.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from .config import Settings
from .models import ConflictType, MemoryNode, Relationship

logger = logging.getLogger(__name__)

__all__ = [
    "ReasoningStep",
    "ReasoningTrace",
    "Conflict",
    "Inference",
    "ReasoningResult",
    "ReasoningEngine",
]

# Predicates that are symmetric/loose and must not be treated as contradictions.
_LOOSE_PREDICATES = frozenset({"co_occurs_with", "related_to"})


@dataclass(slots=True)
class ReasoningStep:
    """A single edge traversed during multi-hop reasoning."""

    hop: int
    subject: str
    predicate: str
    object: str
    node_id: str
    confidence: float


@dataclass(slots=True)
class ReasoningTrace:
    """An ordered set of reasoning steps grouped by hop distance."""

    seeds: List[str] = field(default_factory=list)
    steps: List[ReasoningStep] = field(default_factory=list)

    def by_hop(self) -> Dict[int, List[ReasoningStep]]:
        grouped: Dict[int, List[ReasoningStep]] = defaultdict(list)
        for step in self.steps:
            grouped[step.hop].append(step)
        return dict(grouped)


@dataclass(slots=True)
class Conflict:
    """A detected contradiction across nodes for a (subject, predicate)."""

    subject: str
    predicate: str
    conflict_type: ConflictType
    options: List[Tuple[str, float, str]]  # (object, confidence, node_id)
    resolution: Optional[str] = None
    resolved_node_id: Optional[str] = None

    @property
    def is_resolved(self) -> bool:
        return self.resolution is not None


@dataclass(slots=True)
class Inference:
    """A corroborated, confidence-weighted statement derived from nodes."""

    subject: str
    predicate: str
    object: str
    confidence: float
    supporting_node_ids: List[str] = field(default_factory=list)

    def as_text(self) -> str:
        return f"{self.subject} {self.predicate} {self.object}"


@dataclass(slots=True)
class ReasoningResult:
    """Aggregated output of a reasoning expansion."""

    trace: ReasoningTrace
    conflicts: List[Conflict] = field(default_factory=list)
    inferences: List[Inference] = field(default_factory=list)
    entities: List[str] = field(default_factory=list)


_Edge = Tuple[str, str, str, str, float]  # (subject, predicate, object, node_id, confidence)


class ReasoningEngine:
    """Multi-hop, conflict-aware, confidence-weighted reasoning."""

    def __init__(self, *, settings: Settings, graph_store: Optional[object] = None) -> None:
        self._settings = settings
        self._graph_store = graph_store

    # -- public API -------------------------------------------------------- #
    def reason(
        self,
        nodes: Sequence[MemoryNode],
        *,
        seeds: Optional[Sequence[str]] = None,
        max_hops: Optional[int] = None,
    ) -> ReasoningResult:
        """Run the full reasoning expansion over a working set of nodes."""
        max_hops = self._settings.retrieval.graph_hops if max_hops is None else max_hops
        edges = self._collect_edges(nodes)
        seed_entities = list(seeds) if seeds else self._infer_seeds(nodes)
        trace = self.multi_hop(edges, seed_entities, max_hops)
        conflicts = self.detect_conflicts(edges)
        inferences = self.weighted_inference(edges)
        entities = sorted({e for node in nodes for e in node.entities})
        logger.debug(
            "reason nodes=%d edges=%d seeds=%d steps=%d conflicts=%d inferences=%d",
            len(nodes), len(edges), len(seed_entities), len(trace.steps),
            len(conflicts), len(inferences),
        )
        return ReasoningResult(
            trace=trace,
            conflicts=conflicts,
            inferences=inferences,
            entities=entities,
        )

    def multi_hop(
        self, edges: Sequence[_Edge], seeds: Sequence[str], max_hops: int
    ) -> ReasoningTrace:
        """Breadth-first traversal of the relationship graph from ``seeds``."""
        adjacency: Dict[str, List[_Edge]] = defaultdict(list)
        for edge in edges:
            adjacency[edge[0].lower()].append(edge)
        trace = ReasoningTrace(seeds=list(seeds))
        visited = {s.lower() for s in seeds}
        frontier = list({s.lower() for s in seeds})
        for hop in range(1, max(1, max_hops) + 1):
            next_frontier: List[str] = []
            for entity_key in frontier:
                for subject, predicate, obj, node_id, confidence in adjacency.get(
                    entity_key, []
                ):
                    trace.steps.append(
                        ReasoningStep(
                            hop=hop,
                            subject=subject,
                            predicate=predicate,
                            object=obj,
                            node_id=node_id,
                            confidence=confidence,
                        )
                    )
                    obj_key = obj.lower()
                    if obj_key not in visited:
                        visited.add(obj_key)
                        next_frontier.append(obj_key)
            if not next_frontier:
                break
            frontier = next_frontier
        return trace

    def detect_conflicts(self, edges: Sequence[_Edge]) -> List[Conflict]:
        """Flag (subject, predicate) pairs that map to incompatible objects.

        For each (subject, predicate) we keep the highest-confidence sighting of
        every distinct object. When more than one distinct object survives, the
        pair is contradictory and is resolved in favour of the highest-confidence
        object (confidence-weighted resolution).
        """
        surface: Dict[Tuple[str, str], Dict[str, Tuple[str, float, str]]] = defaultdict(dict)
        for subject, predicate, obj, node_id, confidence in edges:
            if predicate in _LOOSE_PREDICATES:
                continue
            key = (subject.lower(), predicate.lower())
            current = surface[key].get(obj.lower())
            if current is None or confidence > current[1]:
                surface[key][obj.lower()] = (obj, confidence, node_id)

        conflicts: List[Conflict] = []
        for (subj_key, pred_key), objects in surface.items():
            if len(objects) < 2:
                continue
            options = sorted(objects.values(), key=lambda t: t[1], reverse=True)
            best_obj, _best_conf, best_node = options[0]
            conflicts.append(
                Conflict(
                    subject=subj_key,
                    predicate=pred_key,
                    conflict_type=ConflictType.VALUE_MISMATCH,
                    options=[(o, c, n) for (o, c, n) in options],
                    resolution=best_obj,
                    resolved_node_id=best_node,
                )
            )
        return conflicts

    def weighted_inference(self, edges: Sequence[_Edge]) -> List[Inference]:
        """Aggregate corroborating edges into confidence-weighted inferences.

        Identical (subject, predicate, object) triples observed across multiple
        nodes are combined with noisy-OR: ``1 - prod(1 - confidence_i)``.
        """
        grouped: Dict[Tuple[str, str, str], List[Tuple[float, str]]] = defaultdict(list)
        surface: Dict[Tuple[str, str, str], Tuple[str, str, str]] = {}
        for subject, predicate, obj, node_id, confidence in edges:
            key = (subject.lower(), predicate.lower(), obj.lower())
            grouped[key].append((confidence, node_id))
            surface.setdefault(key, (subject, predicate, obj))

        inferences: List[Inference] = []
        for key, observations in grouped.items():
            miss = 1.0
            support: List[str] = []
            for confidence, node_id in observations:
                miss *= 1.0 - max(0.0, min(1.0, confidence))
                support.append(node_id)
            subject, predicate, obj = surface[key]
            inferences.append(
                Inference(
                    subject=subject,
                    predicate=predicate,
                    object=obj,
                    confidence=round(1.0 - miss, 6),
                    supporting_node_ids=support,
                )
            )
        inferences.sort(key=lambda inf: inf.confidence, reverse=True)
        return inferences

    # -- helpers ----------------------------------------------------------- #
    @staticmethod
    def _collect_edges(nodes: Sequence[MemoryNode]) -> List[_Edge]:
        edges: List[_Edge] = []
        for node in nodes:
            relationships: List[Relationship] = node.decoded_relationships()
            for rel in relationships:
                edges.append(
                    (rel.subject, rel.predicate, rel.object, node.id, rel.confidence)
                )
        return edges

    @staticmethod
    def _infer_seeds(nodes: Sequence[MemoryNode]) -> List[str]:
        freq: Dict[str, int] = defaultdict(int)
        for node in nodes:
            for entity in node.entities:
                freq[entity] += 1
        ranked = sorted(freq.items(), key=lambda kv: kv[1], reverse=True)
        return [entity for entity, _ in ranked[:8]]
