"""Tests for hermes_cli.jarvis_prime.work_packet (Wave 0 foundation).

Covers WorkPacket creation, serialization, validation, confidence clamping,
risk-class checks, owner-gated-action preservation, and the package
re-export wired up by Wave 0.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from hermes_cli.jarvis_prime.work_packet import (
    FindingSeverity,
    VALID_RISK_CLASSES,
    WorkPacket,
    WorkPacketValidationFinding,
)


def _complete_packet(**overrides) -> WorkPacket:
    defaults = dict(
        mission="lock the JARVIS Prime foundation",
        repo_root="/repo",
        branch="feature/jarvis-foundation-lock",
        risk_class="RC1",
        acceptance_criteria=["WorkPacket model exists", "tests pass"],
        rollback_plan="revert the foundation-lock commit",
    )
    defaults.update(overrides)
    return WorkPacket(**defaults)


# --- creation --------------------------------------------------------------


def test_default_packet_has_utc_aware_timestamp() -> None:
    packet = WorkPacket()
    assert isinstance(packet.created_at, datetime)
    assert packet.created_at.tzinfo is not None
    assert packet.created_at.utcoffset() == timezone.utc.utcoffset(None)


def test_default_packet_lists_are_independent_per_instance() -> None:
    a = WorkPacket()
    b = WorkPacket()
    a.allowed_files.append("x.py")
    assert b.allowed_files == []


def test_complete_packet_constructs_without_error() -> None:
    packet = _complete_packet()
    assert packet.mission == "lock the JARVIS Prime foundation"
    assert packet.risk_class == "RC1"
    assert packet.acceptance_criteria == [
        "WorkPacket model exists",
        "tests pass",
    ]


# --- to_dict / from_dict ---------------------------------------------------


def test_to_dict_serializes_datetime_to_iso_string() -> None:
    packet = _complete_packet()
    data = packet.to_dict()
    assert isinstance(data["created_at"], str)
    # Round-trip the timestamp
    parsed = datetime.fromisoformat(data["created_at"])
    assert parsed.tzinfo is not None


def test_to_dict_contains_all_canonical_fields() -> None:
    packet = _complete_packet()
    data = packet.to_dict()
    for required in (
        "mission",
        "repo_root",
        "branch",
        "risk_class",
        "allowed_files",
        "protected_files",
        "non_goals",
        "acceptance_criteria",
        "files_changed",
        "tests_run",
        "tests_failed",
        "verification_summary",
        "rollback_plan",
        "owner_gated_actions",
        "owner_authorization_phrase",
        "citations",
        "confidence",
        "created_at",
    ):
        assert required in data, f"missing field in to_dict: {required}"


def test_from_dict_round_trips_packet() -> None:
    original = _complete_packet(
        owner_gated_actions=["main_branch_merge"],
        citations=["docs/jarvis-prime-operating-system.md"],
        confidence=0.8,
    )
    data = original.to_dict()
    restored = WorkPacket.from_dict(data)

    assert restored.mission == original.mission
    assert restored.repo_root == original.repo_root
    assert restored.branch == original.branch
    assert restored.risk_class == original.risk_class
    assert restored.acceptance_criteria == original.acceptance_criteria
    assert restored.rollback_plan == original.rollback_plan
    assert restored.owner_gated_actions == ["main_branch_merge"]
    assert restored.citations == ["docs/jarvis-prime-operating-system.md"]
    assert restored.confidence == pytest.approx(0.8)
    assert restored.created_at == original.created_at


def test_from_dict_ignores_unknown_keys() -> None:
    data = {
        "mission": "x",
        "repo_root": "/r",
        "branch": "b",
        "risk_class": "RC0",
        "acceptance_criteria": ["a"],
        "rollback_plan": "revert",
        "garbage_field": "ignored",
    }
    packet = WorkPacket.from_dict(data)
    assert packet.mission == "x"
    assert not hasattr(packet, "garbage_field")


def test_from_dict_falls_back_to_default_on_unparseable_created_at() -> None:
    packet = WorkPacket.from_dict({"created_at": "not-a-date"})
    assert isinstance(packet.created_at, datetime)
    assert packet.created_at.tzinfo is not None


# --- validate --------------------------------------------------------------


def test_validate_returns_no_errors_for_complete_packet() -> None:
    packet = _complete_packet(confidence=0.7)
    findings = packet.validate()
    errors = [f for f in findings if f.severity == FindingSeverity.ERROR]
    assert errors == [], f"unexpected errors: {errors}"
    assert packet.is_valid()


def test_validate_reports_each_missing_required_field() -> None:
    packet = WorkPacket()
    finding_fields = {f.field_name for f in packet.validate()
                      if f.severity == FindingSeverity.ERROR}
    for required in (
        "mission",
        "repo_root",
        "branch",
        "risk_class",
        "acceptance_criteria",
        "rollback_plan",
    ):
        assert required in finding_fields, (
            f"validate did not flag missing required field: {required}"
        )


def test_missing_required_fields_helper_lists_them() -> None:
    packet = WorkPacket()
    missing = packet.missing_required_fields()
    assert set(missing) == {
        "mission",
        "repo_root",
        "branch",
        "risk_class",
        "acceptance_criteria",
        "rollback_plan",
    }


def test_validate_flags_invalid_risk_class() -> None:
    packet = _complete_packet(risk_class="RC9")
    errors = [
        f for f in packet.validate()
        if f.severity == FindingSeverity.ERROR and f.field_name == "risk_class"
    ]
    assert errors, "validate did not flag invalid risk_class RC9"
    assert not packet.is_valid()


def test_validate_accepts_each_canonical_risk_class() -> None:
    for rc in VALID_RISK_CLASSES:
        packet = _complete_packet(risk_class=rc, confidence=0.5)
        assert packet.is_valid(), f"{rc} should validate"


# --- confidence clamping ---------------------------------------------------


def test_confidence_below_zero_clamps_to_zero() -> None:
    packet = _complete_packet(confidence=-0.5)
    assert packet.confidence == 0.0


def test_confidence_above_one_clamps_to_one() -> None:
    packet = _complete_packet(confidence=1.7)
    assert packet.confidence == 1.0


def test_confidence_inside_range_is_preserved() -> None:
    packet = _complete_packet(confidence=0.42)
    assert packet.confidence == pytest.approx(0.42)


def test_clamped_zero_confidence_surfaces_warning_not_error() -> None:
    packet = _complete_packet(confidence=-1.0)
    confidence_findings = [
        f for f in packet.validate() if f.field_name == "confidence"
    ]
    assert confidence_findings, "expected a confidence finding"
    assert all(
        f.severity == FindingSeverity.WARNING for f in confidence_findings
    )
    assert packet.is_valid()  # warning, not error


def test_non_numeric_confidence_is_error() -> None:
    packet = _complete_packet()
    packet.confidence = "high"  # type: ignore[assignment]
    errors = [
        f for f in packet.validate()
        if f.field_name == "confidence" and f.severity == FindingSeverity.ERROR
    ]
    assert errors


# --- owner-gated actions are data, never executed --------------------------


def test_owner_gated_actions_are_preserved_as_data() -> None:
    packet = _complete_packet(
        owner_gated_actions=[
            "main_branch_merge",
            "production_deploy",
            "package_publish",
        ],
        owner_authorization_phrase=None,
    )
    assert packet.owner_gated_actions == [
        "main_branch_merge",
        "production_deploy",
        "package_publish",
    ]
    assert packet.owner_authorization_phrase is None
    # Round-trip preserves them — no side effects on serialize.
    restored = WorkPacket.from_dict(packet.to_dict())
    assert restored.owner_gated_actions == packet.owner_gated_actions


def test_owner_authorization_phrase_can_be_recorded_without_executing() -> None:
    packet = _complete_packet(
        owner_gated_actions=["main_branch_merge"],
        owner_authorization_phrase="Yes, with authorization.",
    )
    assert packet.owner_authorization_phrase == "Yes, with authorization."
    assert packet.owner_gated_actions == ["main_branch_merge"]
    # WorkPacket is data-only; nothing in this module should execute,
    # mutate, or remove the gated actions just because the phrase is set.
    assert packet.is_valid()


def test_invalid_authorization_phrase_type_is_error() -> None:
    packet = _complete_packet()
    packet.owner_authorization_phrase = 42  # type: ignore[assignment]
    errors = [
        f for f in packet.validate()
        if f.field_name == "owner_authorization_phrase"
        and f.severity == FindingSeverity.ERROR
    ]
    assert errors


# --- finding shape ---------------------------------------------------------


def test_validation_finding_serializes_to_dict() -> None:
    finding = WorkPacketValidationFinding(
        field_name="mission",
        severity=FindingSeverity.ERROR,
        message="mission is required",
    )
    assert finding.to_dict() == {
        "field": "mission",
        "severity": "error",
        "message": "mission is required",
    }


# --- package export wiring (Wave 0 task 4) ---------------------------------


def test_package_exports_work_packet_symbols() -> None:
    import hermes_cli.jarvis_prime as jp

    assert jp.WorkPacket is WorkPacket
    assert jp.WorkPacketValidationFinding is WorkPacketValidationFinding
    assert "WorkPacket" in jp.__all__
    assert "WorkPacketValidationFinding" in jp.__all__


def test_package_import_does_not_break_existing_exports() -> None:
    # Sanity check that adding WorkPacket didn't shadow or remove
    # earlier exports the runtime depends on.
    import hermes_cli.jarvis_prime as jp

    for symbol in (
        "Mode",
        "Router",
        "RouteTarget",
        "OwnerAuth",
        "AUTHORIZATION_PHRASE",
        "run_gate_summary",
    ):
        assert hasattr(jp, symbol), f"existing export {symbol} disappeared"
