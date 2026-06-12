"""Controlled-English front-end: plain English -> typed IntentGraph.

Deterministic, keyword/grammar driven — no LLM, no IO. It **delegates**
intent / risk / owner-gate / bypass classification to the existing
``route_request`` (one source of truth) and layers concept/slot/constraint
extraction on top.

Ambiguity is a first-class output: when coverage is low or a required slot is
unresolved, the frontend emits :class:`AmbiguityFinding`s with concrete
clarifying questions instead of fabricating intent. The caller
(``nl_compile``) must surface those questions rather than compile a guess.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping, Optional

from muse_cli.jarvis_prime.intent_graph import (
    IntentEdge,
    IntentEdgeKind,
    IntentGraph,
    IntentNode,
    IntentNodeKind,
    Slot,
)
from muse_cli.jarvis_prime.natural_language_coder import route_request


# ---------------------------------------------------------------------------
# Lexicon / ontology (deterministic; extend as the corpus grows)
# ---------------------------------------------------------------------------

_CONFIDENCE_FLOOR = 0.5

# Trigger cues -> the event phrase follows the cue.
_TRIGGER_RE = re.compile(
    r"(?i)\b(?:when|whenever|each time|every time|on (?:a )?new)\b\s+(.+?)"
    r"(?:,|\barrives?\b|\bcomes? in\b|\bis received\b|\bhappens\b|$)"
)

# Verb -> canonical operation category.
_IO_VERBS = {
    "extract": "extract",
    "parse": "extract",
    "read": "read",
    "fetch": "fetch",
    # declarative-read verbs (drive the SQL backend)
    "select": "select",
    "query": "query",
    "list": "list",
    "retrieve": "fetch",
    "lookup": "fetch",
    "save": "save",
    "store": "save",
    "write": "write",
    "append": "write",
    "record": "write",
    "log": "write",
    "compute": "compute",
}
_NOTIFY_VERBS = {
    "alert": "alert",
    "notify": "alert",
    "ping": "alert",
    "message": "message",
    "email": "message",
    "send": "send",
    "post": "post",
}
_EDIT_VERBS = {
    "add": "add",
    "implement": "implement",
    "build": "build",
    "create": "create",
    "wire": "wire",
    "refactor": "refactor",
    "rename": "rename",
    "fix": "fix",
    "test": "test",
    "document": "document",
    "review": "review",
    "audit": "audit",
}

# Noun -> (node kind, normalized label).
_SOURCE_NOUNS = {
    "email": "email",
    "inbox": "email",
    "api": "api",
    "endpoint": "api",
    "database": "api",
}
_OUTPUT_NOUNS = {
    "alert": "alert",
    "notification": "alert",
    "message": "message",
    "ledger": "ledger",
}
_ENTITY_NOUNS = {
    "invoice": "invoice",
    "vendor": "vendor",
    "total": "total",
    "amount": "amount",
    "pdf": "pdf",
    "file": "file",
    "function": "function",
    "module": "module",
    "gateway": "gateway",
}

# Constraint cues.
_CONSTRAINT_RE = re.compile(
    r"(?i)\b(?:if|unless|only if|when)\b\s+(.+?)(?:,|\.|$)"
)

# Explicit backend steers.
_HINT_WORKFLOW = ("as a workflow", "build an automation", "automation flow",
                  "automate")
_HINT_REPO = ("edit the repo", "in the codebase", "add a function",
              "in the repo", "code change")

# Explicit language steers → emit a BACKEND_HINT for the concrete language
# target (python / sql / rust). Checked before the workflow/repo hints.
_LANG_HINTS: tuple[tuple[str, str], ...] = (
    ("in python", "python"),
    ("python function", "python"),
    ("python script", "python"),
    ("python module", "python"),
    ("write a function", "python"),
    ("write a script", "python"),
    ("in rust", "rust"),
    ("rust module", "rust"),
    ("rust function", "rust"),
    ("systems programming", "rust"),
    ("high performance", "rust"),
    ("sql query", "sql"),
    ("select query", "sql"),
    ("query the database", "sql"),
    ("a sql ", "sql"),
)

_STOPWORDS = frozenset(
    {
        "the", "a", "an", "and", "or", "to", "me", "my", "is", "are", "be",
        "with", "for", "of", "in", "on", "it", "that", "this", "do", "please",
        "then", "also", "new", "if", "when", "so", "as", "i", "you", "we",
        "all", "where", "from", "into", "at", "by", "every", "each", "any",
    }
)


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AmbiguityFinding:
    code: str            # "unresolved_slot" | "low_confidence" | "multi_backend"
    node_id: Optional[str]
    message: str
    question: str        # the clarifying question to surface

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "node_id": self.node_id,
            "message": self.message,
            "question": self.question,
        }


@dataclass(frozen=True)
class ParseResult:
    graph: IntentGraph
    confidence: float
    ambiguities: tuple[AmbiguityFinding, ...]
    needs_clarification: bool

    def clarifying_questions(self) -> tuple[str, ...]:
        return tuple(a.question for a in self.ambiguities)

    def to_dict(self) -> dict[str, Any]:
        return {
            "graph": self.graph.to_dict(),
            "confidence": round(self.confidence, 4),
            "ambiguities": [a.to_dict() for a in self.ambiguities],
            "needs_clarification": self.needs_clarification,
        }


# ---------------------------------------------------------------------------
# Parse
# ---------------------------------------------------------------------------


def parse(prompt: str, context: Optional[Mapping] = None) -> ParseResult:
    text = (prompt or "").strip()
    route = route_request(text, context)

    nodes: list[IntentNode] = []
    edges: list[IntentEdge] = []
    recognized: set[str] = set()

    lowered = text.lower()

    # 1. Trigger
    trigger_node: Optional[IntentNode] = None
    m = _TRIGGER_RE.search(text)
    if m:
        event = _normalize(m.group(1))
        trigger_node = IntentNode.make(
            IntentNodeKind.TRIGGER,
            event or "event",
            slots=(Slot("event", "event", event or None, required=True),),
            sources=(m.group(0).strip(),),
        )
        nodes.append(trigger_node)
        recognized.update(_salient_tokens(m.group(0)))

    # 2. Operations (ordered by position)
    op_nodes: list[IntentNode] = []
    for verb, canon, kind_hint, pos in _scan_verbs(lowered):
        slots = (Slot("verb", "string", canon),)
        node = IntentNode.make(IntentNodeKind.OPERATION, canon, slots=slots,
                               sources=(verb,))
        op_nodes.append(node)
        nodes.append(node)
        recognized.add(verb)

    # 3. Entities / data sources / outputs (ontology lookup)
    out_nodes: list[IntentNode] = []
    for noun, label in _scan_nouns(lowered, _SOURCE_NOUNS):
        nodes.append(IntentNode.make(IntentNodeKind.DATA_SOURCE, label,
                                     sources=(noun,)))
        recognized.add(noun)
    for noun, label in _scan_nouns(lowered, _OUTPUT_NOUNS):
        n = IntentNode.make(IntentNodeKind.OUTPUT, label, sources=(noun,))
        out_nodes.append(n)
        nodes.append(n)
        recognized.add(noun)
    for noun, label in _scan_nouns(lowered, _ENTITY_NOUNS):
        nodes.append(IntentNode.make(IntentNodeKind.ENTITY, label,
                                     sources=(noun,)))
        recognized.add(noun)

    # 4. Constraints
    constraint_nodes: list[IntentNode] = []
    for cm in _CONSTRAINT_RE.finditer(text):
        expr = _normalize(cm.group(1))
        if not expr:
            continue
        node = IntentNode.make(
            IntentNodeKind.CONSTRAINT,
            expr,
            slots=(Slot("expr", "predicate", expr, required=True),),
            sources=(cm.group(0).strip(),),
        )
        constraint_nodes.append(node)
        nodes.append(node)
        recognized.update(_salient_tokens(cm.group(0)))

    # 5. Policies (from the owner gates route_request already detected)
    policy_nodes: list[IntentNode] = []
    for gate in route.owner_gates:
        node = IntentNode.make(IntentNodeKind.POLICY, gate.value)
        policy_nodes.append(node)
        nodes.append(node)

    # 6. Backend hint — explicit language steers first (python/sql/rust),
    # then workflow, then repo.
    lang_label = next((lab for phrase, lab in _LANG_HINTS if phrase in lowered), None)
    if lang_label is not None:
        for phrase, lab in _LANG_HINTS:
            if lab == lang_label and phrase in lowered:
                recognized.update(_salient_tokens(phrase))
        nodes.append(IntentNode.make(IntentNodeKind.BACKEND_HINT, lang_label))
    elif any(phrase in lowered for phrase in _HINT_WORKFLOW):
        for phrase in _HINT_WORKFLOW:
            if phrase in lowered:
                nodes.append(IntentNode.make(IntentNodeKind.BACKEND_HINT,
                                             "automation_flow", sources=(phrase,)))
                recognized.update(_salient_tokens(phrase))
                break
    else:
        for phrase in _HINT_REPO:
            if phrase in lowered:
                nodes.append(IntentNode.make(IntentNodeKind.BACKEND_HINT,
                                             "repo_work_packet",
                                             sources=(phrase,)))
                recognized.update(_salient_tokens(phrase))
                break

    # --- edges (lightweight but meaningful sequencing) ---------------------
    if trigger_node and op_nodes:
        edges.append(IntentEdge(trigger_node.id, op_nodes[0].id,
                                IntentEdgeKind.TRIGGERS))
    for a, b in zip(op_nodes, op_nodes[1:]):
        edges.append(IntentEdge(a.id, b.id, IntentEdgeKind.DEPENDS_ON))
    if op_nodes:
        last_op = op_nodes[-1]
        for out in out_nodes:
            kind = (IntentEdgeKind.ALERTS if out.label in ("alert", "message")
                    else IntentEdgeKind.PRODUCES)
            edges.append(IntentEdge(last_op.id, out.id, kind))
        for c in constraint_nodes:
            edges.append(IntentEdge(last_op.id, c.id,
                                    IntentEdgeKind.CONSTRAINED_BY))
        for p in policy_nodes:
            edges.append(IntentEdge(last_op.id, p.id,
                                    IntentEdgeKind.GUARDED_BY))

    graph = IntentGraph(
        nodes=tuple(nodes),
        edges=tuple(edges),
        intent=route.intent,
        risk_class=route.risk_class,
        owner_gates=route.owner_gates,
        raw_text=text,
        blocked=route.blocked,
    )

    confidence = _confidence(lowered, recognized, graph)
    ambiguities = _ambiguities(graph, confidence)
    needs = bool(ambiguities) and any(
        a.code in ("low_confidence", "unresolved_slot", "multi_backend")
        for a in ambiguities
    )
    return ParseResult(
        graph=graph,
        confidence=confidence,
        ambiguities=tuple(ambiguities),
        needs_clarification=needs,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _normalize(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


def _salient_tokens(text: str) -> set[str]:
    return {
        t for t in re.findall(r"[a-zA-Z]+", text.lower())
        if t not in _STOPWORDS and len(t) > 2
    }


def _scan_verbs(lowered: str):
    """Yield (verb, canonical, kind_hint, position) in source order."""

    found = []
    for table, hint in (
        (_IO_VERBS, "io"),
        (_NOTIFY_VERBS, "notify"),
        (_EDIT_VERBS, "edit"),
    ):
        for verb, canon in table.items():
            for mt in re.finditer(rf"\b{re.escape(verb)}\b", lowered):
                found.append((mt.start(), verb, canon, hint))
    found.sort(key=lambda x: x[0])
    seen: set[str] = set()
    for pos, verb, canon, hint in found:
        if canon in seen:
            continue
        seen.add(canon)
        yield verb, canon, hint, pos


def _scan_nouns(lowered: str, table: Mapping[str, str]):
    seen: set[str] = set()
    for noun, label in table.items():
        # Tolerate a simple plural ("invoice" matches "invoices").
        if re.search(rf"\b{re.escape(noun)}s?\b", lowered) and label not in seen:
            seen.add(label)
            yield noun, label


def _confidence(lowered: str, recognized: set[str], graph: IntentGraph) -> float:
    salient = _salient_tokens(lowered)
    if not salient:
        return 0.0
    coverage = len(recognized & salient) / len(salient)
    # An empty graph (no operations/triggers) cannot be confidently compiled.
    if not graph.nodes_of(IntentNodeKind.OPERATION) and not graph.has_kind(
        IntentNodeKind.TRIGGER
    ):
        coverage = min(coverage, 0.3)
    return round(max(0.0, min(1.0, coverage)), 4)


def _ambiguities(graph: IntentGraph, confidence: float) -> list[AmbiguityFinding]:
    out: list[AmbiguityFinding] = []

    for node, slot in graph.unfilled_required_slots():
        out.append(
            AmbiguityFinding(
                code="unresolved_slot",
                node_id=node.id,
                message=f"{node.kind.value} '{node.label}' is missing '{slot.name}'",
                question=(
                    f"What is the '{slot.name}' for the {node.kind.value} "
                    f"'{node.label}'?"
                ),
            )
        )

    fv = graph.feature_vector()
    if fv["has_trigger"] and fv["edit_verbs"] > 0:
        out.append(
            AmbiguityFinding(
                code="multi_backend",
                node_id=None,
                message="request mixes an event trigger with repo edits",
                question=(
                    "Should this be built as an automation flow (event-driven) "
                    "or as a repo code change? Both signals are present."
                ),
            )
        )

    if confidence < _CONFIDENCE_FLOOR:
        out.append(
            AmbiguityFinding(
                code="low_confidence",
                node_id=None,
                message=f"low parse confidence ({confidence:.2f})",
                question=(
                    "I couldn't pin down what you want with confidence. Can you "
                    "restate the request naming the data, the action, and the "
                    "result?"
                ),
            )
        )

    return out


__all__ = ["AmbiguityFinding", "ParseResult", "parse"]
