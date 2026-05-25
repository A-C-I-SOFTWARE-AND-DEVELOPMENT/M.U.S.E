"""Tests for hermes_cli.jarvis_prime.work_packet — Wave 0 baseline.

Covers the canonical WorkPacket model used as the standard JARVIS
Prime handoff envelope:

- construction defaults
- to_dict() / from_dict() round-trip
- validate() passes for a complete packet
- validate() reports missing required fields
- invalid risk_class is reported
- out-of-range confidence is handled safely (warning + clamp helper)
- owner_gated_actions are retained as data and never executed
- public package import + WorkPacket export
"""

from __future__ import annotations

import importlib
from datetime import datetime, timezone

import pytest

from hermes_cli.jarvis_prime.work_packet import (
    REQUIRED_FIELDS,
    VALID_RISK_CLASSES,
    FindingSeverity,
    WorkPacket,
    WorkPacketValidationFinding,
)


def _complete_packet(**overrides) -> WorkPacket:
    base = dict(
        mission="Lock the JARVIS Prime foundation for Wave 0.",
        repo_root="/home/user/hermes-agent",
        branch="feature/jarvis-foundation-lock",
        risk_class="RC1",
        allowed_files=["hermes_cli/jarvis_prime/work_packet.py"],
        protected_files=["main"],
        non_goals=["No CLI expansion in Wave 0."],
        acceptance_criteria=[
            "WorkPacket dataclass exists",
            "Baseline tests pass",
        ],
        files_changed=["hermes_cli/jarvis_prime/work_packet.py"],
        tests_run=["pytest tests/test_jarvis_prime_work_packet.py"],
        tests_failed=[],
        verification_summary="All Wave 0 tests pass locally.",
        rollback_plan="git revert the foundation-lock commit.",
        owner_gated_actions=[],
        owner_authorization_phrase=None,
        citations=["docs/jarvis-prime-operating-system.md"],
        confidence=0.85,
    )
    base.update(overrides)
    return WorkPacket(**base)


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


def test_workpacket_default_construction_is_safe() -> None:
    packet = WorkPacket()
    assert packet.mission == ""
    assert packet.risk_class == ""
    assert packet.allowed_files == []
    assert packet.owner_gated_actions == []
    assert packet.confidence == 0.0
    assert isinstance(packet.created_at, datetime)
    assert packet.created_at.tzinfo is not None
    assert packet.created_at.utcoffset() == timezone.utc.utcoffset(packet.created_at)


def test_workpacket_collection_fields_are_independent_instances() -> None:
    a = WorkPacket()
    b = WorkPacket()
    a.allowed_files.append("x")
    assert b.allowed_files == [], "default_factory must not share mutable state"


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


def test_to_dict_emits_iso_created_at() -> None:
    packet = _complete_packet()
    data = packet.to_dict()
    assert isinstance(data["created_at"], str)
    parsed = datetime.fromisoformat(data["created_at"])
    assert parsed.tzinfo is not None


def test_to_dict_round_trips_via_from_dict() -> None:
    packet = _complete_packet()
    restored = WorkPacket.from_dict(packet.to_dict())
    assert restored.mission == packet.mission
    assert restored.repo_root == packet.repo_root
    assert restored.branch == packet.branch
    assert restored.risk_class == packet.risk_class
    assert restored.acceptance_criteria == packet.acceptance_criteria
    assert restored.rollback_plan == packet.rollback_plan
    assert restored.confidence == pytest.approx(packet.confidence)
    assert restored.created_at == packet.created_at


def test_from_dict_ignores_unknown_keys() -> None:
    data = _complete_packet().to_dict()
    data["totally_invented_future_field"] = ["ignore me"]
    restored = WorkPacket.from_dict(data)
    assert restored.mission == "Lock the JARVIS Prime foundation for Wave 0."


def test_from_dict_recovers_from_bad_created_at() -> None:
    data = _complete_packet().to_dict()
    data["created_at"] = "not-a-real-timestamp"
    restored = WorkPacket.from_dict(data)
    assert isinstance(restored.created_at, datetime)
    assert restored.created_at.tzinfo is not None


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_validate_passes_for_complete_packet() -> None:
    packet = _complete_packet()
    findings = packet.validate()
    assert findings == []
    assert packet.is_valid() is True


def test_validate_reports_missing_required_fields() -> None:
    packet = WorkPacket()
    missing = {f.field for f in packet.validate() if f.severity is FindingSeverity.ERROR}
    for required in REQUIRED_FIELDS:
        assert required in missing, f"expected {required!r} to be reported missing"
    assert packet.is_valid() is False


def test_validate_reports_blank_string_required_field() -> None:
    packet = _complete_packet(mission="   ")
    fields = {f.field for f in packet.validate() if f.severity is FindingSeverity.ERROR}
    assert "mission" in fields


def test_validate_reports_empty_collection_required_field() -> None:
    packet = _complete_packet(acceptance_criteria=[])
    fields = {f.field for f in packet.validate() if f.severity is FindingSeverity.ERROR}
    assert "acceptance_criteria" in fields


def test_validate_reports_invalid_risk_class() -> None:
    packet = _complete_packet(risk_class="RC9")
    findings = packet.validate()
    risk_findings = [f for f in findings if f.field == "risk_class"]
    assert risk_findings, "invalid risk_class should produce a finding"
    assert risk_findings[0].severity is FindingSeverity.ERROR


@pytest.mark.parametrize("risk_class", sorted(VALID_RISK_CLASSES))
def test_validate_accepts_each_spec_risk_class(risk_class: str) -> None:
    packet = _complete_packet(risk_class=risk_class)
    fields = {f.field for f in packet.validate()}
    assert "risk_class" not in fields


# ---------------------------------------------------------------------------
# Confidence handling
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("value", [-0.5, 1.5, 99.0])
def test_validate_warns_on_out_of_range_confidence(value: float) -> None:
    packet = _complete_packet(confidence=value)
    warnings = [
        f for f in packet.validate()
        if f.field == "confidence" and f.severity is FindingSeverity.WARNING
    ]
    assert warnings, f"confidence={value} should produce a warning"
    # Warning-only — packet is still structurally valid.
    assert packet.is_valid() is True


@pytest.mark.parametrize(
    "value,expected",
    [(-1.0, 0.0), (0.0, 0.0), (0.5, 0.5), (1.0, 1.0), (2.0, 1.0)],
)
def test_clamped_confidence_clamps_to_unit_interval(value: float, expected: float) -> None:
    packet = _complete_packet(confidence=value)
    assert packet.clamped_confidence() == pytest.approx(expected)


def test_clamped_confidence_handles_non_numeric() -> None:
    packet = _complete_packet()
    # Bypass type system to confirm runtime safety — packets may be
    # rehydrated from imperfect external sources.
    packet.confidence = "oops"  # type: ignore[assignment]
    assert packet.clamped_confidence() == 0.0


def test_validate_reports_non_numeric_confidence_as_error() -> None:
    packet = _complete_packet()
    packet.confidence = "oops"  # type: ignore[assignment]
    errors = [
        f for f in packet.validate()
        if f.field == "confidence" and f.severity is FindingSeverity.ERROR
    ]
    assert errors


# ---------------------------------------------------------------------------
# Owner-gated actions are data only
# ---------------------------------------------------------------------------


def test_owner_gated_actions_retained_as_data_not_executed() -> None:
    actions = ["production_deploy", "main_branch_merge", "package_publish"]
    packet = _complete_packet(owner_gated_actions=list(actions))
    assert packet.owner_gated_actions == actions
    # Validation must not raise and must not "consume" or mutate the
    # owner-gated list — they are descriptive, not callable.
    packet.validate()
    assert packet.owner_gated_actions == actions
    # Serialization preserves them verbatim.
    assert packet.to_dict()["owner_gated_actions"] == actions
    # Restored packet still has them as plain strings, never invoked.
    restored = WorkPacket.from_dict(packet.to_dict())
    assert restored.owner_gated_actions == actions
    assert restored.owner_authorization_phrase is None


# ---------------------------------------------------------------------------
# Findings shape
# ---------------------------------------------------------------------------


def test_finding_to_dict_shape() -> None:
    finding = WorkPacketValidationFinding(
        field="mission",
        severity=FindingSeverity.ERROR,
        message="mission is required",
    )
    assert finding.to_dict() == {
        "field": "mission",
        "severity": "error",
        "message": "mission is required",
    }


# ---------------------------------------------------------------------------
# Package export
# ---------------------------------------------------------------------------


def test_package_exports_work_packet() -> None:
    pkg = importlib.import_module("hermes_cli.jarvis_prime")
    assert hasattr(pkg, "WorkPacket")
    assert pkg.WorkPacket is WorkPacket
    assert hasattr(pkg, "WorkPacketValidationFinding")
    assert hasattr(pkg, "FindingSeverity")
    assert hasattr(pkg, "VALID_RISK_CLASSES")
    assert "WorkPacket" in pkg.__all__
    assert "WorkPacketValidationFinding" in pkg.__all__
