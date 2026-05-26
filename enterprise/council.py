"""Orchestrator runtime for the enterprise council.

The Orchestrator agent (defined in ``skills/enterprise-council/orchestrator/SKILL.md``)
asks the LLM to produce a *plan* — an ordered list of structured tasks
— from the user's one-tap command. This module gives that plan a place
to run.

The runtime exposes two functions:

  * ``plan(goal, decomposer)`` — wraps an LLM-produced plan (or a
    deterministic decomposer in tests) into a list of `Task` objects
    with classified risk.
  * ``dispatch(plan, runner, judge_fn, policy_gate)`` — drives the
    plan, spawning a leaf per task via ``runner``, judging each
    output, retrying on failure, and escalating only when
    ``policy_gate(task)`` returns True.

The runtime is intentionally synchronous and side-effect-free apart
from audit writes. Asynchronous fan-out is left to the caller — for
Hermes' subagent loop we'd wrap each leaf call in
``asyncio.to_thread`` or its native scheduler.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Optional, Sequence

from enterprise.audit import audit
from enterprise.judge import JudgeVerdict, cross_check
from enterprise.policy import Risk, Task, classify, requires_human


@dataclass(frozen=True)
class PlannedTask:
    """A Task plus the orchestrator's pre-classified risk + jury hint."""

    task: Task
    risk: Risk
    needs_jury: bool


@dataclass
class LeafOutcome:
    """One leaf's structured return — what the orchestrator hands to the Judge."""

    result: Mapping[str, Any]
    jury_result: Optional[Mapping[str, Any]] = None
    result_tags: tuple[str, ...] = ()
    result_summary: str = ""
    secret_fingerprints: tuple[str, ...] = ()


@dataclass
class DispatchResult:
    """End-of-run summary the Orchestrator returns to the user."""

    session_id: str
    completed: list[Mapping[str, Any]] = field(default_factory=list)
    escalated: list[Mapping[str, Any]] = field(default_factory=list)
    failed: list[Mapping[str, Any]] = field(default_factory=list)


PlanDecomposer = Callable[[str], Sequence[Task]]
LeafRunner = Callable[[Task], LeafOutcome]
HumanGate = Callable[[Task, Risk], bool]


def plan(goal: str, decomposer: PlanDecomposer) -> list[PlannedTask]:
    """Run ``decomposer`` against ``goal`` and tag each task with risk.

    The orchestrator's SKILL.md instructs the LLM to emit a JSON list
    matching `Task`'s shape; a thin parser in the SKILL wraps that into
    ``Task`` instances and passes them here. Tests use a deterministic
    decomposer.
    """
    tasks = list(decomposer(goal))
    planned: list[PlannedTask] = []
    for t in tasks:
        risk = classify(t)
        # We always request a jury for HIGH risk; MEDIUM gets one when
        # the task is irreversible or carries an external-comms tag.
        needs_jury = risk == Risk.HIGH or any(
            tag in t.tags for tag in ("irreversible", "external-mass", "@jury")
        )
        planned.append(PlannedTask(task=t, risk=risk, needs_jury=needs_jury))
    return planned


def _confirm_high_risk(task: Task, risk: Risk) -> bool:
    """Default human gate: only HIGH-risk tasks pause for confirmation.

    Tests override this to either always-allow or always-block. Real
    Hermes wiring routes through the existing approval flow.
    """
    return not requires_human(task)


def dispatch(
    planned: Sequence[PlannedTask],
    runner: LeafRunner,
    *,
    session_id: Optional[str] = None,
    human_gate: HumanGate = _confirm_high_risk,
    max_retries: int = 1,
    required_keys: tuple[str, ...] = ("status",),
) -> DispatchResult:
    """Drive a planned list of tasks to completion.

    Per-task flow:
      1. ``human_gate(task, risk)`` decides whether to pause. If it
         returns False, the task is recorded as escalated and skipped.
      2. ``runner(task)`` returns a `LeafOutcome`. We feed that to the
         Judge with the task-declared required keys.
      3. On schema_fail / policy_fail / judge_disagree, we retry up to
         ``max_retries`` times. The retry re-runs ``runner`` and
         re-judges. After exhaustion the task is recorded as failed.

    A row is audited for *every* event (plan, dispatch, leaf_result,
    judge, retry, escalate, done) so the Monitor has a complete trail.
    """
    sid = session_id or f"council-{uuid.uuid4().hex[:8]}"
    audit(sid, "plan", "orchestrator", extra={"task_count": len(planned)})
    out = DispatchResult(session_id=sid)

    for pt in planned:
        task, risk = pt.task, pt.risk
        if not human_gate(task, risk):
            audit(
                sid,
                "escalate",
                "orchestrator",
                tool=f"{task.domain}.{task.action}",
                risk=risk,
                validation="escalated",
                result_summary=f"awaiting human approval for {task.domain}.{task.action}",
            )
            out.escalated.append({"task": _task_to_dict(task), "risk": risk.value})
            continue

        audit(
            sid,
            "dispatch",
            "orchestrator",
            tool=f"{task.domain}.{task.action}",
            args=task.args,
            risk=risk,
        )

        attempts = 0
        last_verdict: Optional[JudgeVerdict] = None
        last_outcome: Optional[LeafOutcome] = None
        while attempts <= max_retries:
            t0 = time.monotonic()
            outcome = runner(task)
            elapsed = (time.monotonic() - t0) * 1000
            last_outcome = outcome
            audit(
                sid,
                "leaf_result",
                task.domain,
                tool=task.action,
                result=outcome.result,
                result_summary=outcome.result_summary,
                risk=risk,
                duration_ms=elapsed,
                secret_fingerprints=outcome.secret_fingerprints,
            )
            verdict = cross_check(
                task=task,
                declared_risk=risk,
                leaf_result=outcome.result,
                jury_result=outcome.jury_result if pt.needs_jury else None,
                required_keys=required_keys,
                result_tags=outcome.result_tags,
            )
            last_verdict = verdict
            audit(
                sid,
                "judge",
                "judge",
                tool=task.action,
                validation=verdict.validation,
                result_summary="; ".join(verdict.reasons)[:200],
                risk=risk,
                retry_count=attempts,
            )
            if verdict.ok:
                break
            attempts += 1
            if attempts <= max_retries:
                audit(
                    sid,
                    "retry",
                    "orchestrator",
                    tool=task.action,
                    retry_count=attempts,
                    validation=verdict.validation,
                )

        record = {
            "task": _task_to_dict(task),
            "risk": risk.value,
            "validation": last_verdict.validation if last_verdict else "no_verdict",
            "result": dict(last_outcome.result) if last_outcome else None,
        }
        if last_verdict and last_verdict.ok:
            out.completed.append(record)
        else:
            out.failed.append(record)

    audit(
        sid,
        "done",
        "orchestrator",
        result_summary=(
            f"completed={len(out.completed)} "
            f"escalated={len(out.escalated)} "
            f"failed={len(out.failed)}"
        ),
    )
    return out


def _task_to_dict(task: Task) -> dict[str, Any]:
    return {
        "domain": task.domain,
        "action": task.action,
        "args": dict(task.args),
        "rationale": task.rationale,
        "tags": list(task.tags),
    }
