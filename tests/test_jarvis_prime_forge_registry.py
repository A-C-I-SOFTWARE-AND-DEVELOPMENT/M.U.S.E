"""Tests for the content-addressed Forge candidate registry (the lookup)."""

import dataclasses

import pytest

from hermes_cli.jarvis_prime.forge import KIND_FORGE_REGISTER, ForgeError
from hermes_cli.jarvis_prime.forge.registry import CandidateRecord, CandidateRegistry
from hermes_cli.jarvis_prime.guardrail_evidence import GuardrailLedger

CODE = "def solve(xs):\n    return sum(xs)\n"


def _record(code=CODE, task_id="alg_sum"):
    return CandidateRecord.build(code=code, task_id=task_id, contributor_id="alice")


def test_register_resolve_round_trip(tmp_path):
    ledger = GuardrailLedger(tmp_path / "ledger.jsonl")
    registry = CandidateRegistry(tmp_path / "candidates.jsonl", ledger=ledger)
    record = registry.register(_record())
    assert record.candidate_id.startswith("cand_")
    resolved = registry.resolve(record.candidate_id)
    assert resolved.code == CODE
    assert [r.kind for r in ledger.read_all()] == [KIND_FORGE_REGISTER]
    # Persisted across reload.
    assert CandidateRegistry(tmp_path / "candidates.jsonl").resolve(record.candidate_id)


def test_resolve_unknown_id_fails_never_fuzzy_matches(tmp_path):
    registry = CandidateRegistry(tmp_path / "candidates.jsonl")
    registry.register(_record())
    with pytest.raises(ForgeError, match="unresolved"):
        registry.resolve("cand_doesnotexist00")


def test_same_content_reregister_is_idempotent(tmp_path):
    ledger = GuardrailLedger(tmp_path / "ledger.jsonl")
    registry = CandidateRegistry(tmp_path / "candidates.jsonl", ledger=ledger)
    first = registry.register(_record())
    second = registry.register(_record())
    assert first.candidate_id == second.candidate_id
    assert len(registry.all()) == 1
    assert len(ledger.read_all()) == 1  # no duplicate ledger entry


def test_lookalike_substitution_detected(tmp_path):
    registry = CandidateRegistry(tmp_path / "candidates.jsonl")
    genuine = registry.register(_record())
    # Forge a record claiming the genuine id but carrying different code.
    forged = dataclasses.replace(
        _record(code="def solve(xs):\n    return 0\n"),
        candidate_id=genuine.candidate_id,
    )
    with pytest.raises(ForgeError, match="lookalike"):
        registry.register(forged)
    # Tampered hash field is also caught.
    tampered = dataclasses.replace(_record(), payload_sha256="f" * 64)
    with pytest.raises(ForgeError, match="lookalike"):
        registry.register(tampered)


def test_lookup_by_hash_and_for_task(tmp_path):
    registry = CandidateRegistry(tmp_path / "candidates.jsonl")
    a = registry.register(_record())
    b = registry.register(_record(code="def solve(xs):\n    t=0\n    return t\n"))
    registry.register(_record(code="def other():\n    pass\n", task_id="alg_other"))
    by_hash = registry.lookup_by_hash(a.payload_sha256)
    assert by_hash is not None and by_hash.candidate_id == a.candidate_id
    assert registry.lookup_by_hash("0" * 64) is None
    assert {r.candidate_id for r in registry.for_task("alg_sum")} == {
        a.candidate_id,
        b.candidate_id,
    }
