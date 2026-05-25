"""Risk classification + human-in-the-loop gating."""

from __future__ import annotations

import pytest

from enterprise.policy import Risk, Task, classify, known_actions, requires_human


def test_known_low_risk_actions_classify_as_low():
    assert classify(Task("finance", "invoice.read")) == Risk.LOW
    assert classify(Task("hr", "policy.lookup")) == Risk.LOW
    assert classify(Task("customer-service", "ticket.classify")) == Risk.LOW


def test_known_high_risk_actions_classify_as_high():
    assert classify(Task("finance", "payment.wire", {"amount": 100})) == Risk.HIGH
    assert classify(Task("hr", "employee.terminate")) == Risk.HIGH
    assert classify(Task("sales", "contract.execute")) == Risk.HIGH


def test_invoice_below_threshold_stays_medium():
    t = Task("finance", "invoice.create", {"amount": 1_000, "vendor": "X"})
    assert classify(t) == Risk.MEDIUM


def test_invoice_above_threshold_escalates_to_high():
    t = Task("finance", "invoice.create", {"amount": 75_000, "vendor": "X"})
    assert classify(t) == Risk.HIGH


def test_sales_discount_threshold_bumps_to_high():
    # 30% discount > 25% threshold → MEDIUM → HIGH.
    t = Task("sales", "discount.apply", {"discount": 0.30})
    assert classify(t) == Risk.HIGH


def test_unknown_read_verb_defaults_to_low():
    assert classify(Task("finance", "invoice.summarize")) == Risk.LOW


def test_unknown_write_verb_defaults_to_medium():
    assert classify(Task("finance", "invoice.annotate")) == Risk.MEDIUM


def test_unknown_destructive_verb_defaults_to_high():
    assert classify(Task("finance", "invoice.delete")) == Risk.HIGH


def test_tag_override_forces_high():
    t = Task("finance", "report.generate", tags=("@review-me",))
    assert classify(t) == Risk.HIGH


def test_gdpr_tag_bumps_one_level():
    base = Task("hr", "policy.lookup", tags=())
    assert classify(base) == Risk.LOW
    bumped = Task("hr", "policy.lookup", tags=("gdpr",))
    assert classify(bumped) == Risk.MEDIUM


@pytest.mark.parametrize(
    "autonomy,task,expected",
    [
        ("default", Task("finance", "invoice.read"), False),
        ("default", Task("finance", "payment.wire", {"amount": 1}), True),
        ("strict", Task("finance", "invoice.create", {"amount": 100}), True),
        ("strict", Task("finance", "invoice.read"), False),
        ("yolo", Task("finance", "payment.wire", {"amount": 1_000_000}), False),
    ],
)
def test_requires_human_modes(autonomy, task, expected):
    assert requires_human(task, autonomy=autonomy) is expected


def test_known_actions_covers_all_five_domains():
    actions = known_actions()
    domains = {d for d, _ in actions}
    assert {"finance", "hr", "customer-service", "operations", "sales"} <= domains
