"""Baseline tests for the JARVIS Prime Wave 0 foundation.

These tests cover the things Wave 0 is responsible for:

- the package imports cleanly from a fresh interpreter
- ``WorkPacket`` constructs with safe defaults
- ``to_dict`` / ``from_dict`` round-trip preserves the packet
- ``validate`` accepts a fully-populated packet
- ``validate`` reports each required field that is missing
- ``confidence`` outside [0, 1] is reported, not silently clamped
- a non-numeric ``confidence`` is reported as an invalid type
- an unknown ``risk_class`` is reported as an invalid value
- ``owner_gated_actions`` are preserved on the packet and never
  executed by anything in this package
"""

from __future__ import annotations

import datetime as _dt

import pytest


def _complete_packet():
    from hermes_cli.jarvis_prime import WorkPacket

    return WorkPacket(
        mission="Lock JARVIS Prime foundation for Wave 0.",
        repo_root="/home/user/hermes-agent",
        branch="claude/jarvis-foundation-lock-TVECb",
        risk_class="RC1",
        allowed_files=["hermes_cli/jarvis_prime/work_packet.py"],
        protected_files=["main"],
        non_goals=["semantic immune layer"],
        acceptance_criteria=[
            "WorkPacket import succeeds",
            "validate() returns empty for a complete packet",
        ],
        files_changed=["hermes_cli/jarvis_prime/work_packet.py"],
        tests_run=["pytest tests/jarvis_prime -q"],
        tests_failed=[],
        verification_summary="All baseline tests passed locally.",
        rollback_plan="Delete hermes_cli/jarvis_prime/ and tests/jarvis_prime/.",
        owner_gated_actions=[],
        citations=["docs/jarvis-prime-wave-plan.md"],
        confidence=0.9,
    )


def test_package_imports_cleanly():
    # If hermes_cli.jarvis_prime accidentally pulls in heavy or
    # third-party deps at import time it will surface here.
    import importlib

    module = importlib.import_module("hermes_cli.jarvis_prime")

    for name in (
        "WorkPacket",
        "WorkPacketValidationFinding",
        "RISK_CLASSES",
        "OWNER_AUTHORIZATION_PHRASE",
    ):
        assert hasattr(module, name), f"missing export: {name}"


def test_default_packet_has_timezone_aware_created_at():
    from hermes_cli.jarvis_prime import WorkPacket

    packet = WorkPacket()
    parsed = _dt.datetime.fromisoformat(packet.created_at)
    assert parsed.tzinfo is not None, "created_at must be timezone-aware"
    assert parsed.utcoffset() == _dt.timedelta(0), "created_at must be UTC"


def test_to_dict_returns_plain_serializable_data():
    packet = _complete_packet()
    data = packet.to_dict()

    # to_dict must be a plain dict of primitives / lists of primitives
    # — anything that json.dumps would refuse fails the contract.
    import json

    json.dumps(data)

    # mutating the returned dict's lists must not affect the packet
    data["allowed_files"].append("evil.py")
    assert "evil.py" not in packet.allowed_files


def test_from_dict_round_trips_a_complete_packet():
    from hermes_cli.jarvis_prime import WorkPacket

    packet = _complete_packet()
    rebuilt = WorkPacket.from_dict(packet.to_dict())

    assert rebuilt.to_dict() == packet.to_dict()


def test_from_dict_ignores_unknown_keys():
    from hermes_cli.jarvis_prime import WorkPacket

    data = _complete_packet().to_dict()
    data["future_field_we_dont_know_about"] = "ignore me"

    rebuilt = WorkPacket.from_dict(data)
    assert rebuilt.mission == "Lock JARVIS Prime foundation for Wave 0."


def test_validate_accepts_a_complete_packet():
    packet = _complete_packet()
    assert packet.validate() == []
    assert packet.is_valid()


def test_validate_reports_each_missing_required_field():
    from hermes_cli.jarvis_prime import WorkPacket

    packet = WorkPacket()  # everything empty
    missing = packet.missing_required_fields()

    for required in (
        "mission",
        "repo_root",
        "branch",
        "risk_class",
        "acceptance_criteria",
        "rollback_plan",
    ):
        assert required in missing, (
            f"validate() should flag missing required field '{required}'; "
            f"got {missing}"
        )


def test_validate_reports_invalid_risk_class():
    packet = _complete_packet()
    packet.risk_class = "RC99"

    codes = {f.code for f in packet.validate() if f.field == "risk_class"}
    assert "invalid_value" in codes


@pytest.mark.parametrize("bad", [-0.1, 1.1, 2.0, -5.0])
def test_validate_reports_out_of_range_confidence(bad):
    packet = _complete_packet()
    packet.confidence = bad

    codes = {f.code for f in packet.validate() if f.field == "confidence"}
    assert "out_of_range" in codes


def test_validate_reports_non_numeric_confidence():
    packet = _complete_packet()
    packet.confidence = "high"  # type: ignore[assignment]

    codes = {f.code for f in packet.validate() if f.field == "confidence"}
    assert "invalid_type" in codes


def test_owner_gated_actions_are_preserved_not_executed():
    from hermes_cli.jarvis_prime import OWNER_AUTHORIZATION_PHRASE, WorkPacket

    packet = _complete_packet()
    packet.owner_gated_actions = [
        "merge to main",
        "publish package",
        "rotate API key",
    ]

    # Nothing in the package should execute these. We assert that by
    # round-tripping the packet through to_dict / from_dict and
    # confirming the actions survive unchanged, and that the canonical
    # authorization phrase is still the data-only sentinel.
    rebuilt = WorkPacket.from_dict(packet.to_dict())

    assert rebuilt.owner_gated_actions == [
        "merge to main",
        "publish package",
        "rotate API key",
    ]
    assert rebuilt.owner_authorization_phrase == OWNER_AUTHORIZATION_PHRASE
    # And the packet itself is still valid (data only, no execution).
    assert rebuilt.is_valid()


def test_owner_gated_actions_with_wrong_phrase_are_flagged():
    packet = _complete_packet()
    packet.owner_gated_actions = ["merge to main"]
    packet.owner_authorization_phrase = "sure go ahead"

    codes = {
        f.code
        for f in packet.validate()
        if f.field == "owner_authorization_phrase"
    }
    assert "phrase_mismatch" in codes
