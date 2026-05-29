"""Tests for the goal-boundary-governed repair loop."""

from __future__ import annotations

from hermes_cli.jarvis_prime.goal_boundary import GoalBoundary
from hermes_cli.workers.repair_loop import (
    PatchOutcome,
    TestOutcome,
    run_repair_loop,
)


def _boundary(max_iterations: int = 5) -> GoalBoundary:
    return GoalBoundary.create(
        objective="make the failing test pass",
        allowed_actions=["edit_file", "run_tests"],
        stop_conditions=(),
        max_iterations=max_iterations,
        rollback_plan="git checkout -- .",
    )


def test_succeeds_when_patch_fixes_tests():
    # Fails on iteration 1, passes on iteration 2 after a patch.
    state = {"fixed": False}

    def runner() -> TestOutcome:
        if state["fixed"]:
            return TestOutcome(passed=True)
        return TestOutcome(passed=False, failing_tests=("test_foo",), exit_code=1)

    def patcher(ctx) -> PatchOutcome:
        state["fixed"] = True
        return PatchOutcome(
            applied=True, changed_files=("foo.py",), summary="fix off-by-one"
        )

    result = run_repair_loop(boundary=_boundary(), test_runner=runner, patcher=patcher)
    assert result.succeeded is True
    assert result.iterations == 2
    assert result.stop_reason == "tests green"
    assert result.final_test.passed


def test_stops_at_max_iterations_when_never_fixed():
    def runner() -> TestOutcome:
        return TestOutcome(passed=False, failing_tests=("test_bar",), exit_code=1)

    def patcher(ctx) -> PatchOutcome:
        return PatchOutcome(applied=True, summary="attempt")

    result = run_repair_loop(
        boundary=_boundary(max_iterations=3), test_runner=runner, patcher=patcher
    )
    assert result.succeeded is False
    assert "max_iterations" in result.stop_reason
    # 3 iterations attempted, then the 4th tick is refused.
    assert result.iterations == 3


def test_stops_when_patch_makes_no_progress():
    def runner() -> TestOutcome:
        return TestOutcome(passed=False, failing_tests=("t",), exit_code=1)

    def patcher(ctx) -> PatchOutcome:
        return PatchOutcome(applied=False, summary="could not find a fix")

    result = run_repair_loop(boundary=_boundary(), test_runner=runner, patcher=patcher)
    assert result.succeeded is False
    assert "no progress" in result.stop_reason
    assert result.iterations == 1


def test_localizer_feeds_candidate_files():
    seen = {}

    class FakeLoc:
        def localize(self, issue, *, limit=8):
            seen["issue"] = issue
            return [type("L", (), {"path": "svc/uploader.py"})()]

    state = {"n": 0}

    def runner() -> TestOutcome:
        state["n"] += 1
        return TestOutcome(passed=state["n"] > 1, failing_tests=("test_uploader",))

    def patcher(ctx) -> PatchOutcome:
        assert ctx.candidate_files == ("svc/uploader.py",)
        return PatchOutcome(applied=True)

    result = run_repair_loop(
        boundary=_boundary(), test_runner=runner, patcher=patcher, localizer=FakeLoc()
    )
    assert result.succeeded
    assert "test_uploader" in seen["issue"]


def test_steps_recorded_for_ledger():
    def runner() -> TestOutcome:
        return TestOutcome(passed=False, failing_tests=("t",))

    def patcher(ctx) -> PatchOutcome:
        return PatchOutcome(applied=False)

    result = run_repair_loop(boundary=_boundary(), test_runner=runner, patcher=patcher)
    phases = {s["phase"] for s in result.steps}
    assert "test" in phases and "patch" in phases
