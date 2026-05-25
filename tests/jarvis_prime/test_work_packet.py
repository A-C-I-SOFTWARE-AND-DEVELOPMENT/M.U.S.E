"""Wave 0 baseline tests for hermes_cli.jarvis_prime.work_packet."""

from __future__ import annotations

import importlib
from datetime import datetime, timezone

import pytest

from hermes_cli.jarvis_prime.work_packet import (
    AUTHORIZATION_PHRASE,
    VALID_RISK_CLASSES,
    WorkPacket,
    WorkPacketValidationFinding,
)


def _complete_packet(**overrides) -> WorkPacket:
    """Build a packet that validates clean by default."""

    kwargs = dict(
        mission="Lock the Wave 0 foundation",
        repo_root="/home/user/hermes-agent",
        branch="feature/jarvis-foundation-lock",
        risk_class="RC1",
        allowed_files=["CANONICAL_REPO.md", "docs/jarvis-prime-wave-plan.md"],
        protected_files=["main.py"],
        non_goals=["semantic immune layer", "cli expansion"],
        acceptance_criteria=["docs added", "tests pass"],
        files_changed=["CANONICAL_REPO.md"],
        tests_run=["pytest tests/jarvis_prime -q"],
        tests_failed=[],
        verification_summary="all tests passed",
        rollback_plan="git revert <merge-sha>",
        owner_gated_actions=[],
        owner_authorization_phrase="",
        citations=["docs/jarvis-prime-operating-system.md"],
        confidence=0.9,
    )
    kwargs.update(overrides)
    return WorkPacket(**kwargs)


# ---------------------------------------------------------------------------
# Creation
# ---------------------------------------------------------------------------


def test_workpacket_creation_defaults() -> None:
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
    assert packet.created_at.tzinfo.utcoffset(packet.created_at) == timezone.utc.utcoffset(packet.created_at)


def test_workpacket_creation_with_fields() -> None:
    packet = _complete_packet()
    assert packet.mission == "Lock the Wave 0 foundation"
    assert packet.risk_class == "RC1"
    assert packet.confidence == 0.9
    assert "CANONICAL_REPO.md" in packet.allowed_files


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


def test_to_dict_returns_json_safe_payload() -> None:
    packet = _complete_packet()
    data = packet.to_dict()

    assert isinstance(data, dict)
    assert data["mission"] == "Lock the Wave 0 foundation"
    assert data["risk_class"] == "RC1"
    assert isinstance(data["created_at"], str)
    # ISO-8601 with timezone offset (datetime.fromisoformat round-trips).
    parsed = datetime.fromisoformat(data["created_at"])
    assert parsed.tzinfo is not None


def test_to_dict_is_defensive_copy() -> None:
    packet = _complete_packet()
    data = packet.to_dict()
    data["allowed_files"].append("INJECTED.md")
    assert "INJECTED.md" not in packet.allowed_files


def test_from_dict_round_trips() -> None:
    original = _complete_packet()
    rebuilt = WorkPacket.from_dict(original.to_dict())

    assert rebuilt.mission == original.mission
    assert rebuilt.repo_root == original.repo_root
    assert rebuilt.branch == original.branch
    assert rebuilt.risk_class == original.risk_class
    assert rebuilt.allowed_files == original.allowed_files
    assert rebuilt.acceptance_criteria == original.acceptance_criteria
    assert rebuilt.confidence == original.confidence
    # created_at should round-trip to an aware datetime equal to original
    assert rebuilt.created_at == original.created_at


def test_from_dict_ignores_unknown_keys() -> None:
    payload = _complete_packet().to_dict()
    payload["mystery_key"] = "ignored"
    rebuilt = WorkPacket.from_dict(payload)
    assert not hasattr(rebuilt, "mystery_key")


def test_from_dict_rejects_non_mapping() -> None:
    with pytest.raises(TypeError):
        WorkPacket.from_dict(["not", "a", "mapping"])  # type: ignore[arg-type]


def test_from_dict_handles_naive_created_at_string() -> None:
    payload = _complete_packet().to_dict()
    payload["created_at"] = "2026-05-25T12:00:00"  # naive ISO string
    rebuilt = WorkPacket.from_dict(payload)
    assert rebuilt.created_at.tzinfo is not None


# ---------------------------------------------------------------------------
# Validation — happy path
# ---------------------------------------------------------------------------


def test_validate_passes_on_complete_packet() -> None:
    packet = _complete_packet()
    assert packet.validate() == []
    assert packet.is_valid() is True


def test_validate_passes_for_every_supported_risk_class() -> None:
    for rc in sorted(VALID_RISK_CLASSES):
        packet = _complete_packet(risk_class=rc)
        assert packet.validate() == [], f"risk_class={rc} should validate"


# ---------------------------------------------------------------------------
# Validation — missing required fields
# ---------------------------------------------------------------------------


def test_validate_reports_missing_required_fields() -> None:
    packet = WorkPacket()  # all defaults / empty
    findings = packet.validate()
    fields_with_findings = {f.field for f in findings}

    # The brief lists these as required for validation:
    for required in (
        "mission",
        "repo_root",
        "branch",
        "risk_class",
        "acceptance_criteria",
        "rollback_plan",
    ):
        assert required in fields_with_findings, (
            f"validation should report missing field: {required}"
        )

    # Findings must be structured, not raw strings.
    assert all(isinstance(f, WorkPacketValidationFinding) for f in findings)
    assert all(f.severity for f in findings)


def test_validate_treats_whitespace_only_as_missing() -> None:
    packet = _complete_packet(mission="   ", repo_root="\t")
    findings = {(f.field, f.severity) for f in packet.validate()}
    assert ("mission", "missing") in findings
    assert ("repo_root", "missing") in findings


# ---------------------------------------------------------------------------
# Validation — confidence bounds
# ---------------------------------------------------------------------------


def test_validate_flags_confidence_below_zero() -> None:
    packet = _complete_packet(confidence=-0.5)
    findings = packet.validate()
    assert any(f.field == "confidence" and f.severity == "out_of_range" for f in findings)


def test_validate_flags_confidence_above_one() -> None:
    packet = _complete_packet(confidence=1.5)
    findings = packet.validate()
    assert any(f.field == "confidence" and f.severity == "out_of_range" for f in findings)


def test_validate_flags_non_numeric_confidence() -> None:
    packet = _complete_packet()
    packet.confidence = "high"  # type: ignore[assignment]
    findings = packet.validate()
    assert any(f.field == "confidence" and f.severity == "invalid" for f in findings)


def test_clamp_confidence_clips_into_unit_interval() -> None:
    packet = _complete_packet(confidence=2.0)
    packet.clamp_confidence()
    assert packet.confidence == 1.0

    packet.confidence = -3.0
    packet.clamp_confidence()
    assert packet.confidence == 0.0

    packet.confidence = "nope"  # type: ignore[assignment]
    packet.clamp_confidence()
    assert packet.confidence == 0.0


# ---------------------------------------------------------------------------
# Validation — risk class
# ---------------------------------------------------------------------------


def test_validate_flags_invalid_risk_class() -> None:
    packet = _complete_packet(risk_class="RC9")
    findings = packet.validate()
    assert any(f.field == "risk_class" and f.severity == "invalid" for f in findings)


def test_valid_risk_classes_are_RC0_through_RC4() -> None:
    assert VALID_RISK_CLASSES == frozenset({"RC0", "RC1", "RC2", "RC3", "RC4"})


# ---------------------------------------------------------------------------
# Owner-gated actions stay as data
# ---------------------------------------------------------------------------


def test_owner_gated_actions_are_preserved_as_data() -> None:
    packet = _complete_packet(
        owner_gated_actions=["main_branch_merge", "package_publish"],
        owner_authorization_phrase=AUTHORIZATION_PHRASE,
    )

    # They survive a serialization round trip without being touched.
    rebuilt = WorkPacket.from_dict(packet.to_dict())
    assert rebuilt.owner_gated_actions == ["main_branch_merge", "package_publish"]
    assert rebuilt.owner_authorization_phrase == AUTHORIZATION_PHRASE

    # With the exact phrase, validation does not complain about
    # authorization. (It still validates the rest of the packet.)
    findings = packet.validate()
    assert not any(f.field == "owner_authorization_phrase" for f in findings)


def test_owner_gated_actions_without_phrase_remain_deferred() -> None:
    packet = _complete_packet(
        owner_gated_actions=["main_branch_merge"],
        owner_authorization_phrase="",
    )
    findings = packet.validate()
    assert any(
        f.field == "owner_authorization_phrase" and f.severity == "missing"
        for f in findings
    )


def test_owner_authorization_phrase_must_be_exact() -> None:
    packet = _complete_packet(
        owner_gated_actions=["main_branch_merge"],
        owner_authorization_phrase="yes with authorization",  # no comma, no period
    )
    findings = packet.validate()
    assert any(
        f.field == "owner_authorization_phrase" and f.severity == "invalid"
        for f in findings
    )


def test_owner_gated_actions_are_not_executed_on_creation() -> None:
    """Sanity check: constructing a packet with destructive-sounding
    action names is purely data — no side effects, no callouts, no
    raised exceptions, no environment mutation.
    """

    import os

    snapshot = dict(os.environ)
    packet = WorkPacket(
        mission="m",
        repo_root="/tmp",
        branch="b",
        risk_class="RC4",
        acceptance_criteria=["x"],
        rollback_plan="y",
        owner_gated_actions=[
            "production_deploy",
            "force_push",
            "modify_secrets",
            "dns_change",
        ],
        owner_authorization_phrase=AUTHORIZATION_PHRASE,
    )
    assert packet.owner_gated_actions == [
        "production_deploy",
        "force_push",
        "modify_secrets",
        "dns_change",
    ]
    assert os.environ == snapshot


# ---------------------------------------------------------------------------
# Package import surface
# ---------------------------------------------------------------------------


def test_jarvis_prime_package_imports_and_exposes_workpacket() -> None:
    module = importlib.import_module("hermes_cli.jarvis_prime")
    # Re-import (cached) — the package must remain importable.
    importlib.reload(module)
    assert hasattr(module, "WorkPacket")
    assert hasattr(module, "WorkPacketValidationFinding")
    assert hasattr(module, "VALID_RISK_CLASSES")
    assert module.WorkPacket is WorkPacket
    assert "WorkPacket" in module.__all__
    assert "WorkPacketValidationFinding" in module.__all__
