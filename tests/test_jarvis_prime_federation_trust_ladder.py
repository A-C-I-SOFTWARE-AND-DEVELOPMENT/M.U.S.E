"""Tests for the contributor trust ladder (federation/trust_ladder.py)."""

from typing import Any, cast

import pytest

from hermes_cli.jarvis_prime.federation import KIND_BAND_CHANGE, FederationError
from hermes_cli.jarvis_prime.federation.quorum_auth import (
    QuorumPolicy,
    create_quorum_challenge,
    finalize,
    respond,
)
from hermes_cli.jarvis_prime.federation.trust_ladder import (
    BAND_MAX_RISK_CLASS,
    ContributorBand,
    ContributorRecord,
    ContributorStore,
    evaluate_band,
    max_risk_class,
    promote_to_maintainer,
)
from hermes_cli.jarvis_prime.guardrail_evidence import GuardrailLedger


def _quorum_grant():
    quorum = create_quorum_challenge(
        "registry_mutation", policy=QuorumPolicy(threshold=1, signers=("owner",))
    )
    respond(quorum, "owner", quorum.per_signer["owner"].required_phrase)
    grant = finalize(quorum)
    assert grant is not None
    return grant


def test_new_contributor_starts_propose_only(tmp_path):
    store = ContributorStore(tmp_path / "contributors.json")
    record = store.get("alice")
    assert record.band == ContributorBand.B0
    assert max_risk_class(record.band) == "propose_only"


def test_track_record_promotes_through_b1_to_b2(tmp_path):
    store = ContributorStore(tmp_path / "contributors.json")
    ledger = GuardrailLedger(tmp_path / "ledger.jsonl")
    for _ in range(5):
        record = store.record_outcome("bob", accepted=True, ledger=ledger)
    assert record.band == ContributorBand.B1
    for _ in range(20):
        record = store.record_outcome("bob", accepted=True, ledger=ledger)
    assert record.band == ContributorBand.B2
    changes = [r for r in ledger.read_all() if r.kind == KIND_BAND_CHANGE]
    assert [(c.payload["from"], c.payload["to"]) for c in changes] == [
        ("B0", "B1"),
        ("B1", "B2"),
    ]
    assert ledger.verify_chain().ok


def test_low_acceptance_rate_blocks_b2():
    record = ContributorRecord("carol", accepted=25, rejected=25)
    assert record.acceptance_rate == 0.5
    assert evaluate_band(record) == ContributorBand.B1


def test_b3_is_never_automatic():
    record = ContributorRecord("dave", accepted=1000, rejected=0)
    assert evaluate_band(record) == ContributorBand.B2


def test_b3_requires_real_grant(tmp_path):
    store = ContributorStore(tmp_path / "contributors.json")
    ledger = GuardrailLedger(tmp_path / "ledger.jsonl")
    record = store.get("erin")
    not_a_grant = cast(Any, {"action": "fake"})
    with pytest.raises(FederationError):
        promote_to_maintainer(record, not_a_grant, store=store, ledger=ledger)
    promoted = promote_to_maintainer(record, _quorum_grant(), store=store, ledger=ledger)
    assert promoted.band == ContributorBand.B3
    change = [r for r in ledger.read_all() if r.kind == KIND_BAND_CHANGE][-1]
    assert change.payload["cause"] == "maintainer_grant"
    # B3 with a clean record is preserved by re-evaluation.
    assert evaluate_band(promoted) == ContributorBand.B3


def test_fatal_floors_even_a_maintainer(tmp_path):
    store = ContributorStore(tmp_path / "contributors.json")
    ledger = GuardrailLedger(tmp_path / "ledger.jsonl")
    record = store.get("frank")
    record.accepted = 100
    promote_to_maintainer(record, _quorum_grant(), store=store, ledger=ledger)
    floored = store.record_outcome("frank", accepted=False, fatal=True, ledger=ledger)
    assert floored.band == ContributorBand.B0
    change = [r for r in ledger.read_all() if r.kind == KIND_BAND_CHANGE][-1]
    assert change.payload["cause"] == "fatal_violation"
    with pytest.raises(FederationError):
        promote_to_maintainer(floored, _quorum_grant(), store=store)


def test_max_risk_class_table_complete():
    assert {b: max_risk_class(b) for b in ContributorBand} == BAND_MAX_RISK_CLASS
    assert BAND_MAX_RISK_CLASS[ContributorBand.B1] == "RC1"
    assert BAND_MAX_RISK_CLASS[ContributorBand.B3] == "RC2"  # no band reaches RC3+


def test_store_persists_across_reload(tmp_path):
    path = tmp_path / "contributors.json"
    store = ContributorStore(path)
    for _ in range(5):
        store.record_outcome("grace", accepted=True)
    reloaded = ContributorStore(path)
    assert reloaded.get("grace").band == ContributorBand.B1
