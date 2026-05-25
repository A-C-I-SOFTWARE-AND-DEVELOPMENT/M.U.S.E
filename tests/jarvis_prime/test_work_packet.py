"""Wave 0 baseline tests for the JARVIS Prime WorkPacket model.

These tests cover the contract documented in
``hermes_cli/jarvis_prime/work_packet.py``: creation defaults,
round-tripping through ``to_dict`` / ``from_dict``, validation of
required fields, risk-class validation, confidence clamping, and the
data-only treatment of ``owner_gated_actions``.

The tests deliberately exercise the package via its public ``__init__``
exports so a regression in the export surface also fails here.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone


def test_jarvis_prime_package_imports():
    import hermes_cli.jarvis_prime as jp

    assert hasattr(jp, "WorkPacket")
    assert hasattr(jp, "WorkPacketValidationFinding")
    assert hasattr(jp, "VALID_RISK_CLASSES")
    assert hasattr(jp, "OWNER_AUTHORIZATION_PHRASE")
    assert "WorkPacket" in jp.__all__
    assert "WorkPacketValidationFinding" in jp.__all__


def _complete_packet():
    from hermes_cli.jarvis_prime import WorkPacket

    return WorkPacket(
        mission="Lock the JARVIS Prime foundation",
        repo_root="/home/user/hermes-agent",
        branch="feature/jarvis-foundation-lock",
        risk_class="RC1",
        allowed_files=["hermes_cli/jarvis_prime/work_packet.py"],
        protected_files=["main"],
        non_goals=["semantic immune layer", "real Claude/Codex dispatch"],
        acceptance_criteria=[
            "WorkPacket dataclass exists",
            "tests pass",
        ],
        files_changed=["hermes_cli/jarvis_prime/work_packet.py"],
        tests_run=["tests/jarvis_prime/test_work_packet.py"],
        tests_failed=[],
        verification_summary="pytest tests/jarvis_prime -q",
        rollback_plan="git checkout main -- hermes_cli/jarvis_prime",
        owner_gated_actions=[],
        owner_authorization_phrase="",
        citations=["CANONICAL_REPO.md", "docs/jarvis-prime-wave-plan.md"],
        confidence=0.9,
    )


# ── Creation ─────────────────────────────────────────────────────


def test_workpacket_creation_defaults_are_safe():
    from hermes_cli.jarvis_prime import WorkPacket

    packet = WorkPacket()

    assert packet.mission == ""
    assert packet.allowed_files == []
    assert packet.protected_files == []
    assert packet.owner_gated_actions == []
    assert packet.confidence == 0.0
    assert isinstance(packet.created_at, datetime)
    assert packet.created_at.tzinfo is not None
    assert packet.created_at.utcoffset() == timezone.utc.utcoffset(packet.created_at)


def test_workpacket_created_at_is_timezone_aware_utc():
    packet = _complete_packet()

    assert packet.created_at.tzinfo is not None
    assert packet.created_at.utcoffset().total_seconds() == 0


# ── Serialization ────────────────────────────────────────────────


def test_to_dict_is_json_safe():
    packet = _complete_packet()

    payload = packet.to_dict()

    # created_at must be a string for JSON safety.
    assert isinstance(payload["created_at"], str)
    # round-trip through json.dumps / json.loads.
    serialized = json.dumps(payload)
    reloaded = json.loads(serialized)
    assert reloaded["mission"] == packet.mission
    assert reloaded["risk_class"] == "RC1"
    assert reloaded["allowed_files"] == packet.allowed_files


def test_from_dict_round_trips():
    from hermes_cli.jarvis_prime import WorkPacket

    original = _complete_packet()
    payload = original.to_dict()

    rebuilt = WorkPacket.from_dict(payload)

    assert rebuilt.mission == original.mission
    assert rebuilt.repo_root == original.repo_root
    assert rebuilt.branch == original.branch
    assert rebuilt.risk_class == original.risk_class
    assert rebuilt.allowed_files == original.allowed_files
    assert rebuilt.acceptance_criteria == original.acceptance_criteria
    assert rebuilt.rollback_plan == original.rollback_plan
    assert rebuilt.confidence == original.confidence
    assert isinstance(rebuilt.created_at, datetime)
    assert rebuilt.created_at.tzinfo is not None


def test_from_dict_ignores_unknown_keys():
    from hermes_cli.jarvis_prime import WorkPacket

    payload = _complete_packet().to_dict()
    payload["unknown_future_field"] = {"nested": True}

    rebuilt = WorkPacket.from_dict(payload)

    assert rebuilt.mission == "Lock the JARVIS Prime foundation"


# ── Validation ───────────────────────────────────────────────────


def test_validate_passes_on_complete_packet():
    packet = _complete_packet()

    findings = packet.validate()

    assert findings == []
    assert packet.is_valid() is True


def test_validate_reports_missing_required_fields():
    from hermes_cli.jarvis_prime import WorkPacket

    packet = WorkPacket()

    findings = packet.validate()
    missing = {f.field for f in findings if f.code == "missing_required_field"}

    assert {
        "mission",
        "repo_root",
        "branch",
        "risk_class",
        "acceptance_criteria",
        "rollback_plan",
    }.issubset(missing)
    assert packet.is_valid() is False


def test_validate_reports_invalid_risk_class():
    from hermes_cli.jarvis_prime import WorkPacket

    packet = _complete_packet()
    packet.risk_class = "RC9"

    findings = packet.validate()
    codes = {f.code for f in findings}

    assert "invalid_risk_class" in codes


def test_valid_risk_classes_cover_rc0_through_rc4():
    from hermes_cli.jarvis_prime import VALID_RISK_CLASSES

    assert VALID_RISK_CLASSES == ("RC0", "RC1", "RC2", "RC3", "RC4")


# ── Confidence handling ─────────────────────────────────────────


def test_confidence_below_zero_is_clamped():
    from hermes_cli.jarvis_prime import WorkPacket

    packet = WorkPacket(confidence=-0.4)

    assert packet.confidence == 0.0


def test_confidence_above_one_is_clamped():
    from hermes_cli.jarvis_prime import WorkPacket

    packet = WorkPacket(confidence=2.5)

    assert packet.confidence == 1.0


def test_confidence_garbage_input_does_not_crash():
    from hermes_cli.jarvis_prime import WorkPacket

    packet = WorkPacket(confidence="not a number")  # type: ignore[arg-type]

    assert packet.confidence == 0.0


# ── Owner-gated actions are data, not behavior ──────────────────


def test_owner_gated_actions_are_retained_but_not_executed():
    from hermes_cli.jarvis_prime import WorkPacket

    actions = [
        "merge integration/jarvis-prime-runtime into main",
        "publish hermes-agent 0.15.0 to PyPI",
        "rotate ANTHROPIC_API_KEY",
    ]
    packet = WorkPacket(
        mission="rollout",
        repo_root="/repo",
        branch="integration/jarvis-prime-runtime",
        risk_class="RC4",
        acceptance_criteria=["owner approved"],
        rollback_plan="revert merge commit",
        owner_gated_actions=actions,
        owner_authorization_phrase="Yes, with authorization.",
    )

    # Data preserved verbatim.
    assert packet.owner_gated_actions == actions
    # Survives serialization.
    assert packet.to_dict()["owner_gated_actions"] == actions
    # validate() does not raise or mutate the actions.
    findings = packet.validate()
    error_codes = {f.code for f in findings if f.severity == "error"}
    assert "missing_owner_authorization" not in error_codes
    assert packet.owner_gated_actions == actions


def test_rc4_packet_without_authorization_phrase_is_flagged():
    from hermes_cli.jarvis_prime import WorkPacket

    packet = WorkPacket(
        mission="rollout",
        repo_root="/repo",
        branch="integration/jarvis-prime-runtime",
        risk_class="RC4",
        acceptance_criteria=["owner approved"],
        rollback_plan="revert merge commit",
        owner_gated_actions=["merge to main"],
        owner_authorization_phrase="",
    )

    codes = {f.code for f in packet.validate()}
    assert "missing_owner_authorization" in codes
