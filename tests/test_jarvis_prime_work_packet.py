"""Tests for hermes_cli.jarvis_prime.work_packet — schema, validation, owner gates."""

from __future__ import annotations

import importlib

import pytest

from hermes_cli.jarvis_prime.owner_auth import AUTHORIZATION_PHRASE
from hermes_cli.jarvis_prime.work_packet import (
    REQUIRED_FIELDS,
    VALID_RISK_CLASSES,
    WorkPacket,
    WorkPacketValidationFinding,
)


def _complete_packet_kwargs() -> dict:
    return dict(
        mission="Port the WorkPacket model onto current main",
        repo_root="/home/user/hermes-agent",
        branch="feature/jarvis-workpacket-foundation-current-main",
        risk_class="RC1",
        allowed_files=["hermes_cli/jarvis_prime/work_packet.py"],
        protected_files=["main"],
        non_goals=["overwrite shipped runtime modules"],
        acceptance_criteria=["WorkPacket validates", "existing tests still pass"],
        files_changed=["hermes_cli/jarvis_prime/work_packet.py"],
        tests_run=["tests/test_jarvis_prime_work_packet.py"],
        tests_failed=[],
        verification_summary="pytest tests/test_jarvis_prime_work_packet.py passes",
        rollback_plan="git revert the foundation commit",
        owner_gated_actions=["main_branch_merge"],
        citations=["docs/jarvis-prime-wave-plan.md", "CANONICAL_REPO.md"],
        confidence=0.8,
    )


def test_work_packet_creation_defaults_are_safe() -> None:
    packet = WorkPacket()

    assert packet.mission == ""
    assert packet.allowed_files == []
    assert packet.protected_files == []
    assert packet.non_goals == []
    assert packet.acceptance_criteria == []
    assert packet.owner_gated_actions == []
    assert packet.confidence == 0.0
    assert packet.created_at
    assert "T" in packet.created_at


def test_acting_agent_id_is_optional_and_empty_by_default() -> None:
    # Additive field for C19: optional, empty by default so existing packet
    # construction and serialization are unaffected; round-trips through
    # to_dict / from_dict.
    assert WorkPacket().acting_agent_id == ""

    packet = WorkPacket(acting_agent_id="claude-code-windows")
    payload = packet.to_dict()
    assert payload["acting_agent_id"] == "claude-code-windows"
    assert WorkPacket.from_dict(payload).acting_agent_id == "claude-code-windows"


def test_authorization_phrase_default_matches_owner_auth_canonical() -> None:
    # Single source of truth: WorkPacket must default to the exact string
    # the shipped owner-auth gate enforces.
    assert WorkPacket().owner_authorization_phrase == AUTHORIZATION_PHRASE
    assert AUTHORIZATION_PHRASE == "Yes, with authorization."


def test_work_packet_to_dict_round_trips() -> None:
    packet = WorkPacket(**_complete_packet_kwargs())
    payload = packet.to_dict()

    assert payload["mission"] == "Port the WorkPacket model onto current main"
    assert payload["risk_class"] == "RC1"
    assert payload["allowed_files"] == ["hermes_cli/jarvis_prime/work_packet.py"]
    assert payload["confidence"] == 0.8
    assert "created_at" in payload


def test_work_packet_from_dict_recovers_packet_and_ignores_unknown_keys() -> None:
    original = WorkPacket(**_complete_packet_kwargs())
    payload = original.to_dict()
    payload["future_field_v2"] = "ignored"

    recovered = WorkPacket.from_dict(payload)

    assert recovered.mission == original.mission
    assert recovered.repo_root == original.repo_root
    assert recovered.risk_class == original.risk_class
    assert recovered.acceptance_criteria == original.acceptance_criteria
    assert recovered.owner_gated_actions == original.owner_gated_actions
    assert recovered.confidence == original.confidence


def test_validate_passes_on_complete_packet() -> None:
    packet = WorkPacket(**_complete_packet_kwargs())

    assert packet.validate() == []
    assert packet.is_valid() is True


def test_validate_reports_each_missing_required_field() -> None:
    packet = WorkPacket()
    findings = packet.validate()

    flagged = {f.field for f in findings if f.code == "missing"}
    for required in REQUIRED_FIELDS:
        assert required in flagged, f"{required} should be reported missing"


def test_confidence_below_zero_is_clamped() -> None:
    assert WorkPacket(confidence=-0.5).confidence == 0.0


def test_confidence_above_one_is_clamped() -> None:
    assert WorkPacket(confidence=1.7).confidence == 1.0


def test_confidence_non_numeric_is_handled_safely() -> None:
    assert WorkPacket(confidence="not-a-number").confidence == 0.0  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]  # mock/duck-typed test fixture


def test_invalid_risk_class_is_reported() -> None:
    kwargs = _complete_packet_kwargs()
    kwargs["risk_class"] = "RC9"
    packet = WorkPacket(**kwargs)

    codes = {(f.field, f.code) for f in packet.validate()}
    assert ("risk_class", "invalid_value") in codes


@pytest.mark.parametrize("rc", list(VALID_RISK_CLASSES))
def test_all_documented_risk_classes_are_accepted(rc: str) -> None:
    kwargs = _complete_packet_kwargs()
    kwargs["risk_class"] = rc
    assert WorkPacket(**kwargs).is_valid()


def test_owner_gated_actions_are_retained_but_not_executed() -> None:
    # The whole point of the packet's owner_gated_actions field is to
    # preserve intent without acting on it. Verify retention.
    actions = ["main_branch_merge", "package_publish", "dns_change"]
    packet = WorkPacket(**{**_complete_packet_kwargs(), "owner_gated_actions": actions})  # ty: ignore[invalid-argument-type]  # mock/duck-typed test fixture

    assert packet.owner_gated_actions == actions
    assert packet.owner_authorization_phrase == AUTHORIZATION_PHRASE
    assert packet.to_dict()["owner_gated_actions"] == actions


def test_owner_gated_actions_without_auth_phrase_is_flagged() -> None:
    kwargs = _complete_packet_kwargs()
    kwargs["owner_authorization_phrase"] = ""
    packet = WorkPacket(**kwargs)

    fields_codes = {(f.field, f.code) for f in packet.validate()}
    assert ("owner_authorization_phrase", "missing") in fields_codes


def test_from_dict_rejects_non_dict_input() -> None:
    with pytest.raises(TypeError):
        WorkPacket.from_dict("not a dict")  # type: ignore[arg-type]  # ty: ignore[invalid-argument-type]  # mock/duck-typed test fixture


def test_package_reexports_work_packet_symbols() -> None:
    # The minimal additive edit to hermes_cli.jarvis_prime.__init__
    # should expose WorkPacket alongside the shipped runtime exports.
    module = importlib.import_module("hermes_cli.jarvis_prime")

    assert hasattr(module, "WorkPacket")
    assert hasattr(module, "WorkPacketValidationFinding")
    assert hasattr(module, "WORK_PACKET_REQUIRED_FIELDS")
    assert hasattr(module, "WORK_PACKET_RISK_CLASSES")

    # And the shipped runtime exports must still be present — proves
    # the edit was additive, not destructive.
    for shipped in ("JarvisPrime", "OwnerAuth", "AUTHORIZATION_PHRASE",
                    "Mode", "Router", "run_gate_summary"):
        assert hasattr(module, shipped), f"shipped export {shipped!r} regressed"


def test_validation_finding_to_dict_shape() -> None:
    finding = WorkPacketValidationFinding(field="mission", code="missing", message="x")
    assert finding.to_dict() == {"field": "mission", "code": "missing", "message": "x"}
