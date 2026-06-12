"""Tests for the real per-grain AgentExecutor (model call stubbed via a seam)."""

from __future__ import annotations

from pathlib import Path

from muse_cli.swarm.executor import AgentExecutor, GrainRunOutput
from muse_cli.swarm.grainler import partition
from muse_cli.swarm.specialist import build_grain_agent_spec


class FakeRunner:
    """A deterministic AgentRunner: writes a tiny patch, no network."""

    def __init__(self, fail_grains=()):
        self.fail_grains = set(fail_grains)
        self.seen: list[str] = []

    def run(self, spec, workdir, grain):
        self.seen.append(grain.grain_id)
        ok = grain.grain_id not in self.fail_grains
        return GrainRunOutput(
            output_md=f"did {grain.grain_id}",
            patch_diff=f"+++ b/{grain.grain_id}.py\n+x = 1\n",
            changed_files=(f"{grain.grain_id}.py",),
            validation_output="ok" if ok else "FAILED",
            status={"success": ok, "grain_id": grain.grain_id},
            usage={"cost_usd": 0.01, "model": spec.model_lane},
            success=ok,
            error=None if ok else "verification failed",
        )


def _plan():
    return partition(
        "two areas",
        grains=[
            {"intent": "api", "globs": ["src/api/**"], "model_lane": "claude"},
            {"intent": "web", "globs": ["src/web/**"], "model_lane": "codex"},
        ],
    )


def _specs(plan):
    return {
        g.grain_id: build_grain_agent_spec(g, goal=plan.goal, blackboard_namespace="swarm/j")
        for g in plan.grains
    }


def test_agent_executor_runs_each_grain_and_writes_artifacts(tmp_path: Path):
    plan = _plan()
    runner = FakeRunner()
    ex = AgentExecutor(agent_runner=runner, use_worktrees=False)
    # Without worktrees, all grains share repo dir; point at tmp_path subdirs by
    # giving each its own dir via a custom provision-free run. Here use_worktrees
    # is False so workdir == repo; artifacts land in tmp_path.
    results = ex.run(tmp_path, plan, _specs(plan))

    assert {r.grain_id for r in results} == {g.grain_id for g in plan.grains}
    assert all(r.state == "completed" for r in results)
    assert sorted(runner.seen) == sorted(g.grain_id for g in plan.grains)
    # Artifacts written (last grain wins the shared dir, but files exist).
    assert (tmp_path / "status.json").exists()
    assert (tmp_path / "patch.diff").exists()
    assert (tmp_path / "usage.json").exists()


def test_agent_executor_marks_failed_grain(tmp_path: Path):
    plan = _plan()
    runner = FakeRunner(fail_grains={"g00-api"})
    ex = AgentExecutor(agent_runner=runner, use_worktrees=False)
    results = ex.run(tmp_path, plan, _specs(plan))
    by_id = {r.grain_id: r for r in results}
    assert by_id["g00-api"].state == "failed"
    assert by_id["g01-web"].state == "completed"


def test_runner_crash_is_contained(tmp_path: Path):
    class Boom:
        def run(self, spec, workdir, grain):
            raise RuntimeError("kaboom")

    plan = partition("one", grains=[{"intent": "x", "globs": ["a/**"]}])
    specs = _specs(plan)
    ex = AgentExecutor(agent_runner=Boom(), use_worktrees=False)
    results = ex.run(tmp_path, plan, specs)
    assert results[0].state == "failed"
    assert "runner exception" in results[0].error  # ty: ignore[unsupported-operator]  # mock/duck-typed test fixture
