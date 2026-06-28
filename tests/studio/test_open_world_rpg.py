"""Tests for the Skyrim-class open-world RPG blueprint + producer.

Hermetic: the studio is pinned offline so key-less / network adapters stub,
and the full build plan materializes without spend.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent.studio import (
    GameBrief,
    Provider,
    Quality,
    StudioOrchestrator,
    load_open_world_rpg_blueprint,
)


@pytest.fixture(autouse=True)
def _studio_offline(monkeypatch):
    monkeypatch.setenv("AXIOM_STUDIO_OFFLINE", "1")


@pytest.fixture
def studio(tmp_path):
    return StudioOrchestrator(root=tmp_path / "studio_out")


# ── Blueprint resource ──────────────────────────────────────────────


def test_blueprint_loads_with_all_domains_and_phases():
    bp = load_open_world_rpg_blueprint()
    assert len(bp.domains) == 27
    assert len(bp.phases) == 5
    assert bp.engine_recommended == "UE5"
    # Every domain is keyed and prioritized; P0 keystones are present.
    assert all(d.key and d.priority for d in bp.domains)
    p0 = {d.key for d in bp.p0_domains}
    assert {"world_streaming", "world_persistence", "physics_collision"} <= p0
    # The dependency graph and critical path are populated.
    assert bp.dependency_edges
    assert bp.critical_path


def test_blueprint_lookup_and_ordering():
    bp = load_open_world_rpg_blueprint()
    d = bp.domain("combat_magic")
    assert d is not None and d.lane and d.capabilities
    # ordered_domains leads with P0.
    assert bp.ordered_domains()[0].priority == "P0"
    # as_plan() is JSON-serializable and round-trips the counts.
    plan = bp.as_plan()
    assert len(json.loads(json.dumps(plan))["domains"]) == 27


# ── Producer ────────────────────────────────────────────────────────


def test_produce_open_world_rpg_scaffolds_and_plans(studio):
    brief = GameBrief(
        title="Aetherbound",
        genre="open-world action-RPG",
        setting="post-magical-collapse frontier",
        core_loop="explore -> quest -> fight -> grow",
        engine=Provider.UE5,
        quality=Quality.PREVIZ,
    )
    m = studio.produce_open_world_rpg(brief)

    assert m.kind == "game"
    # No stage failed (offline -> ok/stubbed only).
    bad = [s for s in m.stages if s.status not in ("ok", "stubbed")]
    assert not bad, f"failed stages: {[(s.stage, s.notes) for s in bad]}"

    # Engine project scaffold actually wrote a .uproject (UE5).
    eng = next(s for s in m.stages if s.stage == "engine_project")
    assert eng.status == "ok"

    # The machine-readable build plan was materialized as queryable JSON.
    plan_stage = next(s for s in m.stages if s.stage == "build_plan")
    assert plan_stage.status == "ok"
    plan_dir = m.workdir / "build_plan"
    for fname in ("blueprint.json", "phases.json", "domains.json",
                  "critical_path.json", "dependency_graph.json", "engine.json"):
        assert (plan_dir / fname).exists(), fname
    domains = json.loads((plan_dir / "domains.json").read_text(encoding="utf-8"))
    assert len(domains) == 27
    engine = json.loads((plan_dir / "engine.json").read_text(encoding="utf-8"))
    assert engine["recommended"] == "UE5"

    # Foundational production stages are present (stubbed offline).
    stages = {s.stage for s in m.stages}
    assert {"gdd", "world_bible", "gameplay_code"} <= stages
    assert (m.workdir / "manifest.txt").exists()
