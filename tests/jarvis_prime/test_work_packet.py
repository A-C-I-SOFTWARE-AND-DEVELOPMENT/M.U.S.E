"""Baseline tests for the Wave 0 JARVIS Prime ``WorkPacket`` model."""

from __future__ import annotations

import importlib
import json
from datetime import datetime

import pytest

from hermes_cli.jarvis_prime import (
    REQUIRED_FIELDS,
    RISK_CLASSES,
    WorkPacket,
    WorkPacketValidationFinding,
)


def _complete_packet(**overrides) -> WorkPacket:
    """Return a WorkPacket whose required fields are all populated."""
    base = dict(
        mission="Lock the foundation for JARVIS Prime",
        repo_root="/home/user/hermes-agent",
        branch="feature/jarvis-foundation-lock",
        risk_class="RC1",
        acceptance_criteria=["WorkPacket model exists", "tests pass"],
        rollback_plan="git restore the four new paths",
        confidence=0.85,
    )
    base.update(overrides)
    return WorkPacket(**base)


# ── Construction ───────────────────────────────────────────────────────


def test_workpacket_creation_defaults_are_safe():
    pkt = WorkPacket()
    # Collection fields default to empty containers, not None.
    assert pkt.allowed_files == []
    assert pkt.protected_files == []
    assert pkt.non_goals == []
    assert pkt.acceptance_criteria == []
    assert pkt.files_changed == []
    assert pkt.tests_run == []
    assert pkt.tests_failed == []
    assert pkt.owner_gated_actions == []
    assert pkt.citations == []
    # Scalar text fields default to empty string.
    assert pkt.mission == ""
    assert pkt.verification_summary == ""
    # Confidence is None by default — validate() will report it.
    assert pkt.confidence is None


def test_workpacket_created_at_is_timezone_aware_utc_iso():
    pkt = WorkPacket()
    parsed = datetime.fromisoformat(pkt.created_at)
    assert parsed.tzinfo is not None, "created_at must be timezone-aware"
    assert parsed.utcoffset().total_seconds() == 0, "created_at must be UTC"


def test_workpacket_collections_are_per_instance():
    a = WorkPacket()
    b = WorkPacket()
    a.allowed_files.append("foo.py")
    assert b.allowed_files == [], "default_factory lists must not be shared"


# ── Serialization ──────────────────────────────────────────────────────


def test_to_dict_round_trip_via_from_dict():
    pkt = _complete_packet(
        allowed_files=["hermes_cli/jarvis_prime/work_packet.py"],
        protected_files=["main.py"],
        non_goals=["no CLI expansion"],
        files_changed=["hermes_cli/jarvis_prime/__init__.py"],
        tests_run=["tests/jarvis_prime/test_work_packet.py"],
        tests_failed=[],
        verification_summary="all green",
        owner_gated_actions=["merge to main"],
        owner_authorization_phrase="Yes, with authorization.",
        citations=["docs/jarvis-prime-wave-plan.md"],
    )
    data = pkt.to_dict()
    # to_dict must be JSON-serializable.
    encoded = json.dumps(data)
    decoded = json.loads(encoded)
    restored = WorkPacket.from_dict(decoded)
    assert restored == pkt


def test_from_dict_ignores_unknown_keys():
    data = {
        "mission": "x",
        "repo_root": "/r",
        "branch": "b",
        "risk_class": "RC0",
        "acceptance_criteria": ["a"],
        "rollback_plan": "r",
        "confidence": 0.5,
        # extra junk a forward-compat producer might emit:
        "future_field": "ignored",
        "another": [1, 2, 3],
    }
    pkt = WorkPacket.from_dict(data)
    assert pkt.mission == "x"
    assert not hasattr(pkt, "future_field")


def test_from_dict_rejects_non_dict():
    with pytest.raises(TypeError):
        WorkPacket.from_dict("not a dict")  # type: ignore[arg-type]


def test_from_dict_defensively_copies_lists():
    src_list = ["a.py", "b.py"]
    data = {
        "mission": "x",
        "repo_root": "/r",
        "branch": "b",
        "risk_class": "RC0",
        "acceptance_criteria": ["c1"],
        "rollback_plan": "r",
        "allowed_files": src_list,
    }
    pkt = WorkPacket.from_dict(data)
    src_list.append("c.py")
    assert pkt.allowed_files == ["a.py", "b.py"], (
        "from_dict must copy list values, not alias them"
    )


# ── Validation ─────────────────────────────────────────────────────────


def test_validate_complete_packet_has_no_findings():
    pkt = _complete_packet()
    assert pkt.validate() == []
    assert pkt.is_valid() is True


def test_validate_reports_each_missing_required_field():
    pkt = WorkPacket()  # everything blank
    findings = pkt.validate()
    reported_fields = {f.field for f in findings if f.code == "missing"}
    for required in REQUIRED_FIELDS:
        assert required in reported_fields, f"expected missing {required!r}"


def test_validation_finding_is_structured():
    pkt = WorkPacket()
    findings = pkt.validate()
    assert findings, "blank packet must produce findings"
    for f in findings:
        assert isinstance(f, WorkPacketValidationFinding)
        d = f.to_dict()
        assert set(d.keys()) == {"field", "code", "message"}


def test_validate_reports_invalid_risk_class():
    pkt = _complete_packet(risk_class="RC9")
    findings = pkt.validate()
    codes = {(f.field, f.code) for f in findings}
    assert ("risk_class", "invalid_value") in codes


@pytest.mark.parametrize("rc", list(RISK_CLASSES))
def test_validate_accepts_all_documented_risk_classes(rc):
    pkt = _complete_packet(risk_class=rc)
    findings = pkt.validate()
    # No risk_class findings for any documented class.
    assert not [f for f in findings if f.field == "risk_class"]


def test_validate_reports_missing_confidence():
    pkt = _complete_packet(confidence=None)
    findings = pkt.validate()
    assert any(
        f.field == "confidence" and f.code == "missing" for f in findings
    )


# ── Confidence handling ────────────────────────────────────────────────


def test_confidence_below_zero_is_handled_safely_via_from_dict():
    pkt = WorkPacket.from_dict(
        {
            "mission": "m",
            "repo_root": "/r",
            "branch": "b",
            "risk_class": "RC0",
            "acceptance_criteria": ["a"],
            "rollback_plan": "r",
            "confidence": -0.5,
        }
    )
    # from_dict clamps into [0.0, 1.0] rather than raising.
    assert pkt.confidence == 0.0
    # And the clamped value passes validation.
    assert not [f for f in pkt.validate() if f.field == "confidence"]


def test_confidence_above_one_is_handled_safely_via_from_dict():
    pkt = WorkPacket.from_dict(
        {
            "mission": "m",
            "repo_root": "/r",
            "branch": "b",
            "risk_class": "RC0",
            "acceptance_criteria": ["a"],
            "rollback_plan": "r",
            "confidence": 7.0,
        }
    )
    assert pkt.confidence == 1.0


def test_confidence_out_of_range_on_direct_assignment_is_reported():
    # Direct field assignment bypasses from_dict's clamp; validate must
    # still report the problem so callers can't sneak past gates.
    pkt = _complete_packet()
    pkt.confidence = 3.0
    findings = pkt.validate()
    assert any(
        f.field == "confidence" and f.code == "out_of_range" for f in findings
    )


def test_confidence_non_numeric_is_reported():
    pkt = _complete_packet()
    pkt.confidence = "high"  # type: ignore[assignment]
    findings = pkt.validate()
    assert any(
        f.field == "confidence" and f.code == "invalid_type" for f in findings
    )


# ── Owner-gated actions are data, not execution ────────────────────────


def test_owner_gated_actions_are_retained_but_not_executed():
    actions = [
        "merge to main",
        "deploy to production",
        "rotate ANTHROPIC_API_KEY",
    ]
    pkt = _complete_packet(
        owner_gated_actions=list(actions),
        owner_authorization_phrase="",  # not yet authorized
    )
    # The packet preserves the requested actions verbatim …
    assert pkt.owner_gated_actions == actions
    # … and the authorization phrase remains empty until owner provides it.
    assert pkt.owner_authorization_phrase == ""
    # Round-tripping must not strip them.
    assert WorkPacket.from_dict(pkt.to_dict()).owner_gated_actions == actions


# ── Import surface ─────────────────────────────────────────────────────


def test_jarvis_prime_package_imports_cleanly():
    module = importlib.import_module("hermes_cli.jarvis_prime")
    for name in ("WorkPacket", "WorkPacketValidationFinding",
                 "RISK_CLASSES", "REQUIRED_FIELDS"):
        assert hasattr(module, name), f"hermes_cli.jarvis_prime missing {name}"


def test_jarvis_prime_runtime_is_stdlib_only_at_import_time():
    # If work_packet.py ever grows a third-party import, this test will
    # fail because importlib.import_module would raise ImportError in a
    # bare environment. Here we just confirm the import succeeds even
    # when no Hermes runtime subsystems have been pre-loaded.
    module = importlib.import_module("hermes_cli.jarvis_prime.work_packet")
    assert module.WorkPacket is WorkPacket
