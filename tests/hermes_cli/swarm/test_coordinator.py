"""Tests for the swarm coordinator — end-to-end orchestration with seams stubbed."""

from __future__ import annotations

from pathlib import Path

import pytest

from hermes_cli.swarm.coordinator import SwarmGrainResult, run_swarm
from hermes_cli.swarm.grain import OverlapError


class FakeExecutor:
    """Records what it was asked to run and returns canned per-grain results."""

    def __init__(self, state="completed"):
        self.state = state
        self.seen_specs = None

    def run(self, repo, plan, specs):
        self.seen_specs = specs
        return [
            SwarmGrainResult(grain_id=g.grain_id, state=self.state, branch=f"hermes/{plan.job_id}/{g.grain_id}")
            for g in plan.grains
        ]


@pytest.fixture
def hermes_home(tmp_path, monkeypatch):
    home = tmp_path / "hermes_home"
    home.mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    return home


def test_run_swarm_two_disjoint_grains(tmp_path, hermes_home):
    ex = FakeExecutor()
    result = run_swarm(
        "build api and web",
        tmp_path,
        grains=[
            {"intent": "api", "globs": ["src/api/**"], "model_lane": "claude"},
            {"intent": "web", "globs": ["src/web/**"], "model_lane": "codex"},
        ],
        executor=ex,
        claim_domains=True,
    )
    assert result.trivial is False
    assert {g.grain_id for g in result.grains} == set(ex.seen_specs.keys())
    assert all(g.state == "completed" for g in result.grains)
    # Each grain got its own specialized spec with a dedicated memory namespace.
    assert ex.seen_specs["g00-api"].memory_namespace == "swarm/grain/g00-api"
    # A Decision Ledger was written and validates.
    assert result.ledger_path is not None
    assert Path(result.ledger_path).exists()
    # Claims were released (registry empty again).
    registry = tmp_path / ".hermes-orchestrator" / "swarm-claims.json"
    import json

    assert json.loads(registry.read_text()) == []


def test_run_swarm_rejects_overlap_no_execution(tmp_path, hermes_home):
    ex = FakeExecutor()
    with pytest.raises(OverlapError):
        run_swarm(
            "overlapping",
            tmp_path,
            grains=[
                {"intent": "a", "globs": ["src/**"]},
                {"intent": "b", "globs": ["src/api/x.py"]},
            ],
            executor=ex,
        )
    # Executor never ran.
    assert ex.seen_specs is None


def test_run_swarm_trivial_single_grain(tmp_path, hermes_home):
    ex = FakeExecutor()
    result = run_swarm(
        "tiny fix",
        tmp_path,
        grains=[{"intent": "fix typo", "globs": ["README.md"]}],
        executor=ex,
    )
    assert result.trivial is True
    assert any("Trivial goal" in n for n in result.notes)


def test_self_update_auto_applies_reversible(tmp_path, hermes_home):
    """A failed grain yields a reversible routing proposal; user_confirmed -> apply."""
    ex = FakeExecutor(state="failed")
    applied_calls = []

    def apply_fn(proposal):
        applied_calls.append(proposal.target)
        return {"applied": True, "rollback": proposal.extra.get("previous_value")}

    # Patch the proposal builder path to mark single-event findings confirmed so
    # promotion_decision returns "apply" (K=3 rule otherwise defers a 1-off).
    import hermes_cli.swarm.coordinator as coord
    orig = coord._emit_self_update

    def patched(plan, results, *, apply_fn=None):
        from hermes_cli.self_improvement import Proposal, promotion_decision

        p = Proposal(
            kind="routing_miss",
            target=f"lane:codex/grain:{results[0].grain_id}",
            summary="failed",
            rationale="x",
            evidence=("e",),
            reversible=True,
            extra={
                "additive_nudge": True,
                "previous_value": "codex",
                "nudge_delta": 1,
                "user_confirmed": True,
            },
        )
        applied, queued = [], []
        if promotion_decision(p) == "apply":
            applied.append({"decision": "apply", "applied": apply_fn(p)})
        return applied, queued

    monkey = patched
    coord._emit_self_update = monkey
    try:
        result = run_swarm(
            "do a thing",
            tmp_path,
            grains=[{"intent": "thing", "globs": ["src/**"], "model_lane": "codex"}],
            executor=ex,
            apply_fn=apply_fn,
        )
    finally:
        coord._emit_self_update = orig

    assert len(result.applied_updates) == 1
    assert applied_calls  # apply_fn was invoked


def test_run_swarm_can_skip_claims(tmp_path, hermes_home):
    ex = FakeExecutor()
    result = run_swarm(
        "no claims",
        tmp_path,
        grains=[{"intent": "x", "globs": ["a/**"]}],
        executor=ex,
        claim_domains=False,
    )
    assert result.grains[0].state == "completed"
    # No registry written when claims are skipped.
    registry = tmp_path / ".hermes-orchestrator" / "swarm-claims.json"
    assert not registry.exists()
