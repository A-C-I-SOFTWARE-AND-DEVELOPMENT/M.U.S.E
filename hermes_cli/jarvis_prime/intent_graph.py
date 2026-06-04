"""Typed semantic intent graph (IR) for the JARVIS Prime NL compiler.

This is the *front half* of the natural-language programming pipeline: a
plain-English request is parsed (by :mod:`semantic_frontend`) into a typed
graph of concepts/slots/constraints/actions, the backend selector scores
that graph, and a backend compiler emits an artifact (a ``CodingWorkPacket``
or an ``AutomationFlow``).

Design notes
------------
- This is a **purpose-built, lightweight IR**, deliberately *not* the
  analytical ``graphrag.graph.KnowledgeGraph``. That graph models *existing*
  repo artifacts (FILE/FUNCTION/CALLS) for retrieval; this one models a
  *requested* program's semantics (Trigger/Operation/Constraint). They share
  design idioms (deterministic ids, ``to_dict``/``from_dict`` round-trips,
  provenance pointers) but not their type vocabulary.
- ``graph_id`` reuses :func:`guardrail_evidence.canonical_json` /
  :func:`guardrail_evidence.sha256_hex`, the exact scheme behind
  ``CodingWorkPacket.packet_id`` — the same logical request hashes the same.
- Everything here is frozen/immutable and IO-free. No execution, no disk.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping

from hermes_cli.jarvis_prime.guardrail_evidence import canonical_json, sha256_hex
from hermes_cli.jarvis_prime.natural_language_coder import (
    CodingIntent,
    OwnerGate,
    RiskClass,
)


# ---------------------------------------------------------------------------
# Node / edge / slot vocabulary
# ---------------------------------------------------------------------------


class IntentNodeKind(str, Enum):
    ENTITY = "entity"              # a domain object: "invoice", "vendor", "ledger"
    DATA_SOURCE = "data_source"    # where data comes from: email, repo file, api
    TRIGGER = "trigger"            # event that starts a flow: "when X arrives"
    OPERATION = "operation"        # an action verb: extract / write / refactor
    CONSTRAINT = "constraint"      # typed predicate / guard: "if vendor is new"
    POLICY = "policy"              # owner-gate / risk policy hook
    OUTPUT = "output"              # produced artifact: alert / file edit / row
    QUALITY_TARGET = "quality_target"  # acceptance / verification expectation
    BACKEND_HINT = "backend_hint"  # explicit steer: "as a workflow"


class IntentEdgeKind(str, Enum):
    TRIGGERS = "triggers"            # TRIGGER -> OPERATION
    READS_FROM = "reads_from"        # OPERATION -> DATA_SOURCE
    PRODUCES = "produces"            # OPERATION -> OUTPUT
    OPERATES_ON = "operates_on"      # OPERATION -> ENTITY
    CONSTRAINED_BY = "constrained_by"  # OPERATION/OUTPUT -> CONSTRAINT
    GUARDED_BY = "guarded_by"        # OPERATION/OUTPUT -> POLICY
    DEPENDS_ON = "depends_on"        # OPERATION -> OPERATION (sequencing)
    ALERTS = "alerts"               # OPERATION -> OUTPUT (notification)


# Verbs that imply editing the repository (drive REPO_WORK_PACKET selection).
REPO_EDIT_VERBS: frozenset[str] = frozenset(
    {
        "add",
        "implement",
        "build",
        "create",
        "wire",
        "support",
        "refactor",
        "rename",
        "fix",
        "test",
        "document",
        "review",
        "audit",
    }
)

# Output/source labels that imply non-repo IO (drive AUTOMATION_FLOW selection).
NON_REPO_IO_LABELS: frozenset[str] = frozenset(
    {"email", "inbox", "api", "alert", "message", "notification", "ledger"}
)

# BACKEND_HINT labels that name a concrete language target (drive PYTHON/SQL/RUST).
_LANG_TARGETS: frozenset[str] = frozenset({"python", "sql", "rust"})

# Verbs that imply a declarative read (drive SQL selection).
_READ_VERBS: frozenset[str] = frozenset(
    {"read", "extract", "fetch", "query", "select", "list", "get"}
)


@dataclass(frozen=True)
class Slot:
    """A typed, possibly-unresolved key/value carried by a node.

    ``value is None`` on a ``required`` slot is the signal the frontend uses
    to raise an ambiguity rather than guess.
    """

    name: str
    type: str = "string"
    value: object | None = None
    required: bool = True

    @property
    def filled(self) -> bool:
        return self.value is not None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "type": self.type,
            "value": self.value,
            "required": self.required,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Slot":
        return cls(
            name=str(data.get("name", "")),
            type=str(data.get("type", "string")),
            value=data.get("value"),
            required=bool(data.get("required", True)),
        )


@dataclass(frozen=True)
class IntentNode:
    id: str
    kind: IntentNodeKind
    label: str
    slots: tuple[Slot, ...] = ()
    sources: tuple[str, ...] = ()  # provenance pointers (text spans / phrases)

    @classmethod
    def make(
        cls,
        kind: IntentNodeKind,
        label: str,
        *,
        slots: tuple[Slot, ...] = (),
        sources: tuple[str, ...] = (),
    ) -> "IntentNode":
        """Build a node with a deterministic id over (kind, label, slot names)."""

        stable = [kind.value, label, sorted(s.name for s in slots)]
        node_id = sha256_hex(canonical_json(stable))[:16]
        return cls(id=node_id, kind=kind, label=label, slots=tuple(slots),
                   sources=tuple(sources))

    def slot(self, name: str) -> Slot | None:
        for s in self.slots:
            if s.name == name:
                return s
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind.value,
            "label": self.label,
            "slots": [s.to_dict() for s in self.slots],
            "sources": list(self.sources),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "IntentNode":
        return cls(
            id=str(data["id"]),
            kind=IntentNodeKind(data["kind"]),
            label=str(data.get("label", "")),
            slots=tuple(Slot.from_dict(s) for s in data.get("slots", ())),
            sources=tuple(data.get("sources", ())),
        )


@dataclass(frozen=True)
class IntentEdge:
    src: str
    dst: str
    kind: IntentEdgeKind

    def to_dict(self) -> dict[str, Any]:
        return {"src": self.src, "dst": self.dst, "kind": self.kind.value}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "IntentEdge":
        return cls(
            src=str(data["src"]),
            dst=str(data["dst"]),
            kind=IntentEdgeKind(data["kind"]),
        )


# ---------------------------------------------------------------------------
# The graph
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class IntentGraph:
    nodes: tuple[IntentNode, ...] = ()
    edges: tuple[IntentEdge, ...] = ()
    intent: CodingIntent = CodingIntent.UNKNOWN
    risk_class: RiskClass = RiskClass.RC1
    owner_gates: tuple[OwnerGate, ...] = ()
    raw_text: str = ""
    blocked: bool = False

    # -- queries ------------------------------------------------------------

    def nodes_of(self, kind: IntentNodeKind) -> tuple[IntentNode, ...]:
        return tuple(n for n in self.nodes if n.kind == kind)

    def has_kind(self, kind: IntentNodeKind) -> bool:
        return any(n.kind == kind for n in self.nodes)

    def unfilled_required_slots(self) -> tuple[tuple[IntentNode, Slot], ...]:
        out: list[tuple[IntentNode, Slot]] = []
        for node in self.nodes:
            for s in node.slots:
                if s.required and not s.filled:
                    out.append((node, s))
        return tuple(out)

    def feature_vector(self) -> dict[str, Any]:
        """The *only* surface the backend selector reads.

        Keeps the selector from reaching into node internals — it scores a
        flat dict of structural features.
        """

        edit_verbs = 0
        for op in self.nodes_of(IntentNodeKind.OPERATION):
            verb_slot = op.slot("verb")
            verb = str(verb_slot.value).lower() if verb_slot and verb_slot.value else op.label.lower()
            if verb in REPO_EDIT_VERBS:
                edit_verbs += 1

        labels = {n.label.lower() for n in self.nodes}
        non_repo_io = bool(labels & NON_REPO_IO_LABELS)
        repo_scoped = edit_verbs > 0 or any(
            "/" in n.label or n.label.endswith(".py") or "**" in n.label
            for n in self.nodes
        )
        output_kinds = [n.label for n in self.nodes_of(IntentNodeKind.OUTPUT)]
        hint_nodes = self.nodes_of(IntentNodeKind.BACKEND_HINT)
        backend_hint = hint_nodes[0].label if hint_nodes else None

        # Language hint: a BACKEND_HINT pointing at a concrete language target.
        lang_hint = next(
            (n.label for n in hint_nodes if n.label in _LANG_TARGETS), None
        )

        # Declarative-read signal (drives SQL): read/extract/fetch operations
        # over a data source/entity, with no edits and no event trigger.
        read_ops = False
        for op in self.nodes_of(IntentNodeKind.OPERATION):
            verb_slot = op.slot("verb")
            verb = str(verb_slot.value).lower() if verb_slot and verb_slot.value else op.label.lower()
            if verb in _READ_VERBS:
                read_ops = True
                break
        has_data = self.has_kind(IntentNodeKind.DATA_SOURCE) or self.has_kind(
            IntentNodeKind.ENTITY
        )
        read_only = (
            read_ops
            and edit_verbs == 0
            and has_data
            and not self.has_kind(IntentNodeKind.TRIGGER)
        )

        return {
            "has_trigger": self.has_kind(IntentNodeKind.TRIGGER),
            "edit_verbs": edit_verbs,
            "repo_scoped": repo_scoped,
            "non_repo_io": non_repo_io,
            "output_kinds": output_kinds,
            "backend_hint": backend_hint,
            "lang_hint": lang_hint,
            "read_only": read_only,
            "unresolved": len(self.unfilled_required_slots()),
            "blocked": self.blocked,
        }

    # -- identity / serialization ------------------------------------------

    @property
    def graph_id(self) -> str:
        """Deterministic id over the *semantic* shape (not raw text/timestamps).

        Mirrors ``CodingWorkPacket.packet_id``: the same logical request always
        hashes the same, so compile decisions are replay-safe.
        """

        stable = {
            "nodes": sorted(
                [n.kind.value, n.label, sorted(s.name for s in n.slots)]
                for n in self.nodes
            ),
            "edges": sorted(
                [e.src, e.dst, e.kind.value] for e in self.edges
            ),
            "intent": self.intent.value,
            "risk_class": self.risk_class.value,
            "owner_gates": sorted(g.value for g in self.owner_gates),
            "blocked": self.blocked,
        }
        return sha256_hex(canonical_json(stable))

    def to_dict(self) -> dict[str, Any]:
        return {
            "graph_id": self.graph_id,
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "intent": self.intent.value,
            "risk_class": self.risk_class.value,
            "owner_gates": [g.value for g in self.owner_gates],
            "raw_text": self.raw_text,
            "blocked": self.blocked,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "IntentGraph":
        return cls(
            nodes=tuple(IntentNode.from_dict(n) for n in data.get("nodes", ())),
            edges=tuple(IntentEdge.from_dict(e) for e in data.get("edges", ())),
            intent=CodingIntent(data.get("intent", CodingIntent.UNKNOWN.value)),
            risk_class=RiskClass(data.get("risk_class", RiskClass.RC1.value)),
            owner_gates=tuple(
                OwnerGate(g) for g in data.get("owner_gates", ())
            ),
            raw_text=str(data.get("raw_text", "")),
            blocked=bool(data.get("blocked", False)),
        )


__all__ = [
    "IntentNodeKind",
    "IntentEdgeKind",
    "Slot",
    "IntentNode",
    "IntentEdge",
    "IntentGraph",
    "REPO_EDIT_VERBS",
    "NON_REPO_IO_LABELS",
]
