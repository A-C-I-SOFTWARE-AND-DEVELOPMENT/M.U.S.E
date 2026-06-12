"""Tests for the swarm coordinator (fake workers; no GPU, no parallel HW)."""

from __future__ import annotations

import pytest

from hermes_cli.jarvis_prime.model_scorecard import ScorecardBook
from hermes_cli.jarvis_prime.research_fabric.autoresearch.engine import ExperimentConfig
from hermes_cli.jarvis_prime.research_fabric.autoresearch.swarm import (
    LaneSpec,
    plan_swarm,
    run_swarm,
)
from hermes_cli.jarvis_prime.self_update import ProposalBook, ProposalStatus

from .test_autoresearch_bridge import FakeAutoresearchWorker


def _base_config(tmp_path) -> ExperimentConfig:
    return ExperimentConfig(
        tag="jun12",
        workspace_dir=str(tmp_path / "swarm"),
        max_cost_usd=6.0,
        cost_per_hour_usd=3.0,
        vram_budget_mb=12000.0,
    )


def test_plan_swarm_unique_branches_workspaces_and_split_ceiling(tmp_path) -> None:
    plan = plan_swarm("jun12", 3, base_config=_base_config(tmp_path))
    branches = [a.branch for a in plan.assignments]
    assert branches == [
        "autoresearch/jun12-gpu0",
        "autoresearch/jun12-gpu1",
        "autoresearch/jun12-gpu2",
    ]
    workspaces = {a.workspace_dir for a in plan.assignments}
    assert len(workspaces) == 3  # no shared writable state
    assert all(a.config.max_cost_usd == pytest.approx(2.0) for a in plan.assignments)
    assert "3 lane(s)" in plan.summary()


def test_plan_swarm_modal_lanes_and_validation(tmp_path) -> None:
    plan = plan_swarm(
        "m1",
        [LaneSpec(device="cuda:0"), LaneSpec(device="modal:H100", cost_per_hour_usd=4.5)],
        base_config=_base_config(tmp_path),
    )
    assert plan.assignments[1].branch == "autoresearch/m1-modal1"
    assert plan.assignments[1].config.cost_per_hour_usd == 4.5
    with pytest.raises(ValueError, match="at least one lane"):
        plan_swarm("empty", 0, base_config=_base_config(tmp_path))


def test_run_swarm_merges_books_and_emits_one_proposal(tmp_path) -> None:
    plan = plan_swarm("jun12", 3, base_config=_base_config(tmp_path))
    lane_bpb = {0: 0.99, 1: 0.95, 2: 0.97}
    workers = {
        k: FakeAutoresearchWorker(champion_bpb=v) for k, v in lane_bpb.items()
    }
    book = ProposalBook()
    merged = ScorecardBook()
    outcome = run_swarm(
        plan,
        worker_factory=lambda a: workers[a.lane_id],
        book=book,
        baseline_bpb=1.0,
        scorecard_book=merged,
    )
    # single-writer merge collected every lane's champion card
    assert len(merged.scorecards) == 3
    # exactly ONE proposal, from the best lane (lane 1, bpb 0.95)
    assert len(book.proposals) == 1
    assert book.proposals[0].status is ProposalStatus.NEEDS_OWNER_APPROVAL
    assert outcome.best_lane is not None
    assert outcome.best_lane.assignment.lane_id == 1
    assert outcome.proposal_outcome is not None
    assert outcome.proposal_outcome.proposal is book.proposals[0]


def test_infeasible_best_lane_is_excluded(tmp_path) -> None:
    plan = plan_swarm("jun12", 2, base_config=_base_config(tmp_path))
    workers = {
        # lane 0 "wins" bpb but its result is infeasible (no feasible champion)
        0: FakeAutoresearchWorker(champion_bpb=None, infeasible_bpb=0.90),
        1: FakeAutoresearchWorker(champion_bpb=0.97),
    }
    book = ProposalBook()
    outcome = run_swarm(
        plan,
        worker_factory=lambda a: workers[a.lane_id],
        book=book,
        baseline_bpb=1.0,
    )
    assert outcome.best_lane is not None
    assert outcome.best_lane.assignment.lane_id == 1  # feasible lane wins
    assert len(book.proposals) == 1


def test_all_lanes_failing_yields_no_proposal(tmp_path) -> None:
    plan = plan_swarm("jun12", 2, base_config=_base_config(tmp_path))
    book = ProposalBook()
    outcome = run_swarm(
        plan,
        worker_factory=lambda a: FakeAutoresearchWorker(champion_bpb=1.10),  # regressions
        book=book,
        baseline_bpb=1.0,
    )
    assert outcome.best_lane is None
    assert outcome.proposal_outcome is None
    assert book.proposals == []


def test_lane_exception_is_isolated(tmp_path) -> None:
    plan = plan_swarm("jun12", 2, base_config=_base_config(tmp_path))

    def factory(assignment):
        if assignment.lane_id == 0:
            raise RuntimeError("lane 0 GPU on fire")
        return FakeAutoresearchWorker(champion_bpb=0.96)

    book = ProposalBook()
    outcome = run_swarm(
        plan, worker_factory=factory, book=book, baseline_bpb=1.0
    )
    assert "on fire" in outcome.lanes[0].error
    assert outcome.lanes[0].improvement is None
    assert outcome.best_lane is not None
    assert outcome.best_lane.assignment.lane_id == 1
    assert len(book.proposals) == 1
