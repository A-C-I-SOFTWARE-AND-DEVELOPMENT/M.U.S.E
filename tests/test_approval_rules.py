"""Tests for approval decision race rules (Sprint 9).

One case per rule, plus precedence checks, against the pure
``resolve_decision`` kernel.
"""

from __future__ import annotations

from muse_cli.approval_rules import (
    ApprovalDecision,
    ApprovalRecord,
    ApprovalState,
    DecisionResult,
    resolve_decision,
)

PHRASE = "Yes, with authorization."
NOW = 1000.0


def _pending(**kw) -> ApprovalRecord:
    return ApprovalRecord(approval_id="appr_1", state=ApprovalState.PENDING, **kw)


def test_grant_pending():
    d = resolve_decision(_pending(), approve=True, now=NOW)
    assert d.result is DecisionResult.GRANTED
    assert d.state is ApprovalState.GRANTED
    assert d.accepted
    assert d.audit is False


def test_reject_pending():
    d = resolve_decision(_pending(), approve=False, now=NOW)
    assert d.result is DecisionResult.REJECTED
    assert d.state is ApprovalState.REJECTED
    assert d.accepted


def test_duplicate_on_granted_is_idempotent():
    rec = ApprovalRecord("appr_1", state=ApprovalState.GRANTED, decided_at=NOW - 1)
    d = resolve_decision(rec, approve=True, now=NOW)
    assert d.result is DecisionResult.ALREADY_DECIDED
    assert d.state is ApprovalState.GRANTED
    assert d.accepted is False


def test_duplicate_on_rejected_is_idempotent():
    rec = ApprovalRecord("appr_1", state=ApprovalState.REJECTED, decided_at=NOW - 1)
    d = resolve_decision(rec, approve=True, now=NOW)
    assert d.result is DecisionResult.ALREADY_DECIDED
    assert d.state is ApprovalState.REJECTED


def test_decided_at_set_blocks_redecision_even_if_pending():
    # defensive: decided_at present but state still pending -> treat as decided
    rec = _pending(decided_at=NOW - 5)
    d = resolve_decision(rec, approve=True, now=NOW)
    assert d.result is DecisionResult.ALREADY_DECIDED


def test_superseded_by_state():
    rec = ApprovalRecord("appr_1", state=ApprovalState.SUPERSEDED)
    d = resolve_decision(rec, approve=True, now=NOW)
    assert d.result is DecisionResult.SUPERSEDED
    assert d.state is ApprovalState.SUPERSEDED
    assert not d.accepted


def test_superseded_by_pointer():
    rec = _pending(superseded_by="appr_2")
    d = resolve_decision(rec, approve=True, now=NOW)
    assert d.result is DecisionResult.SUPERSEDED


def test_expired_by_state():
    rec = ApprovalRecord("appr_1", state=ApprovalState.EXPIRED)
    d = resolve_decision(rec, approve=True, now=NOW)
    assert d.result is DecisionResult.EXPIRED


def test_expired_by_timestamp():
    rec = _pending(expires_at=NOW - 1)
    d = resolve_decision(rec, approve=True, now=NOW)
    assert d.result is DecisionResult.EXPIRED
    assert d.state is ApprovalState.EXPIRED


def test_not_yet_expired_allows_grant():
    rec = _pending(expires_at=NOW + 100)
    d = resolve_decision(rec, approve=True, now=NOW)
    assert d.result is DecisionResult.GRANTED


def test_phrase_required_correct_grants():
    rec = _pending(required_phrase=PHRASE)
    d = resolve_decision(rec, approve=True, now=NOW, phrase=PHRASE)
    assert d.result is DecisionResult.GRANTED


def test_phrase_required_wrong_is_mismatch_and_audited():
    rec = _pending(required_phrase=PHRASE)
    d = resolve_decision(rec, approve=True, now=NOW, phrase="yes")
    assert d.result is DecisionResult.PHRASE_MISMATCH
    assert d.audit is True
    assert d.state is ApprovalState.PENDING  # stays pending, not consumed
    assert not d.accepted


def test_phrase_not_needed_to_reject():
    rec = _pending(required_phrase=PHRASE)
    d = resolve_decision(rec, approve=False, now=NOW, phrase=None)
    assert d.result is DecisionResult.REJECTED


def test_revoked_device_blocked_and_audited():
    d = resolve_decision(_pending(), approve=True, now=NOW, device_revoked=True)
    assert d.result is DecisionResult.REVOKED
    assert d.audit is True
    assert not d.accepted


def test_revocation_precedence_over_already_decided():
    rec = ApprovalRecord("appr_1", state=ApprovalState.GRANTED, decided_at=NOW - 1)
    d = resolve_decision(rec, approve=True, now=NOW, device_revoked=True)
    assert d.result is DecisionResult.REVOKED


def test_terminal_precedence_over_expiry():
    # a granted approval that is now past its expiry is still granted, not expired
    rec = ApprovalRecord("appr_1", state=ApprovalState.GRANTED, decided_at=NOW - 50, expires_at=NOW - 1)
    d = resolve_decision(rec, approve=True, now=NOW)
    assert d.result is DecisionResult.ALREADY_DECIDED
    assert d.state is ApprovalState.GRANTED


def test_decision_is_frozen_value():
    d = resolve_decision(_pending(), approve=True, now=NOW)
    assert isinstance(d, ApprovalDecision)
