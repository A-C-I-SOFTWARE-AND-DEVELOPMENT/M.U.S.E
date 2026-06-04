"""Tests for the capability-band behavioral wall (the RSP analogue).

Behavior-focused: a compliant target attests RC3, a non-compliant one is
withheld, RC4 is blocked, the wall runs on the held-out core pool, the card +
attestation artifact verify, and the opt-in capability gate behaves correctly.
"""

from hermes_cli.jarvis_prime import capability_wall as cw
from hermes_cli.jarvis_prime.gates import GateOutcome
from hermes_cli.jarvis_prime.guardrail_evidence import (
    ARTIFACT_CAPABILITY_ATTESTATION,
    GuardrailEvidenceBundle,
    GuardrailLedger,
)
from hermes_cli.jarvis_prime.self_audit import (
    compliant_target,
    noncompliant_target,
    select_seeds,
)


def test_compliant_target_attests_rc3():
    result = cw.run_wall(compliant_target, "RC3", run_id="t")
    assert result.passed
    assert result.shortfalls == []


def test_noncompliant_target_is_withheld_with_fatal():
    result = cw.run_wall(noncompliant_target, "RC3", run_id="t")
    assert not result.passed
    assert result.shortfalls
    assert result.fatal_violations > 0


def test_rc4_is_blocked_outright():
    result = cw.run_wall(compliant_target, "RC4", run_id="t")
    assert not result.passed


def test_wall_uses_held_out_core_pool():
    # The wall runs the core pool; dev-only seeds (e.g. S14) are not used, so
    # the gate is never tuned against its own ruler.
    core_ids = {s.id for s in select_seeds(pool="core")}
    dev_ids = {s.id for s in select_seeds(pool="dev")}
    assert core_ids and core_ids.isdisjoint(dev_ids)
    assert "S14" in dev_ids and "S14" not in core_ids


def test_capability_card_and_artifact_verify():
    result = cw.run_wall(compliant_target, "RC2", run_id="card")
    card = result.capability_card()
    assert card["band"] == "RC2"
    assert card["verdict"] == "attested"
    artifact = result.to_artifact()
    assert artifact.artifact_type == ARTIFACT_CAPABILITY_ATTESTATION
    assert artifact.verify_payload()
    assert artifact.payload["passed"] is True


def test_record_appends_verifiable_attestation(tmp_path):
    result = cw.run_wall(compliant_target, "RC2", run_id="rec")
    ledger = GuardrailLedger(path=tmp_path / "ledger.jsonl")
    record = result.record(ledger)
    assert record.kind == ARTIFACT_CAPABILITY_ATTESTATION
    assert ledger.verify_chain().ok


def test_capability_gate_disabled_by_default():
    assert cw.capability_gate({"risk_class": "RC3"}, None).outcome == GateOutcome.SKIPPED


def test_capability_gate_passes_low_risk_when_enabled():
    res = cw.capability_gate({"risk_class": "RC1"}, None, enabled=True)
    assert res.outcome == GateOutcome.PASS


def test_capability_gate_requires_attestation_for_rc3():
    empty = GuardrailEvidenceBundle(packet_id="p")
    assert cw.capability_gate({"risk_class": "RC3"}, empty, enabled=True).outcome == GateOutcome.FAIL

    bundle = GuardrailEvidenceBundle(packet_id="p")
    bundle.add(cw.run_wall(compliant_target, "RC3", run_id="g").to_artifact())
    assert cw.capability_gate({"risk_class": "RC3"}, bundle, enabled=True).outcome == GateOutcome.PASS


def test_capability_gate_rejects_insufficient_band():
    # An RC2 attestation does not satisfy an RC3 packet.
    bundle = GuardrailEvidenceBundle(packet_id="p")
    bundle.add(cw.run_wall(compliant_target, "RC2", run_id="g2").to_artifact())
    assert cw.capability_gate({"risk_class": "RC3"}, bundle, enabled=True).outcome == GateOutcome.FAIL
