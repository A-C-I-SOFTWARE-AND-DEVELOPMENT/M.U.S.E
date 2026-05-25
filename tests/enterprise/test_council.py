"""End-to-end orchestrator dispatch behaviour.

Exercises the council runtime against the mock adapters: plan a one-tap
goal, dispatch the tasks, confirm the right ones complete autonomously,
the high-risk one gets escalated, the audit trail is well-shaped, and
a retry loop fires once on schema failure.
"""

from __future__ import annotations

import json

from enterprise.audit import read_events
from enterprise.council import LeafOutcome, PlannedTask, dispatch, plan
from enterprise.policy import Risk, Task


def _decompose_q3_closeout(_goal: str) -> list[Task]:
    """Deterministic decomposer standing in for an LLM plan."""
    return [
        Task(
            "finance", "invoice.read", {"invoice_id": "INV-1"}, rationale="status check"
        ),
        Task(
            "finance",
            "invoice.create",
            {"vendor": "Small Co", "amount": 1_200},
            rationale="small bill",
        ),
        Task(
            "finance",
            "invoice.create",
            {"vendor": "Big Co", "amount": 75_000},
            rationale="big bill",
        ),
        Task(
            "operations",
            "compliance.check",
            {"region": "EU", "category": "financial", "evidence": ("dpa", "soc2")},
        ),
        Task(
            "sales",
            "proposal.draft",
            {"lead_id": "LEAD-9", "product": "Pro", "amount": 5_000},
        ),
    ]


def _runner(task: Task) -> LeafOutcome:
    """Stub leaf that returns plausible structured results per (domain,action)."""
    if task.domain == "finance" and task.action == "invoice.read":
        return LeafOutcome({
            "status": "ok",
            "invoice": {"id": "INV-1", "amount": 100, "state": "open"},
        })
    if task.domain == "finance" and task.action == "invoice.create":
        return LeafOutcome({
            "status": "ok",
            "invoice_id": "INV-X",
            "amount": task.args["amount"],
        })
    if task.domain == "operations":
        return LeafOutcome({"status": "ok", "verdict": "pass", "findings": []})
    if task.domain == "sales":
        return LeafOutcome({
            "status": "ok",
            "proposal_id": "PROP-X",
            "amount": task.args["amount"],
        })
    return LeafOutcome({"status": "unknown"})


def test_plan_classifies_risk_per_task():
    planned = plan("close out Q3", _decompose_q3_closeout)
    assert len(planned) == 5
    by_action = {
        (p.task.domain, p.task.action, p.task.args.get("amount", None)): p.risk
        for p in planned
    }
    assert by_action[("finance", "invoice.read", None)] == Risk.LOW
    assert by_action[("finance", "invoice.create", 1_200)] == Risk.MEDIUM
    assert by_action[("finance", "invoice.create", 75_000)] == Risk.HIGH  # bumped
    assert by_action[("operations", "compliance.check", None)] == Risk.LOW
    assert by_action[("sales", "proposal.draft", 5_000)] == Risk.LOW


def test_dispatch_one_tap_run_separates_completed_from_escalated(audit_dir):
    planned = plan("close out Q3", _decompose_q3_closeout)
    result = dispatch(planned, _runner, session_id="sess-council-1")
    # The $75k invoice should escalate; the rest should complete.
    assert len(result.escalated) == 1
    assert result.escalated[0]["task"]["action"] == "invoice.create"
    assert result.escalated[0]["risk"] == "high"
    assert len(result.completed) == 4
    assert result.failed == []


def test_dispatch_records_full_audit_trail(audit_dir):
    planned = plan("close out Q3", _decompose_q3_closeout)
    dispatch(planned, _runner, session_id="sess-council-trail")
    events = read_events("sess-council-trail")
    by_event: dict[str, int] = {}
    for ev in events:
        by_event[ev.event] = by_event.get(ev.event, 0) + 1
    assert by_event["plan"] == 1
    assert by_event["dispatch"] == 4  # 5 tasks - 1 escalated = 4 dispatched
    assert by_event["leaf_result"] == 4
    assert by_event["judge"] == 4
    assert by_event["escalate"] == 1
    assert by_event["done"] == 1


def test_retry_fires_once_then_records_failure_on_persistent_schema_fail(audit_dir):
    """Runner returns a malformed result; orchestrator must retry exactly once."""
    calls: list[Task] = []

    def bad_runner(task: Task) -> LeafOutcome:
        calls.append(task)
        return LeafOutcome({"oops": "no status key"})  # schema fail

    planned = [
        PlannedTask(
            task=Task("finance", "invoice.read", {"invoice_id": "X"}),
            risk=Risk.LOW,
            needs_jury=False,
        )
    ]
    result = dispatch(planned, bad_runner, session_id="sess-retry", max_retries=1)
    assert len(calls) == 2  # initial + 1 retry
    assert len(result.failed) == 1
    assert result.failed[0]["validation"] == "schema_fail"

    events = read_events("sess-retry")
    retry_events = [e for e in events if e.event == "retry"]
    assert len(retry_events) == 1


def test_dispatch_done_summary_matches_outcome_counts(audit_dir):
    planned = plan("close out Q3", _decompose_q3_closeout)
    dispatch(planned, _runner, session_id="sess-summary")
    events = read_events("sess-summary")
    done = [e for e in events if e.event == "done"]
    assert len(done) == 1
    assert "completed=4" in done[0].result_summary
    assert "escalated=1" in done[0].result_summary


def test_yolo_mode_skips_human_gate(audit_dir):
    """When the human gate always returns True, even HIGH-risk tasks execute."""
    planned = plan("close out Q3", _decompose_q3_closeout)
    result = dispatch(
        planned,
        _runner,
        session_id="sess-yolo",
        human_gate=lambda task, risk: True,
    )
    assert result.escalated == []
    assert len(result.completed) == 5
