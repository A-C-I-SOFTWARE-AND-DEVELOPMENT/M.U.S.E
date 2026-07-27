"""Unit tests for Scout prefetch helper."""

from __future__ import annotations

from pathlib import Path

from hermes_cli.swarm.grain import FileDomain, Grain, SwarmPlan
from hermes_cli.swarm.scout import (
    prefetch_for_plan,
    prefetch_for_queries,
    inject_scout_into_specs,
)
from hermes_cli.swarm.specialist import GrainAgentSpec


def test_prefetch_for_queries_parallel_fake_gatherers(tmp_path: Path):
    calls: list[str] = []

    def fake_code(q, repo):
        calls.append(f"code:{q}")
        return f"HIT {q}"

    def fake_docs(q, repo):
        calls.append(f"docs:{q}")
        return f"DOC {q}"

    result = prefetch_for_queries(
        [("g1", "repo: alpha"), ("g1", "docs: beta"), ("shared", "gamma")],
        tmp_path,
        gatherers={"code": fake_code, "docs": fake_docs, "web": lambda q, r: ""},
        max_workers=4,
    )
    assert len(result.packets) >= 3
    assert any("HIT" in p.text or "DOC" in p.text for p in result.packets)
    blob = result.context_blob(grain_id="g1")
    assert "SCOUT/" in blob


def test_prefetch_for_plan_posts_blackboard(tmp_path: Path):
    from hermes_cli.swarm.blackboard import SwarmBlackboard

    plan = SwarmPlan(
        job_id="job-test",
        goal="fix flaky pytest in qa",
        created_at="2026-01-01T00:00:00Z",
        grains=(
            Grain(
                grain_id="g-qa",
                intent="stabilize flaky pytest",
                domain=FileDomain(globs=("tests/**",)),
            ),
        ),
    )
    board = SwarmBlackboard("job-test")
    result = prefetch_for_plan(
        plan,
        tmp_path,
        blackboard=board,
        gatherers={
            "code": lambda q, r: "code-hit",
            "docs": lambda q, r: "docs-hit",
            "web": lambda q, r: "",
            "memory": lambda q, r: "",
        },
    )
    assert result.packets
    notes = board.read()
    assert any(e.kind == "scout" for e in notes)


def test_inject_scout_into_specs():
    from hermes_cli.swarm.scout import ScoutPacket, ScoutResult

    spec = GrainAgentSpec(
        grain_id="g1",
        model_lane="muse-local",
        toolsets=("filesystem",),
        iteration_budget=10,
        token_budget=4000,
        memory_namespace="swarm/g1",
        system_prompt="You are grain g1.",
        context="prior context",
    )
    scout = ScoutResult(
        packets=[
            ScoutPacket(lane="code", query="x", grain_id="g1", text="found foo"),
        ]
    )
    out = inject_scout_into_specs({"g1": spec}, scout)
    assert "SCOUT/code" in out["g1"].context
    assert "Prefer SCOUT" in out["g1"].system_prompt
