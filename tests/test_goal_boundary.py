"""Tests for the Goal Boundary Layer (paperclip governance)."""

from __future__ import annotations

import pytest

from muse_cli.jarvis_prime.goal_boundary import (
    BoundaryError,
    Decision,
    GoalBoundary,
    LoopController,
    StopReason,
)
from muse_cli.jarvis_prime.owner_auth import AUTHORIZATION_PHRASE


def _boundary(**overrides) -> GoalBoundary:
    base = dict(
        objective="tidy imports",
        allowed_actions=["edit_file", "run_tests"],
        forbidden_actions=["force_push"],
        stop_conditions=["tests_green"],
        max_iterations=3,
        max_cost=1.0,
        owner_approval_threshold=0.0,
        rollback_plan="git revert HEAD",
    )
    base.update(overrides)
    return GoalBoundary.create(**base)  # ty: ignore[invalid-argument-type]  # mock/duck-typed test fixture


def test_refuses_loop_without_brakes():
    with pytest.raises(BoundaryError):
        GoalBoundary.create(
            objective="optimize forever",
            allowed_actions=["edit_file"],
            stop_conditions=(),
            max_iterations=0,
            max_cost=0.0,
            rollback_plan="revert",
        )


def test_requires_objective_and_rollback():
    with pytest.raises(BoundaryError):
        GoalBoundary.create(
            objective="  ", allowed_actions=["x"], max_iterations=1, rollback_plan="r"
        )
    with pytest.raises(BoundaryError):
        GoalBoundary.create(
            objective="ok", allowed_actions=["x"], max_iterations=1, rollback_plan=""
        )


def test_allowed_forbidden_overlap_rejected():
    with pytest.raises(BoundaryError):
        GoalBoundary.create(
            objective="ok",
            allowed_actions=["edit_file"],
            forbidden_actions=["edit_file"],
            max_iterations=1,
            rollback_plan="r",
        )


def test_continue_until_max_iterations():
    ctrl = LoopController(boundary=_boundary())
    v1 = ctrl.tick(next_action="edit_file", action_cost=0.1)
    v2 = ctrl.tick(next_action="run_tests", action_cost=0.1)
    v3 = ctrl.tick(next_action="edit_file", action_cost=0.1)
    assert [v.decision for v in (v1, v2, v3)] == [Decision.CONTINUE] * 3
    v4 = ctrl.tick(next_action="edit_file")
    assert v4.decision is Decision.STOP
    assert v4.stop_reason is StopReason.MAX_ITERATIONS


def test_stop_condition_signal():
    ctrl = LoopController(boundary=_boundary())
    v = ctrl.tick(next_action="run_tests", signals={"tests_green": True})
    assert v.decision is Decision.STOP
    assert v.stop_reason is StopReason.STOP_CONDITION_MET


def test_cost_ceiling():
    ctrl = LoopController(boundary=_boundary(max_cost=0.5, stop_conditions=()))
    ctrl.tick(next_action="edit_file", action_cost=0.4)
    v = ctrl.tick(next_action="edit_file", action_cost=0.4)
    assert v.decision is Decision.STOP
    assert v.stop_reason is StopReason.MAX_COST


def test_forbidden_action_stops():
    ctrl = LoopController(boundary=_boundary())
    v = ctrl.tick(next_action="force_push")
    assert v.decision is Decision.STOP
    assert v.stop_reason is StopReason.FORBIDDEN_ACTION


def test_action_outside_allowlist_stops():
    ctrl = LoopController(boundary=_boundary())
    v = ctrl.tick(next_action="delete_database")
    assert v.decision is Decision.STOP
    assert v.stop_reason is StopReason.FORBIDDEN_ACTION


def test_owner_gated_action_requires_phrase():
    # production_deploy is an owner-gated action; allow it in the allowlist so
    # the gate (not the allowlist) is what blocks it.
    b = _boundary(
        allowed_actions=["edit_file", "production_deploy"], forbidden_actions=[]
    )
    ctrl = LoopController(boundary=b)
    v = ctrl.tick(next_action="production_deploy")
    assert v.decision is Decision.NEEDS_OWNER_APPROVAL
    assert v.stop_reason is StopReason.NEEDS_OWNER_APPROVAL

    assert ctrl.authorize("yes go ahead") is False
    assert ctrl.authorize(AUTHORIZATION_PHRASE) is True
    v2 = ctrl.tick(next_action="production_deploy")
    assert v2.decision is Decision.CONTINUE


def test_cost_threshold_requires_owner():
    b = _boundary(
        owner_approval_threshold=0.5,
        max_cost=0.0,
        stop_conditions=(),
        max_iterations=10,
    )
    ctrl = LoopController(boundary=b)
    v = ctrl.tick(next_action="edit_file", action_cost=0.6)
    assert v.decision is Decision.NEEDS_OWNER_APPROVAL
    ctrl.authorize(AUTHORIZATION_PHRASE)
    v2 = ctrl.tick(next_action="edit_file", action_cost=0.6)
    assert v2.decision is Decision.CONTINUE


def test_objective_complete_stops():
    ctrl = LoopController(boundary=_boundary())
    ctrl.mark_complete()
    v = ctrl.tick(next_action="edit_file")
    assert v.stop_reason is StopReason.OBJECTIVE_COMPLETE


def test_ledger_records_capture_run():
    ctrl = LoopController(boundary=_boundary())
    ctrl.tick(next_action="edit_file", action_cost=0.1)
    ctrl.tick(next_action="run_tests", signals={"tests_green": True})
    records = ctrl.ledger_records(job_id="job-1")
    assert records[0]["kind"] == "goal_boundary_declared"
    assert records[0]["job_id"] == "job-1"
    assert any(r.get("kind") == "goal_boundary_verdict" for r in records[1:])
