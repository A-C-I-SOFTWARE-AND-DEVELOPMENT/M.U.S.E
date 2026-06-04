"""Tests for strict, evidence-bound gate evaluation.

The central guarantee: a packet's self-attestation (``diff_reviewed=True``,
``tests_run=[...]``) can never pass strict gates — only captured artifacts can.
A real evidence bundle whose ``packet_id`` does not match the packet is also
rejected, so evidence cannot be replayed against a different packet.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from hermes_cli.jarvis_prime import guardrail_collectors as gc
from hermes_cli.jarvis_prime.gates import (
    GateOutcome,
    run_gate_summary,
    run_strict_gate_summary,
)
from hermes_cli.jarvis_prime.guardrail_evidence import (
    EvidenceArtifact,
    GuardrailEvidenceBundle,
)
from hermes_cli.jarvis_prime.natural_language_coder import build_work_packet


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "-c", "user.email=t@t.t",
         "-c", "user.name=t", *args],
        cwd=repo, check=True, capture_output=True,
    )


@pytest.fixture()
def repo_with_change(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    (repo / ".gitignore").write_text("__pycache__/\n", encoding="utf-8")
    (repo / "a.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "init")
    (repo / "a.py").write_text("def f():\n    return 2\n", encoding="utf-8")
    return repo


def _full_bundle(repo: Path, packet_id: str) -> GuardrailEvidenceBundle:
    b = GuardrailEvidenceBundle(packet_id=packet_id)
    b.add(gc.collect_git_diff_evidence(str(repo), allowed_files=["a.py"]))
    b.add(gc.collect_secret_scan_evidence(str(repo), ["a.py"]))
    b.add(gc.collect_test_evidence(str(repo), ["python -m compileall -q a.py"], run=True)[0])
    b.add(
        gc.collect_review_evidence(
            "scope checked, logic sound", "codex", packet_id,
            verdict="approve", risk_class="RC2",
            contrarian_notes=["consider negative inputs"],
        )
    )
    b.add(
        gc.collect_rollback_evidence(
            str(repo), ["git checkout a.py"], changed_files=["a.py"], branch="feat/x"
        )
    )
    return b


def test_self_attested_packet_fails_strict_gates() -> None:
    packet = build_work_packet("refactor the helper in a.py")
    gp = packet.to_gate_packet()
    # The honest gate packet no longer carries fabricated evidence fields...
    assert "diff_reviewed" not in gp
    assert "files_changed" not in gp
    # ...and even if a caller injects them, strict mode ignores them.
    gp["diff_reviewed"] = True
    gp["files_changed"] = ["a.py"]
    gp["tests_run"] = ["pytest"]
    summary = run_strict_gate_summary(gp, None)
    assert summary.overall is not GateOutcome.PASS
    by_name = {r.name: r.outcome for r in summary.results}
    assert by_name["build"] is GateOutcome.FAIL
    assert by_name["review"] is GateOutcome.FAIL
    assert by_name["test"] is GateOutcome.FAIL


def test_packet_with_matching_artifacts_passes_strict_gates(repo_with_change: Path) -> None:
    packet = build_work_packet("refactor the helper in a.py")
    gp = packet.to_gate_packet()
    bundle = _full_bundle(repo_with_change, gp["packet_id"])
    summary = run_strict_gate_summary(gp, bundle)
    assert summary.overall is GateOutcome.PASS, summary.render()


def test_packet_id_mismatch_fails(repo_with_change: Path) -> None:
    packet = build_work_packet("refactor the helper in a.py")
    gp = packet.to_gate_packet()
    bundle = _full_bundle(repo_with_change, "WRONG-PACKET-ID")
    summary = run_strict_gate_summary(gp, bundle)
    build = next(r for r in summary.results if r.name == "build")
    assert build.outcome is GateOutcome.FAIL
    assert "packet_id" in " ".join(build.findings)


def test_secret_in_diff_fails_security_gate(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    (repo / "a.py").write_text("x = 1\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "init")
    (repo / "a.py").write_text(
        "token = 'sk-ABCDEFGHIJKLMNOPQRSTUV0123456789'\n", encoding="utf-8"
    )
    packet = build_work_packet("refactor the helper in a.py")
    gp = packet.to_gate_packet()
    bundle = _full_bundle(repo, gp["packet_id"])
    summary = run_strict_gate_summary(gp, bundle)
    security = next(r for r in summary.results if r.name == "security")
    assert security.outcome is GateOutcome.FAIL


def test_owner_gate_requires_grant_artifact(repo_with_change: Path) -> None:
    # A packet carrying an owner-gated action needs a challenge-bound grant.
    packet = build_work_packet("deploy the service to production")
    gp = packet.to_gate_packet()
    assert gp["owner_gated_actions"], "deploy should surface an owner-gated action"
    bundle = _full_bundle(repo_with_change, gp["packet_id"])
    summary = run_strict_gate_summary(gp, bundle)
    owner = next(r for r in summary.results if r.name == "owner_approval")
    assert owner.outcome is GateOutcome.NEEDS_OWNER_APPROVAL

    # Add the matching grant artifact -> the owner gate clears.
    from hermes_cli.jarvis_prime.owner_auth import authorize_challenge, create_challenge

    action = gp["owner_gated_actions"][0]
    ch = create_challenge(action, subject=gp["packet_id"])
    grant = authorize_challenge(ch, ch.required_phrase)
    bundle.add(grant.to_artifact())
    summary2 = run_strict_gate_summary(gp, bundle)
    owner2 = next(r for r in summary2.results if r.name == "owner_approval")
    assert owner2.outcome is GateOutcome.PASS


# --- evidence requirements + legacy compatibility --------------------------


def test_evidence_requirements_scale_with_risk() -> None:
    rc2 = build_work_packet("refactor the router module")
    assert rc2.risk_class == "RC2"
    reqs = rc2.to_evidence_requirements()
    for needed in ("git_diff", "secret_scan", "test_result", "review", "rollback"):
        assert needed in reqs
    assert "owner_authorization_grant" not in reqs

    rc3 = build_work_packet("deploy the service to production")
    assert "owner_authorization_grant" in rc3.to_evidence_requirements()


def test_legacy_planning_gate_still_passes() -> None:
    # Backward compatibility: the default (non-strict) summary is unchanged.
    packet = build_work_packet("add durable memory tree support")
    summary = run_gate_summary(packet.to_gate_packet())
    planning = next(r for r in summary.results if r.name == "planning")
    assert planning.outcome is GateOutcome.PASS
