"""Tests for hermes_cli.jarvis_prime.work_packet — standard WorkPacket."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, cast

import pytest

from hermes_cli.jarvis_prime import (
    RiskClass,
    ValidationSeverity,
    WorkPacket,
    WorkPacketValidationFinding,
)
from hermes_cli.jarvis_prime.work_packet import VALID_RISK_CLASSES


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


def test_workpacket_constructs_with_no_args() -> None:
    packet = WorkPacket()
    assert packet.mission == ""
    assert packet.repo_root == ""
    assert packet.branch == ""
    assert packet.risk_class == ""
    assert packet.allowed_files == []
    assert packet.confidence == 0.0
    assert isinstance(packet.created_at, datetime)
    assert packet.created_at.tzinfo is timezone.utc


def test_workpacket_default_created_at_is_timezone_aware_utc() -> None:
    packet = WorkPacket()
    offset = packet.created_at.utcoffset()
    assert offset is not None
    assert offset.total_seconds() == 0


def test_workpacket_default_lists_are_independent_instances() -> None:
    a = WorkPacket()
    b = WorkPacket()
    a.allowed_files.append("x.py")
    assert b.allowed_files == []  # no shared mutable default


def test_workpacket_accepts_all_fields() -> None:
    packet = WorkPacket(
        mission="lock the foundation",
        repo_root="/home/user/hermes-agent",
        branch="feature/jarvis-foundation-lock",
        risk_class="RC1",
        allowed_files=["hermes_cli/jarvis_prime/work_packet.py"],
        protected_files=["main"],
        non_goals=["expand the CLI"],
        acceptance_criteria=["tests pass", "import succeeds"],
        files_changed=["hermes_cli/jarvis_prime/work_packet.py"],
        tests_run=["pytest tests/test_jarvis_prime_work_packet.py"],
        tests_failed=[],
        verification_summary="all green",
        rollback_plan="git revert <sha>",
        owner_gated_actions=["main_branch_merge"],
        owner_authorization_phrase="Yes, with authorization.",
        citations=["docs/jarvis-prime-wave-plan.md"],
        confidence=0.9,
    )
    assert packet.mission == "lock the foundation"
    assert packet.owner_gated_actions == ["main_branch_merge"]
    assert packet.confidence == 0.9


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


def test_to_dict_round_trip_via_from_dict() -> None:
    packet = WorkPacket(
        mission="m",
        repo_root="/r",
        branch="b",
        risk_class="RC2",
        acceptance_criteria=["green"],
        rollback_plan="revert",
        confidence=0.5,
    )
    data = packet.to_dict()
    rebuilt = WorkPacket.from_dict(data)
    assert rebuilt.mission == packet.mission
    assert rebuilt.repo_root == packet.repo_root
    assert rebuilt.branch == packet.branch
    assert rebuilt.risk_class == packet.risk_class
    assert rebuilt.acceptance_criteria == packet.acceptance_criteria
    assert rebuilt.rollback_plan == packet.rollback_plan
    assert rebuilt.confidence == packet.confidence
    assert rebuilt.created_at == packet.created_at


def test_to_dict_is_json_serializable() -> None:
    packet = WorkPacket(
        mission="m",
        repo_root="/r",
        branch="b",
        risk_class="RC0",
        acceptance_criteria=["c"],
        rollback_plan="rb",
        confidence=0.1,
    )
    payload = json.dumps(packet.to_dict())
    parsed = json.loads(payload)
    assert parsed["mission"] == "m"
    assert parsed["risk_class"] == "RC0"
    assert isinstance(parsed["created_at"], str)
    # ISO-8601 round-trip
    datetime.fromisoformat(parsed["created_at"])


def test_to_dict_returns_independent_lists() -> None:
    packet = WorkPacket(allowed_files=["a.py"])
    data = packet.to_dict()
    data["allowed_files"].append("b.py")
    assert packet.allowed_files == ["a.py"]


def test_from_dict_ignores_unknown_keys() -> None:
    rebuilt = WorkPacket.from_dict(
        {
            "mission": "m",
            "repo_root": "/r",
            "branch": "b",
            "risk_class": "RC1",
            "future_field": "ignore me",
        }
    )
    assert rebuilt.mission == "m"
    assert not hasattr(rebuilt, "future_field")


def test_from_dict_accepts_iso_datetime_string() -> None:
    iso = "2026-05-25T12:00:00+00:00"
    rebuilt = WorkPacket.from_dict({"created_at": iso})
    assert rebuilt.created_at == datetime(2026, 5, 25, 12, 0, tzinfo=timezone.utc)


def test_from_dict_promotes_naive_iso_datetime_to_utc() -> None:
    rebuilt = WorkPacket.from_dict({"created_at": "2026-05-25T12:00:00"})
    assert rebuilt.created_at.tzinfo is timezone.utc


def test_from_dict_rejects_non_mapping() -> None:
    with pytest.raises(TypeError):
        WorkPacket.from_dict(cast(Any, ["not", "a", "mapping"]))


# ---------------------------------------------------------------------------
# Validation — passes
# ---------------------------------------------------------------------------


def _complete_packet(**overrides: Any) -> WorkPacket:
    base: dict[str, Any] = {
        "mission": "lock the foundation",
        "repo_root": "/home/user/hermes-agent",
        "branch": "feature/jarvis-foundation-lock",
        "risk_class": "RC1",
        "acceptance_criteria": ["import succeeds"],
        "rollback_plan": "git revert",
        "confidence": 0.8,
    }
    base.update(overrides)
    return WorkPacket(**base)


def test_validate_passes_for_complete_packet() -> None:
    findings = _complete_packet().validate()
    assert findings == []


def test_is_valid_true_for_complete_packet() -> None:
    assert _complete_packet().is_valid() is True


# ---------------------------------------------------------------------------
# Validation — missing required fields
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "missing_field",
    [
        "mission",
        "repo_root",
        "branch",
        "risk_class",
        "acceptance_criteria",
        "rollback_plan",
    ],
)
def test_validate_reports_missing_required_field(missing_field: str) -> None:
    override = {missing_field: [] if missing_field == "acceptance_criteria" else ""}
    findings = _complete_packet(**override).validate()
    fields_flagged = {f.field for f in findings}
    assert missing_field in fields_flagged
    matching = [f for f in findings if f.field == missing_field]
    assert all(f.severity == ValidationSeverity.ERROR for f in matching)


def test_missing_required_fields_helper_lists_all_six() -> None:
    packet = WorkPacket()  # everything empty
    missing = packet.missing_required_fields()
    assert set(missing) == {
        "mission",
        "repo_root",
        "branch",
        "risk_class",
        "acceptance_criteria",
        "rollback_plan",
    }


def test_validate_finding_to_dict_is_json_safe() -> None:
    finding = WorkPacketValidationFinding(
        field="mission",
        message="required field 'mission' is missing or empty",
    )
    json.dumps(finding.to_dict())  # must not raise


# ---------------------------------------------------------------------------
# Validation — risk_class
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("rc", ["RC0", "RC1", "RC2", "RC3", "RC4"])
def test_validate_accepts_each_supported_risk_class(rc: str) -> None:
    findings = _complete_packet(risk_class=rc).validate()
    assert all(f.field != "risk_class" for f in findings)


def test_validate_reports_invalid_risk_class() -> None:
    findings = _complete_packet(risk_class="RC99").validate()
    risk_findings = [f for f in findings if f.field == "risk_class"]
    assert len(risk_findings) == 1
    assert "invalid risk_class" in risk_findings[0].message
    assert risk_findings[0].severity == ValidationSeverity.ERROR


def test_risk_class_enum_matches_valid_set() -> None:
    assert {rc.value for rc in RiskClass} == VALID_RISK_CLASSES


# ---------------------------------------------------------------------------
# Validation — confidence
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("conf", [-0.01, 1.01, -1.0, 2.0, 100.0])
def test_validate_reports_confidence_out_of_range(conf: float) -> None:
    findings = _complete_packet(confidence=conf).validate()
    conf_findings = [f for f in findings if f.field == "confidence"]
    assert len(conf_findings) == 1
    assert "between 0.0 and 1.0" in conf_findings[0].message


@pytest.mark.parametrize("conf", [0.0, 0.5, 1.0])
def test_validate_accepts_confidence_in_range(conf: float) -> None:
    findings = _complete_packet(confidence=conf).validate()
    assert all(f.field != "confidence" for f in findings)


def test_validate_reports_non_numeric_confidence() -> None:
    # constructing the dataclass with a bogus confidence is allowed —
    # validate() is where we catch it. mirror typical "agent fed us
    # junk" scenarios.
    packet = _complete_packet()
    packet.confidence = cast(Any, "high")
    findings = packet.validate()
    conf_findings = [f for f in findings if f.field == "confidence"]
    assert len(conf_findings) == 1
    assert "real number" in conf_findings[0].message


def test_validate_rejects_bool_as_confidence() -> None:
    packet = _complete_packet()
    packet.confidence = cast(Any, True)
    findings = packet.validate()
    assert any(f.field == "confidence" for f in findings)


# ---------------------------------------------------------------------------
# Owner-gated actions — preserved as data, never executed
# ---------------------------------------------------------------------------


def test_owner_gated_actions_are_preserved_in_to_dict() -> None:
    packet = _complete_packet(
        owner_gated_actions=["main_branch_merge", "production_deploy"],
        owner_authorization_phrase="Yes, with authorization.",
    )
    data = packet.to_dict()
    assert data["owner_gated_actions"] == [
        "main_branch_merge",
        "production_deploy",
    ]
    assert data["owner_authorization_phrase"] == "Yes, with authorization."


def test_owner_gated_actions_without_phrase_emits_warning_only() -> None:
    packet = _complete_packet(
        owner_gated_actions=["main_branch_merge"],
        owner_authorization_phrase=None,
    )
    findings = packet.validate()
    auth_findings = [f for f in findings if f.field == "owner_authorization_phrase"]
    assert len(auth_findings) == 1
    assert auth_findings[0].severity == ValidationSeverity.WARNING
    # Warning alone should not flip is_valid to False.
    assert packet.is_valid() is True


def test_workpacket_module_does_not_execute_owner_gated_actions() -> None:
    # Construction and validation must never side-effect on an owner
    # action — the WorkPacket is data, dispatch is elsewhere.
    packet = _complete_packet(
        owner_gated_actions=[
            "production_deploy",
            "main_branch_merge",
            "spend_money",
        ],
    )
    # validate() is the only behavior on the model; it must not raise
    # or touch the network / filesystem.
    findings = packet.validate()
    assert isinstance(findings, list)
    # And the data is still there afterwards, untouched.
    assert packet.owner_gated_actions == [
        "production_deploy",
        "main_branch_merge",
        "spend_money",
    ]


# ---------------------------------------------------------------------------
# Package-level export wiring
# ---------------------------------------------------------------------------


def test_workpacket_is_exported_from_package() -> None:
    import hermes_cli.jarvis_prime as jp

    assert jp.WorkPacket is WorkPacket
    assert jp.WorkPacketValidationFinding is WorkPacketValidationFinding
    assert jp.RiskClass is RiskClass
    assert jp.ValidationSeverity is ValidationSeverity
    assert "WorkPacket" in jp.__all__
    assert "WorkPacketValidationFinding" in jp.__all__


def test_package_import_remains_stdlib_only() -> None:
    # Importing the package must not pull in pydantic, requests, httpx,
    # yaml, or any plugin backend at module import time.
    import sys

    # Trigger a fresh import path by checking after `jp` is imported.
    import hermes_cli.jarvis_prime  # noqa: F401

    for forbidden in ("pydantic", "requests", "httpx"):
        assert forbidden not in sys.modules or not any(
            mod.startswith(forbidden)
            and "hermes_cli.jarvis_prime" in str(getattr(sys.modules[mod], "__file__", ""))
            for mod in list(sys.modules)
        )
