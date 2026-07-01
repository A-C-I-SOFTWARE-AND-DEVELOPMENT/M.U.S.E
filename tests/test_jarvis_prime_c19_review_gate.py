"""C19 builder != reviewer enforcement in the strict review gate.

Clause C19 (``docs/jarvis-constitution.md``): for RC2+ work, the agent that
wrote the change is not the one that approves it. Previously C19 was only
*scored* by the self-audit layer — the strict review gate accepted a review
whose ``reviewer_id`` equalled the change's builder, so a self-approving review
passed. These tests pin the gate behavior: RC2+ self-approval now FAILS, while
distinct reviewers and sub-RC2 work are unaffected.
"""

from __future__ import annotations

from hermes_cli.jarvis_prime.gates import (
    GateOutcome,
    strict_review_gate,
)
from hermes_cli.jarvis_prime.guardrail_evidence import (
    GitDiffEvidence,
    GuardrailEvidenceBundle,
    ReviewEvidence,
    sha256_hex,
)

_PACKET_ID = "pkt_c19"


def _diff_artifact(producer: str, *, changed=("a.py",)):
    return GitDiffEvidence(
        repo_root="/repo",
        git_available=True,
        branch="feat/x",
        changed_files=tuple(changed),
    ).to_artifact(producer=producer)


def _review_artifact(reviewer_id: str, *, verdict="approve", producer="reviewer"):
    return ReviewEvidence(
        reviewer_id=reviewer_id,
        verdict=verdict,
        diff_hash="deadbeef",
        review_hash=sha256_hex("scope checked, logic sound"),
        summary="scope checked, logic sound",
        contrarian_notes=("consider negative inputs",),
    ).to_artifact(producer=producer)


def _bundle(diff_producer: str, reviewer_id: str, *, verdict="approve"):
    b = GuardrailEvidenceBundle(packet_id=_PACKET_ID)
    b.add(_diff_artifact(diff_producer))
    b.add(_review_artifact(reviewer_id, verdict=verdict))
    return b


def test_rc2_self_approval_is_rejected_with_c19_reason() -> None:
    # Reviewer identity == the builder (git_diff producer) at RC2 => FAIL.
    bundle = _bundle(diff_producer="codex", reviewer_id="codex")
    packet = {"packet_id": _PACKET_ID, "risk_class": "RC2"}

    result = strict_review_gate(packet, bundle)

    assert result.outcome is GateOutcome.FAIL
    assert "C19" in result.reason
    assert "codex" in result.reason
    # The colliding identity is named in the findings for the audit trail.
    joined = " ".join(result.findings)
    assert "reviewer_id=codex" in joined
    assert "builder=codex" in joined


def test_rc3_self_approval_is_rejected() -> None:
    # C19 applies to every band >= RC2, not only RC2.
    bundle = _bundle(diff_producer="agent-7", reviewer_id="agent-7")
    packet = {"packet_id": _PACKET_ID, "risk_class": "RC3"}

    result = strict_review_gate(packet, bundle)

    assert result.outcome is GateOutcome.FAIL
    assert "C19" in result.reason


def test_rc2_distinct_reviewer_still_passes() -> None:
    # builder != reviewer at RC2 => the gate passes on the approve verdict.
    bundle = _bundle(diff_producer="builder-bot", reviewer_id="review-bot")
    packet = {"packet_id": _PACKET_ID, "risk_class": "RC2"}

    result = strict_review_gate(packet, bundle)

    assert result.outcome is GateOutcome.PASS
    assert result.reason == "reviewer verdict: approve"


def test_rc1_self_approval_is_unaffected() -> None:
    # Below the C19 threshold, self-approval is not gated (legacy behavior).
    bundle = _bundle(diff_producer="solo", reviewer_id="solo")
    packet = {"packet_id": _PACKET_ID, "risk_class": "RC1"}

    result = strict_review_gate(packet, bundle)

    assert result.outcome is GateOutcome.PASS
    assert result.reason == "reviewer verdict: approve"


def test_rc0_self_approval_is_unaffected() -> None:
    bundle = _bundle(diff_producer="solo", reviewer_id="solo")
    packet = {"packet_id": _PACKET_ID, "risk_class": "RC0"}

    result = strict_review_gate(packet, bundle)

    assert result.outcome is GateOutcome.PASS


def test_missing_risk_class_defaults_below_c19_threshold() -> None:
    # A packet with no risk_class defaults to RC1, so self-approval is not gated
    # (matches capability_wall._packet_rc); this keeps legacy callers unchanged.
    bundle = _bundle(diff_producer="solo", reviewer_id="solo")
    packet = {"packet_id": _PACKET_ID}

    result = strict_review_gate(packet, bundle)

    assert result.outcome is GateOutcome.PASS


def test_rc2_self_approval_with_reviewer_id_fallback_to_producer() -> None:
    # When reviewer_id is blank, the review artifact's producer identifies the
    # reviewer; a self-approval must still be caught.
    b = GuardrailEvidenceBundle(packet_id=_PACKET_ID)
    b.add(_diff_artifact("codex"))
    b.add(_review_artifact("", producer="codex"))
    packet = {"packet_id": _PACKET_ID, "risk_class": "RC2"}

    result = strict_review_gate(packet, b)

    assert result.outcome is GateOutcome.FAIL
    assert "C19" in result.reason


def test_rc2_explicit_blocked_verdict_still_fails_before_c19() -> None:
    # An explicit blocking verdict is still honored; C19 does not mask it.
    bundle = _bundle(
        diff_producer="builder-bot", reviewer_id="review-bot", verdict="blocked"
    )
    packet = {"packet_id": _PACKET_ID, "risk_class": "RC2"}

    result = strict_review_gate(packet, bundle)

    assert result.outcome is GateOutcome.FAIL
    assert "blocked" in result.reason
