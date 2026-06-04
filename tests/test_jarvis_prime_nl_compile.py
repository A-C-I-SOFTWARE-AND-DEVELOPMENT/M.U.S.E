"""End-to-end tests for the NL compile façade.

Covers backend dispatch, the gate-check path, terminal clarification, the
ledger/memory side-effect policy, and the no-side-effects guarantee.
"""

from __future__ import annotations

from pathlib import Path

from hermes_cli.jarvis_prime import nl_compile
from hermes_cli.jarvis_prime.backend_selector import BackendTarget
from hermes_cli.jarvis_prime.gates import run_gate_summary
from hermes_cli.jarvis_prime.natural_language_coder import build_work_packet

INVOICE = (
    "when a new invoice email arrives, extract the total, save the PDF, "
    "write the amount to the ledger, and alert me if the vendor is new"
)
REPO = "add a function to the gateway module and add tests"


def test_invoice_compiles_to_automation_flow() -> None:
    res = nl_compile.compile_request(INVOICE)
    assert not res.needs_clarification
    assert res.backend is not None and res.compile_result is not None
    assert res.backend.selected == BackendTarget.AUTOMATION_FLOW
    assert res.compile_result.target == BackendTarget.AUTOMATION_FLOW


def test_repo_prompt_compiles_to_work_packet() -> None:
    res = nl_compile.compile_request(REPO)
    assert res.backend is not None and res.compile_result is not None
    assert res.backend.selected == BackendTarget.REPO_WORK_PACKET
    assert res.compile_result.gate_packet is not None


def test_gate_check_matches_cmd_packet_outcome() -> None:
    res = nl_compile.compile_request(REPO, gate_check=True)
    assert res.gate_summary is not None
    # Same gate path _cmd_packet uses over the same prompt's packet.
    baseline = run_gate_summary(build_work_packet(REPO).to_gate_packet())
    assert res.gate_summary.overall == baseline.overall


def test_vague_prompt_is_terminal_clarification() -> None:
    res = nl_compile.compile_request("do the thing with the stuff")
    assert res.needs_clarification
    assert res.clarifying_questions()
    assert res.compile_result is None
    assert res.backend is None


def test_default_compile_has_no_side_effects(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    nl_compile.compile_request(INVOICE)  # no job_id, no learn
    assert not (tmp_path / "jobs").exists()
    assert not (tmp_path / "jarvis_prime" / "memory_tree.jsonl").exists()


def test_ledger_written_only_in_job_context(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    from hermes_cli import orchestrator_ledger

    nl_compile.compile_request(REPO, job_id="nl-compile-test")
    entries = orchestrator_ledger.read("nl-compile-test")
    assert entries
    assert any(e.get("kind") == "nl-compile" for e in entries)


def test_learn_writes_proposed_session_memory(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    from hermes_cli.jarvis_prime.memory_tree import (
        ApprovalState,
        MemoryLayer,
        MemoryTreeStore,
    )

    nl_compile.compile_request(INVOICE, learn=True)
    store = MemoryTreeStore.load()
    nodes = list(store.nodes.values())
    assert nodes, "learn should have proposed at least one node"
    assert all(n.approval_state == ApprovalState.PROPOSED for n in nodes)
    assert all(n.layer == MemoryLayer.SESSION for n in nodes)
