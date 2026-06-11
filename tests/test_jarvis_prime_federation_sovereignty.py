"""Tests for the sovereignty index."""

import json

from hermes_cli.jarvis_prime.federation import KIND_SOVEREIGNTY_REPORT
from hermes_cli.jarvis_prime.federation.attestation import FederationRegistry
from hermes_cli.jarvis_prime.federation.sovereignty import compute_sovereignty_index
from hermes_cli.jarvis_prime.guardrail_evidence import GuardrailLedger


def test_fresh_deployment_scores_full(tmp_path):
    ledger = GuardrailLedger(tmp_path / "ledger.jsonl")
    ledger.append("test_seed", "s", {"n": 1})
    registry = FederationRegistry(tmp_path / "peers.json")
    report = compute_sovereignty_index(ledger=ledger, registry=registry)
    assert report.score == 1.0
    assert {c.check_id for c in report.checks} == {
        "ledger_verifiable",
        "owner_gates_enforced",
        "kill_switch_reachable",
        "local_first",
        "no_central_dependency",
        "non_amendable_core_intact",
    }


def test_tampered_ledger_drops_the_score(tmp_path):
    ledger = GuardrailLedger(tmp_path / "ledger.jsonl")
    ledger.append("test_seed", "s1", {"n": 1})
    ledger.append("test_seed", "s2", {"n": 2})
    lines = ledger.path.read_text(encoding="utf-8").splitlines()
    record = json.loads(lines[0])
    record["payload"] = {"n": 999}
    lines[0] = json.dumps(record, sort_keys=True)
    ledger.path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    report = compute_sovereignty_index(ledger=ledger)
    by_id = {c.check_id: c for c in report.checks}
    assert not by_id["ledger_verifiable"].passed
    assert report.score == 5 / 6


def test_record_appends_report_to_ledger(tmp_path):
    ledger = GuardrailLedger(tmp_path / "ledger.jsonl")
    ledger.append("test_seed", "s", {"n": 1})
    report = compute_sovereignty_index(ledger=ledger, record=True)
    records = ledger.read_all()
    assert records[-1].kind == KIND_SOVEREIGNTY_REPORT
    assert records[-1].payload["score"] == report.score
    assert ledger.verify_chain().ok
