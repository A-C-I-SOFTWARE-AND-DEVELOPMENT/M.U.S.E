"""Tests for risk-adaptive orchestration — job classification + profiled gates.

Covers the Phase 1 exits: jobs are blast-radius-classified at creation,
a HIGH job blocks at OwnerApproval until the exact authorization phrase,
and a tampered event chain flips the release gate to FAIL.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from muse_cli.jarvis_prime.axiom_bridge import get_bridge, reset_bridge
from muse_cli.jarvis_prime.gates import GateOutcome
from muse_cli.job_controller import JobController, estimate_job_risk, run_job_gates
from muse_cli.orchestrator_models import JobMode


@pytest.fixture(autouse=True)
def _fresh_bridge(monkeypatch: pytest.MonkeyPatch):
    # CI exports MUSE_AXIOM_GATES=0 for hermeticity; these tests exercise
    # the live bridge against the per-test HERMES_HOME, so re-enable it.
    monkeypatch.delenv("MUSE_AXIOM_GATES", raising=False)
    reset_bridge()
    yield
    reset_bridge()


@pytest.fixture
def controller(tmp_path: Path) -> JobController:
    return JobController(root=tmp_path / ".hermes-orchestrator")


def _complete_packet(**extra) -> dict:
    packet = {
        "packet_id": "pkt-1",
        "repo_root": "/repo",
        "branch": "main",
        "mission": "demo",
        "allowed_files": ["a.py"],
        "non_goals": ["none"],
        "acceptance_criteria": ["works"],
        "files_changed": ["a.py"],
        "commits_scoped": True,
        "verification_summary": "tests pass",
        "remaining_risks": ["low"],
        "rollback_plan": "git revert",
        "commit_hash": "abc123",
    }
    packet.update(extra)
    return packet


def test_estimate_job_risk_bands() -> None:
    research = estimate_job_risk(JobMode.RESEARCH, True)
    assert research is not None
    assert research["risk"] == "LOW"
    assert research["strict_evidence"] is False
    assert research["gates"] == ["build", "test"]

    trusted_build = estimate_job_risk(JobMode.BUILD, True)
    assert trusted_build is not None
    assert trusted_build["risk"] == "MED"
    assert trusted_build["strict_evidence"] is True
    assert "owner_approval" not in trusted_build["gates"]

    untrusted_build = estimate_job_risk(JobMode.BUILD, False)
    assert untrusted_build is not None
    assert untrusted_build["risk"] == "HIGH"
    assert "owner_approval" in untrusted_build["gates"]
    assert len(untrusted_build["gates"]) == 8


def test_overrides_sharpen_estimate() -> None:
    quiet = estimate_job_risk(
        JobMode.BUILD, True, overrides={"effects": (), "loc": 2}
    )
    assert quiet is not None
    assert quiet["risk"] == "LOW"


def test_create_job_stores_classification_and_chains_it(
    controller: JobController,
) -> None:
    job = controller.create_job(
        prompt="rip out the old config loader",
        mode=JobMode.BUILD,
        repo_root="/srv/example",
        trusted_local=False,
    )
    risk = job.metadata["risk"]
    assert risk["risk"] == "HIGH"
    assert "owner_approval" in risk["gates"]

    reloaded = controller.load_job(job.job_id)
    assert reloaded.metadata["risk"]["risk"] == "HIGH"

    events = [e for e in get_bridge().tail(10) if e["kind"] == "job.classified"]
    assert events and events[-1]["payload"]["job_id"] == job.job_id
    assert events[-1]["payload"]["risk"] == "HIGH"


def test_high_job_blocks_at_owner_approval(controller: JobController) -> None:
    job = controller.create_job(
        prompt="mis-scoped: rewrite everything",
        mode=JobMode.BUILD,
        repo_root="/srv/example",
        trusted_local=False,
    )
    # Even a packet that self-attests everything blocks at OwnerApproval
    # (and strict evidence fails the self-attested gates).
    summary = run_job_gates(job, _complete_packet())
    by_name = {r.name: r for r in summary.results}
    assert by_name["owner_approval"].outcome == GateOutcome.NEEDS_OWNER_APPROVAL
    assert "Yes, with authorization." in by_name["owner_approval"].reason
    assert summary.overall != GateOutcome.PASS


def test_low_job_runs_only_profile_gates(controller: JobController) -> None:
    job = controller.create_job(
        prompt="summarize the readme",
        mode=JobMode.RESEARCH,
        repo_root="/srv/example",
        trusted_local=True,
    )
    summary = run_job_gates(job, _complete_packet(scope_respected=True))
    assert [r.name for r in summary.results] == ["build", "test"]


def test_med_job_is_evidence_strict(controller: JobController) -> None:
    job = controller.create_job(
        prompt="add a healthz endpoint",
        mode=JobMode.BUILD,
        repo_root="/srv/example",
        trusted_local=True,
    )
    # Self-attested packet, no evidence bundle: strict gates must fail.
    summary = run_job_gates(job, _complete_packet(tests_passed=True))
    assert summary.overall == GateOutcome.FAIL
    by_name = {r.name: r for r in summary.results}
    assert by_name["test"].outcome == GateOutcome.FAIL


def test_tampered_chain_fails_release(controller: JobController) -> None:
    bridge = get_bridge()
    bridge.record_event("gate.summary", {"packet_id": "pkt-1", "overall": "pass"})

    from muse_cli.jarvis_prime.gates import release_gate

    packet = _complete_packet()
    assert release_gate(packet).outcome == GateOutcome.PASS

    text = bridge.chain_path.read_text(encoding="utf-8")
    bridge.chain_path.write_text(text.replace("pkt-1", "pkt-X"), encoding="utf-8")
    result = release_gate(packet)
    assert result.outcome == GateOutcome.FAIL
    assert "chain" in result.reason
