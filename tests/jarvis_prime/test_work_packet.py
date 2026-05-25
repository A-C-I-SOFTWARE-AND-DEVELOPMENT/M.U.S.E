"""Baseline tests for the JARVIS Prime WorkPacket model (Wave 0)."""

from __future__ import annotations

import datetime as _dt

import pytest


def _complete_packet_kwargs() -> dict:
    return {
        "mission": "Lock the JARVIS Prime foundation",
        "repo_root": "/home/user/hermes-agent",
        "branch": "claude/jarvis-foundation-lock-g9i9x",
        "risk_class": "RC1",
        "allowed_files": ["hermes_cli/jarvis_prime/work_packet.py"],
        "protected_files": ["main"],
        "non_goals": ["semantic immune layer"],
        "acceptance_criteria": ["WorkPacket importable", "validate returns []"],
        "files_changed": [],
        "tests_run": [],
        "tests_failed": [],
        "verification_summary": "pending",
        "rollback_plan": "git checkout main -- hermes_cli/jarvis_prime",
        "owner_gated_actions": ["deploy", "merge to main"],
        "citations": ["docs/jarvis-prime-wave-plan.md"],
        "confidence": 0.6,
    }


def test_package_imports_workpacket():
    from hermes_cli.jarvis_prime import WorkPacket, WorkPacketValidationFinding

    assert WorkPacket is not None
    assert WorkPacketValidationFinding is not None


def test_workpacket_construction_defaults():
    from hermes_cli.jarvis_prime import WorkPacket

    packet = WorkPacket()
    assert packet.mission == ""
    assert packet.allowed_files == []
    assert packet.confidence == 0.0
    assert isinstance(packet.created_at, str)
    parsed = _dt.datetime.fromisoformat(packet.created_at)
    assert parsed.tzinfo is not None, "created_at must be timezone-aware"


def test_to_dict_round_trip_with_from_dict():
    from hermes_cli.jarvis_prime import WorkPacket

    packet = WorkPacket(**_complete_packet_kwargs())
    snapshot = packet.to_dict()

    assert snapshot["mission"] == "Lock the JARVIS Prime foundation"
    assert snapshot["risk_class"] == "RC1"
    assert snapshot["owner_gated_actions"] == ["deploy", "merge to main"]

    rebuilt = WorkPacket.from_dict(snapshot)
    assert rebuilt.to_dict() == snapshot


def test_from_dict_ignores_unknown_keys():
    from hermes_cli.jarvis_prime import WorkPacket

    data = _complete_packet_kwargs()
    data["unexpected"] = "ignored"
    packet = WorkPacket.from_dict(data)
    assert packet.mission == data["mission"]


def test_from_dict_rejects_non_dict():
    from hermes_cli.jarvis_prime import WorkPacket

    with pytest.raises(TypeError):
        WorkPacket.from_dict(["not", "a", "dict"])  # type: ignore[arg-type]


def test_validate_passes_for_complete_packet():
    from hermes_cli.jarvis_prime import WorkPacket

    packet = WorkPacket(**_complete_packet_kwargs())
    assert packet.validate() == []
    assert packet.is_valid() is True


def test_validate_reports_each_missing_required_field():
    from hermes_cli.jarvis_prime import WorkPacket

    packet = WorkPacket()  # all defaults / empty
    findings = packet.validate()
    reported = {f.field for f in findings}
    for required in ("mission", "repo_root", "branch", "risk_class", "acceptance_criteria", "rollback_plan"):
        assert required in reported, f"expected validation finding for {required}"


def test_invalid_risk_class_is_reported():
    from hermes_cli.jarvis_prime import WorkPacket

    kwargs = _complete_packet_kwargs()
    kwargs["risk_class"] = "RC9"
    packet = WorkPacket(**kwargs)
    findings = packet.validate()
    risk_findings = [f for f in findings if f.field == "risk_class"]
    assert risk_findings, "invalid risk_class must produce a finding"
    assert risk_findings[0].code == "invalid_value"


@pytest.mark.parametrize("rc", ["RC0", "RC1", "RC2", "RC3", "RC4"])
def test_all_valid_risk_classes_accepted(rc):
    from hermes_cli.jarvis_prime import WorkPacket

    kwargs = _complete_packet_kwargs()
    kwargs["risk_class"] = rc
    packet = WorkPacket(**kwargs)
    assert all(f.field != "risk_class" for f in packet.validate())


@pytest.mark.parametrize(
    "raw,expected",
    [(-0.5, 0.0), (0.0, 0.0), (0.42, 0.42), (1.0, 1.0), (1.5, 1.0), ("nope", 0.0)],
)
def test_confidence_is_clamped_on_construction(raw, expected):
    from hermes_cli.jarvis_prime import WorkPacket

    packet = WorkPacket(confidence=raw)
    assert packet.confidence == expected


def test_owner_gated_actions_retained_but_not_executed():
    from hermes_cli.jarvis_prime import OWNER_AUTHORIZATION_PHRASE, WorkPacket

    actions = ["deploy", "publish package", "rotate secrets"]
    packet = WorkPacket(
        **{**_complete_packet_kwargs(), "owner_gated_actions": actions}
    )

    # Data is preserved verbatim.
    assert packet.owner_gated_actions == actions
    snapshot = packet.to_dict()
    assert snapshot["owner_gated_actions"] == actions

    # The phrase is data, not a callable / side effect.
    assert packet.owner_authorization_phrase == OWNER_AUTHORIZATION_PHRASE
    assert isinstance(packet.owner_authorization_phrase, str)


def test_invalid_list_field_type_is_reported():
    from hermes_cli.jarvis_prime import WorkPacket

    packet = WorkPacket(**_complete_packet_kwargs())
    packet.allowed_files = "not-a-list"  # type: ignore[assignment]
    findings = packet.validate()
    assert any(f.field == "allowed_files" and f.code == "invalid_type" for f in findings)


def test_validation_finding_to_dict():
    from hermes_cli.jarvis_prime import WorkPacketValidationFinding

    finding = WorkPacketValidationFinding(field="x", code="y", message="z")
    assert finding.to_dict() == {"field": "x", "code": "y", "message": "z"}
