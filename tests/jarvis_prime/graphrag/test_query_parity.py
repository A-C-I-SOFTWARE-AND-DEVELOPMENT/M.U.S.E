"""Parity tests for GraphRAG ``global_query`` (FU-20, GraphRAG arm).

``local_query`` and ``coding_query`` hand back a ``GraphAnswer`` whose
``nodes`` are ranked by a single deterministic contract — relevance score
(``_score_node``) first, node id second — with de-duplicated, source-backed
citations collected over exactly that node + edge set. ``global_query`` used
to order its surfaced nodes by community-block-then-degree instead, so its
``nodes`` field did not match the other modes' ranking contract.

These tests pin the now-shared behavior: ``global_query`` returns
relevance-ranked nodes (same key as ``local_query``), stable across runs,
with citations populated by the shared ``_collect_citations`` helper — while
keeping its unique ``communities`` summaries, its signature, and its
never-raises contract intact, fully offline (in-memory graph only).
"""

from __future__ import annotations

import pytest

from muse_cli.jarvis_prime.graphrag.graph import (
    EdgeType,
    KnowledgeGraph,
    NodeType,
)
from muse_cli.jarvis_prime.graphrag.query import (
    GraphAnswer,
    _collect_citations,
    _score_node,
    _terms,
    coding_query,
    global_query,
    local_query,
)


def _src(uri: str, kind: str = "repo") -> dict:
    return {"uri": uri, "kind": kind}


@pytest.fixture()
def graph() -> KnowledgeGraph:
    """A small, fully source-backed graph with two connected clusters.

    Cluster A (calculator): a file, the function it defines, its test, and a
    doc that cites it. Cluster B (gateway): a separate file + function. Edges
    keep the clusters connected enough for label propagation to form
    communities, and every node/edge carries provenance so citations are
    non-trivial.
    """

    g = KnowledgeGraph()
    calc = g.add_node(
        NodeType.FILE,
        "pkg/calculator.py",
        title="calculator.py",
        sources=[_src("pkg/calculator.py")],
    )
    add_fn = g.add_node(
        NodeType.FUNCTION,
        "pkg/calculator.py::add",
        title="add",
        attrs={"summary": "calculator add function"},
        sources=[_src("pkg/calculator.py#L4")],
    )
    helpers = g.add_node(
        NodeType.FILE,
        "pkg/helpers.py",
        title="helpers.py",
        sources=[_src("pkg/helpers.py")],
    )
    test_calc = g.add_node(
        NodeType.FILE,
        "tests/test_calculator.py",
        title="test_calculator.py",
        sources=[_src("tests/test_calculator.py")],
    )
    doc = g.add_node(
        NodeType.DOCUMENT,
        "docs/calculator-guide.md",
        title="Calculator guide",
        attrs={"summary": "the calculator add function lives here"},
        sources=[_src("docs/calculator-guide.md", kind="doc")],
    )
    gw_file = g.add_node(
        NodeType.FILE,
        "pkg/gateway.py",
        title="gateway.py",
        sources=[_src("pkg/gateway.py")],
    )
    gw_fn = g.add_node(
        NodeType.FUNCTION,
        "pkg/gateway.py::route",
        title="route",
        attrs={"summary": "gateway route dispatcher"},
        sources=[_src("pkg/gateway.py#L9")],
    )

    g.add_edge(calc.id, add_fn.id, EdgeType.OWNS, sources=[_src("pkg/calculator.py")])
    g.add_edge(calc.id, helpers.id, EdgeType.DEPENDS_ON, sources=[_src("pkg/calculator.py#L1")])
    g.add_edge(test_calc.id, add_fn.id, EdgeType.TESTS, sources=[_src("tests/test_calculator.py")])
    g.add_edge(doc.id, calc.id, EdgeType.CITES, sources=[_src("docs/calculator-guide.md", kind="doc")])
    g.add_edge(gw_file.id, gw_fn.id, EdgeType.OWNS, sources=[_src("pkg/gateway.py")])
    return g


def test_global_query_populates_citations(graph: KnowledgeGraph):
    """Parity: ``global_query`` now returns source-backed citations, like
    ``local_query`` / ``coding_query`` do."""

    ans = global_query(graph, "calculator add function")
    assert isinstance(ans, GraphAnswer)
    assert ans.mode == "global"
    assert ans.citations, "global_query must surface provenance citations"
    # Every citation is a real provenance pointer (uri + kind), not invented.
    assert all(c.get("uri") and c.get("kind") for c in ans.citations)


def test_global_query_citations_match_collect_helper(graph: KnowledgeGraph):
    """Citations are produced by the shared ``_collect_citations`` helper over
    exactly the returned node + edge set — i.e. the same collection behavior
    the other modes use, not a bespoke path."""

    ans = global_query(graph, "calculator add function")
    expected = _collect_citations(ans.nodes, ans.edges)
    assert ans.citations == expected


def test_global_query_nodes_use_local_ranking_contract(graph: KnowledgeGraph):
    """The surfaced nodes are ranked by the *same* deterministic key as
    ``local_query`` / ``coding_query``: ``(-_score_node, node.id)``."""

    question = "calculator add function"
    ans = global_query(graph, question)
    terms = _terms(question)
    expected_order = sorted(ans.nodes, key=lambda n: (-_score_node(n, terms), n.id))
    assert [n.id for n in ans.nodes] == [n.id for n in expected_order]


def test_global_query_is_deterministic_across_runs(graph: KnowledgeGraph):
    """Stable ordering: two runs over the same graph yield identical node
    order, edges, and citations."""

    a = global_query(graph, "calculator add function")
    b = global_query(graph, "calculator add function")
    assert [n.id for n in a.nodes] == [n.id for n in b.nodes]
    assert [e.key for e in a.edges] == [e.key for e in b.edges]
    assert a.citations == b.citations
    # Communities (global_query's unique contribution) stay deterministic too.
    assert a.communities == b.communities


def test_global_query_ranking_parity_with_local_and_coding(graph: KnowledgeGraph):
    """All three modes share one ranking contract: any node a mode returns is
    ordered by the same ``(-_score_node, id)`` key. Verify ``global`` lines up
    with ``local`` and ``coding`` rather than using a divergent order."""

    question = "calculator add function"
    terms = _terms(question)

    def _is_locally_ranked(ans: GraphAnswer) -> bool:
        ids = [n.id for n in ans.nodes]
        ranked = [n.id for n in sorted(ans.nodes, key=lambda n: (-_score_node(n, terms), n.id))]
        return ids == ranked

    assert _is_locally_ranked(local_query(graph, question))
    assert _is_locally_ranked(coding_query(graph, question))
    assert _is_locally_ranked(global_query(graph, question))


def test_global_query_preserves_communities_and_shape(graph: KnowledgeGraph):
    """Parity is additive: ``global_query`` keeps its community summaries and
    the full ``GraphAnswer`` shape (nodes, edges, citations, communities)."""

    ans = global_query(graph, "calculator")
    assert ans.communities, "global_query still summarizes communities"
    first = ans.communities[0]
    assert "top_titles" in first and "edge_types" in first
    # Surfaced nodes and edges are mutually consistent: edges only connect
    # nodes that were returned.
    node_ids = {n.id for n in ans.nodes}
    assert all(e.src in node_ids and e.dst in node_ids for e in ans.edges)


def test_global_query_never_raises_on_empty_graph():
    """Never-raises contract preserved: an empty graph yields an empty,
    well-formed answer rather than an exception."""

    ans = global_query(KnowledgeGraph(), "anything")
    assert ans.mode == "global"
    assert ans.nodes == []
    assert ans.citations == []
    assert ans.communities == []


def test_global_query_never_raises_on_empty_question(graph: KnowledgeGraph):
    """No query terms (empty/stopword-only question) falls back to larger
    clusters and still returns a valid, citation-bearing answer."""

    ans = global_query(graph, "")
    assert ans.mode == "global"
    # With no terms it ranks by cluster size and still surfaces nodes; the
    # answer shape and citation collection remain intact.
    assert _collect_citations(ans.nodes, ans.edges) == ans.citations
