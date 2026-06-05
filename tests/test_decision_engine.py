"""Tests for the unified decision engine (Sprint 2).

Table-driven coverage of the auto/ask/refuse merge rules, every reason code,
the owner-phrase rule, and redacted serialization.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from hermes_cli.decision_engine import (
    DecisionInput,
    DecisionTier,
    ReasonCode,
    from_approval_decision,
    live_publish_input,
    merge_decision_inputs,
    owner_gate_input,
    policy_input,
    protected_path_input,
    remote_execution_input,
    secret_input,
    validation_input,
)


def _inp(tier: DecisionTier, reason: ReasonCode | None = None, source: str = "s") -> DecisionInput:
    return DecisionInput(source=source, tier=tier, reason=reason, detail="d")


# ---------------------------------------------------------------------------
# Tier merge rules
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "tiers,expected",
    [
        ([DecisionTier.AUTO], DecisionTier.AUTO),
        ([DecisionTier.AUTO, DecisionTier.AUTO], DecisionTier.AUTO),
        ([DecisionTier.AUTO, DecisionTier.ASK], DecisionTier.ASK),
        ([DecisionTier.ASK, DecisionTier.AUTO], DecisionTier.ASK),
        ([DecisionTier.AUTO, DecisionTier.REFUSE], DecisionTier.REFUSE),
        ([DecisionTier.ASK, DecisionTier.REFUSE], DecisionTier.REFUSE),
        ([DecisionTier.REFUSE, DecisionTier.ASK, DecisionTier.AUTO], DecisionTier.REFUSE),
    ],
)
def test_tier_coalescing(tiers, expected):
    inputs = [
        _inp(t, None if t is DecisionTier.AUTO else ReasonCode.POLICY_REFUSAL)
        for t in tiers
    ]
    verdict = merge_decision_inputs("act", inputs)
    assert verdict.tier is expected


def test_empty_inputs_fail_safe_to_ask():
    verdict = merge_decision_inputs("act", [])
    assert verdict.tier is DecisionTier.ASK


def test_missing_required_source_becomes_ask():
    # only "secrets" provided; "validation" required but missing
    verdict = merge_decision_inputs(
        "act",
        [secret_input([])],
        required_sources=["validation"],
    )
    assert verdict.tier is DecisionTier.ASK
    assert ReasonCode.UNKNOWN_RISK in verdict.reason_codes
    assert any(i.source == "validation" for i in verdict.inputs)


def test_all_auto_with_present_required_is_auto():
    verdict = merge_decision_inputs(
        "act",
        [secret_input([]), validation_input(True)],
        required_sources=["secrets", "validation"],
    )
    assert verdict.tier is DecisionTier.AUTO
    assert verdict.is_auto
    assert verdict.required_owner_phrase is None


# ---------------------------------------------------------------------------
# Per-collector rules (one per reason code)
# ---------------------------------------------------------------------------


def test_secret_finding_refuses():
    verdict = merge_decision_inputs("publish", [secret_input(["leaked AKIA..."])])
    assert verdict.is_refuse
    assert ReasonCode.SECRET_DETECTED in verdict.reason_codes


def test_protected_path_soft_is_ask_hard_is_refuse():
    soft = merge_decision_inputs("edit", [protected_path_input(["SECURITY.md"])])
    assert soft.tier is DecisionTier.ASK
    assert ReasonCode.PROTECTED_PATH in soft.reason_codes

    hard = merge_decision_inputs("edit", [protected_path_input(["id_rsa"], hard=True)])
    assert hard.tier is DecisionTier.REFUSE


def test_validation_failure_refuses_unless_override():
    blocked = merge_decision_inputs("merge", [validation_input(False)])
    assert blocked.is_refuse
    assert ReasonCode.VALIDATION_FAILED in blocked.reason_codes

    overridable = merge_decision_inputs("merge", [validation_input(False, override_allowed=True)])
    assert overridable.tier is DecisionTier.ASK


def test_remote_execution_never_auto():
    requested = merge_decision_inputs("bridge", [remote_execution_input(True)])
    assert requested.tier is DecisionTier.ASK
    assert ReasonCode.REMOTE_EXECUTION in requested.reason_codes
    assert requested.required_owner_phrase  # remote exec needs the phrase

    not_requested = merge_decision_inputs("bridge", [remote_execution_input(False)])
    assert not_requested.is_auto


def test_live_publish_allowlist_rules():
    refused = merge_decision_inputs(
        "github.publish_pr",
        [live_publish_input(repo_allowlisted=False, action_allowlisted=True)],
    )
    assert refused.is_refuse
    assert ReasonCode.LIVE_PUBLISH in refused.reason_codes

    asked = merge_decision_inputs(
        "github.publish_pr",
        [live_publish_input(repo_allowlisted=True, action_allowlisted=True)],
    )
    assert asked.tier is DecisionTier.ASK
    assert asked.required_owner_phrase  # live publish always needs the phrase


def test_owner_gate_requires_phrase():
    gated = merge_decision_inputs("spend_money", [owner_gate_input(True, action="spend_money")])
    assert gated.tier is DecisionTier.ASK
    assert ReasonCode.OWNER_REQUIRED in gated.reason_codes
    assert gated.required_owner_phrase == "Yes, with authorization."
    assert gated.needs_owner_phrase

    ungated = merge_decision_inputs("read", [owner_gate_input(False)])
    assert ungated.is_auto


def test_policy_refusal_passthrough():
    verdict = merge_decision_inputs("act", [policy_input(DecisionTier.REFUSE, "blocked by policy")])
    assert verdict.is_refuse
    assert ReasonCode.POLICY_REFUSAL in verdict.reason_codes


# ---------------------------------------------------------------------------
# Owner-phrase rule: a *soft* ask (no owner-gated reason) needs no phrase
# ---------------------------------------------------------------------------


def test_soft_ask_does_not_require_phrase():
    verdict = merge_decision_inputs("edit", [validation_input(False, override_allowed=True)])
    assert verdict.tier is DecisionTier.ASK
    assert verdict.required_owner_phrase is None  # VALIDATION_FAILED is not owner-gated


# ---------------------------------------------------------------------------
# Legacy adapter
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value,expected_tier",
    [("allow", DecisionTier.AUTO), ("confirm", DecisionTier.ASK), ("deny", DecisionTier.REFUSE)],
)
def test_from_approval_decision_maps_legacy_values(value, expected_tier):
    inp = from_approval_decision(value, "legacy reason")
    assert inp.tier is expected_tier


def test_from_approval_decision_accepts_enum_like():
    class _D:
        value = "confirm"

    inp = from_approval_decision(_D(), "x")
    assert inp.tier is DecisionTier.ASK


# ---------------------------------------------------------------------------
# Construction guards
# ---------------------------------------------------------------------------


def test_non_auto_input_requires_reason():
    with pytest.raises(ValueError):
        DecisionInput(source="s", tier=DecisionTier.REFUSE)


# ---------------------------------------------------------------------------
# Redacted serialization
# ---------------------------------------------------------------------------


def test_to_redacted_dict_redacts_secrets_in_detail():
    leaky = DecisionInput(
        source="logs",
        tier=DecisionTier.REFUSE,
        reason=ReasonCode.SECRET_DETECTED,
        detail="token ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 leaked",
    )
    verdict = merge_decision_inputs("publish", [leaky])
    payload = verdict.to_redacted_dict()

    serialized = str(payload)
    assert "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789" not in serialized
    # structure is intact
    assert payload["tier"] == "refuse"
    assert "secret_detected" in payload["reason_codes"]
    assert payload["inputs"][0]["source"] == "logs"


def test_to_redacted_dict_shape_and_phrase():
    verdict = merge_decision_inputs(
        "github.publish_pr",
        [live_publish_input(repo_allowlisted=True, action_allowlisted=True)],
        allowed_until=datetime(2030, 1, 1, tzinfo=timezone.utc),
        audit_id="audit_123",
    )
    payload = verdict.to_redacted_dict()
    assert set(payload) == {
        "id",
        "tier",
        "action_type",
        "rationale",
        "reason_codes",
        "inputs",
        "required_owner_phrase",
        "allowed_until",
        "audit_id",
    }
    assert payload["required_owner_phrase"] == "Yes, with authorization."
    assert payload["allowed_until"] == "2030-01-01T00:00:00+00:00"
    assert payload["audit_id"] == "audit_123"
    assert payload["id"].startswith("dv_")


def test_verdict_id_is_unique():
    a = merge_decision_inputs("act", [secret_input([])])
    b = merge_decision_inputs("act", [secret_input([])])
    assert a.id != b.id


# ---------------------------------------------------------------------------
# Contract fixture (Sprint 1): the engine output matches the committed shape
# ---------------------------------------------------------------------------


def test_serialized_verdict_matches_committed_fixture():
    fixture_path = (
        Path(__file__).parent / "fixtures" / "security" / "decision_verdict_ask.json"
    )
    fixture = json.loads(fixture_path.read_text())

    verdict = merge_decision_inputs(
        "github.publish_pr",
        [live_publish_input(repo_allowlisted=True, action_allowlisted=True)],
    )
    payload = verdict.to_redacted_dict()

    # Same contract keys, and the stable fields match (id is random by design).
    assert set(payload) == set(fixture)
    for stable in ("tier", "action_type", "reason_codes", "required_owner_phrase"):
        assert payload[stable] == fixture[stable]
    assert payload["inputs"][0]["reason"] == fixture["inputs"][0]["reason"]
