"""Observatory layout engine (``gateway.cockpit.observatory_layout_engine``).

Unit tests for the deterministic 3D layouts (super-node force-directed,
per-cluster radial+refined member placement, cbrt cluster radius) plus the
handler wiring: snapshot clusters and layout expansions now carry *computed*
positions with an honest ``layout_algo`` label, memoized per graph-cache
version (spec ``docs/synapse/design/10-observatory-spec.md`` §2.1/§3).
"""

from __future__ import annotations

import math
from collections.abc import Iterator
from pathlib import Path

import pytest

from gateway.cockpit import handlers as h
from gateway.cockpit import handlers_observatory as ho
from gateway.cockpit import observatory_layout_engine as ole
from gateway.cockpit import observatory_metrics as om


@pytest.fixture()
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    monkeypatch.setenv("HERMES_ORCHESTRATOR_HOME", str(tmp_path / "orchestrator"))
    om.reset_collector()
    yield tmp_path
    om.reset_collector()


def _clusters(n: int) -> list[dict[str, object]]:
    return [{"id": f"c-{i:03d}", "members": 10 + i} for i in range(n)]


def _ring_edges(n: int) -> list[dict[str, object]]:
    return [
        {"a": f"c-{i:03d}", "b": f"c-{(i + 1) % n:03d}", "weight": 1.0 + i % 3}
        for i in range(n)
    ]


# ── super_layout ─────────────────────────────────────────────────────────────


def test_super_layout_deterministic_same_seed() -> None:
    clusters, edges = _clusters(20), _ring_edges(20)
    a = ole.super_layout(clusters, edges, seed=42)
    b = ole.super_layout(clusters, edges, seed=42)
    assert a == b  # byte-identical, not merely close


def test_super_layout_different_seed_differs() -> None:
    clusters, edges = _clusters(20), _ring_edges(20)
    a = ole.super_layout(clusters, edges, seed=1)
    b = ole.super_layout(clusters, edges, seed=2)
    assert a != b


def test_super_layout_positions_every_cluster_within_box() -> None:
    clusters, edges = _clusters(60), _ring_edges(60)
    pos = ole.super_layout(clusters, edges, seed=7)
    assert set(pos) == {c["id"] for c in clusters}  # all clusters positioned
    for x, y, z in pos.values():
        assert abs(x) <= ole.BOX_HALF
        assert abs(y) <= ole.BOX_HALF
        assert abs(z) <= ole.BOX_HALF
    # Normalization fills the box: at least one coordinate hits the boundary.
    assert max(abs(c) for p in pos.values() for c in p) == pytest.approx(
        ole.BOX_HALF, abs=0.01
    )
    # Layout is non-degenerate: clusters do not all collapse to one point.
    assert len({p for p in pos.values()}) == len(clusters)


def test_super_layout_edge_cases() -> None:
    assert ole.super_layout([], [], seed=1) == {}
    assert ole.super_layout([{"id": "c-solo"}], [], seed=1) == {
        "c-solo": (0.0, 0.0, 0.0)
    }


def test_super_layout_pulls_connected_clusters_closer() -> None:
    # Two connected pairs + isolated nodes: connected pairs should sit closer
    # together on average than the global mean pairwise distance.
    clusters = _clusters(12)
    edges = [
        {"a": "c-000", "b": "c-001", "weight": 10.0},
        {"a": "c-002", "b": "c-003", "weight": 10.0},
    ]
    pos = ole.super_layout(clusters, edges, seed=11)

    def dist(a: str, b: str) -> float:
        return math.dist(pos[a], pos[b])

    connected = (dist("c-000", "c-001") + dist("c-002", "c-003")) / 2
    ids = sorted(pos)
    all_pairs = [
        dist(ids[i], ids[j])
        for i in range(len(ids))
        for j in range(i + 1, len(ids))
    ]
    assert connected < sum(all_pairs) / len(all_pairs)


def test_layout_algo_label_is_valid() -> None:
    assert ole.layout_algo() in {ole.ALGO_FR3D, ole.ALGO_NX_SPRING}
    assert ole.member_layout_algo() == ole.ALGO_RADIAL


def test_seed_from_is_stable_and_version_sensitive() -> None:
    assert ole.seed_from("g-20260610-1200") == ole.seed_from("g-20260610-1200")
    assert ole.seed_from("g-20260610-1200") != ole.seed_from("g-20260610-1201")
    assert ole.seed_from("g-x", "c-1") != ole.seed_from("g-x", "c-2")


# ── solar_layout (Nero Solar System) ─────────────────────────────────────────


def test_solar_layout_deterministic_same_seed() -> None:
    clusters, edges = _clusters(20), _ring_edges(20)
    a = ole.solar_layout(clusters, edges, seed=42)
    b = ole.solar_layout(clusters, edges, seed=42)
    assert a == b  # byte-identical, not merely close


def test_solar_layout_different_seed_differs() -> None:
    clusters, edges = _clusters(20), _ring_edges(20)
    assert ole.solar_layout(clusters, edges, seed=1) != ole.solar_layout(
        clusters, edges, seed=2
    )


def test_solar_layout_within_box_and_off_the_core() -> None:
    clusters, edges = _clusters(40), _ring_edges(40)
    pos = ole.solar_layout(clusters, edges, seed=7)
    assert set(pos) == {c["id"] for c in clusters}  # every cluster, no extras
    for p in pos.values():
        assert all(abs(c) <= ole.BOX_HALF + 1e-6 for c in p)
        # The origin is the Nero Core (the sun) — no planet may sit on it.
        assert math.dist(p, (0.0, 0.0, 0.0)) > 0.0
    # Non-degenerate: bodies do not collapse onto one another.
    assert len(set(pos.values())) == len(clusters)


def test_solar_layout_ignores_edges() -> None:
    # Placement is geometric, so cluster_edges must not change the result.
    clusters = _clusters(15)
    assert ole.solar_layout(clusters, _ring_edges(15), seed=3) == ole.solar_layout(
        clusters, [], seed=3
    )


def test_solar_layout_heavier_clusters_take_inner_orbits() -> None:
    # _clusters sets members = 10 + i, so higher index = heavier. The heaviest
    # cluster must orbit closer to the core than the lightest.
    clusters = _clusters(30)
    pos = ole.solar_layout(clusters, [], seed=9)
    heaviest = max(clusters, key=lambda c: c["members"])["id"]
    lightest = min(clusters, key=lambda c: c["members"])["id"]
    assert math.dist(pos[heaviest], (0.0, 0.0, 0.0)) < math.dist(
        pos[lightest], (0.0, 0.0, 0.0)
    )


def test_solar_layout_edge_cases() -> None:
    assert ole.solar_layout([], [], seed=1) == {}
    solo = ole.solar_layout([{"id": "c-solo", "members": 5}], [], seed=1)
    assert set(solo) == {"c-solo"}
    assert math.dist(solo["c-solo"], (0.0, 0.0, 0.0)) > 0.0  # not on the sun


def test_solar_layout_algo_label() -> None:
    assert ole.solar_layout_algo() == ole.ALGO_SOLAR


# ── member_layout ────────────────────────────────────────────────────────────


def _member_nodes(n: int) -> list[dict[str, object]]:
    return [{"id": f"n-{i:04d}", "degree": n - i} for i in range(n)]


def _member_edges(n: int) -> list[dict[str, object]]:
    return [
        {"a": f"n-{i:04d}", "b": f"n-{(i * 7 + 1) % n:04d}", "weight": 1.0}
        for i in range(0, n, 3)
    ]


def test_member_layout_deterministic() -> None:
    nodes, edges = _member_nodes(150), _member_edges(150)
    center, radius = (10.0, -5.0, 3.0), 8.0
    a = ole.member_layout(nodes, edges, center, radius, seed=99)
    b = ole.member_layout(nodes, edges, center, radius, seed=99)
    assert a == b
    assert a != ole.member_layout(nodes, edges, center, radius, seed=100)


def test_member_layout_contained_within_radius_of_center() -> None:
    nodes, edges = _member_nodes(400), _member_edges(400)
    center, radius = (50.0, 0.0, -20.0), 12.0
    pos = ole.member_layout(nodes, edges, center, radius, seed=5)
    assert set(pos) == {str(n["id"]) for n in nodes}  # everyone placed
    for p in pos.values():
        assert math.dist(p, center) <= radius + 1e-6
    # Non-degenerate: members spread, not collapsed onto the center.
    assert len(set(pos.values())) > 1


def test_member_layout_top_degree_node_sits_innermost() -> None:
    nodes = _member_nodes(100)
    pos = ole.member_layout(nodes, [], (0.0, 0.0, 0.0), 10.0, seed=3)
    hub = math.dist(pos["n-0000"], (0.0, 0.0, 0.0))  # highest degree
    leaf = math.dist(pos["n-0099"], (0.0, 0.0, 0.0))  # lowest degree
    assert hub < leaf


def test_member_layout_edge_cases() -> None:
    assert ole.member_layout([], [], (0.0, 0.0, 0.0), 5.0, seed=1) == {}
    solo = ole.member_layout(
        [{"id": "n-1", "degree": 0}], [], (1.0, 2.0, 3.0), 5.0, seed=1
    )
    assert solo == {"n-1": (1.0, 2.0, 3.0)}


# ── cluster_radius ───────────────────────────────────────────────────────────


def test_cluster_radius_cbrt_scaled_and_monotone() -> None:
    counts = [0, 1, 2, 8, 27, 100, 412, 5000]
    radii = [ole.cluster_radius(c) for c in counts]
    assert radii == sorted(radii)  # monotone non-decreasing
    assert ole.cluster_radius(0) == 0.0
    assert ole.cluster_radius(1) > 0.0
    # cbrt scaling: 8x the members ⇒ 2x the radius.
    assert ole.cluster_radius(8) == pytest.approx(2 * ole.cluster_radius(1))
    assert ole.cluster_radius(27) == pytest.approx(3 * ole.cluster_radius(1))


# ── handler wiring (real graph, computed positions, memoization) ─────────────


def _seed_graph(home: Path) -> None:
    from hermes_cli.jarvis_prime.graphrag import GraphStore
    from hermes_cli.jarvis_prime.graphrag.graph import (
        EdgeType,
        KnowledgeGraph,
        NodeType,
    )

    g = KnowledgeGraph()
    a = g.add_node(
        NodeType.FILE,
        "gateway/cockpit/handlers.py",
        title="handlers.py",
        sources=[{"uri": "gateway/cockpit/handlers.py", "kind": "repo"}],
    )
    b = g.add_node(
        NodeType.FILE,
        "gateway/cockpit/server.py",
        title="server.py",
        sources=[{"uri": "gateway/cockpit/server.py", "kind": "repo"}],
    )
    c = g.add_node(NodeType.DOCUMENT, "docs/a.md", title="a.md")
    d = g.add_node(NodeType.DOCUMENT, "docs/b.md", title="b.md")
    g.add_edge(a.id, b.id, EdgeType.IMPORTS)
    g.add_edge(c.id, d.id, EdgeType.CITES)
    GraphStore().save(g)


def test_snapshot_clusters_have_computed_layout(home: Path) -> None:
    _seed_graph(home)
    res = h.observatory_snapshot(h.Request(method="GET", path="x"))
    assert res.status == 200
    graph = res.payload["graph"]
    assert graph["layout_status"] == "computed"
    assert graph["layout_algo"] in {ole.ALGO_FR3D, ole.ALGO_NX_SPRING}
    for cluster in graph["clusters"]:
        assert isinstance(cluster["pos"], list) and len(cluster["pos"]) == 3
        assert all(abs(c) <= ole.BOX_HALF for c in cluster["pos"])
        assert cluster["radius"] == ole.cluster_radius(cluster["members"])


def test_layout_expansion_returns_positions_within_cluster(home: Path) -> None:
    _seed_graph(home)
    snap = h.observatory_snapshot(h.Request(method="GET", path="x"))
    cluster = snap.payload["graph"]["clusters"][0]
    res = h.observatory_layout(
        h.Request(method="GET", path="x", query={"cluster": cluster["id"]})
    )
    assert res.status == 200
    assert res.payload["layout_status"] == "computed"
    assert res.payload["layout_algo"] == ole.ALGO_RADIAL
    for node in res.payload["nodes"]:
        pos = node["pos"]
        assert isinstance(pos, list) and len(pos) == 3
        # Local space, relative to the cluster center (spec §3.4).
        assert math.dist(pos, (0.0, 0.0, 0.0)) <= cluster["radius"] + 1e-6


def test_layout_is_deterministic_across_cache_rebuilds(home: Path) -> None:
    _seed_graph(home)
    cid = h.observatory_snapshot(h.Request(method="GET", path="x")).payload[
        "graph"
    ]["clusters"][0]["id"]
    req = h.Request(method="GET", path="x", query={"cluster": cid})
    first = h.observatory_layout(req).payload
    # Drop the memoized summary: forces a full recompute from the same graph
    # file (same graph_version ⇒ same seed ⇒ identical positions).
    ho._CLUSTER_CACHE["key"] = None
    ho._CLUSTER_CACHE["summary"] = None
    second = h.observatory_layout(req).payload
    assert first["graph_version"] == second["graph_version"]
    assert [n["pos"] for n in first["nodes"]] == [n["pos"] for n in second["nodes"]]


def test_member_layout_memoized_per_cluster(home: Path) -> None:
    _seed_graph(home)
    cid = h.observatory_snapshot(h.Request(method="GET", path="x")).payload[
        "graph"
    ]["clusters"][0]["id"]
    req = h.Request(method="GET", path="x", query={"cluster": cid})
    h.observatory_layout(req)
    summary = ho._CLUSTER_CACHE["summary"]
    assert cid in summary["_member_layouts"]  # cached after first request
    cached = summary["_member_layouts"][cid]
    h.observatory_layout(req)
    assert summary["_member_layouts"][cid] is cached  # reused, not recomputed


def test_snapshot_solar_layout_overlays_positions(home: Path) -> None:
    _seed_graph(home)
    force = h.observatory_snapshot(h.Request(method="GET", path="x"))
    solar = h.observatory_snapshot(
        h.Request(method="GET", path="x", query={"layout": "solar"})
    )
    assert force.status == solar.status == 200
    # Default path keeps the force-directed algo; solar reports its own label.
    assert force.payload["graph"]["layout_algo"] in {ole.ALGO_FR3D, ole.ALGO_NX_SPRING}
    assert solar.payload["graph"]["layout_algo"] == ole.ALGO_SOLAR
    fpos = {c["id"]: tuple(c["pos"]) for c in force.payload["graph"]["clusters"]}
    spos = {c["id"]: tuple(c["pos"]) for c in solar.payload["graph"]["clusters"]}
    assert set(fpos) == set(spos)  # same real clusters, none fabricated
    for p in spos.values():
        assert all(abs(c) <= ole.BOX_HALF + 1e-6 for c in p)
    # The overlay must not corrupt the cached force-directed summary: asking
    # for the default layout again still returns the force positions.
    again = h.observatory_snapshot(h.Request(method="GET", path="x"))
    assert {c["id"]: tuple(c["pos"]) for c in again.payload["graph"]["clusters"]} == fpos
