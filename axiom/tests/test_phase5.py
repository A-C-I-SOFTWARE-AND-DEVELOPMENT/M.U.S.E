"""Phase 5 — orchestration with gates: HTN-lite task trees with
verifier nodes, exactly-once leaves, and the risk-tiered change flow.
EXIT GATE: a HIGH change without the exact ceremonial phrase is
provably never executed, and the denial is in the ledger.
"""

from __future__ import annotations

import pytest

from axiom.core.ledger import Ledger
from axiom.orchestrator.gates import Change, RISK_HIGH, RISK_LOW, RISK_MED
from axiom.orchestrator.htn import Plan, Task
from axiom.orchestrator.jobs import JobStore
from axiom.orchestrator.proposals import (
    CEREMONIAL_PHRASE,
    propose_change,
)


# ----------------------------------------------------------------- 5.1 HTN

def test_htn_composite_requires_verifier_task():
    leaf = Task.leaf("add", inputs={"a": 1}, job=lambda i: i["a"] + 1)
    with pytest.raises(ValueError):
        Task.composite("parent", children=[leaf], verifier=None)


def test_htn_leaf_jobs_exactly_once():
    calls = []

    def job(inputs):
        calls.append(inputs)
        return inputs["x"] * 2

    tree = Task.composite(
        "doubles",
        children=[
            Task.leaf("d1", inputs={"x": 1}, job=job),
            Task.leaf("d2", inputs={"x": 2}, job=job),
        ],
        verifier=lambda results: all(isinstance(r, int) for r in results),
    )
    store = JobStore(":memory:")
    plan = Plan(store)
    out1 = plan.execute(tree)
    out2 = plan.execute(tree)  # replay: nothing re-runs
    assert out1 == out2 == [2, 4]
    assert len(calls) == 2  # two leaves, each exactly once


def test_htn_verifier_failure_halts():
    tree = Task.composite(
        "bad",
        children=[Task.leaf("l", inputs={"x": 1}, job=lambda i: i["x"])],
        verifier=lambda results: False,  # the decomposition lies
    )
    plan = Plan(JobStore(":memory:"))
    with pytest.raises(RuntimeError, match="verifier"):
        plan.execute(tree)


def test_htn_nested_decomposition():
    def job(inputs):
        return inputs["x"] + 1

    inner = Task.composite(
        "inner",
        children=[Task.leaf("a", inputs={"x": 1}, job=job)],
        verifier=lambda results: results == [2],
    )
    outer = Task.composite(
        "outer",
        children=[inner, Task.leaf("b", inputs={"x": 10}, job=job)],
        verifier=lambda results: len(results) == 2,
    )
    assert Plan(JobStore(":memory:")).execute(outer) == [[2], 11]


# -------------------------------------------------- 5.2/5.3 risk-tiered auth

def _changes():
    return {
        RISK_LOW: Change("comment fix", loc=2, files=1),
        RISK_MED: Change("new preset", loc=40, files=2, effects=("db.write",)),
        RISK_HIGH: Change("default routing change", loc=200, files=8,
                          effects=("net", "db.write"),
                          changes_default_behavior=True),
    }


def test_low_change_silent_executes_and_ledgers():
    ledger = Ledger(":memory:")
    ran = []
    out = propose_change(_changes()[RISK_LOW], lambda: ran.append(1),
                         ledger=ledger)
    assert out["executed"] is True and out["risk"] == RISK_LOW
    assert out["auth"] == "silent"
    assert ran == [1]
    gate_events = ledger.events("gate_result")
    assert gate_events, "every gate result must be ledgered"
    assert ledger.verify_chain() is True


def test_med_change_requires_lightweight_callback():
    ledger = Ledger(":memory:")
    ran = []
    # No approver: deny by default.
    out = propose_change(_changes()[RISK_MED], lambda: ran.append(1),
                         ledger=ledger)
    assert out["executed"] is False and ran == []
    assert ledger.events("change_denied")
    # Callback approves: executes.
    out = propose_change(_changes()[RISK_MED], lambda: ran.append(1),
                         ledger=ledger, approver=lambda change: True)
    assert out["executed"] is True and ran == [1]
    assert out["auth"] == "lightweight"


def test_high_without_exact_phrase_is_never_executed():
    """EXIT GATE: HIGH + wrong phrase => provably not executed,
    denial ledgered."""
    ledger = Ledger(":memory:")
    ran = []
    for bad in (None, True, "yes", "Yes with authorization",
                "yes, with authorization.", "Yes, with authorization"):
        out = propose_change(
            _changes()[RISK_HIGH], lambda: ran.append(1),
            ledger=ledger,
            approver=(lambda b: (lambda change: b))(bad),
        )
        assert out["executed"] is False
        assert out["auth"] == "ceremonial"
    assert ran == []  # the plan body NEVER ran
    denials = ledger.events("change_denied")
    assert len(denials) == 6
    assert all(d["payload"]["risk"] == RISK_HIGH for d in denials)
    assert ledger.verify_chain() is True


def test_high_with_exact_phrase_executes():
    ledger = Ledger(":memory:")
    ran = []
    out = propose_change(_changes()[RISK_HIGH], lambda: ran.append(1),
                         ledger=ledger,
                         approver=lambda change: CEREMONIAL_PHRASE)
    assert out["executed"] is True and ran == [1]
    # OwnerApproval appears in the ledgered gate results.
    gates_run = [e["payload"]["gate"] for e in ledger.events("gate_result")]
    assert "OwnerApproval" in gates_run
