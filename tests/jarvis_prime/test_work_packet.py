"""Baseline tests for the JARVIS Prime WorkPacket data contract (Wave 0)."""

from datetime import datetime

import pytest

from hermes_cli.jarvis_prime import (
    VALID_RISK_CLASSES,
    WorkPacket,
    WorkPacketValidationFinding,
)


def _complete_packet(**overrides):
    """Return a minimally-valid WorkPacket; overrides win."""
    base = dict(
        mission="Lock the JARVIS Prime foundation.",
        repo_root="/home/user/hermes-agent",
        branch="claude/jarvis-foundation-lock-cL37G",
        risk_class="RC1",
        allowed_files=["hermes_cli/jarvis_prime/work_packet.py"],
        protected_files=["main"],
        non_goals=["semantic immune layer"],
        acceptance_criteria=["WorkPacket model exists and validates"],
        files_changed=["hermes_cli/jarvis_prime/work_packet.py"],
        tests_run=["tests/jarvis_prime"],
        tests_failed=[],
        verification_summary="pytest tests/jarvis_prime -q passed",
        rollback_plan="git revert the foundation commit",
        owner_gated_actions=[],
        owner_authorization_phrase="",
        citations=["docs/jarvis-prime-wave-plan.md"],
        confidence=0.8,
    )
    base.update(overrides)
    return WorkPacket(**base)


class TestWorkPacketCreation:
    def test_default_construction_uses_safe_defaults(self):
        wp = WorkPacket()
        assert wp.mission == ""
        assert wp.allowed_files == []
        assert wp.owner_gated_actions == []
        assert isinstance(wp.created_at, str) and wp.created_at

    def test_created_at_is_timezone_aware_utc(self):
        wp = WorkPacket()
        parsed = datetime.fromisoformat(wp.created_at)
        assert parsed.tzinfo is not None
        # UTC offset should be zero
        assert parsed.utcoffset().total_seconds() == 0

    def test_default_list_fields_are_independent(self):
        wp1 = WorkPacket()
        wp2 = WorkPacket()
        wp1.allowed_files.append("a")
        assert wp2.allowed_files == []


class TestWorkPacketSerialization:
    def test_to_dict_round_trip(self):
        wp = _complete_packet()
        d = wp.to_dict()
        assert d["mission"] == wp.mission
        assert d["allowed_files"] == wp.allowed_files
        assert d["confidence"] == wp.confidence
        assert d["created_at"] == wp.created_at

    def test_from_dict_restores_fields(self):
        wp = _complete_packet()
        restored = WorkPacket.from_dict(wp.to_dict())
        assert restored.mission == wp.mission
        assert restored.risk_class == wp.risk_class
        assert restored.acceptance_criteria == wp.acceptance_criteria
        assert restored.confidence == wp.confidence

    def test_from_dict_ignores_unknown_keys(self):
        wp = WorkPacket.from_dict(
            {
                "mission": "demo",
                "repo_root": "/tmp/x",
                "branch": "demo",
                "risk_class": "RC0",
                "rollback_plan": "git reset",
                "acceptance_criteria": ["one"],
                "confidence": 0.5,
                "this_is_not_a_field": "ignored",
            }
        )
        assert wp.mission == "demo"
        assert not hasattr(wp, "this_is_not_a_field")

    def test_from_dict_rejects_non_dict(self):
        with pytest.raises(TypeError):
            WorkPacket.from_dict(["not", "a", "dict"])

    def test_from_dict_clamps_confidence(self):
        too_high = WorkPacket.from_dict({"confidence": 5.0})
        too_low = WorkPacket.from_dict({"confidence": -0.3})
        garbage = WorkPacket.from_dict({"confidence": "banana"})
        assert too_high.confidence == 1.0
        assert too_low.confidence == 0.0
        assert garbage.confidence == 0.0


class TestWorkPacketValidation:
    def test_complete_packet_has_no_findings(self):
        assert _complete_packet().validate() == []

    def test_missing_required_fields_are_reported(self):
        wp = WorkPacket()
        findings = wp.validate()
        reported = {f.field for f in findings}
        for required in (
            "mission",
            "repo_root",
            "branch",
            "risk_class",
            "rollback_plan",
            "acceptance_criteria",
        ):
            assert required in reported, f"expected {required} in findings"

    def test_invalid_risk_class_is_reported(self):
        wp = _complete_packet(risk_class="RC9")
        findings = wp.validate()
        invalid = [f for f in findings if f.field == "risk_class"]
        assert invalid, "expected a finding for invalid risk_class"
        assert invalid[0].code == "invalid"

    def test_every_documented_risk_class_validates(self):
        for rc in VALID_RISK_CLASSES:
            wp = _complete_packet(risk_class=rc)
            assert all(f.field != "risk_class" for f in wp.validate()), rc

    def test_confidence_out_of_range_is_reported(self):
        wp_high = _complete_packet(confidence=1.5)
        wp_low = _complete_packet(confidence=-0.1)
        for wp in (wp_high, wp_low):
            findings = [f for f in wp.validate() if f.field == "confidence"]
            assert findings, "expected confidence finding"
            assert findings[0].code == "out_of_range"

    def test_confidence_non_numeric_is_reported(self):
        wp = _complete_packet(confidence="not-a-number")
        findings = [f for f in wp.validate() if f.field == "confidence"]
        assert findings, "expected confidence finding"
        assert findings[0].code == "invalid"

    def test_findings_are_structured_dataclasses(self):
        wp = WorkPacket()
        for f in wp.validate():
            assert isinstance(f, WorkPacketValidationFinding)
            assert isinstance(f.to_dict(), dict)
            assert set(f.to_dict().keys()) == {"field", "code", "message"}


class TestOwnerGatedActions:
    def test_owner_gated_actions_are_preserved_as_data(self):
        wp = _complete_packet(
            owner_gated_actions=["merge to main", "publish package"],
            owner_authorization_phrase="Yes, with authorization.",
        )
        assert wp.owner_gated_actions == ["merge to main", "publish package"]
        # validate() does not raise, does not execute, does not mutate
        assert wp.validate() == []
        assert wp.owner_gated_actions == ["merge to main", "publish package"]

    def test_owner_gated_actions_without_authorization_phrase_are_reported(self):
        wp = _complete_packet(
            owner_gated_actions=["merge to main"],
            owner_authorization_phrase="",
        )
        findings = [f for f in wp.validate() if f.field == "owner_authorization_phrase"]
        assert findings, "expected an owner_authorization_phrase finding"
        assert findings[0].code == "missing"

    def test_no_method_executes_owner_gated_actions(self):
        # The contract is that WorkPacket holds owner-gated actions as data.
        # There must be no method that runs them.
        wp = _complete_packet(owner_gated_actions=["deploy production"])
        for attr in dir(wp):
            if attr.startswith("_"):
                continue
            name = attr.lower()
            assert "execute" not in name, f"unexpected executor on WorkPacket: {attr}"
            assert "deploy" not in name, f"unexpected deploy method on WorkPacket: {attr}"
            assert "publish" not in name, f"unexpected publish method on WorkPacket: {attr}"
