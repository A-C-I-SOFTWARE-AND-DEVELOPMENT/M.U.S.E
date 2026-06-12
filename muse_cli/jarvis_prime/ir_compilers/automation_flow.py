"""Automation-flow DSL backend.

Compiles an :class:`IntentGraph` into an ``AutomationFlow`` — a small,
validatable, event/trigger document (the "when an invoice email arrives,
extract the total, write it to the ledger, alert if the vendor is new"
case).

Named ``AutomationFlow`` (not "workflow") deliberately: ``muse_cli.workflows``
already owns a *phase-gated orchestration job* state machine, which is a
different concept. This DSL describes event-driven automations and is the
backend's analog of a ``CodingWorkPacket`` — describe/validate only, no
execution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from muse_cli.jarvis_prime.backend_selector import BackendContext, BackendTarget
from muse_cli.jarvis_prime.guardrail_evidence import canonical_json, sha256_hex
from muse_cli.jarvis_prime.intent_graph import (
    IntentGraph,
    IntentNodeKind,
)
from muse_cli.jarvis_prime.ir_compilers.base import CompileResult
from muse_cli.jarvis_prime.natural_language_coder import _GATE_TO_OWNER_AUTH

# Output kinds that leave the system and therefore require an owner gate.
_EXTERNAL_OUTPUTS = frozenset({"alert", "message"})
_ALLOWED_OPS = frozenset(
    {"extract", "read", "fetch", "save", "write", "compute",
     "alert", "message", "send", "post"}
)


@dataclass(frozen=True)
class FlowTrigger:
    kind: str            # "event"
    event: str
    filters: tuple[dict, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "event": self.event,
                "filters": [dict(f) for f in self.filters]}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "FlowTrigger":
        return cls(kind=str(d.get("kind", "event")), event=str(d.get("event", "")),
                   filters=tuple(d.get("filters", ())))


@dataclass(frozen=True)
class FlowStep:
    id: str
    op: str
    target: str = ""
    params: dict = field(default_factory=dict)
    produces: Optional[str] = None
    owner_gates: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "op": self.op, "target": self.target,
                "params": dict(self.params), "produces": self.produces,
                "owner_gates": list(self.owner_gates)}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "FlowStep":
        return cls(id=str(d["id"]), op=str(d.get("op", "")),
                   target=str(d.get("target", "")), params=dict(d.get("params", {})),
                   produces=d.get("produces"),
                   owner_gates=tuple(d.get("owner_gates", ())))


@dataclass(frozen=True)
class FlowCondition:
    expr: str
    guards: tuple[str, ...] = ()   # step ids this condition guards

    def to_dict(self) -> dict[str, Any]:
        return {"expr": self.expr, "guards": list(self.guards)}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "FlowCondition":
        return cls(expr=str(d.get("expr", "")), guards=tuple(d.get("guards", ())))


@dataclass(frozen=True)
class FlowOutput:
    kind: str            # "alert" | "message" | "file" | "record"
    channel: str = ""
    payload: dict = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "channel": self.channel,
                "payload": dict(self.payload)}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "FlowOutput":
        return cls(kind=str(d.get("kind", "")), channel=str(d.get("channel", "")),
                   payload=dict(d.get("payload", {})))


@dataclass(frozen=True)
class FlowValidationFinding:
    field: str
    severity: str        # "error" | "warning"
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {"field": self.field, "severity": self.severity,
                "message": self.message}


@dataclass(frozen=True)
class FlowValidationResult:
    ok: bool
    findings: tuple[FlowValidationFinding, ...] = ()

    @property
    def errors(self) -> tuple[FlowValidationFinding, ...]:
        return tuple(f for f in self.findings if f.severity == "error")

    def to_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "findings": [f.to_dict() for f in self.findings]}


@dataclass(frozen=True)
class AutomationFlow:
    name: str = ""
    version: str = "hermes.automation.v1"
    triggers: tuple[FlowTrigger, ...] = ()
    steps: tuple[FlowStep, ...] = ()
    conditions: tuple[FlowCondition, ...] = ()
    outputs: tuple[FlowOutput, ...] = ()
    risk_class: str = "RC1"
    owner_gated_actions: tuple[str, ...] = ()
    provenance: dict = field(default_factory=dict)

    @property
    def flow_id(self) -> str:
        stable = {
            "name": self.name,
            "triggers": sorted(t.to_dict()["event"] for t in self.triggers),
            "steps": sorted([s.op, s.target] for s in self.steps),
            "outputs": sorted(o.kind for o in self.outputs),
            "owner_gated_actions": sorted(self.owner_gated_actions),
        }
        return sha256_hex(canonical_json(stable))

    def to_dict(self) -> dict[str, Any]:
        return {
            "flow_id": self.flow_id,
            "name": self.name,
            "version": self.version,
            "triggers": [t.to_dict() for t in self.triggers],
            "steps": [s.to_dict() for s in self.steps],
            "conditions": [c.to_dict() for c in self.conditions],
            "outputs": [o.to_dict() for o in self.outputs],
            "risk_class": self.risk_class,
            "owner_gated_actions": list(self.owner_gated_actions),
            "provenance": dict(self.provenance),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "AutomationFlow":
        return cls(
            name=str(d.get("name", "")),
            version=str(d.get("version", "hermes.automation.v1")),
            triggers=tuple(FlowTrigger.from_dict(t) for t in d.get("triggers", ())),
            steps=tuple(FlowStep.from_dict(s) for s in d.get("steps", ())),
            conditions=tuple(FlowCondition.from_dict(c) for c in d.get("conditions", ())),
            outputs=tuple(FlowOutput.from_dict(o) for o in d.get("outputs", ())),
            risk_class=str(d.get("risk_class", "RC1")),
            owner_gated_actions=tuple(d.get("owner_gated_actions", ())),
            provenance=dict(d.get("provenance", {})),
        )

    def validate(self) -> FlowValidationResult:
        findings: list[FlowValidationFinding] = []

        if not self.triggers:
            findings.append(FlowValidationFinding(
                "triggers", "error", "an automation flow needs at least one trigger"))
        if not self.steps:
            findings.append(FlowValidationFinding(
                "steps", "error", "an automation flow needs at least one step"))

        for s in self.steps:
            if s.op not in _ALLOWED_OPS:
                findings.append(FlowValidationFinding(
                    "steps", "warning", f"unknown step op '{s.op}'"))

        # External outputs (alert/message) must carry an owner gate.
        for out in self.outputs:
            if out.kind in _EXTERNAL_OUTPUTS and not self.owner_gated_actions:
                findings.append(FlowValidationFinding(
                    "outputs", "error",
                    f"external output '{out.kind}' must be owner-gated"))

        ok = not any(f.severity == "error" for f in findings)
        return FlowValidationResult(ok=ok, findings=tuple(findings))


class AutomationFlowCompiler:
    target = BackendTarget.AUTOMATION_FLOW

    def compile(
        self, graph: IntentGraph, context: Optional[BackendContext] = None
    ) -> CompileResult:
        triggers = tuple(
            FlowTrigger(kind="event", event=n.label)
            for n in graph.nodes_of(IntentNodeKind.TRIGGER)
        )

        steps: list[FlowStep] = []
        for i, op in enumerate(graph.nodes_of(IntentNodeKind.OPERATION)):
            verb_slot = op.slot("verb")
            verb = str(verb_slot.value) if verb_slot and verb_slot.value else op.label
            steps.append(FlowStep(id=f"step{i + 1}", op=verb,
                                  target=_first_entity_label(graph)))

        conditions = tuple(
            FlowCondition(expr=_constraint_expr(n))
            for n in graph.nodes_of(IntentNodeKind.CONSTRAINT)
        )

        outputs = tuple(
            FlowOutput(kind=n.label, channel="owner" if n.label in _EXTERNAL_OUTPUTS else "")
            for n in graph.nodes_of(IntentNodeKind.OUTPUT)
        )

        owner_actions = tuple(sorted({
            _GATE_TO_OWNER_AUTH[g] for g in graph.owner_gates
            if g in _GATE_TO_OWNER_AUTH
        }))

        flow = AutomationFlow(
            name=_flow_name(graph),
            triggers=triggers,
            steps=tuple(steps),
            conditions=conditions,
            outputs=outputs,
            risk_class=graph.risk_class.value,
            owner_gated_actions=owner_actions,
            provenance={"graph_id": graph.graph_id},
        )

        result = flow.validate()
        notes = tuple(f"{f.severity}: {f.message}" for f in result.findings)
        return CompileResult(
            target=self.target,
            artifact=flow,
            artifact_dict=flow.to_dict(),
            gate_packet=None,
            notes=notes,
        )


def _constraint_expr(node) -> str:
    slot = node.slot("expr")
    if slot is not None and slot.value is not None:
        return str(slot.value)
    return node.label


def _first_entity_label(graph: IntentGraph) -> str:
    ents = graph.nodes_of(IntentNodeKind.ENTITY)
    return ents[0].label if ents else ""


def _flow_name(graph: IntentGraph) -> str:
    triggers = graph.nodes_of(IntentNodeKind.TRIGGER)
    if triggers:
        return f"on_{triggers[0].label.replace(' ', '_')[:40]}"
    return (graph.raw_text[:40] or "automation").strip().replace(" ", "_")


__all__ = [
    "FlowTrigger",
    "FlowStep",
    "FlowCondition",
    "FlowOutput",
    "FlowValidationFinding",
    "FlowValidationResult",
    "AutomationFlow",
    "AutomationFlowCompiler",
]
