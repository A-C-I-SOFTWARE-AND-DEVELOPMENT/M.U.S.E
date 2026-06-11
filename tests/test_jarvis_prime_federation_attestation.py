"""Tests for cross-attestation, peer registry, and divergence detection."""

import json

import pytest

from hermes_cli.jarvis_prime.federation import (
    KIND_DIVERGENCE,
    KIND_PEER_ATTESTATION,
    FederationError,
)
from hermes_cli.jarvis_prime.federation.attestation import (
    AttestationBundle,
    FederationRegistry,
    LedgerHeadAttestation,
    attest_local,
    detect_divergence,
)
from hermes_cli.jarvis_prime.federation import identity as identity_mod
from hermes_cli.jarvis_prime.federation.identity import init_identity
from hermes_cli.jarvis_prime.guardrail_evidence import EvidenceArtifact, GuardrailLedger


def _node(tmp_path, name="alpha"):
    node_dir = tmp_path / name
    identity = init_identity(name, dir=node_dir)
    ledger = GuardrailLedger(node_dir / "ledger.jsonl")
    ledger.append("test_seed", "s1", {"n": 1})
    ledger.append("test_seed", "s2", {"n": 2})
    return identity, ledger, node_dir


def test_attest_local_matches_verify_chain(tmp_path):
    identity, ledger, node_dir = _node(tmp_path)
    bundle = attest_local(ledger, identity, signature_dir=node_dir)
    diag = ledger.verify_chain()
    assert bundle.head.ledger_head_hash == diag.head_hash
    assert bundle.head.ledger_length == diag.length == 2
    assert bundle.node.node_id == identity.node_id
    assert bundle.head.constitution_version


def test_attest_local_refuses_broken_chain(tmp_path):
    identity, ledger, node_dir = _node(tmp_path)
    # Corrupt the first record's payload on disk.
    lines = ledger.path.read_text(encoding="utf-8").splitlines()
    record = json.loads(lines[0])
    record["payload"] = {"n": 999}
    lines[0] = json.dumps(record, sort_keys=True)
    ledger.path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert not ledger.verify_chain().ok
    with pytest.raises(FederationError):
        attest_local(ledger, identity, signature_dir=node_dir)


def test_bundle_file_round_trip_and_tamper_detection(tmp_path):
    identity, ledger, node_dir = _node(tmp_path)
    artifact = EvidenceArtifact.make(
        "test_result", producer="t", subject="pytest", payload={"passed": True}
    )
    bundle = attest_local(ledger, identity, artifacts=(artifact,), signature_dir=node_dir)
    path = bundle.write(tmp_path / "bundle.json")
    restored = AttestationBundle.read(path)
    assert restored.bundle_sha256 == bundle.bundle_sha256
    assert restored.artifacts[0].payload_sha256 == artifact.payload_sha256

    data = json.loads(path.read_text(encoding="utf-8"))
    data["head"]["ledger_head_hash"] = "f" * 64
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(FederationError):
        AttestationBundle.read(path)


def test_registry_records_peer_and_ledgers_it(tmp_path):
    identity, peer_ledger, node_dir = _node(tmp_path, "peer")
    bundle = attest_local(peer_ledger, identity, signature_dir=node_dir)
    local_ledger = GuardrailLedger(tmp_path / "local_ledger.jsonl")
    registry = FederationRegistry(tmp_path / "peers.json")
    record = registry.record(bundle, ledger=local_ledger)
    assert record.node_id == identity.node_id
    assert registry.head_history(identity.node_id) == {2: bundle.head.ledger_head_hash}
    kinds = [r.kind for r in local_ledger.read_all()]
    assert kinds == [KIND_PEER_ATTESTATION]
    assert local_ledger.verify_chain().ok
    # Registry persists across reload.
    assert FederationRegistry(tmp_path / "peers.json").get(identity.node_id) is not None


def test_split_brain_detected_and_refused(tmp_path):
    identity, peer_ledger, node_dir = _node(tmp_path, "peer")
    bundle_a = attest_local(peer_ledger, identity, signature_dir=node_dir)
    registry = FederationRegistry(tmp_path / "peers.json")
    local_ledger = GuardrailLedger(tmp_path / "local_ledger.jsonl")
    registry.record(bundle_a, ledger=local_ledger)

    # Same node, same length, different head hash.
    forged_head = LedgerHeadAttestation(
        node_id=identity.node_id,
        ledger_head_hash="e" * 64,
        ledger_length=bundle_a.head.ledger_length,
        constitution_version=bundle_a.head.constitution_version,
        created_at=bundle_a.head.created_at,
        payload_sha256=bundle_a.head.payload_sha256,
        signature={},
    )
    bundle_b = AttestationBundle.build(identity, forged_head)
    findings = detect_divergence(registry, bundle_b)
    assert [f.kind for f in findings] == ["split_brain"]

    with pytest.raises(FederationError):
        registry.record(bundle_b, ledger=local_ledger)
    kinds = [r.kind for r in local_ledger.read_all()]
    assert kinds == [KIND_PEER_ATTESTATION, KIND_DIVERGENCE]
    # The divergent head was never adopted.
    assert registry.head_history(identity.node_id)[bundle_a.head.ledger_length] == (
        bundle_a.head.ledger_head_hash
    )
    # allow_divergent overrides the refusal explicitly.
    registry.record(bundle_b, ledger=local_ledger, allow_divergent=True)


def test_fork_detected_when_chain_shrinks(tmp_path):
    identity, peer_ledger, node_dir = _node(tmp_path, "peer")
    bundle_long = attest_local(peer_ledger, identity, signature_dir=node_dir)  # length 2
    registry = FederationRegistry(tmp_path / "peers.json")
    registry.record(bundle_long)

    shrunk_head = LedgerHeadAttestation(
        node_id=identity.node_id,
        ledger_head_hash="d" * 64,
        ledger_length=1,
        constitution_version=bundle_long.head.constitution_version,
        created_at=bundle_long.head.created_at,
        payload_sha256=bundle_long.head.payload_sha256,
        signature={},
    )
    findings = detect_divergence(registry, AttestationBundle.build(identity, shrunk_head))
    assert findings and findings[0].kind == "fork"


def test_growing_chain_is_not_divergence(tmp_path):
    identity, peer_ledger, node_dir = _node(tmp_path, "peer")
    registry = FederationRegistry(tmp_path / "peers.json")
    registry.record(attest_local(peer_ledger, identity, signature_dir=node_dir))
    peer_ledger.append("test_seed", "s3", {"n": 3})
    bundle = attest_local(peer_ledger, identity, signature_dir=node_dir)
    assert detect_divergence(registry, bundle) == []
    record = registry.record(bundle)
    assert set(registry.head_history(identity.node_id)) == {2, 3}
    assert record.last_seen


def test_hmac_identity_is_admissible_but_unverified(tmp_path, monkeypatch):
    monkeypatch.setattr(identity_mod, "_ED25519_AVAILABLE", False)
    identity, ledger, node_dir = _node(tmp_path, "hmac-node")
    assert identity.algo == "hmac-sha256"
    assert identity.public_key_hex == ""
    bundle = attest_local(ledger, identity, signature_dir=node_dir)
    assert bundle.head.signature.get("algo") == "hmac-sha256"
    registry = FederationRegistry(tmp_path / "peers.json")
    record = registry.record(bundle)
    assert record.signature_verified is False  # honest: hash-anchored, not signature-verified
