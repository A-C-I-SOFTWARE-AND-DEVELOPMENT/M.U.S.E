"""Repair loop — failed test → localize → patch → rerun → stop after limit.

This is the self-healing inner loop of the Prompt → Patch → Test → PR pipeline.
It is intentionally **dependency-injected**: the test runner, the patcher
(a worker actuator), and the localizer are passed in, so the loop is
deterministic and unit-testable without spawning a real Claude Code / Codex /
Aider / Goose process.

Safety is non-negotiable: the loop runs *inside* a
:class:`~muse_cli.jarvis_prime.goal_boundary.GoalBoundary`. It cannot iterate
forever — the boundary's ``max_iterations`` (or a stop condition / cost
ceiling) terminates it, and every step is recorded for the ledger.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional, Protocol

from muse_cli.jarvis_prime.goal_boundary import (
    Decision,
    GoalBoundary,
    LoopController,
)


@dataclass(frozen=True)
class TestOutcome:
    __test__ = False  # not a pytest test class despite the name

    passed: bool
    failing_tests: tuple[str, ...] = ()
    log: str = ""
    exit_code: int = 0

    def to_dict(self) -> dict[str, object]:
        return {
            "passed": self.passed,
            "failing_tests": list(self.failing_tests),
            "exit_code": self.exit_code,
        }


@dataclass(frozen=True)
class PatchOutcome:
    applied: bool
    changed_files: tuple[str, ...] = ()
    summary: str = ""
    diff: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "applied": self.applied,
            "changed_files": list(self.changed_files),
            "summary": self.summary,
        }


class Localizer(Protocol):
    def localize(self, issue: str, *, limit: int = 8): ...


# Callables the caller injects.
TestRunner = Callable[[], TestOutcome]
Patcher = Callable[["RepairContext"], PatchOutcome]


@dataclass
class RepairContext:
    objective: str
    iteration: int
    last_test: TestOutcome
    candidate_files: tuple[str, ...]
    history: list[dict[str, object]] = field(default_factory=list)


@dataclass(frozen=True)
class RepairResult:
    succeeded: bool
    iterations: int
    stop_reason: str
    final_test: Optional[TestOutcome]
    steps: tuple[dict[str, object], ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "succeeded": self.succeeded,
            "iterations": self.iterations,
            "stop_reason": self.stop_reason,
            "final_test": self.final_test.to_dict() if self.final_test else None,
            "steps": list(self.steps),
        }


def run_repair_loop(
    *,
    boundary: GoalBoundary,
    test_runner: TestRunner,
    patcher: Patcher,
    localizer: Optional[Localizer] = None,
    patch_action: str = "edit_file",
    on_step: Optional[Callable[[dict[str, object]], None]] = None,
) -> RepairResult:
    """Drive the repair loop under a goal boundary.

    Sequence per iteration:
      1. run tests; if green, stop (success).
      2. localize the failing tests to candidate files (if a localizer given).
      3. ask the patcher to apply a fix.
      4. ask the boundary whether another iteration is permitted.

    Stops on: tests green, boundary STOP/NEEDS_OWNER_APPROVAL, or a patch that
    makes no change (no progress).
    """

    controller = LoopController(boundary=boundary)
    steps: list[dict[str, object]] = []
    last_test: Optional[TestOutcome] = None
    history: list[dict[str, object]] = []

    def emit(step: dict[str, object]) -> None:
        steps.append(step)
        if on_step is not None:
            on_step(step)

    while True:
        # Gate the *next* iteration before doing work.
        verdict = controller.tick(next_action=patch_action, action_cost=1.0)
        if verdict.decision is not Decision.CONTINUE:
            return RepairResult(
                succeeded=False,
                iterations=controller.iteration,
                stop_reason=verdict.reason,
                final_test=last_test,
                steps=tuple(steps),
            )

        iteration = controller.iteration

        # 1. Run tests.
        test = test_runner()
        last_test = test
        emit({"iteration": iteration, "phase": "test", **test.to_dict()})
        if test.passed:
            controller.mark_complete()
            return RepairResult(
                succeeded=True,
                iterations=iteration,
                stop_reason="tests green",
                final_test=test,
                steps=tuple(steps),
            )

        # 2. Localize.
        candidates: tuple[str, ...] = ()
        if localizer is not None:
            issue = "tests failing: " + ", ".join(test.failing_tests or ["unknown"])
            locs = localizer.localize(issue, limit=5)
            candidates = tuple(getattr(loc, "path", str(loc)) for loc in locs)
            emit({
                "iteration": iteration,
                "phase": "localize",
                "candidate_files": list(candidates),
            })

        # 3. Patch.
        ctx = RepairContext(
            objective=boundary.objective,
            iteration=iteration,
            last_test=test,
            candidate_files=candidates,
            history=history,
        )
        patch = patcher(ctx)
        emit({"iteration": iteration, "phase": "patch", **patch.to_dict()})
        history.append({"iteration": iteration, "patch": patch.to_dict()})

        if not patch.applied:
            return RepairResult(
                succeeded=False,
                iterations=iteration,
                stop_reason="patcher made no change (no progress)",
                final_test=test,
                steps=tuple(steps),
            )
        # loop continues: next tick re-runs tests to verify the patch.


def ledger_records(
    result: RepairResult, *, job_id: str | None = None
) -> list[dict[str, object]]:
    out: list[dict[str, object]] = [
        {"kind": "repair_loop_start", "job_id": job_id},
    ]
    for step in result.steps:
        rec = dict(step)
        rec["kind"] = "repair_loop_step"
        rec["job_id"] = job_id
        out.append(rec)
    out.append({"kind": "repair_loop_result", "job_id": job_id, **result.to_dict()})
    return out


__all__ = [
    "TestOutcome",
    "PatchOutcome",
    "RepairContext",
    "RepairResult",
    "run_repair_loop",
    "ledger_records",
]
