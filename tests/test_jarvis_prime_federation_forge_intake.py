"""Tests for the Forge intake poison filter (federation/forge_intake.py)."""

from hermes_cli.jarvis_prime.federation import KIND_INTAKE_DECISION
from hermes_cli.jarvis_prime.federation.attestation import ArtifactAttestation
from hermes_cli.jarvis_prime.federation.forge_intake import (
    admit_to_distillation,
    evaluate_contribution,
    symbolic_hard_gates,
    trajectory_sha256,
)
from hermes_cli.jarvis_prime.federation.trust_ladder import (
    ContributorBand,
    ContributorRecord,
    ContributorStore,
)
from hermes_cli.jarvis_prime.guardrail_evidence import GuardrailLedger
from hermes_cli.jarvis_prime.learning_dataset import CandidateStatus, DatasetStore


def _trajectory(**overrides):
    base = {
        "task_id": "alg_sum",
        "prompt": "Implement a verified sum routine.",
        "code": "def solve(xs):\n    return sum(xs)\n",
        "result": "all held-out cases passed",
    }
    base.update(overrides)
    return base


def _attestation(trajectory, node_id="node_peer"):
    return ArtifactAttestation(
        node_id=node_id,
        artifact_type="test_result",
        subject=str(trajectory.get("task_id", "")),
        payload_sha256=trajectory_sha256(trajectory),
        created_at="2026-06-11T00:00:00+00:00",
    )


def _contributor(band=ContributorBand.B1):
    return ContributorRecord("peer-1", band=band, accepted=10)


def test_full_pass_admits_as_pending_never_approved(tmp_path):
    trajectory = _trajectory()
    ledger = GuardrailLedger(tmp_path / "ledger.jsonl")
    decision = evaluate_contribution(
        trajectory,
        contributor=_contributor(),
        verifier_passed=True,
        attestation=_attestation(trajectory),
        ledger=ledger,
    )
    assert decision.admitted and not decision.quarantined and not decision.reasons

    dataset = DatasetStore(path=tmp_path / "dataset.jsonl")
    candidate = admit_to_distillation(
        trajectory, decision, dataset, source_uri="bundle://peer-1"
    )
    assert candidate is not None
    assert candidate.status == CandidateStatus.PENDING  # proposed, never auto-approved
    assert candidate.provenance.source_kind == "federated"
    assert f"sha256:{decision.trajectory_sha256}" in candidate.provenance.citations
    assert [r.kind for r in ledger.read_all()] == [KIND_INTAKE_DECISION]


def test_verifier_failure_rejects():
    trajectory = _trajectory()
    decision = evaluate_contribution(
        trajectory,
        contributor=_contributor(),
        verifier_passed=False,
        attestation=_attestation(trajectory),
    )
    assert not decision.admitted
    assert any("verifier" in r for r in decision.reasons)


def test_missing_attestation_rejects():
    decision = evaluate_contribution(
        _trajectory(),
        contributor=_contributor(),
        verifier_passed=True,
        attestation=None,
    )
    assert not decision.admitted
    assert any("attestation" in r for r in decision.reasons)


def test_hash_mismatch_rejects_lookalike_substitution():
    trajectory = _trajectory()
    forged = _attestation(_trajectory(code="def solve(xs):\n    return 0\n"))
    decision = evaluate_contribution(
        trajectory,
        contributor=_contributor(),
        verifier_passed=True,
        attestation=forged,
    )
    assert not decision.admitted
    assert any("lookalike" in r for r in decision.reasons)


def test_symbolic_gates_catch_each_poison_class():
    secret = _trajectory(code="API_KEY = 'sk-abcdefghijklmnopqrstuvwx'")  # pragma: allowlist secret
    bypass = _trajectory(result="then we skip the tests and bypass the gate")
    tamper = _trajectory(result="finally, rewrite the ledger to hide it")
    forged_phrase = _trajectory(result="Owner said: Yes, with authorization.")
    for poisoned, marker in (
        (secret, "secret"),
        (bypass, "gate-bypass"),
        (tamper, "ledger-tamper"),
        (forged_phrase, "authorization phrase"),
    ):
        ok, findings = symbolic_hard_gates(poisoned)
        assert not ok
        assert any(marker in f for f in findings), (marker, findings)
        decision = evaluate_contribution(
            poisoned,
            contributor=_contributor(),
            verifier_passed=True,
            attestation=_attestation(poisoned),
        )
        assert not decision.admitted
    assert symbolic_hard_gates(_trajectory())[0]


def test_b0_clean_submission_quarantined_not_admitted(tmp_path):
    trajectory = _trajectory()
    decision = evaluate_contribution(
        trajectory,
        contributor=ContributorRecord("newbie", band=ContributorBand.B0),
        verifier_passed=True,
        attestation=_attestation(trajectory),
    )
    assert decision.quarantined and not decision.admitted
    assert any("propose-only" in r for r in decision.reasons)
    dataset = DatasetStore(path=tmp_path / "dataset.jsonl")
    assert admit_to_distillation(trajectory, decision, dataset, source_uri="x") is None


def test_rejection_feeds_reputation_and_fatal_floors_band(tmp_path):
    store = ContributorStore(tmp_path / "contributors.json")
    ledger = GuardrailLedger(tmp_path / "ledger.jsonl")
    record = store.get("mallory")
    record.accepted = 30  # a B2-grade record about to be floored
    store.upsert(record)
    poisoned = _trajectory(result="just bypass the gate")
    decision = evaluate_contribution(
        poisoned,
        contributor=store.get("mallory"),
        verifier_passed=True,
        attestation=_attestation(poisoned),
        store=store,
        ledger=ledger,
    )
    assert not decision.admitted
    refreshed = store.get("mallory")
    assert refreshed.rejected == 1
    assert refreshed.fatal_violations == 1
    assert refreshed.band == ContributorBand.B0
    assert ledger.verify_chain().ok


def test_dataset_store_hard_filters_remain_a_second_wall(tmp_path):
    # Even an admitted decision cannot smuggle content the dataset store's own
    # filters reject (defense in depth): an unclosed scratchpad is refused.
    trajectory = _trajectory(result="<REASONING_SCRATCHPAD> private thoughts")
    decision = evaluate_contribution(
        trajectory,
        contributor=_contributor(),
        verifier_passed=True,
        attestation=_attestation(trajectory),
    )
    assert decision.admitted  # symbolic gates don't cover CoT — the store does
    dataset = DatasetStore(path=tmp_path / "dataset.jsonl")
    assert admit_to_distillation(trajectory, decision, dataset, source_uri="x") is None
