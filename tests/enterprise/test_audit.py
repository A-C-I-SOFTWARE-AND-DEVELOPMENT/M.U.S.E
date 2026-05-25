"""Audit JSONL shape + redaction integrity."""

from __future__ import annotations

import json

from enterprise.audit import audit, read_events
from enterprise.policy import Risk


def test_audit_writes_jsonl_with_expected_fields(audit_dir):
    audit(
        "sess-1",
        "plan",
        "orchestrator",
        extra={"task_count": 3},
    )
    path = audit_dir / "sess-1.jsonl"
    assert path.exists()
    rows = path.read_text(encoding="utf-8").splitlines()
    assert len(rows) == 1
    row = json.loads(rows[0])
    assert row["event"] == "plan"
    assert row["agent"] == "orchestrator"
    assert row["session_id"] == "sess-1"
    assert "ts" in row and isinstance(row["ts"], (int, float))
    assert row["extra"] == {"task_count": 3}


def test_audit_appends_subsequent_events(audit_dir):
    audit("sess-2", "plan", "orchestrator")
    audit("sess-2", "dispatch", "orchestrator", tool="finance.invoice.create")
    audit(
        "sess-2",
        "leaf_result",
        "finance",
        tool="invoice.create",
        result={"status": "ok"},
    )
    events = read_events("sess-2")
    assert [e.event for e in events] == ["plan", "dispatch", "leaf_result"]


def test_audit_hashes_args_and_result_not_raw_values(audit_dir):
    audit(
        "sess-3",
        "dispatch",
        "orchestrator",
        tool="finance.invoice.create",
        args={"vendor": "ACME", "amount": 100, "memo": "internal"},
        result={"status": "ok", "invoice_id": "INV-ABC"},
        risk=Risk.MEDIUM,
    )
    row = json.loads((audit_dir / "sess-3.jsonl").read_text().splitlines()[0])
    # args_hash present, but raw arg values NOT in the row.
    assert row["args_hash"] and len(row["args_hash"]) == 12
    assert row["result_hash"] and len(row["result_hash"]) == 12
    serialised = json.dumps(row)
    assert "ACME" not in serialised
    assert "INV-ABC" not in serialised


def test_audit_redacts_known_secret_shapes_in_summary(audit_dir):
    audit(
        "sess-4",
        "leaf_result",
        "finance",
        tool="invoice.create",
        result_summary="created invoice using sk-LEAKED_KEY_AAAAAAAAAAAAAAAAAA",
    )
    rendered = (audit_dir / "sess-4.jsonl").read_text()
    assert "sk-LEAKED_KEY" not in rendered


def test_audit_records_risk_and_validation(audit_dir):
    audit(
        "sess-5",
        "judge",
        "judge",
        tool="invoice.create",
        risk=Risk.HIGH,
        validation="ok",
    )
    row = json.loads((audit_dir / "sess-5.jsonl").read_text().splitlines()[0])
    assert row["risk"] == "high"
    assert row["validation"] == "ok"


def test_read_events_returns_empty_when_no_file(audit_dir):
    assert read_events("never-existed") == []


def test_audit_records_secret_fingerprints_not_values(audit_dir):
    audit(
        "sess-6",
        "leaf_result",
        "finance",
        tool="invoice.create",
        result={"status": "ok"},
        secret_fingerprints=("stripe:abc12345",),
    )
    row = json.loads((audit_dir / "sess-6.jsonl").read_text().splitlines()[0])
    assert row["secret_fingerprints"] == ["stripe:abc12345"]
