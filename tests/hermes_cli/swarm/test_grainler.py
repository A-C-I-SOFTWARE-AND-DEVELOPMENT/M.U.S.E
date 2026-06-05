"""Tests for the Grainler — partitioning, the disjoint proof, and lowering."""

from __future__ import annotations

import pytest

from hermes_cli.swarm.grain import OverlapError
from hermes_cli.swarm.grainler import partition, to_execution_plan


def test_partition_explicit_grains_disjoint():
    plan = partition(
        "build api and web",
        grains=[
            {"intent": "api work", "globs": ["src/api/**"]},
            {"intent": "web work", "globs": ["src/web/**"]},
        ],
    )
    assert len(plan.grains) == 2
    assert {g.grain_id for g in plan.grains} == {
        g.grain_id for g in plan.grains
    }  # unique
    assert plan.is_trivial is False


def test_partition_rejects_overlap_before_running():
    with pytest.raises(OverlapError):
        partition(
            "two grains, same files",
            grains=[
                {"intent": "a", "globs": ["src/**"]},
                {"intent": "b", "globs": ["src/api/routes.py"]},
            ],
        )


def test_partition_requires_goal():
    with pytest.raises(ValueError):
        partition("   ", grains=[{"intent": "x", "globs": ["a/**"]}])


def test_partition_spec_needs_globs():
    with pytest.raises(ValueError):
        partition("g", grains=[{"intent": "no files"}])


def test_partition_custom_decomposer_trivial():
    plan = partition(
        "tiny change",
        decomposer=lambda goal, repo: [{"intent": goal, "globs": ["README.md"]}],
    )
    assert plan.is_trivial is True
    assert plan.grains[0].domain.globs == ("README.md",)


def test_to_execution_plan_prompt_only_uses_worktrees():
    plan = partition(
        "two areas",
        grains=[
            {"intent": "api", "globs": ["src/api/**"], "model_lane": "claude"},
            {"intent": "web", "globs": ["src/web/**"], "model_lane": "codex"},
        ],
    )
    exec_plan = to_execution_plan(plan)
    exec_plan.validate()
    assert exec_plan.use_worktrees is True
    assert {w.worker_id for w in exec_plan.workers} == {
        g.grain_id for g in plan.grains
    }
    for w in exec_plan.workers:
        assert w.use_worktree is True
        assert w.mode.value == "prompt-only"
        assert w.command is None


def test_to_execution_plan_command_builder_is_local_run():
    plan = partition("one", grains=[{"intent": "x", "globs": ["a/**"]}])
    exec_plan = to_execution_plan(
        plan, command_builder=lambda g: ["echo", g.grain_id]
    )
    w = exec_plan.workers[0]
    assert w.mode.value == "local-run"
    assert w.command == ["echo", w.worker_id]


def test_to_execution_plan_concurrency_capped():
    plan = partition(
        "three",
        grains=[
            {"intent": "a", "globs": ["a/**"]},
            {"intent": "b", "globs": ["b/**"]},
            {"intent": "c", "globs": ["c/**"]},
        ],
    )
    exec_plan = to_execution_plan(plan, max_concurrency=2)
    assert exec_plan.concurrency == 2
