"""Tests for the verifiable-guardrail evidence model and tamper-evident ledger.

Hermetic: the autouse ``_hermetic_environment`` fixture points HERMES_HOME at a
tmp dir; ledger tests additionally use explicit ``tmp_path`` ledger files.
"""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

import pytest

from muse_cli.jarvis_prime.guardrail_evidence import (
    EvidenceArtifact,
    GuardrailEvidenceBundle,
    GuardrailLedger,
    canonical_json,
)


# --- artifacts -------------------------------------------------------------


def test_artifact_payload_sha256_is_deterministic() -> None:
    payload = {"b": 2, "a": 1, "nested": {"y": 1, "x": 2}}
    a = EvidenceArtifact.make("git_diff", producer="p", subject="s", payload=payload)
    b = EvidenceArtifact.make(
        "git_diff", producer="p", subject="s", payload={"a": 1, "b": 2, "nested": {"x": 2, "y": 1}}
    )
    # Key order must not change the digest.
    assert a.payload_sha256 == b.payload_sha256
    assert a.verify_payload() is True


def test_artifact_tamper_breaks_payload_hash() -> None:
    a = EvidenceArtifact.make("review", producer="p", subject="s", payload={"v": "approve"})
    tampered = EvidenceArtifact.from_dict({**a.to_dict(), "payload": {"v": "blocked"}})
    assert tampered.verify_payload() is False


# --- ledger hash chain -----------------------------------------------------


def test_chain_validates_after_multiple_appends(tmp_path: Path) -> None:
    ledger = GuardrailLedger(tmp_path / "ledger.jsonl")
    for i in range(5):
        ledger.append("gate_summary", f"subject-{i}", {"i": i})
    diag = ledger.verify_chain()
    assert diag.ok is True
    assert diag.length == 5
    assert diag.head_hash == ledger.latest_hash()


def test_empty_ledger_verifies(tmp_path: Path) -> None:
    diag = GuardrailLedger(tmp_path / "ledger.jsonl").verify_chain()
    assert diag.ok is True
    assert diag.length == 0


def test_mutated_record_is_detected(tmp_path: Path) -> None:
    path = tmp_path / "ledger.jsonl"
    ledger = GuardrailLedger(path)
    for i in range(3):
        ledger.append("gate_summary", f"s{i}", {"i": i})
    lines = path.read_text().splitlines()
    rec = json.loads(lines[1])
    rec["payload"] = {"i": 999}  # mutate without recomputing record_hash
    lines[1] = json.dumps(rec, sort_keys=True)
    path.write_text("\n".join(lines) + "\n")

    diag = ledger.verify_chain()
    assert diag.ok is False
    assert diag.broken_at == 1
    assert "mismatch" in diag.reason


def test_broken_link_is_detected(tmp_path: Path) -> None:
    path = tmp_path / "ledger.jsonl"
    ledger = GuardrailLedger(path)
    ledger.append("a", "s", {})
    ledger.append("b", "s", {})
    # Drop the first record — the second's previous_record_hash now dangles.
    lines = path.read_text().splitlines()
    path.write_text(lines[1] + "\n")

    diag = ledger.verify_chain()
    assert diag.ok is False
    assert diag.broken_at == 0


def test_malformed_line_is_reported_not_repaired(tmp_path: Path) -> None:
    path = tmp_path / "ledger.jsonl"
    ledger = GuardrailLedger(path)
    ledger.append("a", "s", {})
    with path.open("a", encoding="utf-8") as fh:
        fh.write("{not json\n")
    diag = ledger.verify_chain()
    assert diag.ok is False
    assert diag.malformed_lines == (1,)
    # The ledger file is left intact — never silently repaired.
    assert "{not json" in path.read_text()


def test_ledger_file_mode_best_effort_0600(tmp_path: Path) -> None:
    path = tmp_path / "ledger.jsonl"
    GuardrailLedger(path).append("a", "s", {})
    mode = stat.S_IMODE(os.stat(path).st_mode)
    # On POSIX we expect 0600; tolerate platforms that cannot honor it.
    if os.name == "posix":
        assert mode == 0o600


def test_default_path_honors_hermes_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    expected = tmp_path / "jarvis_prime" / "guardrail_ledger.jsonl"
    assert GuardrailLedger.default_path() == expected


# --- bundle ----------------------------------------------------------------


def test_bundle_roundtrip_and_lookup() -> None:
    bundle = GuardrailEvidenceBundle(packet_id="pid")
    art = EvidenceArtifact.make("test_result", producer="p", subject="pytest", payload={"passed": True})
    bundle.add(art)
    assert bundle.has("test_result")
    assert not bundle.has("git_diff")
    restored = GuardrailEvidenceBundle.from_dict(bundle.to_dict())
    assert restored.packet_id == "pid"
    assert restored.by_type("test_result")[0].payload_sha256 == art.payload_sha256
