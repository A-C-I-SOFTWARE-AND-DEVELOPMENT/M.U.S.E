"""Baseline tests for the Wave 0 JARVIS Prime WorkPacket model.

These tests are intentionally narrow: they exercise the schema, the
serialization round-trip, the validation behaviour, and the
import-time export surface. They must remain stdlib-only.
"""

from __future__ import annotations

import importlib

import pytest


def _complete_packet_kwargs() -> dict:
    return dict(
        mission="Lock the JARVIS Prime foundation",
        repo_root="/home/user/hermes-agent",
        branch="feature/jarvis-foundation-lock",
        risk_class="RC1",
        allowed_files=["hermes_cli/jarvis_prime/work_packet.py"],
        protected_files=["main"],
        non_goals=["semantic immune layer", "runtime enforcement"],
        acceptance_criteria=["WorkPacket validates", "tests pass"],
        files_changed=["hermes_cli/jarvis_prime/work_packet.py"],
        tests_run=["tests/jarvis_prime/test_work_packet.py"],
        tests_failed=[],
        verification_summary="pytest tests/jarvis_prime -q passes",
        rollback_plan="git revert the foundation commit",
        owner_gated_actions=["merge to main"],
        citations=["docs/jarvis-prime-wave-plan.md"],
        confidence=0.8,
    )


def test_work_packet_creation_defaults_are_safe():
    from hermes_cli.jarvis_prime import WorkPacket

    packet = WorkPacket()

    assert packet.mission == ""
    assert packet.allowed_files == []
    assert packet.protected_files == []
    assert packet.non_goals == []
    assert packet.acceptance_criteria == []
    assert packet.owner_gated_actions == []
    assert packet.confidence == 0.0
    assert packet.created_at  # timezone-aware UTC ISO string
    assert "T" in packet.created_at


def test_work_packet_to_dict_round_trips():
    from hermes_cli.jarvis_prime import WorkPacket

    packet = WorkPacket(**_complete_packet_kwargs())
    payload = packet.to_dict()

    assert payload["mission"] == "Lock the JARVIS Prime foundation"
    assert payload["risk_class"] == "RC1"
    assert payload["allowed_files"] == ["hermes_cli/jarvis_prime/work_packet.py"]
    assert payload["confidence"] == 0.8
    assert "created_at" in payload


def test_work_packet_from_dict_recovers_packet():
    from hermes_cli.jarvis_prime import WorkPacket

    original = WorkPacket(**_complete_packet_kwargs())
    payload = original.to_dict()
    # Inject an unknown forward-compat key to confirm it is ignored.
    payload["future_field_v2"] = "ignored"

    recovered = WorkPacket.from_dict(payload)

    assert recovered.mission == original.mission
    assert recovered.repo_root == original.repo_root
    assert recovered.risk_class == original.risk_class
    assert recovered.acceptance_criteria == original.acceptance_criteria
    assert recovered.owner_gated_actions == original.owner_gated_actions
    assert recovered.confidence == original.confidence


def test_validate_passes_on_complete_packet():
    from hermes_cli.jarvis_prime import WorkPacket

    packet = WorkPacket(**_complete_packet_kwargs())

    findings = packet.validate()

    assert findings == []
    assert packet.is_valid() is True


def test_validate_reports_missing_required_fields():
    from hermes_cli.jarvis_prime import WorkPacket, REQUIRED_FIELDS

    packet = WorkPacket()
    findings = packet.validate()

    flagged = {f.field for f in findings if f.code == "missing"}
    for required in REQUIRED_FIELDS:
        assert required in flagged, f"{required} should be reported missing"


def test_confidence_below_zero_is_clamped():
    from hermes_cli.jarvis_prime import WorkPacket

    packet = WorkPacket(confidence=-0.5)

    assert packet.confidence == 0.0


def test_confidence_above_one_is_clamped():
    from hermes_cli.jarvis_prime import WorkPacket

    packet = WorkPacket(confidence=1.7)

    assert packet.confidence == 1.0


def test_confidence_non_numeric_is_handled_safely():
    from hermes_cli.jarvis_prime import WorkPacket

    packet = WorkPacket(confidence="not-a-number")  # type: ignore[arg-type]

    assert packet.confidence == 0.0


def test_invalid_risk_class_is_reported():
    from hermes_cli.jarvis_prime import WorkPacket

    kwargs = _complete_packet_kwargs()
    kwargs["risk_class"] = "RC9"
    packet = WorkPacket(**kwargs)

    findings = packet.validate()

    codes = {(f.field, f.code) for f in findings}
    assert ("risk_class", "invalid_value") in codes


@pytest.mark.parametrize("rc", ["RC0", "RC1", "RC2", "RC3", "RC4"])
def test_all_documented_risk_classes_are_accepted(rc):
    from hermes_cli.jarvis_prime import WorkPacket

    kwargs = _complete_packet_kwargs()
    kwargs["risk_class"] = rc
    packet = WorkPacket(**kwargs)

    assert packet.is_valid()


def test_owner_gated_actions_are_retained_but_not_executed():
    from hermes_cli.jarvis_prime import WorkPacket, OWNER_AUTHORIZATION_PHRASE

    actions = ["merge to main", "publish to PyPI", "DNS change"]
    packet = WorkPacket(
        **{**_complete_packet_kwargs(), "owner_gated_actions": actions}
    )

    # Data is retained verbatim.
    assert packet.owner_gated_actions == actions
    # The canonical authorization phrase is the default and is preserved.
    assert packet.owner_authorization_phrase == OWNER_AUTHORIZATION_PHRASE
    # to_dict carries the actions through unchanged.
    assert packet.to_dict()["owner_gated_actions"] == actions


def test_owner_gated_actions_without_auth_phrase_is_flagged():
    from hermes_cli.jarvis_prime import WorkPacket

    kwargs = _complete_packet_kwargs()
    kwargs["owner_authorization_phrase"] = ""
    packet = WorkPacket(**kwargs)

    findings = packet.validate()

    fields = {(f.field, f.code) for f in findings}
    assert ("owner_authorization_phrase", "missing") in fields


def test_from_dict_rejects_non_dict_input():
    from hermes_cli.jarvis_prime import WorkPacket

    with pytest.raises(TypeError):
        WorkPacket.from_dict("not a dict")  # type: ignore[arg-type]


def test_package_exports_work_packet_symbols():
    module = importlib.import_module("hermes_cli.jarvis_prime")

    # Required exports per Wave 0 acceptance criteria.
    assert hasattr(module, "WorkPacket")
    assert hasattr(module, "WorkPacketValidationFinding")
    assert hasattr(module, "REQUIRED_FIELDS")
    assert hasattr(module, "VALID_RISK_CLASSES")
    assert hasattr(module, "OWNER_AUTHORIZATION_PHRASE")
