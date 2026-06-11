"""Tests for the compliance evidence matrix and live evidence package."""

from pathlib import Path

import pytest

from hermes_cli.jarvis_prime.federation import (
    KIND_COMPLIANCE_EXPORT,
    KIND_QUORUM_GRANT,
)
from hermes_cli.jarvis_prime.federation.compliance_matrix import (
    CONTROL_MAPPINGS,
    EvidencePackage,
    generate_evidence_package,
    mappings_for,
)
from hermes_cli.jarvis_prime.guardrail_evidence import (
    ARTIFACT_OWNER_GRANT,
    GuardrailLedger,
)

_DOC = (
    Path(__file__).resolve().parents[1]
    / "docs"
    / "federation"
    / "compliance-evidence-matrix.md"
)


def test_eu_ai_act_articles_all_mapped():
    ids = {m.control_id for m in mappings_for("eu_ai_act")}
    assert ids == {"Art9", "Art11", "Art12", "Art14", "Art15"}


def test_every_control_id_in_spec_doc():
    text = _DOC.read_text(encoding="utf-8")
    for mapping in CONTROL_MAPPINGS:
        assert f"**{mapping.control_id}**" in text, mapping.control_id


def test_mappings_for_validates_framework():
    assert mappings_for("all") == CONTROL_MAPPINGS
    assert all(m.framework == "soc2" for m in mappings_for("soc2"))
    with pytest.raises(ValueError):
        mappings_for("hipaa")


def test_package_built_from_live_ledger(tmp_path):
    ledger = GuardrailLedger(tmp_path / "ledger.jsonl")
    ledger.append("gate_summary", "packet-1", {"overall": "pass"})
    ledger.append(ARTIFACT_OWNER_GRANT, "spend_money", {"granted": True})
    ledger.append(KIND_QUORUM_GRANT, "quorum-1", {"threshold": 2})

    package = generate_evidence_package("eu_ai_act", ledger=ledger, record=True)
    diag = package.chain_diagnostics
    assert diag["ok"] is True
    # The export itself was appended *after* the diagnostics snapshot.
    assert diag["length"] == 3
    assert package.owner_grant_count == 1
    assert package.quorum_grant_count == 1
    assert package.ledger_kind_histogram["gate_summary"] == 1
    assert package.constitution_version == "1.1"
    assert package.sovereignty["score"] >= 5 / 6
    assert {c["control_id"] for c in package.controls} == {
        "Art9",
        "Art11",
        "Art12",
        "Art14",
        "Art15",
    }
    records = ledger.read_all()
    assert records[-1].kind == KIND_COMPLIANCE_EXPORT
    assert records[-1].payload["package_sha256"] == package.package_sha256
    assert ledger.verify_chain().ok


def test_package_hash_is_recomputable_and_tamper_evident(tmp_path):
    ledger = GuardrailLedger(tmp_path / "ledger.jsonl")
    ledger.append("test_seed", "s", {"n": 1})
    package = generate_evidence_package("all", ledger=ledger, record=False)
    assert package.verify()
    package.owner_grant_count += 100
    assert not package.verify()


def test_package_write_round_trip(tmp_path):
    ledger = GuardrailLedger(tmp_path / "ledger.jsonl")
    ledger.append("test_seed", "s", {"n": 1})
    package = generate_evidence_package("soc2", ledger=ledger, record=False)
    out = package.write(tmp_path / "evidence.json")
    assert out.exists()
    import json

    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["package_sha256"] == package.package_sha256
    assert (
        EvidencePackage(**{k: v for k, v in data.items() if k != "package_sha256"},
                        package_sha256=data["package_sha256"]).verify()
    )
