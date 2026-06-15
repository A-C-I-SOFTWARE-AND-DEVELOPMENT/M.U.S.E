"""Cockpit Neural Observatory handlers — the read-only ``/v1/observatory/*``
route family (SYNAPSE Phase 3, ``docs/synapse/design/10-observatory-spec.md``).

Strictly additive and read-only: every handler is a pure read over the
:mod:`gateway.cockpit.observatory_metrics` collector and the existing
GraphRAG cache. Nothing here mutates any store, builds the graph, or is
owner-gated.

Honesty rules (binding): every number returned is measured. When the graph
cache has not been built the graph sections answer with the documented
``{"status": "unavailable", ...}`` shape; metrics keys below the confidence
threshold report ``heat: null`` with their real ``n``. Layout positions are
**computed** by :mod:`gateway.cockpit.observatory_layout_engine` (3D
force-directed for super-nodes, degree-ordered radial+refinement for member
expansion), deterministically seeded from the graph version, memoized per
graph-cache version, and labeled with the algorithm that actually ran
(``layout_algo`` — show-your-work doctrine, spec §2.1/§6).

Like ``handlers``, this module is stdlib-only at import time; the collector,
GraphRAG store, and job stores are imported lazily inside each handler.
``Request`` / ``JsonResponse`` are imported from the sibling ``handlers``
module at the *bottom* (the ``handlers_autonomy`` pattern) so the two-way
re-export relationship resolves under any import order.
"""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING, Any, Optional

from . import observatory_layout_engine as _layout_engine

if TYPE_CHECKING:  # annotations only — runtime binding happens at module bottom
    from .handlers import JsonResponse, Request

OBSERVATORY_VERSION = 1

# Pipeline station graph (spec §2.2) — static; jobs flow along these.
STATIONS = ["job", "navigator", "worker", "gate", "ledger"]

# Snapshot cluster cap (spec §2.1: ~200 super-nodes at default LOD).
_MAX_CLUSTERS = 200
_LAYOUT_DEFAULT_LIMIT = 500
_LAYOUT_MAX_LIMIT = 2000

_GRAPH_UNAVAILABLE = {
    "status": "unavailable",
    "reason": "graph cache not built yet (POST /v1/cockpit/graph/build)",
}

# Cache of the cluster summary keyed by (path, mtime) — recomputed only when
# the GraphRAG cache file changes, never per request.
_CLUSTER_CACHE: dict[str, Any] = {"key": None, "summary": None}


def _bad_request(detail: str) -> "JsonResponse":
    return JsonResponse(400, {"error": "bad_request", "detail": detail})


def _cluster_id(label: str) -> str:
    return "c-" + hashlib.sha1(label.encode("utf-8")).hexdigest()[:8]


def _node_view(graph: Any, node_id_: str) -> dict[str, Any]:
    node = graph.nodes[node_id_]
    degree = len(graph.out_edges(node_id_)) + len(graph.in_edges(node_id_))
    source_ref = None
    if node.sources:
        source_ref = node.sources[0].get("uri") or None
    return {
        "id": node_id_,
        "type": node.type.value,
        "label": node.title or node.key,
        "pos": None,  # filled from the cached member layout by the handler
        "degree": degree,
        "heat": None,
        "source_ref": source_ref or node.key,
    }


def _build_cluster_summary(graph: Any, graph_version: str) -> dict[str, Any]:
    """Cluster the graph into super-nodes (deterministic label propagation).

    Returns ``{clusters, cluster_edges, members}`` where ``members`` maps
    cluster id → sorted member node ids (used by the layout expansion).
    Super-node ``pos`` / ``radius`` are computed here via the layout engine
    (deterministically seeded from ``graph_version``) so the layout is solved
    exactly once per graph-cache version — never per request.
    """
    communities = graph.communities()
    ranked = sorted(communities.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    kept = ranked[:_MAX_CLUSTERS]
    members: dict[str, list[str]] = {}
    clusters: list[dict[str, Any]] = []
    node_to_cluster: dict[str, str] = {}
    for label, ids in kept:
        cid = _cluster_id(label)
        members[cid] = ids
        type_counts: dict[str, int] = {}
        best_id, best_degree = ids[0], -1
        for nid in ids:
            node = graph.nodes[nid]
            type_counts[node.type.value] = type_counts.get(node.type.value, 0) + 1
            degree = len(graph.out_edges(nid)) + len(graph.in_edges(nid))
            if degree > best_degree:
                best_id, best_degree = nid, degree
            node_to_cluster[nid] = cid
        total = len(ids)
        top = graph.nodes[best_id]
        clusters.append(
            {
                "id": cid,
                "label": top.title or top.key,
                "type_mix": {
                    t: round(c / total, 3) for t, c in sorted(type_counts.items())
                },
                "members": total,
                "pos": None,  # filled below from the computed super layout
                "radius": _layout_engine.cluster_radius(total),
                "heat": None,  # filled per-request from measured activations
            }
        )
    edge_weights: dict[tuple[str, str], float] = {}
    for edge in graph.edges.values():
        ca = node_to_cluster.get(edge.src)
        cb = node_to_cluster.get(edge.dst)
        if not ca or not cb or ca == cb:
            continue
        key = (ca, cb) if ca <= cb else (cb, ca)
        edge_weights[key] = edge_weights.get(key, 0.0) + float(edge.weight)
    cluster_edges = [
        {"a": a, "b": b, "weight": round(w, 4), "heat": None}
        for (a, b), w in sorted(edge_weights.items())
    ]
    # Real force-directed 3D layout over the super-node graph, seeded from
    # the graph version (deterministic) — computed once per cache version.
    positions = _layout_engine.super_layout(
        clusters, cluster_edges, _layout_engine.seed_from(graph_version)
    )
    for cluster in clusters:
        pos = positions.get(cluster["id"])
        cluster["pos"] = list(pos) if pos is not None else None
    return {
        "graph_version": graph_version,
        "node_count": len(graph.nodes),
        "edge_count": len(graph.edges),
        "clusters": clusters,
        "cluster_edges": cluster_edges,
        "clusters_total": len(ranked),
        "clusters_truncated": len(ranked) > _MAX_CLUSTERS,
        "members": members,
        "layout_algo": _layout_engine.layout_algo(),
    }


def _graph_summary() -> Optional[dict[str, Any]]:
    """Load (or reuse) the cached cluster summary of the GraphRAG cache.

    Read-only: never builds the graph. ``None`` when the cache is absent or
    empty — callers answer with the documented unavailable shape.
    """
    from hermes_cli.jarvis_prime.graphrag import GraphStore

    store = GraphStore()
    if not store.exists():
        return None
    try:
        stat = store.path.stat()
        cache_key = (str(store.path), stat.st_mtime_ns, stat.st_size)
    except OSError:
        return None
    if _CLUSTER_CACHE["key"] == cache_key and _CLUSTER_CACHE["summary"] is not None:
        return _CLUSTER_CACHE["summary"]
    graph = store.load()
    if not graph.nodes:
        return None
    from datetime import datetime, timezone

    mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
    graph_version = "g-" + mtime.strftime("%Y%m%d-%H%M%S")
    summary = _build_cluster_summary(graph, graph_version)
    summary["_graph"] = graph  # kept for layout expansion (same cache lifetime)
    _CLUSTER_CACHE["key"] = cache_key
    _CLUSTER_CACHE["summary"] = summary
    return summary


def _member_positions(
    summary: dict[str, Any], cluster_id: str
) -> dict[str, tuple[float, float, float]]:
    """Member positions for one cluster, memoized per (graph_version, cluster).

    Lives inside the ``_CLUSTER_CACHE``'d summary dict, so it shares the
    cache's exact lifetime: a graph rebuild replaces the summary and thereby
    invalidates every member layout with it. Computed over the cluster's
    top-degree members up to the layout cap so every request ``limit`` slices
    a prefix of the *same* deterministic layout (positions never jump between
    requests with different limits).
    """
    cache: dict[str, dict[str, tuple[float, float, float]]] = summary.setdefault(
        "_member_layouts", {}
    )
    cached = cache.get(cluster_id)
    if cached is not None:
        return cached
    graph = summary["_graph"]
    members = summary["members"][cluster_id]
    nodes = sorted(
        (
            {
                "id": nid,
                "degree": len(graph.out_edges(nid)) + len(graph.in_edges(nid)),
            }
            for nid in members
        ),
        key=lambda nv: (-nv["degree"], nv["id"]),
    )[:_LAYOUT_MAX_LIMIT]
    kept = {nv["id"] for nv in nodes}
    edges = [
        {"a": e.src, "b": e.dst, "weight": float(e.weight)}
        for e in graph.edges.values()
        if e.src in kept and e.dst in kept
    ]
    positions = _layout_engine.member_layout(
        nodes,
        edges,
        center=(0.0, 0.0, 0.0),  # spec §3.4: local space, relative to center
        radius=_layout_engine.cluster_radius(len(members)),
        seed=_layout_engine.seed_from(summary["graph_version"], cluster_id),
    )
    cache[cluster_id] = positions
    return positions


def _apply_measured_cluster_heat(
    clusters: list[dict[str, Any]], collector: Any
) -> None:
    """Fill cluster heat from measured ``node.activate`` events only.

    Heat = the cluster's share of activation weight over the last hour,
    normalized to the hottest cluster. Clusters with no recorded activations
    keep ``heat: null`` (rendered cool-gray per spec §5) — never a guess.
    """
    try:
        weights = collector.activation_weights("1h")
    except Exception:  # pragma: no cover - defensive
        return
    if not weights:
        return
    hottest = max(weights.values())
    if hottest <= 0:
        return
    for cluster in clusters:
        if cluster["id"] in weights:
            cluster["heat"] = round(weights[cluster["id"]] / hottest, 4)


def _active_jobs() -> tuple[list[dict[str, Any]], int]:
    """Current in-flight jobs + queue depth from the existing job stores."""
    from . import handlers as h

    active: list[dict[str, Any]] = []
    for job in h._collect_jobs():
        status = str(job.get("status", "")).lower()
        if not any(t in status for t in ("run", "queue", "pend", "wait", "approval")):
            continue
        active.append(
            {
                "job_id": job.get("id"),
                "task_class": job.get("task_class"),  # not tracked today → null
                "stage": status or None,
                "stage_entered_at": job.get("updated_at") or job.get("created_at"),
                "queue_pos": None,
            }
        )
        if len(active) >= 50:
            break
    queue_depth = h._queue_snapshot().get("queued", 0)
    return active, queue_depth


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------


def observatory_snapshot(req: Request) -> JsonResponse:
    """One-call Observatory boot: graph clusters + stations + ladder + rollup.

    Read-only (spec §3.1). Graph section is the documented ``unavailable``
    shape until the GraphRAG cache is built; ladder/rollup sections are
    honestly empty until events are recorded.

    ``?layout=solar`` re-arranges the super-node clusters into the deterministic
    "Nero Solar System" orbital layout (Nero Core at the origin); any other
    value (default ``force``) keeps the cached force-directed positions.
    """
    from .handlers import _now_iso

    layout_mode = (req.query.get("layout") or "force").strip().lower()

    try:
        from gateway.cockpit import observatory_metrics as om

        collector = om.get_collector()
    except Exception:  # pragma: no cover - defensive
        return JsonResponse(503, {"error": "collector_unavailable"})

    try:
        summary = _graph_summary()
    except Exception:  # pragma: no cover - defensive
        summary = None
    if summary is None:
        graph_section: dict[str, Any] = dict(_GRAPH_UNAVAILABLE)
    else:
        clusters = [dict(c) for c in summary["clusters"]]
        _apply_measured_cluster_heat(clusters, collector)
        layout_algo = summary["layout_algo"]
        if layout_mode == "solar":
            # Overlay deterministic solar positions onto this request's copy
            # only — the cached force-directed summary is never mutated.
            positions = _layout_engine.solar_layout(
                summary["clusters"],
                summary["cluster_edges"],
                _layout_engine.seed_from(summary["graph_version"], "solar"),
            )
            for cluster in clusters:
                pos = positions.get(cluster["id"])
                if pos is not None:
                    cluster["pos"] = list(pos)
            layout_algo = _layout_engine.solar_layout_algo()
        graph_section = {
            "graph_version": summary["graph_version"],
            "node_count": summary["node_count"],
            "edge_count": summary["edge_count"],
            "clusters": clusters,
            "cluster_edges": summary["cluster_edges"],
            "clusters_total": summary["clusters_total"],
            "clusters_truncated": summary["clusters_truncated"],
            "layout_status": "computed",  # real positions from the engine
            "layout_algo": layout_algo,  # which algorithm ran
        }

    active, queue_depth = _active_jobs()
    payload: dict[str, Any] = {
        "v": OBSERVATORY_VERSION,
        "generated_at": _now_iso(),
        "graph": graph_section,
        "stations": {
            "nodes": list(STATIONS),
            "active_jobs": active,
            "queue_depth": queue_depth,
        },
        "ladder": {"tiers": collector.ladder_rollup("1h")},
        "metrics_rollup": {
            "v": OBSERVATORY_VERSION,
            **collector.rollup("1h"),
        },
    }
    # Nero-Fleet overlay (additive, docs/plans/2026-06-15-nero-fleet-architecture.md).
    try:
        from hermes_cli.jarvis_prime.fleet.registry import get_registry
        from hermes_cli.jarvis_prime.fleet.solar_map import solar_system_view

        fleet_snap = get_registry().snapshot()
        payload["fleet"] = fleet_snap
        graph_for_solar = graph_section if graph_section.get("status") != "unavailable" else None
        payload["nero_solar"] = solar_system_view(
            fleet_snap,
            observatory_graph=graph_for_solar,
        )
    except Exception:
        pass  # fleet overlay is best-effort; snapshot stays valid without it
    return JsonResponse(200, payload)


def observatory_metrics(req: Request) -> JsonResponse:
    """Measured rollups for heat / ladder brightness (spec §3.3).

    ``window`` ∈ 15m|1h|24h|7d (default 1h); optional ``task_class`` filter.
    Heat keys with fewer than ``min_n`` observations report ``heat: null``
    with their real ``n`` — insufficient evidence is stated, never padded.
    """
    window = req.query.get("window", "1h")
    try:
        from gateway.cockpit import observatory_metrics as om
    except Exception:  # pragma: no cover - defensive
        return JsonResponse(503, {"error": "collector_unavailable"})
    if window not in om.WINDOWS:
        return _bad_request(
            f"window: must be one of {', '.join(sorted(om.WINDOWS))} (got {window!r})"
        )
    task_class = req.query.get("task_class") or None
    try:
        collector = om.get_collector()
        rollup = collector.rollup(window, task_class=task_class)
    except Exception:  # pragma: no cover - defensive
        return JsonResponse(503, {"error": "collector_unavailable"})
    return JsonResponse(200, {"v": OBSERVATORY_VERSION, **rollup})


def observatory_layout(req: Request) -> JsonResponse:
    """On-demand cluster expansion for the galaxy LOD (spec §3.4).

    Requires ``cluster``; optional ``limit`` (default 500, capped at 2000 —
    above the cap the top-degree members are returned with ``truncated``).
    ``pos`` is the deterministic radial+refined member layout in local space
    (relative to the cluster center), memoized per (graph_version, cluster).
    """
    cluster = (req.query.get("cluster") or "").strip()
    if not cluster:
        return _bad_request("cluster: required")
    raw_limit = req.query.get("limit", str(_LAYOUT_DEFAULT_LIMIT))
    try:
        limit = int(raw_limit)
    except (TypeError, ValueError):
        return _bad_request(f"limit: must be an integer (got {raw_limit!r})")
    if limit < 1:
        return _bad_request("limit: must be >= 1")
    limit = min(limit, _LAYOUT_MAX_LIMIT)

    try:
        summary = _graph_summary()
    except Exception:  # pragma: no cover - defensive
        summary = None
    if summary is None:
        return JsonResponse(
            200,
            {"v": OBSERVATORY_VERSION, "cluster": cluster, **_GRAPH_UNAVAILABLE},
        )
    members = summary["members"].get(cluster)
    if members is None:
        return JsonResponse(404, {"error": "unknown_cluster"})
    graph = summary["_graph"]
    views = sorted(
        (_node_view(graph, nid) for nid in members),
        key=lambda nv: (-nv["degree"], nv["id"]),
    )
    truncated = len(views) > limit
    views = views[:limit]
    positions = _member_positions(summary, cluster)
    for view in views:
        pos = positions.get(view["id"])
        view["pos"] = list(pos) if pos is not None else None
    kept = {nv["id"] for nv in views}
    edges = [
        {"a": e.src, "b": e.dst, "weight": round(float(e.weight), 4)}
        for e in graph.edges.values()
        if e.src in kept and e.dst in kept
    ]
    edges.sort(key=lambda d: (d["a"], d["b"]))
    return JsonResponse(
        200,
        {
            "v": OBSERVATORY_VERSION,
            "cluster": cluster,
            "graph_version": summary["graph_version"],
            "layout_status": "computed",  # real positions from the engine
            "layout_algo": _layout_engine.member_layout_algo(),
            "truncated": truncated,
            "nodes": views,
            "edges": edges,
        },
    )


# ``Request`` / ``JsonResponse`` canonical definitions — bound at module
# bottom so the two-way import with ``handlers`` (which re-exports the
# handlers above) resolves under any import order (handlers_autonomy pattern).
from .handlers import JsonResponse, Request  # noqa: E402,F401

__all__ = [
    "OBSERVATORY_VERSION",
    "STATIONS",
    "observatory_layout",
    "observatory_metrics",
    "observatory_snapshot",
]
