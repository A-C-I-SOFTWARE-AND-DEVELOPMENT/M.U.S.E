"""Force-directed 3D layout engine for the Neural Observatory galaxy.

Computes the *real* node positions promised by
``docs/synapse/design/10-observatory-spec.md`` §2.1: layout is gateway-side,
deterministic, cached per graph version, and streamed to UE as plain
coordinates (UE renders; it never runs physics).

Two scales, two algorithms (spec's LOD strategy):

* :func:`super_layout` — full Fruchterman–Reingold force-directed layout in
  3D over the ≤200 super-node cluster graph, normalized into the stable
  ``[-BOX_HALF, BOX_HALF]^3`` coordinate box. If :mod:`networkx` happens to
  be importable it is used as a fast path (``spring_layout(dim=3)`` scaled
  into the same box); otherwise a pure-Python FR implementation runs. Either
  way the output shape is identical and :func:`layout_algo` reports which
  algorithm actually ran (show-your-work doctrine).
* :func:`member_layout` — per-cluster expansion (up to ~2000 members), where
  per-request pure-Python FR would be too slow. Members are placed on a
  deterministic degree-ordered Fibonacci-sphere ball around the cluster
  center (hubs inward), then refined with a small fixed number of
  edge-attraction passes and clamped to the cluster radius. Algorithm label:
  ``"radial-refined"``.

Stdlib-only (the optional networkx import degrades silently), pure
functions, no I/O, no globals beyond constants — caching is the caller's
job (``handlers_observatory`` memoizes per graph-cache version).

Determinism contract: every function is a pure function of its arguments;
all randomness flows through ``random.Random(seed)`` and seeds are derived
from the graph version string via :func:`seed_from`. Same inputs ⇒
byte-identical positions, so UE's 2 s layout interpolation only fires when
the graph genuinely changed.
"""

from __future__ import annotations

import hashlib
import math
import random
from typing import Any, Sequence

# Stable coordinate box for the super-node galaxy: [-BOX_HALF, BOX_HALF]^3.
BOX_HALF = 100.0

# Cluster radius = _RADIUS_BASE * cbrt(member_count) — volume ∝ members.
_RADIUS_BASE = 1.5

# Iteration budgets (≤200 super-nodes ⇒ O(n²·iters) ≈ 5M float ops, fine).
_FR_ITERATIONS = 120
_MEMBER_REFINE_PASSES = 12

ALGO_FR3D = "fr3d"
ALGO_NX_SPRING = "nx-spring"
ALGO_RADIAL = "radial-refined"

try:  # optional fast path — never required, never installed by this module
    import networkx as _nx  # ty: ignore[unresolved-import]
except Exception:  # pragma: no cover - environment-dependent
    _nx = None


def layout_algo() -> str:
    """Which algorithm :func:`super_layout` will run in this process."""
    return ALGO_NX_SPRING if _nx is not None else ALGO_FR3D


def member_layout_algo() -> str:
    """Which algorithm :func:`member_layout` runs (always radial-refined)."""
    return ALGO_RADIAL


def seed_from(graph_version: str, extra: str = "") -> int:
    """Deterministic integer seed derived from the graph version string."""
    digest = hashlib.sha1(f"{graph_version}|{extra}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def cluster_radius(member_count: int) -> float:
    """Cluster sphere radius, cbrt-scaled so volume tracks member count."""
    if member_count <= 0:
        return 0.0
    return round(_RADIUS_BASE * float(member_count) ** (1.0 / 3.0), 4)


# ---------------------------------------------------------------------------
# Super-node layout (≤200 clusters): 3D Fruchterman–Reingold
# ---------------------------------------------------------------------------


def super_layout(
    clusters: Sequence[dict[str, Any]],
    cluster_edges: Sequence[dict[str, Any]],
    seed: int,
) -> dict[str, tuple[float, float, float]]:
    """3D force-directed layout of the super-node cluster graph.

    ``clusters`` are the summary dicts (only ``id`` is read); ``cluster_edges``
    are ``{"a", "b", "weight"}`` dicts. Returns cluster id → ``(x, y, z)``
    normalized into ``[-BOX_HALF, BOX_HALF]^3``. Deterministic in ``seed``.
    """
    ids = [str(c["id"]) for c in clusters]
    id_set = set(ids)
    edges: list[tuple[str, str, float]] = []
    for e in cluster_edges:
        a, b = str(e["a"]), str(e["b"])
        if a in id_set and b in id_set and a != b:
            edges.append((a, b, float(e.get("weight") or 1.0)))
    edges.sort()
    if not ids:
        return {}
    if len(ids) == 1:
        return {ids[0]: (0.0, 0.0, 0.0)}
    if _nx is not None:
        raw = _nx_spring(ids, edges, seed)
    else:
        raw = _fr3d(ids, edges, seed)
    return _normalize_box(raw)


def _nx_spring(
    ids: list[str], edges: list[tuple[str, str, float]], seed: int
) -> dict[str, tuple[float, float, float]]:  # pragma: no cover - optional dep
    assert _nx is not None  # caller (`super_layout`) checked
    graph = _nx.Graph()
    graph.add_nodes_from(ids)
    for a, b, w in edges:
        graph.add_edge(a, b, weight=w)
    raw = _nx.spring_layout(graph, dim=3, seed=seed % (2**32), weight="weight")
    return {i: (float(raw[i][0]), float(raw[i][1]), float(raw[i][2])) for i in ids}


def _fr3d(
    ids: list[str],
    edges: list[tuple[str, str, float]],
    seed: int,
    iterations: int = _FR_ITERATIONS,
) -> dict[str, tuple[float, float, float]]:
    """Pure-Python 3D Fruchterman–Reingold. Deterministic in ``seed``."""
    n = len(ids)
    rng = random.Random(seed)
    pos: dict[str, list[float]] = {
        i: [rng.uniform(-1.0, 1.0), rng.uniform(-1.0, 1.0), rng.uniform(-1.0, 1.0)]
        for i in ids
    }
    # Optimal pairwise distance k for an n-node layout in a side-2 cube.
    k = (8.0 / n) ** (1.0 / 3.0)
    k2 = k * k
    temp = 0.2  # initial max step (box units); cools linearly to ~0
    cool = temp / (iterations + 1)
    for _ in range(iterations):
        disp: dict[str, list[float]] = {i: [0.0, 0.0, 0.0] for i in ids}
        # Repulsion: every pair, force k²/d along the separating direction.
        for ia in range(n):
            a = ids[ia]
            pa, da = pos[a], disp[a]
            for ib in range(ia + 1, n):
                b = ids[ib]
                pb = pos[b]
                dx = pa[0] - pb[0]
                dy = pa[1] - pb[1]
                dz = pa[2] - pb[2]
                d2 = dx * dx + dy * dy + dz * dz
                if d2 < 1e-9:
                    d2 = 1e-9
                coef = k2 / d2  # = (k²/d) / d ⇒ displacement of length k²/d
                da[0] += dx * coef
                da[1] += dy * coef
                da[2] += dz * coef
                db = disp[b]
                db[0] -= dx * coef
                db[1] -= dy * coef
                db[2] -= dz * coef
        # Attraction along edges: force d²/k, scaled gently by log weight.
        for a, b, w in edges:
            pa, pb = pos[a], pos[b]
            dx = pa[0] - pb[0]
            dy = pa[1] - pb[1]
            dz = pa[2] - pb[2]
            d = math.sqrt(dx * dx + dy * dy + dz * dz)
            if d < 1e-9:
                continue
            wf = 1.0 + math.log1p(max(w, 0.0))
            coef = (d / k) * wf  # displacement of length d²/k·wf toward peer
            da, db = disp[a], disp[b]
            da[0] -= dx * coef
            da[1] -= dy * coef
            da[2] -= dz * coef
            db[0] += dx * coef
            db[1] += dy * coef
            db[2] += dz * coef
        # Apply displacements, capped at the current temperature.
        for i in ids:
            dv = disp[i]
            length = math.sqrt(dv[0] * dv[0] + dv[1] * dv[1] + dv[2] * dv[2])
            if length < 1e-12:
                continue
            scale = min(length, temp) / length
            p = pos[i]
            p[0] += dv[0] * scale
            p[1] += dv[1] * scale
            p[2] += dv[2] * scale
        temp -= cool
    return {i: (pos[i][0], pos[i][1], pos[i][2]) for i in ids}


def _normalize_box(
    raw: dict[str, tuple[float, float, float]],
) -> dict[str, tuple[float, float, float]]:
    """Center on the centroid and scale into ``[-BOX_HALF, BOX_HALF]^3``."""
    if not raw:
        return {}
    n = len(raw)
    cx = sum(p[0] for p in raw.values()) / n
    cy = sum(p[1] for p in raw.values()) / n
    cz = sum(p[2] for p in raw.values()) / n
    extent = max(
        max(abs(p[0] - cx), abs(p[1] - cy), abs(p[2] - cz)) for p in raw.values()
    )
    scale = BOX_HALF / extent if extent > 1e-9 else 0.0
    return {
        i: (
            round((p[0] - cx) * scale, 4),
            round((p[1] - cy) * scale, 4),
            round((p[2] - cz) * scale, 4),
        )
        for i, p in raw.items()
    }


# ---------------------------------------------------------------------------
# Member layout (per-cluster expansion, up to ~2000 nodes)
# ---------------------------------------------------------------------------


def member_layout(
    nodes: Sequence[dict[str, Any]],
    edges: Sequence[dict[str, Any]],
    center: tuple[float, float, float],
    radius: float,
    seed: int,
    refine_passes: int = _MEMBER_REFINE_PASSES,
) -> dict[str, tuple[float, float, float]]:
    """Deterministic member positions inside a cluster sphere.

    ``nodes`` need ``id`` and ``degree``; ``edges`` are ``{"a", "b", "weight"}``
    dicts. Placement is degree-ordered on a Fibonacci-sphere ball (hubs near
    the center, leaves toward the shell — uniform volume density via a cbrt
    shell ramp), then a fixed number of edge-attraction passes pull connected
    members together. Every position stays within ``radius`` of ``center``.
    """
    order = sorted(
        nodes, key=lambda nv: (-int(nv.get("degree") or 0), str(nv["id"]))
    )
    n = len(order)
    if n == 0:
        return {}
    cx, cy, cz = (float(center[0]), float(center[1]), float(center[2]))
    if n == 1 or radius <= 0.0:
        return {str(nv["id"]): (round(cx, 4), round(cy, 4), round(cz, 4)) for nv in order}

    rng = random.Random(seed)
    golden = math.pi * (3.0 - math.sqrt(5.0))
    jitter = 0.01 * radius
    pos: dict[str, list[float]] = {}
    for i, nv in enumerate(order):
        # Fibonacci-sphere direction i of n (deterministic, well-spread).
        y = 1.0 - 2.0 * (i + 0.5) / n
        ring = math.sqrt(max(0.0, 1.0 - y * y))
        theta = golden * i
        # cbrt shell ramp ⇒ uniform density in the ball; rank 0 (top degree)
        # sits innermost. Headroom (0.9) leaves room for the jitter.
        shell = 0.9 * radius * ((i + 0.5) / n) ** (1.0 / 3.0)
        pos[str(nv["id"])] = [
            cx + math.cos(theta) * ring * shell + rng.uniform(-jitter, jitter),
            cy + y * shell + rng.uniform(-jitter, jitter),
            cz + math.sin(theta) * ring * shell + rng.uniform(-jitter, jitter),
        ]

    pairs: list[tuple[str, str, float]] = []
    for e in edges:
        a, b = str(e["a"]), str(e["b"])
        if a in pos and b in pos and a != b:
            pairs.append((a, b, float(e.get("weight") or 1.0)))
    pairs.sort()

    for _ in range(refine_passes):
        for a, b, w in pairs:
            pa, pb = pos[a], pos[b]
            step = min(0.25, 0.05 * (1.0 + math.log1p(max(w, 0.0))))
            dx = (pb[0] - pa[0]) * step
            dy = (pb[1] - pa[1]) * step
            dz = (pb[2] - pa[2]) * step
            pa[0] += dx
            pa[1] += dy
            pa[2] += dz
            pb[0] -= dx
            pb[1] -= dy
            pb[2] -= dz

    out: dict[str, tuple[float, float, float]] = {}
    for node_id, p in pos.items():
        dx, dy, dz = p[0] - cx, p[1] - cy, p[2] - cz
        dist = math.sqrt(dx * dx + dy * dy + dz * dz)
        if dist > radius:  # containment clamp — never escape the cluster
            shrink = radius / dist
            dx, dy, dz = dx * shrink, dy * shrink, dz * shrink
        out[node_id] = (round(cx + dx, 4), round(cy + dy, 4), round(cz + dz, 4))
    return out


__all__ = [
    "ALGO_FR3D",
    "ALGO_NX_SPRING",
    "ALGO_RADIAL",
    "BOX_HALF",
    "cluster_radius",
    "layout_algo",
    "member_layout",
    "member_layout_algo",
    "seed_from",
    "super_layout",
]
