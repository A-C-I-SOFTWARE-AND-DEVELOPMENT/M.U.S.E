"""C19 reachability through the REAL production bundle assemblers.

Regression guard for the dead-end fixed here: ``strict_review_gate`` enforces
Clause C19 (builder != reviewer) only when a *review-evidence* artifact is in
the bundle. But the two production assemblers
(``nlp_refine.run_execution_refinement`` and ``guardrails_cli._collect``)
previously added only diff / secret-scan / test / rollback evidence and NEVER a
review artifact — so ``strict_review_gate`` always failed first on
"no review evidence captured" and the C19 branch was dead in every production
flow.

These tests drive the REAL assemblers end-to-end and assert that, when the
packet carries a reviewer identity, the assembled bundle now contains review
evidence and the strict review gate actually EVALUATES C19:

* builder == reviewer  -> FAIL on the C19 reason (not on "no review evidence"),
* builder != reviewer  -> C19 identity check passes (the neutral assignment
  verdict then defers to the owner rather than fabricating an approval),
* no reviewer at all    -> no review evidence added (behavior unchanged).

The assignment artifact carries a fixed ``needs_owner`` verdict, so it can never
manufacture a PASS: a real approve/request_changes verdict must still come from
an actual review step.
"""

from __future__ import annotations

import json

from hermes_cli.guardrails_cli import _collect
from hermes_cli.jarvis_prime.gates import (
    GateOutcome,
    strict_review_gate,
)
from hermes_cli.jarvis_prime.guardrail_evidence import (
    ARTIFACT_REVIEW,
    EvidenceArtifact,
    GuardrailEvidenceBundle,
)
from hermes_cli.jarvis_prime.natural_language_coder import build_work_packet
from hermes_cli.jarvis_prime.nlp_refine import run_execution_refinement


class _Compile:
    """Minimal CompileResult stand-in carrying a real gate packet."""

    def __init__(self, gate_packet: dict) -> None:
        self.gate_packet = gate_packet


class _CollectArgs:
    def __init__(self, packet_path: str) -> None:
        self.packet = packet_path
        self.run_tests = False


def _rebuild_bundle_from_refinement(gate_packet: dict, repo_root: str):
    """Run the REAL nlp_refine assembler and reconstruct the bundle it built.

    ``run_execution_refinement`` returns a gate summary, not the bundle, so we
    reproduce the exact assembler once here and reuse the shipped code path in
    the other assertions.
    """

    signal = run_execution_refinement(
        _Compile(gate_packet), repo_root=repo_root, enabled=True, run=False
    )
    return signal


def _review_arts_from_collect(gate_packet: dict, tmp_path) -> list[EvidenceArtifact]:
    packet_path = tmp_path / "packet.json"
    packet_path.write_text(json.dumps(gate_packet), encoding="utf-8")
    result = _collect(_CollectArgs(str(packet_path)))
    return [
        EvidenceArtifact.from_dict(a) if isinstance(a, dict) else a
        for a in result["artifacts"]
    ]


def _bundle_from_collect(gate_packet: dict, tmp_path) -> GuardrailEvidenceBundle:
    packet_path = tmp_path / "packet.json"
    packet_path.write_text(json.dumps(gate_packet), encoding="utf-8")
    result = _collect(_CollectArgs(str(packet_path)))
    bundle = GuardrailEvidenceBundle(packet_id=str(gate_packet.get("packet_id") or ""))
    for a in result["artifacts"]:
        bundle.add(EvidenceArtifact.from_dict(a) if isinstance(a, dict) else a)
    return bundle


# ---------------------------------------------------------------------------
# guardrails_cli._collect assembler
# ---------------------------------------------------------------------------


def test_collect_adds_review_evidence_when_reviewer_assigned(tmp_path) -> None:
    packet = build_work_packet("refactor the router module", repo_root=str(tmp_path))
    assert packet.risk_class == "RC2"
    gate_packet = packet.to_gate_packet()
    assert gate_packet["reviewer_worker"]  # real producer carries a reviewer

    bundle = _bundle_from_collect(gate_packet, tmp_path)

    review = bundle.by_type(ARTIFACT_REVIEW)
    assert review, "reviewer assigned -> review evidence must now be present"
    # The assignment verdict is neutral (never a fabricated approval).
    assert review[-1].payload["verdict"] == "needs_owner"
    assert review[-1].payload["reviewer_id"] == packet.reviewer_worker


def test_collect_self_review_reaches_and_fails_c19(tmp_path) -> None:
    # Builder == reviewer: the gate must now FAIL on the C19 reason, proving the
    # C19 branch is reachable (previously it failed on "no review evidence").
    packet = build_work_packet("refactor the router module", repo_root=str(tmp_path))
    gate_packet = packet.to_gate_packet()
    # Simulate a misconfigured packet whose reviewer is the builder.
    gate_packet["reviewer_worker"] = gate_packet["acting_agent_id"]

    bundle = _bundle_from_collect(gate_packet, tmp_path)
    result = strict_review_gate(gate_packet, bundle)

    assert result.outcome is GateOutcome.FAIL
    assert "C19" in result.reason
    assert "no review evidence" not in result.reason


def test_collect_distinct_reviewer_passes_c19_but_defers_to_owner(tmp_path) -> None:
    # Builder != reviewer: C19 identity check passes; the neutral assignment
    # verdict then defers to the owner rather than fabricating an approval.
    packet = build_work_packet("refactor the router module", repo_root=str(tmp_path))
    gate_packet = packet.to_gate_packet()
    assert gate_packet["acting_agent_id"] != gate_packet["reviewer_worker"]

    bundle = _bundle_from_collect(gate_packet, tmp_path)
    result = strict_review_gate(gate_packet, bundle)

    # Not a C19 FAIL and not a fabricated PASS — it honestly defers to owner.
    assert result.outcome is GateOutcome.NEEDS_OWNER_APPROVAL
    assert "C19" not in result.reason


def test_collect_no_reviewer_leaves_flow_unchanged(tmp_path) -> None:
    packet = build_work_packet("refactor the router module", repo_root=str(tmp_path))
    gate_packet = packet.to_gate_packet()
    # A legacy/partial packet that carries no reviewer identity at all.
    gate_packet.pop("reviewer_worker", None)
    gate_packet.pop("reviewer_id", None)

    bundle = _bundle_from_collect(gate_packet, tmp_path)

    assert not bundle.by_type(ARTIFACT_REVIEW), (
        "no reviewer assigned -> no review evidence added (behavior unchanged)"
    )


# ---------------------------------------------------------------------------
# nlp_refine.run_execution_refinement assembler
# ---------------------------------------------------------------------------


def test_refinement_self_review_reaches_and_fails_c19(tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    packet = build_work_packet("refactor the router module", repo_root=str(repo))
    gate_packet = packet.to_gate_packet()
    gate_packet["reviewer_worker"] = gate_packet["acting_agent_id"]

    signal = run_execution_refinement(
        _Compile(gate_packet), repo_root=str(repo), enabled=True, run=False
    )

    review_results = [
        r for r in signal.gate_summary["results"] if r["name"] == "review"
    ]
    assert review_results, "the strict summary must contain a review result"
    review = review_results[0]
    assert review["outcome"] == GateOutcome.FAIL.value
    assert "C19" in review["reason"]
    assert "no review evidence" not in review["reason"]


def test_refinement_distinct_reviewer_defers_not_fabricates(tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    packet = build_work_packet("refactor the router module", repo_root=str(repo))
    gate_packet = packet.to_gate_packet()
    assert gate_packet["acting_agent_id"] != gate_packet["reviewer_worker"]

    signal = run_execution_refinement(
        _Compile(gate_packet), repo_root=str(repo), enabled=True, run=False
    )

    review = next(
        r for r in signal.gate_summary["results"] if r["name"] == "review"
    )
    # Reachable and NOT a fabricated approval: it defers to owner.
    assert review["outcome"] == GateOutcome.NEEDS_OWNER_APPROVAL.value
    assert "C19" not in review["reason"]


def test_refinement_no_reviewer_no_review_evidence(tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    packet = build_work_packet("refactor the router module", repo_root=str(repo))
    gate_packet = packet.to_gate_packet()
    gate_packet.pop("reviewer_worker", None)
    gate_packet.pop("reviewer_id", None)

    signal = run_execution_refinement(
        _Compile(gate_packet), repo_root=str(repo), enabled=True, run=False
    )

    review = next(
        r for r in signal.gate_summary["results"] if r["name"] == "review"
    )
    # No reviewer -> no review artifact -> the gate fails on absence, exactly as
    # before this change (the wiring did not alter the no-reviewer path).
    assert review["outcome"] == GateOutcome.FAIL.value
    assert "no review evidence" in review["reason"]
