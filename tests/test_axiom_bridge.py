"""Tests for hermes_cli.jarvis_prime.axiom_bridge — the chained event bridge.

HERMES_HOME is per-test (conftest invariant #2), so every test starts
with a fresh, absent chain.
"""

from __future__ import annotations

import json

import pytest

from hermes_cli.jarvis_prime import axiom_bridge
from hermes_cli.jarvis_prime.axiom_bridge import (
    GENESIS_PREV,
    get_bridge,
    main,
    reset_bridge,
)


@pytest.fixture(autouse=True)
def _fresh_bridge(monkeypatch: pytest.MonkeyPatch):
    # CI exports muse_AXIOM_GATES=0 for hermeticity; these tests exercise
    # the live bridge against the per-test HERMES_HOME, so re-enable it.
    monkeypatch.delenv("muse_AXIOM_GATES", raising=False)
    reset_bridge()
    yield
    reset_bridge()


def test_record_audit_tail() -> None:
    bridge = get_bridge()
    h1 = bridge.record_event("test.event", {"n": 1})
    h2 = bridge.record_event("test.event", {"n": 2})
    h3 = bridge.record_event("other.event", {"n": 3})
    assert h1 and h2 and h3

    audit = bridge.audit()
    assert audit["chain_valid"] is True
    assert audit["events"] == 3
    assert audit["tip"] == h3

    last_two = bridge.tail(2)
    assert [e["kind"] for e in last_two] == ["test.event", "other.event"]
    assert last_two[0]["prev"] == h1
    assert last_two[1]["prev"] == h2
    assert bridge.tail(10)[0]["prev"] == GENESIS_PREV


def test_tamper_detected() -> None:
    bridge = get_bridge()
    bridge.record_event("test.event", {"n": 1})
    bridge.record_event("test.event", {"n": 2})

    lines = bridge.chain_path.read_text(encoding="utf-8").splitlines()
    lines[1] = lines[1].replace('"n":2', '"n":9')
    bridge.chain_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    audit = bridge.audit()
    assert audit["chain_valid"] is False
    assert audit["first_bad_seq"] == 1


def test_inert_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("muse_AXIOM_GATES", "0")
    bridge = get_bridge()
    assert bridge.inert is True
    assert bridge.record_event("test.event", {"n": 1}) is None
    assert not bridge.chain_path.exists()
    audit = bridge.audit()
    assert audit["chain_valid"] is None
    assert audit["inert"] is True
    assert bridge.tail() == []


def test_classify_bands() -> None:
    bridge = get_bridge()

    low = bridge.classify_change(loc=2)
    assert low["risk"] == "LOW"
    assert low["gates"] == ["build", "test"]
    assert "owner_approval" not in low["gates"]

    med = bridge.classify_change(effects=["fs.write", "net.fetch"])
    assert med["risk"] == "MED"
    assert "security" in med["gates"]
    assert "rollback" in med["gates"]
    assert "owner_approval" not in med["gates"]

    high = bridge.classify_change(changes_default_behavior=True)
    assert high["risk"] == "HIGH"
    assert "owner_approval" in high["gates"]
    assert len(high["gates"]) == 8


def test_status_shape() -> None:
    status = get_bridge().status()
    for key in ("available", "degraded", "inert", "chain_path", "deps"):
        assert key in status
    assert isinstance(status["available"], bool)
    assert isinstance(status["degraded"], bool)
    assert isinstance(status["inert"], bool)
    assert set(status["deps"]) == {"z3", "blake3", "pynacl"}


def test_home_rebind(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    first = get_bridge().chain_path
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "elsewhere"))
    second = get_bridge().chain_path
    assert first != second


def test_gates_hook_records() -> None:
    from hermes_cli.jarvis_prime.gates import run_gate_summary

    summary = run_gate_summary({"packet_id": "pkt-1", "mission": "demo"})
    events = [e for e in get_bridge().tail(10) if e["kind"] == "gate.summary"]
    assert events, "gate run did not land on the chain"
    assert events[-1]["payload"]["packet_id"] == "pkt-1"
    assert events[-1]["payload"]["overall"] == summary.overall.value


def test_release_gate_fails_on_bad_chain(monkeypatch: pytest.MonkeyPatch) -> None:
    from hermes_cli.jarvis_prime.gates import GateOutcome, release_gate

    packet = {
        "files_changed": ["a.py"],
        "commits_scoped": True,
        "verification_summary": "tests pass",
        "non_goals": ["none"],
        "remaining_risks": ["low"],
        "rollback_plan": "git revert",
    }
    bridge = get_bridge()
    bridge.record_event("gate.summary", {"packet_id": "pkt-1", "overall": "pass"})
    assert release_gate(packet).outcome == GateOutcome.PASS

    text = bridge.chain_path.read_text(encoding="utf-8")
    bridge.chain_path.write_text(text.replace("pkt-1", "pkt-X"), encoding="utf-8")
    tampered = release_gate(packet)
    assert tampered.outcome == GateOutcome.FAIL
    assert "chain" in tampered.reason

    monkeypatch.setenv("muse_AXIOM_GATES", "0")
    assert release_gate(packet).outcome == GateOutcome.PASS


def test_decision_ledger_hook() -> None:
    from hermes_cli import decision_ledger as dl

    ledger = dl.DecisionLedger(decision="Use sqlite for the queue")
    dl.write_ledger(ledger, session_id="s1", validate=False)
    events = [e for e in get_bridge().tail(10) if e["kind"] == "decision.written"]
    assert events
    assert events[-1]["payload"]["session_id"] == "s1"
    assert events[-1]["payload"]["decision"] == "Use sqlite for the queue"


def test_cli_status_audit_tail(capsys: pytest.CaptureFixture) -> None:
    assert main(["status"]) == 0
    status = json.loads(capsys.readouterr().out)
    assert "available" in status

    bridge = get_bridge()
    bridge.record_event("test.event", {"n": 1})
    assert main(["audit"]) == 0
    assert json.loads(capsys.readouterr().out)["chain_valid"] is True

    assert main(["tail", "-n", "1"]) == 0
    assert len(json.loads(capsys.readouterr().out)) == 1

    text = bridge.chain_path.read_text(encoding="utf-8")
    bridge.chain_path.write_text(text.replace('"n":1', '"n":9'), encoding="utf-8")
    assert main(["audit"]) == 1
    assert json.loads(capsys.readouterr().out)["chain_valid"] is False
