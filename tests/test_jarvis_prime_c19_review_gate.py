"""C19 builder != reviewer enforcement in the strict review gate.

Clause C19 (``docs/jarvis-constitution.md``): for RC2+ work, the agent that
wrote the change is not the one that approves it. Previously C19 was only
*scored* by the self-audit layer — and, when first wired into the strict review
gate, it compared the review's ``reviewer_id`` (a real agent id) against the
git_diff artifact's ``producer``. In production that producer is ALWAYS the
fixed literal ``"git_diff_collector"`` set by the collector, so the two operands
lived in different namespaces and could never be equal — C19 never fired.

The mechanism now compares ``reviewer_id`` against the git_diff artifact's
``author_id`` — the acting agent threaded into ``collect_git_diff_evidence`` —
so both operands are real agent ids in the same namespace. Policy is fail-OPEN:
the gate blocks only when BOTH identities are known and equal; an unknown author
at RC2+ passes (fail-open) and emits an observable warning.

The end-to-end tests below drive the REAL ``collect_git_diff_evidence`` (with an
acting agent id) and ``collect_review_evidence`` collectors — they do not
fabricate a ``producer`` value the real collector cannot emit. A handful of
pure gate-unit tests build artifacts directly to exercise band boundaries; those
are labelled as such and never assert on a fabricated ``producer``.
"""

from __future__ import annotations

import logging

from hermes_cli.jarvis_prime.gates import (
    GateOutcome,
    strict_review_gate,
)
from hermes_cli.jarvis_prime.guardrail_collectors import (
    collect_git_diff_evidence,
    collect_review_evidence,
)
from hermes_cli.jarvis_prime.guardrail_evidence import (
    GitDiffEvidence,
    GuardrailEvidenceBundle,
    ReviewEvidence,
    sha256_hex,
)

_PACKET_ID = "pkt_c19"


# ---------------------------------------------------------------------------
# End-to-end tests: drive the REAL collectors.
#
# ``collect_git_diff_evidence`` runs read-only git plumbing over ``repo_root``;
# ``tmp_path`` is a directory with no git repo, so ``git rev-parse`` fails and
# the collector degrades to ``git_available=False`` — but it still records the
# ``author_id`` we passed. That is exactly the field the C19 check now reads, so
# these tests exercise the true production path (author_id from the collector vs
# reviewer_id from the review collector) without needing a real commit.
# ---------------------------------------------------------------------------


def _real_bundle(author_id, reviewer_id, *, verdict="approve", tmp_path):
    b = GuardrailEvidenceBundle(packet_id=_PACKET_ID)
    b.add(collect_git_diff_evidence(str(tmp_path), author_id=author_id))
    b.add(
        collect_review_evidence(
            review_text="scope checked, logic sound",
            reviewer_id=reviewer_id,
            diff_hash="deadbeef",
            verdict=verdict,
            risk_class="RC2",
            contrarian_notes=("consider negative inputs",),
        )
    )
    return b


def test_e2e_rc2_same_acting_agent_fails_with_c19(tmp_path) -> None:
    # Same acting agent authored the diff AND reviewed it => C19 hard FAIL.
    bundle = _real_bundle("codex", "codex", tmp_path=tmp_path)
    packet = {"packet_id": _PACKET_ID, "risk_class": "RC2"}

    result = strict_review_gate(packet, bundle)

    assert result.outcome is GateOutcome.FAIL
    assert "C19" in result.reason
    assert "codex" in result.reason
    joined = " ".join(result.findings)
    assert "reviewer_id=codex" in joined
    assert "builder=codex" in joined


def test_e2e_rc2_distinct_acting_agents_pass(tmp_path) -> None:
    # Distinct builder and reviewer agents => gate passes on the approve verdict.
    bundle = _real_bundle("builder-bot", "review-bot", tmp_path=tmp_path)
    packet = {"packet_id": _PACKET_ID, "risk_class": "RC2"}

    result = strict_review_gate(packet, bundle)

    assert result.outcome is GateOutcome.PASS
    assert result.reason == "reviewer verdict: approve"


def test_e2e_rc2_unknown_author_fails_open_and_warns(tmp_path, caplog) -> None:
    # Production reality when no acting agent id is threaded: author_id is "".
    # Fail-OPEN — the gate must PASS (not block a legitimate flow) — but it must
    # emit an observable warning so the fail-open is not silent.
    bundle = GuardrailEvidenceBundle(packet_id=_PACKET_ID)
    bundle.add(collect_git_diff_evidence(str(tmp_path)))  # no author_id
    bundle.add(
        collect_review_evidence(
            review_text="scope checked, logic sound",
            reviewer_id="review-bot",
            diff_hash="deadbeef",
            verdict="approve",
            risk_class="RC2",
            contrarian_notes=("consider negative inputs",),
        )
    )
    packet = {"packet_id": _PACKET_ID, "risk_class": "RC2"}

    with caplog.at_level(logging.WARNING, logger="hermes.jarvis_prime.gates"):
        result = strict_review_gate(packet, bundle)

    assert result.outcome is GateOutcome.PASS
    assert result.reason == "reviewer verdict: approve"
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert any("C19 fail-open" in r.getMessage() for r in warnings)
    assert any("author_id" in r.getMessage() for r in warnings)


def test_e2e_rc0_rc1_unaffected_even_with_same_agent(tmp_path) -> None:
    # Below the C19 threshold, self-authored + self-reviewed is not gated.
    for rc in ("RC0", "RC1"):
        b = GuardrailEvidenceBundle(packet_id=_PACKET_ID)
        b.add(collect_git_diff_evidence(str(tmp_path), author_id="solo"))
        b.add(
            collect_review_evidence(
                review_text="looks good",
                reviewer_id="solo",
                diff_hash="deadbeef",
                verdict="approve",
                risk_class=rc,
            )
        )
        packet = {"packet_id": _PACKET_ID, "risk_class": rc}

        result = strict_review_gate(packet, b)

        assert result.outcome is GateOutcome.PASS, rc


# ---------------------------------------------------------------------------
# Pure gate-unit tests: artifacts built directly to pin band boundaries and
# verdict precedence. These construct ``GitDiffEvidence(... author_id=...)``
# directly (the real, collector-emittable field) — NOT a fabricated ``producer``.
# ---------------------------------------------------------------------------


def _diff_artifact(author_id: str, *, changed=("a.py",)):
    return GitDiffEvidence(
        repo_root="/repo",
        git_available=True,
        branch="feat/x",
        changed_files=tuple(changed),
        author_id=author_id,
    ).to_artifact()


def _review_artifact(reviewer_id: str, *, verdict="approve", producer="reviewer"):
    return ReviewEvidence(
        reviewer_id=reviewer_id,
        verdict=verdict,
        diff_hash="deadbeef",
        review_hash=sha256_hex("scope checked, logic sound"),
        summary="scope checked, logic sound",
        contrarian_notes=("consider negative inputs",),
    ).to_artifact(producer=producer)


def _bundle(author_id: str, reviewer_id: str, *, verdict="approve"):
    b = GuardrailEvidenceBundle(packet_id=_PACKET_ID)
    b.add(_diff_artifact(author_id))
    b.add(_review_artifact(reviewer_id, verdict=verdict))
    return b


def test_unit_rc3_self_approval_is_rejected() -> None:
    # C19 applies to every band >= RC2, not only RC2.
    bundle = _bundle(author_id="agent-7", reviewer_id="agent-7")
    packet = {"packet_id": _PACKET_ID, "risk_class": "RC3"}

    result = strict_review_gate(packet, bundle)

    assert result.outcome is GateOutcome.FAIL
    assert "C19" in result.reason


def test_unit_missing_risk_class_defaults_below_c19_threshold() -> None:
    # A packet with no risk_class defaults to RC1, so self-approval is not gated
    # (matches capability_wall._packet_rc); this keeps legacy callers unchanged.
    bundle = _bundle(author_id="solo", reviewer_id="solo")
    packet = {"packet_id": _PACKET_ID}

    result = strict_review_gate(packet, bundle)

    assert result.outcome is GateOutcome.PASS


def test_unit_rc2_reviewer_id_falls_back_to_producer() -> None:
    # When reviewer_id is blank, the review artifact's producer identifies the
    # reviewer; a self-approval (producer == builder author_id) is still caught.
    b = GuardrailEvidenceBundle(packet_id=_PACKET_ID)
    b.add(_diff_artifact("codex"))
    b.add(_review_artifact("", producer="codex"))
    packet = {"packet_id": _PACKET_ID, "risk_class": "RC2"}

    result = strict_review_gate(packet, b)

    assert result.outcome is GateOutcome.FAIL
    assert "C19" in result.reason


def test_unit_rc2_explicit_blocked_verdict_still_fails() -> None:
    # An explicit blocking verdict is still honored; C19 does not mask it, and a
    # distinct reviewer means C19 would pass — so the FAIL comes from the verdict.
    bundle = _bundle(
        author_id="builder-bot", reviewer_id="review-bot", verdict="blocked"
    )
    packet = {"packet_id": _PACKET_ID, "risk_class": "RC2"}

    result = strict_review_gate(packet, bundle)

    assert result.outcome is GateOutcome.FAIL
    assert "blocked" in result.reason
