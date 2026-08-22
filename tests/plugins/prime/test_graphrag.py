"""prime graphrag — graph model, store round-trip, indexers, query modes."""

from __future__ import annotations

import json

import pytest

from plugins.prime.graphrag import (
    ALL_INDEXERS,
    EdgeType,
    GraphStore,
    KnowledgeGraph,
    NodeType,
    build_and_save,
    build_graph,
    coding_query,
    default_graph_path,
    find_entity_node,
    global_query,
    load_or_build,
    local_query,
    node_id,
    related_items,
    seed_nodes,
)
from plugins.prime.graphrag.indexers import (
    index_code,
    index_docs,
    index_evidence,
    index_memory,
)
from plugins.prime.memory_tree import MemoryLayer, MemoryTreeStore
from plugins.prime.research_vault import EvidenceStrength, ResearchVault


def fid(path: str) -> str:
    return node_id(NodeType.FILE, path)


@pytest.fixture
def code_graph(repo):
    return build_graph(repo, indexers=["code"])


@pytest.fixture
def full_graph(repo):
    return build_graph(repo, indexers=["code", "docs"])


# ── the graph data model ─────────────────────────────────────────────────────


def test_node_ids_are_deterministic_and_type_scoped():
    assert node_id(NodeType.FILE, "a/b.py") == node_id("file", "a/b.py")
    assert node_id(NodeType.FILE, "a/b.py") != node_id(NodeType.MODULE, "a/b.py")
    assert node_id(NodeType.FILE, "a/b.py").startswith("file:")


def test_add_node_merges_instead_of_clobbering():
    g = KnowledgeGraph()
    g.add_node(NodeType.FILE, "a.py", attrs={"role": "source"}, sources=[{"uri": "a.py"}])
    merged = g.add_node(
        NodeType.FILE,
        "a.py",
        title="a.py",
        attrs={"lines": 3},
        # A provenance pointer the first call did NOT carry, listed twice: the
        # assertion below then fails both on a clobber (the repo pointer would
        # be lost) and on blind concatenation (the doc pointer would appear
        # twice). With the same source on both calls the two behaviours are
        # indistinguishable.
        sources=[{"uri": "docs/a.md", "kind": "doc"}, {"uri": "docs/a.md", "kind": "doc"}],
    )
    assert len(g.nodes) == 1
    assert merged.attrs == {"role": "source", "lines": 3}
    assert merged.sources == [{"uri": "a.py"}, {"uri": "docs/a.md", "kind": "doc"}]


def test_add_edge_requires_existing_endpoints():
    g = KnowledgeGraph()
    a = g.add_node(NodeType.FILE, "a.py")
    assert g.add_edge(a.id, "nonexistent", EdgeType.IMPORTS) is None
    assert g.edges == {}


def test_add_edge_merges_weight_and_provenance():
    g = KnowledgeGraph()
    a = g.add_node(NodeType.FILE, "a.py")
    b = g.add_node(NodeType.FILE, "b.py")
    g.add_edge(a.id, b.id, EdgeType.IMPORTS, sources=[{"uri": "a.py"}])
    edge = g.add_edge(a.id, b.id, EdgeType.IMPORTS, sources=[{"uri": "a.py"}])
    assert len(g.edges) == 1
    assert edge.weight == 2.0
    assert edge.sources == [{"uri": "a.py"}]


def test_neighbors_respects_depth_direction_and_type():
    g = KnowledgeGraph()
    a, b, c = (g.add_node(NodeType.FILE, n) for n in ("a.py", "b.py", "c.py"))
    g.add_edge(a.id, b.id, EdgeType.IMPORTS)
    g.add_edge(b.id, c.id, EdgeType.CALLS)

    assert g.neighbors(a.id, depth=1) == [b.id]
    assert g.neighbors(a.id, depth=2) == sorted([b.id, c.id])
    assert g.neighbors(b.id, direction="out") == [c.id]
    assert g.neighbors(b.id, direction="in") == [a.id]
    assert g.neighbors(a.id, depth=2, edge_types=[EdgeType.IMPORTS]) == [b.id]
    assert a.id not in g.neighbors(a.id, depth=2)


def test_communities_group_connected_nodes():
    g = KnowledgeGraph()
    a, b = (g.add_node(NodeType.FILE, n) for n in ("a.py", "b.py"))
    lonely = g.add_node(NodeType.FILE, "island.py")
    g.add_edge(a.id, b.id, EdgeType.IMPORTS)

    groups = g.communities()
    sizes = sorted(len(m) for m in groups.values())
    assert sizes == [1, 2]
    assert any(sorted(m) == sorted([a.id, b.id]) for m in groups.values())
    assert any(m == [lonely.id] for m in groups.values())


def test_communities_are_deterministic(full_graph):
    assert full_graph.communities() == full_graph.communities()


def test_communities_of_an_empty_graph():
    assert KnowledgeGraph().communities() == {}


def test_stats_counts_by_type(full_graph):
    stats = full_graph.stats()
    assert stats["nodes"] == len(full_graph.nodes)
    assert stats["edges"] == len(full_graph.edges)
    assert stats["by_node_type"]["file"] == 9
    assert stats["by_node_type"]["document"] == 2
    assert stats["by_edge_type"]["tests"] == 1
    # Sorted for stable output.
    assert list(stats["by_node_type"]) == sorted(stats["by_node_type"])


def test_graph_dict_round_trip(full_graph):
    revived = KnowledgeGraph.from_dict(full_graph.to_dict())
    assert set(revived.nodes) == set(full_graph.nodes)
    assert set(revived.edges) == set(full_graph.edges)
    assert revived.stats() == full_graph.stats()
    # Adjacency indexes are rebuilt, not just the dicts.
    file_id = fid("pkg/timeout_config.py")
    assert revived.neighbors(file_id) == full_graph.neighbors(file_id)


def test_from_dict_drops_edges_with_missing_endpoints():
    payload = {
        "nodes": [{"id": "file:x", "type": "file", "key": "a.py"}],
        "edges": [{"src": "file:x", "dst": "file:gone", "type": "imports"}],
    }
    g = KnowledgeGraph.from_dict(payload)
    assert g.edges == {}


# ── GraphStore ───────────────────────────────────────────────────────────────


def test_store_round_trip(tmp_path, full_graph):
    store = GraphStore(tmp_path / "graph.json")
    assert store.exists() is False
    path = store.save(full_graph)
    assert path.exists() and store.exists() is True

    loaded = GraphStore(tmp_path / "graph.json").load()
    assert loaded.stats() == full_graph.stats()
    doc = loaded.nodes[node_id(NodeType.DOCUMENT, "docs/architecture.md")]
    assert doc.sources == [{"uri": "docs/architecture.md", "kind": "doc"}]


def test_store_load_of_a_missing_file_is_empty(tmp_path):
    assert GraphStore(tmp_path / "absent.json").load().nodes == {}


def test_store_reports_a_corrupt_cache_instead_of_raising(tmp_path):
    path = tmp_path / "graph.json"
    path.write_text("{not json", encoding="utf-8")
    store = GraphStore(path)
    assert store.load().nodes == {}
    assert store.load_diagnostics and "load failed" in store.load_diagnostics[0]


def test_default_graph_path_follows_hermes_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    assert default_graph_path() == tmp_path / "prime" / "graph" / "graph.json"


# ── the code indexer ─────────────────────────────────────────────────────────


def test_code_indexer_makes_a_file_node_per_indexed_file(code_graph, index):
    for f in index.files:
        node = code_graph.nodes[fid(f.path)]
        assert node.attrs["role"] == f.role
        assert node.sources == [{"uri": f.path, "kind": "repo"}]


def test_code_indexer_extracts_functions_and_classes(code_graph):
    fn = code_graph.nodes[
        node_id(NodeType.FUNCTION, "pkg/timeout_config.py::load_timeout")
    ]
    cls = code_graph.nodes[
        node_id(NodeType.CLASS, "pkg/timeout_config.py::TimeoutConfig")
    ]
    assert fn.title == "load_timeout"
    assert fn.attrs["lineno"] > 0
    assert fn.sources[0]["line_ref"] == str(fn.attrs["lineno"])
    assert cls.title == "TimeoutConfig"
    # The owning file OWNS both definitions.
    owned = code_graph.neighbors(fid("pkg/timeout_config.py"), edge_types=[EdgeType.OWNS])
    assert fn.id in owned and cls.id in owned


def test_code_indexer_only_records_top_level_defs(code_graph):
    # TimeoutConfig.__init__ is nested inside the class, not a module-level def.
    assert (
        node_id(NodeType.FUNCTION, "pkg/timeout_config.py::__init__")
        not in code_graph.nodes
    )


def test_code_indexer_links_imports_and_dependencies(code_graph):
    client, target = fid("pkg/client.py"), fid("pkg/timeout_config.py")
    types = {
        e.type for e in code_graph.out_edges(client) if e.dst == target
    }
    assert EdgeType.IMPORTS in types
    assert EdgeType.DEPENDS_ON in types


def test_code_indexer_links_tests_to_their_subject(code_graph):
    test_id, target = fid("tests/test_timeout_config.py"), fid("pkg/timeout_config.py")
    edge = code_graph.edges[(test_id, target, "tests")]
    # Both the naming convention and the import edge fire, so the weight sums.
    assert edge.weight == 2.0
    assert edge.sources


def test_code_indexer_resolves_direct_calls(code_graph):
    caller = node_id(NodeType.FUNCTION, "pkg/client.py::fetch")
    callee = node_id(NodeType.FUNCTION, "pkg/timeout_config.py::load_timeout")
    assert (caller, callee, "calls") in code_graph.edges


def test_code_indexer_respects_the_call_edge_budget(repo):
    g = build_graph(repo, indexers=[])
    index_code(g, repo, max_call_edges=0)
    assert not any(e.type == EdgeType.CALLS for e in g.edges.values())


def test_code_indexer_creates_module_nodes(code_graph):
    module = code_graph.nodes[node_id(NodeType.MODULE, "pkg")]
    assert module.attrs["path"] == "pkg"
    owned = code_graph.neighbors(module.id, edge_types=[EdgeType.OWNS])
    assert fid("pkg/client.py") in owned
    # tests/ has no __init__.py, so it is not a package.
    assert node_id(NodeType.MODULE, "tests") not in code_graph.nodes


def test_module_nodes_are_dotted_and_posix_on_every_platform(tmp_path):
    r"""A nested package must key as ``pkg.sub``, not ``pkg\sub``.

    ``str(PurePath.parent)`` yields backslashes on Windows, so the dotted name
    was built by replacing "/" — a no-op there. That left the graph cache
    platform-dependent for the same repo and made ``hermes graph related
    pkg.sub`` unresolvable on Windows.
    """

    from tests.plugins.prime.conftest import write_repo

    repo = write_repo(
        tmp_path / "nested",
        {
            "pkg/__init__.py": "",
            "pkg/sub/__init__.py": "",
            "pkg/sub/deep.py": "def deep():\n    return 1\n",
        },
    )
    g = build_graph(repo, indexers=["code"])
    modules = {n.key for n in g.nodes.values() if n.type is NodeType.MODULE}
    assert modules == {"pkg", "pkg.sub"}
    assert all("\\" not in m for m in modules)
    owned = g.neighbors(
        node_id(NodeType.MODULE, "pkg.sub"), edge_types=[EdgeType.OWNS]
    )
    assert node_id(NodeType.FILE, "pkg/sub/deep.py") in owned


# ── the docs indexer ─────────────────────────────────────────────────────────


def test_docs_indexer_cites_the_files_a_doc_names(full_graph):
    doc = node_id(NodeType.DOCUMENT, "docs/architecture.md")
    cited = full_graph.neighbors(doc, edge_types=[EdgeType.CITES])
    assert set(cited) == {fid("pkg/timeout_config.py"), fid("pkg/client.py")}
    assert full_graph.nodes[doc].attrs["lines"] == 3


def test_docs_indexer_ignores_a_doc_that_names_nothing(full_graph):
    readme = node_id(NodeType.DOCUMENT, "README.md")
    assert full_graph.neighbors(readme, edge_types=[EdgeType.CITES]) == []


def test_docs_indexer_alone_creates_no_cites(repo):
    # Without the code indexer there are no FILE endpoints to cite.
    g = build_graph(repo, indexers=["docs"])
    assert not any(e.type == EdgeType.CITES for e in g.edges.values())
    assert node_id(NodeType.DOCUMENT, "docs/architecture.md") in g.nodes


# ── the evidence indexer ─────────────────────────────────────────────────────


def test_evidence_indexer_adds_source_nodes_and_cites_repo_paths(repo, tmp_path):
    vault = ResearchVault(path=tmp_path / "vault.jsonl")
    web = vault.add(
        "GraphRAG paper",
        "https://example.invalid/paper",
        excerpt="Graphs improve retrieval.",
        evidence_strength=EvidenceStrength.PRIMARY,
        persist=False,
    )
    local = vault.add(
        "Timeout note",
        "pkg/timeout_config.py",
        excerpt="Timeouts default to 30s.",
        evidence_strength=EvidenceStrength.WEAK,
        persist=False,
    )

    g = build_graph(repo, indexers=["code"])
    index_evidence(g, vault=vault)

    web_node = g.nodes[node_id(NodeType.SOURCE, f"research:{web.id}")]
    assert web_node.attrs["evidence_strength"] == "primary"
    assert web_node.attrs["summary"] == "Graphs improve retrieval."
    # A remote URI has no repo endpoint to cite.
    assert g.neighbors(web_node.id, edge_types=[EdgeType.CITES]) == []

    local_node = g.nodes[node_id(NodeType.SOURCE, f"research:{local.id}")]
    edge = g.edges[(local_node.id, fid("pkg/timeout_config.py"), "cites")]
    assert edge.weight == 1.0  # weak evidence weighs least


def test_evidence_strength_sets_the_edge_weight(repo, tmp_path):
    vault = ResearchVault(path=tmp_path / "vault.jsonl")
    art = vault.add(
        "Primary",
        "pkg/client.py",
        evidence_strength=EvidenceStrength.PRIMARY,
        persist=False,
    )
    g = build_graph(repo, indexers=["code"])
    index_evidence(g, vault=vault)
    src = node_id(NodeType.SOURCE, f"research:{art.id}")
    assert g.edges[(src, fid("pkg/client.py"), "cites")].weight == 4.0


# ── the memory indexer ───────────────────────────────────────────────────────


@pytest.fixture
def memory_store(tmp_path):
    store = MemoryTreeStore(path=tmp_path / "memory.jsonl")
    store.write(
        "The cache lives under HERMES_HOME",
        namespace="prime/test",
        title="cache location",
        layer=MemoryLayer.DURABLE,
        source_uri="docs/architecture.md",
        confidence=0.9,
    )
    store.write(
        "The cache lives in /var/cache",
        namespace="prime/test",
        title="cache location",
        layer=MemoryLayer.DURABLE,
        source_uri="docs/architecture.md",
        confidence=0.9,
    )
    return store


def test_memory_indexer_makes_decision_nodes_with_provenance(repo, memory_store):
    g = build_graph(repo, indexers=["code", "docs"])
    index_memory(g, store=memory_store)

    node = next(iter(memory_store.nodes.values()))
    dec = g.nodes[node_id(NodeType.DECISION, f"memory:{node.id}")]
    assert dec.title == "cache location"
    assert dec.attrs["namespace"] == "prime/test"
    assert dec.attrs["contradiction_status"] == "contested"
    assert dec.sources == [{"uri": node.id, "kind": "memory_tree"}]

    src = g.nodes[node_id(NodeType.SOURCE, "docs/architecture.md")]
    assert src.attrs["trust"] == "unverified"
    assert (dec.id, src.id, "cites") in g.edges


def test_memory_indexer_records_contradictions(repo, memory_store):
    g = build_graph(repo, indexers=[])
    index_memory(g, store=memory_store)
    report = memory_store.open_contradictions()[0]
    a = node_id(NodeType.DECISION, f"memory:{report.node_a_id}")
    b = node_id(NodeType.DECISION, f"memory:{report.node_b_id}")
    edge = g.edges[(a, b, "contradicts")]
    assert edge.attrs["status"] == "contested"
    assert edge.attrs["reason"]


def test_memory_indexer_records_supersedes(repo, memory_store):
    report = memory_store.open_contradictions()[0]
    memory_store.resolve_contradiction(report.id, report.node_b_id)
    g = build_graph(repo, indexers=[])
    index_memory(g, store=memory_store)

    winner = node_id(NodeType.DECISION, f"memory:{report.node_b_id}")
    loser = node_id(NodeType.DECISION, f"memory:{report.node_a_id}")
    # The superseded node is inactive, so it never enters the graph...
    assert loser not in g.nodes
    # ...and the dangling SUPERSEDES edge is therefore not created.
    assert (winner, loser, "supersedes") not in g.edges
    assert winner in g.nodes


def test_memory_indexer_copies_only_a_capped_summary(repo, tmp_path):
    store = MemoryTreeStore(path=tmp_path / "memory.jsonl")
    store.write(
        "x" * 900,
        namespace="ns",
        title="long",
        summary="y" * 900,
        persist=False,
    )
    g = KnowledgeGraph()
    index_memory(g, store=store)
    dec = next(iter(g.nodes.values()))
    assert len(dec.attrs["summary"]) == 240
    assert "text" not in dec.attrs  # the full body is never copied


# ── the builder ──────────────────────────────────────────────────────────────


def test_all_indexers_is_the_shipped_set():
    assert ALL_INDEXERS == ("code", "docs", "evidence", "memory")


def test_builder_honours_an_indexer_subset(repo):
    only_docs = build_graph(repo, indexers=["docs"])
    assert {n.type for n in only_docs.nodes.values()} == {NodeType.DOCUMENT}


def test_builder_ignores_unknown_indexer_names(repo):
    assert build_graph(repo, indexers=["nope"]).nodes == {}


def test_builder_runs_in_a_fixed_order_regardless_of_input(repo):
    a = build_graph(repo, indexers=["docs", "code"])
    b = build_graph(repo, indexers=["code", "docs"])
    assert a.stats() == b.stats()


def test_one_failing_indexer_never_aborts_the_build(repo, monkeypatch):
    import plugins.prime.graphrag.builder as builder

    def boom(*a, **kw):
        raise RuntimeError("indexer exploded")

    monkeypatch.setattr(builder, "index_docs", boom)
    graph = build_graph(repo, indexers=["code", "docs"])
    assert graph.nodes  # code still indexed
    assert not any(n.type == NodeType.DOCUMENT for n in graph.nodes.values())


def test_build_and_save_persists(repo, tmp_path):
    store = GraphStore(tmp_path / "graph.json")
    graph, path = build_and_save(repo, indexers=["code"], store=store)
    assert path == tmp_path / "graph.json"
    assert json.loads(path.read_text())["nodes"]
    assert graph.nodes


def test_load_or_build_builds_once_then_reuses_the_cache(repo, tmp_path):
    store = GraphStore(tmp_path / "graph.json")
    first = load_or_build(repo, store=store)
    assert first.nodes

    # A second call must read the cache, not re-walk the repo.
    import plugins.prime.graphrag.builder as builder

    def boom(*a, **kw):
        raise AssertionError("should not rebuild")

    monkeypatch_target = builder.build_graph
    builder.build_graph = boom
    try:
        second = load_or_build(repo, store=store)
    finally:
        builder.build_graph = monkeypatch_target
    assert second.stats() == first.stats()


def test_load_or_build_rebuilds_an_empty_cache(repo, tmp_path):
    store = GraphStore(tmp_path / "graph.json")
    store.save(KnowledgeGraph())
    assert load_or_build(repo, store=store).nodes


# ── query modes ──────────────────────────────────────────────────────────────


def test_seed_nodes_rank_by_term_overlap(full_graph):
    seeds = seed_nodes(full_graph, "timeout_config load_timeout", limit=3)
    # Both query terms hit the function node's title+key, so it outranks the
    # file, which only matches one; every seed is in the named module.
    assert [n.key for n in seeds] == [
        "pkg/timeout_config.py::load_timeout",
        "pkg/timeout_config.py::TimeoutConfig",
        "pkg/timeout_config.py",
    ]


def test_seed_nodes_can_be_restricted_by_type(full_graph):
    seeds = seed_nodes(
        full_graph, "architecture", limit=5, node_types=[NodeType.DOCUMENT]
    )
    assert seeds and all(n.type == NodeType.DOCUMENT for n in seeds)


def test_seed_nodes_of_an_unmatched_question(full_graph):
    assert seed_nodes(full_graph, "zzzqqq nothing") == []


def test_local_query_expands_one_hop_with_citations(full_graph):
    answer = local_query(full_graph, "load_timeout", limit=3)
    assert answer.mode == "local"
    keys = [n.key for n in answer.nodes]
    assert "pkg/timeout_config.py::load_timeout" in keys
    # One hop away: the file that owns it and the callers.
    assert "pkg/timeout_config.py" in keys
    assert answer.citations
    assert all("uri" in c for c in answer.citations)
    assert "load_timeout" in answer.render()


def test_local_query_edges_are_confined_to_the_answer(full_graph):
    answer = local_query(full_graph, "timeout", limit=5)
    ids = {n.id for n in answer.nodes}
    assert all(e.src in ids and e.dst in ids for e in answer.edges)


def test_global_query_summarises_clusters(full_graph):
    answer = global_query(full_graph, "timeout", max_communities=3)
    assert answer.mode == "global"
    assert answer.communities
    top = answer.communities[0]
    assert top["size"] >= 1
    assert top["relevance"] > 0
    assert top["top_titles"]
    assert "cluster" in answer.render()


def test_global_query_without_terms_prefers_large_clusters(full_graph):
    answer = global_query(full_graph, "the and for", max_communities=2)
    sizes = [c["size"] for c in answer.communities]
    assert sizes == sorted(sizes, reverse=True)


def test_coding_query_returns_the_file_its_tests_and_its_docs(full_graph):
    answer = coding_query(full_graph, "timeout_config", limit=4)
    assert answer.mode == "coding"
    keys = [n.key for n in answer.nodes]
    # The three seeds inside the named module come first...
    assert set(keys[:3]) == {
        "pkg/timeout_config.py",
        "pkg/timeout_config.py::load_timeout",
        "pkg/timeout_config.py::TimeoutConfig",
    }
    # ...then the one-hop context a coding task needs: the covering test and
    # the doc that cites the file.
    assert "tests/test_timeout_config.py" in keys
    assert "docs/architecture.md" in keys
    assert "pkg/unrelated.py" not in keys


def test_coding_query_ranks_the_exact_symbol_first(full_graph):
    answer = coding_query(full_graph, "load_timeout", limit=4)
    assert answer.nodes[0].key == "pkg/timeout_config.py::load_timeout"


def test_coding_query_seeds_only_from_code_nodes(full_graph):
    # A markdown file is a FILE node (seedable) but its DOCUMENT twin is not,
    # so the coding lane returns the path, never the document abstraction.
    nodes = coding_query(full_graph, "architecture").nodes
    assert [(n.type, n.key) for n in nodes] == [
        (NodeType.FILE, "docs/architecture.md")
    ]


def test_answer_to_dict_is_json_serialisable(full_graph):
    payload = local_query(full_graph, "timeout").to_dict()
    assert json.loads(json.dumps(payload))["mode"] == "local"
    assert set(payload) == {
        "mode",
        "question",
        "nodes",
        "edges",
        "citations",
        "communities",
    }


def test_queries_are_deterministic(full_graph):
    a = [n.id for n in coding_query(full_graph, "timeout").nodes]
    b = [n.id for n in coding_query(full_graph, "timeout").nodes]
    assert a == b


def test_queries_on_an_empty_graph_are_empty():
    empty = KnowledgeGraph()
    assert local_query(empty, "anything").nodes == []
    assert global_query(empty, "anything").communities == []
    assert coding_query(empty, "anything").nodes == []


# ── related_items / find_entity_node ─────────────────────────────────────────


def test_related_items_buckets_neighbours(full_graph):
    items = related_items(full_graph, fid("pkg/timeout_config.py"))
    buckets = [i["kind"] for i in items]
    assert buckets == sorted(buckets, key=["file", "source", "decision"].index)
    by_ref = {i["ref"]: i for i in items}
    assert by_ref["pkg/client.py"]["relation"] in {"imports", "depends_on"}
    assert by_ref["docs/architecture.md"]["kind"] == "source"
    assert all(i["source_backed"] for i in items)


def test_related_items_honours_the_limit_and_unknown_ids(full_graph):
    assert len(related_items(full_graph, fid("pkg/timeout_config.py"), limit=2)) == 2
    assert related_items(full_graph, "file:nope") == []


def test_find_entity_node_resolves_paths_ids_and_memory_keys(full_graph, repo):
    file_id = fid("pkg/client.py")
    assert find_entity_node(full_graph, key="pkg/client.py") == file_id
    assert find_entity_node(full_graph, key="./pkg/client.py") == file_id
    assert find_entity_node(full_graph, key=file_id) == file_id
    assert find_entity_node(full_graph, key="not/a/path.py") is None
    assert find_entity_node(full_graph, key="") is None


def test_find_entity_node_resolves_a_bare_memory_id(repo, tmp_path):
    store = MemoryTreeStore(path=tmp_path / "memory.jsonl")
    node = store.write("a fact", namespace="ns", title="t", persist=False).node
    g = KnowledgeGraph()
    index_memory(g, store=store)
    assert find_entity_node(g, key=node.id) == node_id(
        NodeType.DECISION, f"memory:{node.id}"
    )
