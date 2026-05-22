"""Validator/Judge: schema, policy, and jury checks."""

from __future__ import annotations

from enterprise.judge import cross_check
from enterprise.policy import Risk, Task


def _ok_task() -> Task:
    return Task("finance", "invoice.create", {"amount": 100, "vendor": "ACME"})


def test_passes_when_result_matches_schema_no_jury():
    v = cross_check(
        task=_ok_task(),
        declared_risk=Risk.MEDIUM,
        leaf_result={"status": "ok", "invoice_id": "INV-1"},
        required_keys=("status", "invoice_id"),
    )
    assert v.ok is True
    assert v.validation == "ok"


def test_fails_when_required_key_missing():
    v = cross_check(
        task=_ok_task(),
        declared_risk=Risk.MEDIUM,
        leaf_result={"status": "ok"},  # missing invoice_id
        required_keys=("status", "invoice_id"),
    )
    assert v.ok is False
    assert v.validation == "schema_fail"
    assert any("invoice_id" in r for r in v.reasons)


def test_fails_when_type_mismatched():
    v = cross_check(
        task=_ok_task(),
        declared_risk=Risk.MEDIUM,
        leaf_result={"status": "ok", "invoice_id": 12345},  # int, not str
        required_keys=("status",),
        optional_types={"invoice_id": str},
    )
    assert v.validation == "schema_fail"


def test_policy_fail_when_leaf_executed_higher_risk():
    v = cross_check(
        task=_ok_task(),
        declared_risk=Risk.MEDIUM,
        leaf_result={"status": "ok"},
        result_tags=("executed-higher-risk",),
    )
    assert v.validation == "policy_fail"


def test_policy_fail_when_irreversible_but_not_high():
    v = cross_check(
        task=_ok_task(),
        declared_risk=Risk.LOW,
        leaf_result={"status": "ok"},
        result_tags=("irreversible",),
    )
    assert v.validation == "policy_fail"


def test_judge_disagree_when_jury_differs_on_substantive_field():
    leaf = {"status": "ok", "amount": 1000, "invoice_id": "INV-X"}
    jury = {"status": "ok", "amount": 1500, "invoice_id": "INV-Y"}
    v = cross_check(
        task=_ok_task(),
        declared_risk=Risk.HIGH,
        leaf_result=leaf,
        jury_result=jury,
    )
    assert v.validation == "judge_disagree"
    # invoice_id is in the auto-ignore list, so the diff must NOT include it.
    assert "invoice_id" not in v.diff
    assert v.diff["amount"] == (1000, 1500)


def test_judge_passes_when_jury_matches_substantively():
    leaf = {"status": "ok", "amount": 1000, "invoice_id": "INV-X"}
    jury = {"status": "ok", "amount": 1000, "invoice_id": "INV-Y"}  # uuid differs only
    v = cross_check(
        task=_ok_task(),
        declared_risk=Risk.HIGH,
        leaf_result=leaf,
        jury_result=jury,
    )
    assert v.ok is True


def test_non_mapping_result_is_a_schema_fail():
    v = cross_check(
        task=_ok_task(),
        declared_risk=Risk.MEDIUM,
        leaf_result="this is a string, not a dict",  # type: ignore[arg-type]
    )
    assert v.validation == "schema_fail"
