"""Tests for W4 retrieval grounding (nlp_retrieval) and its compiler wiring.

Covers: ``ground_objective`` returns a graceful ``RetrievalGrounding`` on a
real repo, degrades to ``ok=False`` when the Navigator import is unavailable,
and the repo compiler never narrows ``allowed_files`` below the safe default
regardless of whether grounding succeeded.
"""

from __future__ import annotations

import sys

from hermes_cli.jarvis_prime.intent_graph import (
    IntentGraph,
    IntentNode,
    IntentNodeKind,
)
from hermes_cli.jarvis_prime.ir_compilers.repo_work_packet import (
    RepoWorkPacketCompiler,
)
from hermes_cli.jarvis_prime.natural_language_coder import (
    CodingIntent,
    CodingWorkPacket,
    _allowed_files_for,
)
from hermes_cli.jarvis_prime.nlp_retrieval import (
    RetrievalGrounding,
    ground_objective,
)


def test_ground_objective_returns_grounding_on_real_repo() -> None:
    g = ground_objective("retry logic in the gateway", ".")
    assert isinstance(g, RetrievalGrounding)
    # Accept either a successful grounding with candidates or a graceful
    # ok=False — but never an exception, and always tuple-typed fields.
    assert isinstance(g.candidate_files, tuple)
    assert isinstance(g.verify_with, tuple)
    assert isinstance(g.notes, tuple)
    assert isinstance(g.ok, bool)


def test_ground_objective_degrades_when_navigator_unavailable(monkeypatch) -> None:
    # Force the Navigator import inside ground_objective to fail.
    monkeypatch.setitem(
        sys.modules, "hermes_cli.jarvis_prime.navigation.navigator", None
    )
    g = ground_objective("retry logic in the gateway", ".")
    assert g.ok is False
    assert g.candidate_files == ()
    assert g.verify_with == ()
    # A note explains the unavailability.
    assert g.notes


def test_grounding_to_dict_round_trips() -> None:
    g = RetrievalGrounding(
        candidate_files=("a.py",),
        verify_with=("tests/test_a.py",),
        notes=("n",),
        ok=True,
    )
    d = g.to_dict()
    assert d == {
        "candidate_files": ["a.py"],
        "verify_with": ["tests/test_a.py"],
        "notes": ["n"],
        "ok": True,
    }


def _refactor_graph() -> IntentGraph:
    nodes = (
        IntentNode.make(IntentNodeKind.OPERATION, "refactor"),
        IntentNode.make(IntentNodeKind.DATA_SOURCE, "gateway/retry.py"),
    )
    return IntentGraph(
        nodes=nodes,
        intent=CodingIntent.REFACTOR,
        raw_text="refactor the gateway retry logic and add tests",
    )


def test_compiler_never_narrows_allowed_files() -> None:
    graph = _refactor_graph()
    result = RepoWorkPacketCompiler().compile(graph)
    packet = result.artifact
    assert isinstance(packet, CodingWorkPacket)
    default = set(_allowed_files_for(graph.intent))
    # Enrichment may add files, but the safe default is always a subset —
    # regardless of whether grounding succeeded.
    assert default <= set(packet.allowed_files)


def test_compiler_enrichment_survives_navigator_failure(monkeypatch) -> None:
    monkeypatch.setitem(
        sys.modules, "hermes_cli.jarvis_prime.navigation.navigator", None
    )
    graph = _refactor_graph()
    # Must not raise even though grounding is unavailable.
    result = RepoWorkPacketCompiler().compile(graph)
    packet = result.artifact
    assert isinstance(packet, CodingWorkPacket)
    default = set(_allowed_files_for(graph.intent))
    assert default <= set(packet.allowed_files)
