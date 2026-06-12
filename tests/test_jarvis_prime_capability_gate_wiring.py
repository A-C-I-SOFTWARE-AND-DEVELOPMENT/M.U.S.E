"""Tests for wiring the opt-in capability gate into the strict-gate path.

Default-off keeps the 8-gate strict suite unchanged; HERMES_CAPABILITY_GATE=1
appends a capability gate that enforces a passing attestation for RC2+ work.
"""

from muse_cli.jarvis_prime import capability_wall as cw
from muse_cli.jarvis_prime.gates import GateOutcome, run_strict_gate_summary
from muse_cli.jarvis_prime.guardrail_evidence import GuardrailEvidenceBundle
from muse_cli.jarvis_prime.self_audit import compliant_target


def _cap(summary):
    return next((r for r in summary.results if r.name == "capability"), None)


def test_capability_gate_absent_by_default(monkeypatch):
    monkeypatch.delenv("HERMES_CAPABILITY_GATE", raising=False)
    summary = run_strict_gate_summary(
        {"risk_class": "RC3", "packet_id": "p"}, GuardrailEvidenceBundle(packet_id="p")
    )
    assert _cap(summary) is None
    assert len(summary.results) == 8


def test_capability_gate_fails_rc3_without_attestation(monkeypatch):
    monkeypatch.setenv("HERMES_CAPABILITY_GATE", "1")
    summary = run_strict_gate_summary(
        {"risk_class": "RC3", "packet_id": "p"}, GuardrailEvidenceBundle(packet_id="p")
    )
    cap = _cap(summary)
    assert cap is not None and cap.outcome == GateOutcome.FAIL


def test_capability_gate_passes_rc3_with_attestation(monkeypatch):
    monkeypatch.setenv("HERMES_CAPABILITY_GATE", "1")
    bundle = GuardrailEvidenceBundle(packet_id="p")
    bundle.add(cw.run_wall(compliant_target, "RC3", run_id="g").to_artifact())
    summary = run_strict_gate_summary({"risk_class": "RC3", "packet_id": "p"}, bundle)
    cap = _cap(summary)
    assert cap is not None and cap.outcome == GateOutcome.PASS


def test_capability_gate_skips_low_rc_when_enabled(monkeypatch):
    monkeypatch.setenv("HERMES_CAPABILITY_GATE", "1")
    summary = run_strict_gate_summary(
        {"risk_class": "RC1", "packet_id": "p"}, GuardrailEvidenceBundle(packet_id="p")
    )
    cap = _cap(summary)
    assert cap is not None and cap.outcome == GateOutcome.PASS
