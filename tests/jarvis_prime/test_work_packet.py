"""Baseline tests for the JARVIS Prime WorkPacket model.

Wave 0 scope. Verifies construction, serialization, validation, risk class
handling, confidence clamping, and that owner-gated actions are retained as
data only.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from hermes_cli.jarvis_prime import (
    RISK_CLASSES,
    WorkPacket,
    WorkPacketValidationFinding,
)


def _complete_packet(**overrides):
    base = dict(
        mission="Lock the Wave 0 foundation",
        repo_root="/home/user/hermes-agent",
        branch="claude/jarvis-foundation-lock-i7Uag",
        risk_class="RC1",
        allowed_files=["hermes_cli/jarvis_prime/"],
        protected_files=["main.py"],
        non_goals=["No CLI expansion"],
        acceptance_criteria=["WorkPacket model exists", "Baseline tests pass"],
        files_changed=["hermes_cli/jarvis_prime/work_packet.py"],
        tests_run=["pytest tests/jarvis_prime -q"],
        tests_failed=[],
        verification_summary="All baseline tests pass locally.",
        rollback_plan="Revert the Wave 0 commit on the feature branch.",
        owner_gated_actions=["merge to main"],
        owner_authorization_phrase="",
        citations=["CANONICAL_REPO.md"],
        confidence=0.8,
    )
    base.update(overrides)
    return WorkPacket(**base)


def test_workpacket_creation_defaults():
    packet = WorkPacket()
    assert packet.mission == ""
    assert packet.repo_root == ""
    assert packet.branch == ""
    assert packet.risk_class == ""
    assert packet.allowed_files == []
    assert packet.protected_files == []
    assert packet.non_goals == []
    assert packet.acceptance_criteria == []
    assert packet.files_changed == []
    assert packet.tests_run == []
    assert packet.tests_failed == []
    assert packet.verification_summary == ""
    assert packet.rollback_plan == ""
    assert packet.owner_gated_actions == []
    assert packet.owner_authorization_phrase == ""
    assert packet.citations == []
    assert packet.confidence == 0.0
    assert isinstance(packet.created_at, datetime)
    assert packet.created_at.tzinfo is not None


def test_workpacket_creation_with_values():
    packet = _complete_packet()
    assert packet.mission == "Lock the Wave 0 foundation"
    assert packet.risk_class == "RC1"
    assert "WorkPacket model exists" in packet.acceptance_criteria
    assert packet.confidence == 0.8


def test_workpacket_default_list_fields_are_independent():
    a = WorkPacket()
    b = WorkPacket()
    a.allowed_files.append("only_a")
    assert b.allowed_files == []


def test_to_dict_roundtrip_serializable():
    packet = _complete_packet()
    data = packet.to_dict()
    assert isinstance(data, dict)
    assert data["mission"] == "Lock the Wave 0 foundation"
    assert data["risk_class"] == "RC1"
    assert isinstance(data["created_at"], str)
    assert data["created_at"].endswith("+00:00") or data["created_at"].endswith(
        "Z"
    )


def test_to_dict_does_not_share_list_state():
    packet = _complete_packet()
    data = packet.to_dict()
    data["allowed_files"].append("mutation")
    assert "mutation" not in packet.allowed_files


def test_from_dict_recovers_packet():
    original = _complete_packet()
    data = original.to_dict()
    rebuilt = WorkPacket.from_dict(data)
    assert rebuilt.mission == original.mission
    assert rebuilt.repo_root == original.repo_root
    assert rebuilt.branch == original.branch
    assert rebuilt.risk_class == original.risk_class
    assert rebuilt.acceptance_criteria == original.acceptance_criteria
    assert rebuilt.confidence == original.confidence
    assert isinstance(rebuilt.created_at, datetime)
    assert rebuilt.created_at.tzinfo is not None


def test_from_dict_ignores_unknown_keys():
    rebuilt = WorkPacket.from_dict(
        {"mission": "x", "unexpected": "drop me"}
    )
    assert rebuilt.mission == "x"
    assert not hasattr(rebuilt, "unexpected")


def test_from_dict_handles_iso_string_created_at():
    rebuilt = WorkPacket.from_dict(
        {"mission": "x", "created_at": "2026-05-25T12:00:00+00:00"}
    )
    assert rebuilt.created_at == datetime(
        2026, 5, 25, 12, 0, 0, tzinfo=timezone.utc
    )


def test_from_dict_handles_z_suffix_created_at():
    rebuilt = WorkPacket.from_dict(
        {"mission": "x", "created_at": "2026-05-25T12:00:00Z"}
    )
    assert rebuilt.created_at.tzinfo is not None
    assert rebuilt.created_at == datetime(
        2026, 5, 25, 12, 0, 0, tzinfo=timezone.utc
    )


def test_from_dict_assigns_utc_when_naive_string():
    rebuilt = WorkPacket.from_dict(
        {"mission": "x", "created_at": "2026-05-25T12:00:00"}
    )
    assert rebuilt.created_at.tzinfo is not None


def test_from_dict_rejects_non_dict():
    with pytest.raises(TypeError):
        WorkPacket.from_dict("not a dict")  # type: ignore[arg-type]


def test_validate_complete_packet_returns_no_findings():
    packet = _complete_packet()
    findings = packet.validate()
    assert findings == []


def test_validate_reports_each_missing_required_field():
    packet = WorkPacket()
    findings = packet.validate()
    missing_fields = {f.field for f in findings if f.code == "missing_required_field"}
    assert {
        "mission",
        "repo_root",
        "branch",
        "risk_class",
        "acceptance_criteria",
        "rollback_plan",
    }.issubset(missing_fields)
    for finding in findings:
        assert isinstance(finding, WorkPacketValidationFinding)
        assert finding.severity in {"error", "warning"}


def test_validate_treats_whitespace_strings_as_missing():
    packet = _complete_packet(mission="   ", rollback_plan="\t")
    findings = packet.validate()
    codes = {(f.field, f.code) for f in findings}
    assert ("mission", "missing_required_field") in codes
    assert ("rollback_plan", "missing_required_field") in codes


def test_validate_rejects_unknown_risk_class():
    packet = _complete_packet(risk_class="RC9")
    findings = packet.validate()
    assert any(f.code == "invalid_risk_class" for f in findings)


def test_validate_accepts_every_supported_risk_class():
    for rc in RISK_CLASSES:
        packet = _complete_packet(risk_class=rc)
        findings = packet.validate()
        assert not any(f.code == "invalid_risk_class" for f in findings)


@pytest.mark.parametrize("bad", [-0.01, 1.01, 5.0, -3.0])
def test_validate_reports_confidence_out_of_range(bad):
    packet = _complete_packet(confidence=bad)
    findings = packet.validate()
    assert any(f.code == "confidence_out_of_range" for f in findings)


@pytest.mark.parametrize("good", [0.0, 0.5, 1.0])
def test_validate_accepts_in_range_confidence(good):
    packet = _complete_packet(confidence=good)
    findings = packet.validate()
    assert not any(
        f.code in {"confidence_out_of_range", "invalid_confidence_type"}
        for f in findings
    )


def test_validate_reports_non_numeric_confidence():
    packet = _complete_packet(confidence="high")  # type: ignore[arg-type]
    findings = packet.validate()
    assert any(f.code == "invalid_confidence_type" for f in findings)


def test_validate_reports_bool_confidence_as_invalid_type():
    packet = _complete_packet(confidence=True)  # type: ignore[arg-type]
    findings = packet.validate()
    assert any(f.code == "invalid_confidence_type" for f in findings)


def test_owner_gated_actions_preserved_as_data_only():
    packet = _complete_packet(
        owner_gated_actions=[
            "merge to main",
            "deploy preview",
            "publish package",
        ]
    )
    assert packet.owner_gated_actions == [
        "merge to main",
        "deploy preview",
        "publish package",
    ]
    assert packet.is_owner_authorized() is False
    findings = packet.validate()
    assert not any(
        f.code == "invalid_owner_gated_action" for f in findings
    )


def test_owner_gated_actions_with_empty_entry_is_invalid():
    packet = _complete_packet(owner_gated_actions=["merge to main", "   "])
    findings = packet.validate()
    assert any(f.code == "invalid_owner_gated_action" for f in findings)


def test_owner_authorization_phrase_exact_match_is_authorized():
    packet = _complete_packet(
        owner_gated_actions=["merge to main"],
        owner_authorization_phrase="Yes, with authorization.",
    )
    assert packet.is_owner_authorized() is True
    findings = packet.validate()
    assert not any(
        f.code == "invalid_authorization_phrase" for f in findings
    )


def test_owner_authorization_phrase_mismatch_is_warning():
    packet = _complete_packet(
        owner_gated_actions=["merge to main"],
        owner_authorization_phrase="yes, with authorization",
    )
    assert packet.is_owner_authorized() is False
    findings = packet.validate()
    assert any(
        f.code == "invalid_authorization_phrase" and f.severity == "warning"
        for f in findings
    )


def test_validation_finding_to_dict_shape():
    finding = WorkPacketValidationFinding(
        field="mission", code="missing_required_field", message="m"
    )
    data = finding.to_dict()
    assert data == {
        "field": "mission",
        "code": "missing_required_field",
        "message": "m",
        "severity": "error",
    }
