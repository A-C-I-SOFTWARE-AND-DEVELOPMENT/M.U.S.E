"""Behavioral tests for the gated automation-flow execution engine (W8)."""

from __future__ import annotations

from muse_cli.jarvis_prime.ir_compilers.automation_flow import (
    AutomationFlow,
    FlowOutput,
    FlowStep,
    FlowTrigger,
)
from muse_cli.jarvis_prime.nlp_flow_exec import (
    _EXTERNAL_OPS,
    _PURE_OPS,
    FlowExecutor,
    FlowRun,
    FlowStepResult,
)
from muse_cli.jarvis_prime.owner_auth import (
    authorize_challenge,
    create_challenge,
)


def _flow_with_external() -> AutomationFlow:
    return AutomationFlow(
        name="on_invoice_email",
        triggers=(FlowTrigger(kind="event", event="invoice_email"),),
        steps=(
            FlowStep(id="s1", op="extract", target="invoice", produces="total"),
            FlowStep(id="s2", op="alert", target="owner", params={"amount": "total"}),
        ),
        outputs=(FlowOutput(kind="alert", channel="owner"),),
        owner_gated_actions=("post_publicly",),
    )


def test_op_classification_disjoint():
    assert _PURE_OPS.isdisjoint(_EXTERNAL_OPS)
    assert "alert" in _EXTERNAL_OPS
    assert "extract" in _PURE_OPS


def test_simulate_default_performs_no_external_io():
    flow = _flow_with_external()
    run = FlowExecutor().run(flow)

    assert isinstance(run, FlowRun)
    assert run.executed is False

    by_id = {s.step_id: s for s in run.steps}
    # Pure step ran.
    assert by_id["s1"].performed is True
    # External step recorded as simulated only — no external IO.
    alert = by_id["s2"]
    assert alert.op == "alert"
    assert alert.performed is False
    assert "simulate" in alert.detail.lower()

    # No external step was ever marked performed in simulate mode.
    assert all(
        (not s.performed) for s in run.steps if s.op in _EXTERNAL_OPS
    )


def test_execute_without_grant_refuses():
    flow = _flow_with_external()
    run = FlowExecutor().run(flow, mode="execute", grant=None)

    assert run.executed is False
    # Log explains the missing grant.
    assert any("grant" in line.lower() for line in run.log)
    assert any("refused" in line.lower() for line in run.log)

    alert = next(s for s in run.steps if s.op == "alert")
    assert alert.performed is False


def test_execute_with_valid_grant_runs_external():
    flow = _flow_with_external()
    ch = create_challenge("post_publicly")
    grant = authorize_challenge(ch, ch.required_phrase)
    assert grant is not None

    run = FlowExecutor().run(flow, mode="execute", grant=grant)

    assert run.executed is True
    alert = next(s for s in run.steps if s.op == "alert")
    assert alert.performed is True
    assert "grant" in alert.detail.lower()


def test_execute_with_wrong_grant_refuses():
    flow = _flow_with_external()
    ch = create_challenge("spend_money")  # does not cover post_publicly
    grant = authorize_challenge(ch, ch.required_phrase)
    assert grant is not None

    run = FlowExecutor().run(flow, mode="execute", grant=grant)

    assert run.executed is False
    alert = next(s for s in run.steps if s.op == "alert")
    assert alert.performed is False
    assert any("does not cover" in line.lower() for line in run.log)


def test_pure_only_flow_executes_without_grant():
    flow = AutomationFlow(
        name="pure_only",
        triggers=(FlowTrigger(kind="event", event="row_added"),),
        steps=(
            FlowStep(id="s1", op="extract", target="row", produces="total"),
            FlowStep(id="s2", op="write", target="ledger", params={"value": "total"}),
        ),
        owner_gated_actions=(),
    )
    run = FlowExecutor().run(flow, mode="execute", grant=None)

    assert run.executed is True
    assert all(s.performed for s in run.steps)


def test_step_context_passing():
    flow = AutomationFlow(
        name="ctx",
        triggers=(FlowTrigger(kind="event", event="ping"),),
        steps=(
            FlowStep(id="s1", op="extract", target="invoice", produces="total"),
            FlowStep(
                id="s2",
                op="compute",
                target="",
                params={"basis": "total"},
                produces="grand_total",
            ),
        ),
    )
    run = FlowExecutor().run(flow)

    assert run.executed is False  # simulate default
    s1, s2 = run.steps
    assert s1.produced == "total"
    assert s2.produced == "grand_total"
    assert s2.performed is True


def test_step_result_and_run_to_dict():
    res = FlowStepResult("s1", "extract", "simulate", True, "ran", "total")
    d = res.to_dict()
    assert d["step_id"] == "s1"
    assert d["produced"] == "total"

    run = FlowExecutor().run(_flow_with_external())
    rd = run.to_dict()
    assert rd["executed"] is False
    assert isinstance(rd["steps"], list)
    assert isinstance(rd["outputs"], list)
    assert rd["outputs"][0]["kind"] == "alert"
    assert isinstance(rd["log"], list)
