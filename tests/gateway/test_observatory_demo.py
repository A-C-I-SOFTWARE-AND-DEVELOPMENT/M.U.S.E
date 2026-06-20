"""The bundled Observatory demo snapshot stays contract-valid and regenerable.

The statically-hosted Neural Observatory (GitHub Pages) renders a bundled
``gateway/cockpit/static/observatory-demo.json`` in opt-in demo mode. These
tests guard that file: (1) it matches the shape ``observatory.js`` reads from
``/v1/observatory/snapshot`` (so the hosted page keeps rendering), and (2) it
stays regenerable from ``scripts/build_observatory_demo.py`` (drift guard), so
the committed bundle never silently diverges from its generator.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEMO = ROOT / "gateway" / "cockpit" / "static" / "observatory-demo.json"
GENERATOR = ROOT / "scripts" / "build_observatory_demo.py"

_GATES = {"planning", "build", "review", "test", "security", "release", "owner", "rollback"}


def _load_demo() -> dict:
    return json.loads(DEMO.read_text(encoding="utf-8"))


def test_demo_snapshot_is_contract_valid() -> None:
    data = _load_demo()
    assert data["_demo"] is True

    graph = data["snapshot"]["graph"]
    assert graph["clusters"], "demo snapshot must carry clusters or the page is blank"
    for cluster in graph["clusters"]:
        assert str(cluster["id"]).startswith("c-")
        assert isinstance(cluster["label"], str) and cluster["label"]
        assert isinstance(cluster["members"], int)
        pos = cluster["pos"]
        assert pos is None or (isinstance(pos, list) and len(pos) == 3)
        # heat is nullable below the confidence gate (spec §5).
        assert cluster["heat"] is None or isinstance(cluster["heat"], (int, float))
    assert graph["cluster_edges"], "demo snapshot must carry cluster edges"

    rollup = data["snapshot"]["metrics_rollup"]
    assert len(rollup["models"]) == 3, "three brain-ladder tiers"
    assert {g["gate"] for g in rollup["gates"]} >= _GATES, "all eight AXIOM gates"

    assert data["recommendations"]["cards"], "at least one verdict card"
    assert data["layouts"], "at least one cluster expansion"


def _load_generator() -> object:
    spec = importlib.util.spec_from_file_location("build_observatory_demo", GENERATOR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_demo_snapshot_is_regenerable() -> None:
    """The committed JSON must still match what the generator produces today."""
    build_snapshot = getattr(_load_generator(), "build_snapshot")
    fresh = build_snapshot()
    committed = _load_demo()["snapshot"]

    assert fresh["graph"]["graph_version"] == committed["graph"]["graph_version"]
    assert len(fresh["graph"]["clusters"]) == len(committed["graph"]["clusters"])
    assert len(fresh["graph"]["cluster_edges"]) == len(committed["graph"]["cluster_edges"])
    # Cluster identities are stable (hash of the real area label).
    assert {c["id"] for c in fresh["graph"]["clusters"]} == {
        c["id"] for c in committed["graph"]["clusters"]
    }
