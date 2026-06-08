"""Tests for the MUSE semantic intent graph (IR).

Covers id determinism, to_dict/from_dict round-trips, unresolved-slot
detection, and the feature_vector contract the backend selector reads.
"""

from __future__ import annotations

from hermes_cli.jarvis_prime.intent_graph import (
    IntentEdge,
    IntentEdgeKind,
    IntentGraph,
    IntentNode,
    IntentNodeKind,
    Slot,
)
from hermes_cli.jarvis_prime.natural_language_coder import (
    CodingIntent,
    OwnerGate,
    RiskClass,
)


def _trigger_graph() -> IntentGraph:
    trigger = IntentNode.make(IntentNodeKind.TRIGGER, "invoice email received")
    op = IntentNode.make(
        IntentNodeKind.OPERATION,
        "extract",
        slots=(Slot("verb", "string", "extract"), Slot("field", "string", "total")),
    )
    alert = IntentNode.make(IntentNodeKind.OUTPUT, "alert")
    return IntentGraph(
        nodes=(trigger, op, alert),
        edges=(
            IntentEdge(trigger.id, op.id, IntentEdgeKind.TRIGGERS),
            IntentEdge(op.id, alert.id, IntentEdgeKind.ALERTS),
        ),
        intent=CodingIntent.IMPLEMENT,
        risk_class=RiskClass.RC3,
        owner_gates=(OwnerGate.EXTERNAL_MESSAGE,),
        raw_text="when an invoice email arrives, extract the total and alert me",
    )


def test_node_id_is_deterministic() -> None:
    a = IntentNode.make(IntentNodeKind.OPERATION, "extract", slots=(Slot("field"),))
    b = IntentNode.make(IntentNodeKind.OPERATION, "extract", slots=(Slot("field"),))
    assert a.id == b.id
    c = IntentNode.make(IntentNodeKind.OPERATION, "write")
    assert c.id != a.id


def test_graph_id_stable_across_rebuild_and_text_independent() -> None:
    g1 = _trigger_graph()
    g2 = _trigger_graph()
    assert g1.graph_id == g2.graph_id
    # graph_id keys on semantics, not the raw prompt wording.
    g3 = IntentGraph(
        nodes=g1.nodes, edges=g1.edges, intent=g1.intent,
        risk_class=g1.risk_class, owner_gates=g1.owner_gates,
        raw_text="totally different wording but same parsed graph",
    )
    assert g3.graph_id == g1.graph_id


def test_graph_id_changes_on_semantic_change() -> None:
    g1 = _trigger_graph()
    extra = IntentNode.make(IntentNodeKind.OPERATION, "write",
                            slots=(Slot("verb", "string", "write"),))
    g2 = IntentGraph(
        nodes=g1.nodes + (extra,), edges=g1.edges, intent=g1.intent,
        risk_class=g1.risk_class, owner_gates=g1.owner_gates,
    )
    assert g2.graph_id != g1.graph_id


def test_to_from_dict_round_trip() -> None:
    g = _trigger_graph()
    restored = IntentGraph.from_dict(g.to_dict())
    assert restored.graph_id == g.graph_id
    assert restored.intent == g.intent
    assert restored.owner_gates == g.owner_gates
    assert {n.label for n in restored.nodes} == {n.label for n in g.nodes}


def test_unfilled_required_slots_detected() -> None:
    node = IntentNode.make(
        IntentNodeKind.OPERATION,
        "write",
        slots=(Slot("target", "string", value=None, required=True),
               Slot("optional", "string", value=None, required=False)),
    )
    g = IntentGraph(nodes=(node,))
    unresolved = g.unfilled_required_slots()
    assert len(unresolved) == 1
    assert unresolved[0][1].name == "target"


def test_feature_vector_flags_trigger_and_io() -> None:
    fv = _trigger_graph().feature_vector()
    assert fv["has_trigger"] is True
    assert fv["non_repo_io"] is True          # "alert" output
    assert fv["edit_verbs"] == 0
    assert "alert" in fv["output_kinds"]


def test_feature_vector_flags_repo_edit() -> None:
    op = IntentNode.make(
        IntentNodeKind.OPERATION,
        "refactor",
        slots=(Slot("verb", "string", "refactor"),),
    )
    target = IntentNode.make(IntentNodeKind.DATA_SOURCE, "gateway/retry.py")
    g = IntentGraph(nodes=(op, target), intent=CodingIntent.REFACTOR)
    fv = g.feature_vector()
    assert fv["edit_verbs"] == 1
    assert fv["repo_scoped"] is True
    assert fv["has_trigger"] is False
