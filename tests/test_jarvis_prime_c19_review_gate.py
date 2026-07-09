"""C19 builder != reviewer enforcement in the review gates (strict + default).

Clause C19 (``docs/jarvis-constitution.md``): for RC2+ work, the agent that
wrote the change is not the one that approves it. Previously C19 was only
*scored* by the self-audit layer — and, when first wired into the strict review
gate, it compared the review's ``reviewer_id`` (a real agent id) against the
git_diff artifact's ``producer``. In production that producer is ALWAYS the
fixed literal ``"git_diff_collector"`` set by the collector, so the two operands
lived in different namespaces and could never be equal — C19 never fired.

The mechanism now compares ``reviewer_id`` against the git_diff artifact's
``author_id`` — the acting agent threaded into ``collect_git_diff_evidence`` —
so both operands are real agent ids in the same namespace. Neither operand falls
back to a collector-tool ``producer`` literal (P0-4 hardening): a fallback would
put the reviewer in a different namespace than the builder and silently exempt
every RC2+ change. Policy is fail-OPEN: the gate blocks only when BOTH identities
are known and equal; an unknown builder OR an unknown reviewer at RC2+ passes
(fail-open) and emits an observable warning.

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


def test_unit_rc2_reviewer_id_does_not_fall_back_to_producer(caplog) -> None:
    # HARDENED (P0-4): the reviewer identity must NOT fall back to the review
    # artifact's ``producer``. In production ``producer`` is the fixed literal
    # ``"reviewer"`` (a different namespace than agent ids), so a fallback would
    # make reviewer == builder impossible and silently exempt every RC2+ change
    # from C19. With a blank reviewer_id the gate now fails OPEN (does not block)
    # and emits an observable C19 warning, rather than fabricating a match.
    b = GuardrailEvidenceBundle(packet_id=_PACKET_ID)
    b.add(_diff_artifact("codex"))
    b.add(_review_artifact("", producer="codex"))
    packet = {"packet_id": _PACKET_ID, "risk_class": "RC2"}

    with caplog.at_level(logging.WARNING, logger="hermes.jarvis_prime.gates"):
        result = strict_review_gate(packet, b)

    assert result.outcome is GateOutcome.PASS
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert any("C19 fail-open" in r.getMessage() for r in warnings)
    assert any("reviewer_id" in r.getMessage() for r in warnings)


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


# ---------------------------------------------------------------------------
# P0-2: the review bundle must be bound to the packet under evaluation, exactly
# as the strict BUILD gate already binds it — an approve-review for packet A may
# not be replayed against packet B.
# ---------------------------------------------------------------------------


def test_review_packet_id_mismatch_fails() -> None:
    b = GuardrailEvidenceBundle(packet_id="OTHER-PACKET")
    b.add(_diff_artifact("builder-bot"))
    b.add(_review_artifact("review-bot"))
    packet = {"packet_id": _PACKET_ID, "risk_class": "RC2"}

    result = strict_review_gate(packet, b)

    assert result.outcome is GateOutcome.FAIL
    assert "packet" in result.reason
    assert "packet_id" in " ".join(result.findings)


# ---------------------------------------------------------------------------
# P0-3: verdict whitelist — only an explicit ``approve`` reaches a terminal
# PASS. An absent ("") or garbled ("lgtm") verdict must FAIL closed instead of
# falling through as if the reviewer had approved.
# ---------------------------------------------------------------------------


def test_absent_verdict_fails_closed() -> None:
    bundle = _bundle(author_id="builder-bot", reviewer_id="review-bot", verdict="")
    packet = {"packet_id": _PACKET_ID, "risk_class": "RC2"}

    result = strict_review_gate(packet, bundle)

    assert result.outcome is GateOutcome.FAIL
    assert "verdict" in result.reason


def test_garbled_verdict_fails_closed() -> None:
    bundle = _bundle(author_id="builder-bot", reviewer_id="review-bot", verdict="lgtm")
    packet = {"packet_id": _PACKET_ID, "risk_class": "RC2"}

    result = strict_review_gate(packet, bundle)

    assert result.outcome is GateOutcome.FAIL
    assert "verdict" in result.reason
    assert "lgtm" in result.reason


def test_explicit_approve_verdict_still_passes() -> None:
    # The happy path is unchanged: a real ``approve`` with a distinct reviewer
    # and a matching packet still PASSes.
    bundle = _bundle(author_id="builder-bot", reviewer_id="review-bot", verdict="approve")
    packet = {"packet_id": _PACKET_ID, "risk_class": "RC2"}

    result = strict_review_gate(packet, bundle)

    assert result.outcome is GateOutcome.PASS
    assert result.reason == "reviewer verdict: approve"


# ---------------------------------------------------------------------------
# P0-4: an empty/"unknown" reviewer_id at RC2+ must not silently exempt C19.
# It fails OPEN (does not block) but emits an observable warning, mirroring the
# missing-builder fail-open branch.
# ---------------------------------------------------------------------------


def test_empty_reviewer_id_rc2_fails_open_and_warns(caplog) -> None:
    b = GuardrailEvidenceBundle(packet_id=_PACKET_ID)
    b.add(_diff_artifact("builder-bot"))
    b.add(_review_artifact(""))  # empty reviewer_id
    packet = {"packet_id": _PACKET_ID, "risk_class": "RC2"}

    with caplog.at_level(logging.WARNING, logger="hermes.jarvis_prime.gates"):
        result = strict_review_gate(packet, b)

    assert result.outcome is GateOutcome.PASS
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert any("C19 fail-open" in r.getMessage() for r in warnings)
    assert any("reviewer_id" in r.getMessage() for r in warnings)


def test_unknown_literal_reviewer_id_rc2_fails_open_and_warns(caplog) -> None:
    # The collector defaults a blank reviewer_id to the literal "unknown"; that
    # must be treated as absent, not as a real agent id.
    b = GuardrailEvidenceBundle(packet_id=_PACKET_ID)
    b.add(_diff_artifact("builder-bot"))
    b.add(_review_artifact("unknown"))
    packet = {"packet_id": _PACKET_ID, "risk_class": "RC2"}

    with caplog.at_level(logging.WARNING, logger="hermes.jarvis_prime.gates"):
        result = strict_review_gate(packet, b)

    assert result.outcome is GateOutcome.PASS
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert any("C19 fail-open" in r.getMessage() for r in warnings)
    assert any("reviewer_id" in r.getMessage() for r in warnings)


def test_distinct_reviewer_id_rc2_does_not_warn(caplog) -> None:
    # A proper distinct reviewer_id enforces C19 without a fail-open warning.
    b = GuardrailEvidenceBundle(packet_id=_PACKET_ID)
    b.add(_diff_artifact("builder-bot"))
    b.add(_review_artifact("review-bot"))
    packet = {"packet_id": _PACKET_ID, "risk_class": "RC2"}

    with caplog.at_level(logging.WARNING, logger="hermes.jarvis_prime.gates"):
        result = strict_review_gate(packet, b)

    assert result.outcome is GateOutcome.PASS
    assert not [r for r in caplog.records if "C19 fail-open" in r.getMessage()]


# ---------------------------------------------------------------------------
# C19 on the DEFAULT (non-strict) review_gate.
#
# The same Clause C19 builder != reviewer check now fires on the default,
# packet-level review_gate — not only the opt-in strict gate. On the default
# path the identities are read off the packet (builder = acting_agent_id /
# author_id, reviewer = reviewer_worker / reviewer_id) rather than an evidence
# bundle. Policy is identical: block only when BOTH identities are known and
# equal at RC2+; below RC2 or with an unknown identity it fails OPEN (no block,
# observable warning), so current flows keep their outcome unchanged.
# ---------------------------------------------------------------------------


def _default_review_ready(**overrides) -> dict:
    """A packet that satisfies the default review_gate's self-attested checks.

    ``diff_reviewed`` and ``contrarian_objection`` present means the gate would
    PASS absent a C19 self-approval, isolating the C19 effect under test.
    """

    packet = {"diff_reviewed": True, "contrarian_objection": "considered"}
    packet.update(overrides)
    return packet


def test_default_gate_rc2_same_agent_fails_c19() -> None:
    from hermes_cli.jarvis_prime.gates import review_gate

    packet = _default_review_ready(
        risk_class="RC2", acting_agent_id="agent-x", reviewer_worker="agent-x"
    )
    result = review_gate(packet)
    assert result.outcome is GateOutcome.FAIL
    assert "C19 self-approval blocked" in result.reason


def test_default_gate_rc2_author_id_reviewer_id_aliases_fail_c19() -> None:
    # The default gate also accepts the author_id / reviewer_id aliases.
    from hermes_cli.jarvis_prime.gates import review_gate

    packet = _default_review_ready(
        risk_class="RC2", author_id="agent-x", reviewer_id="agent-x"
    )
    result = review_gate(packet)
    assert result.outcome is GateOutcome.FAIL
    assert "C19 self-approval blocked" in result.reason


def test_default_gate_rc2_distinct_agents_pass_unchanged() -> None:
    from hermes_cli.jarvis_prime.gates import review_gate

    packet = _default_review_ready(
        risk_class="RC2", acting_agent_id="builder-bot", reviewer_worker="review-bot"
    )
    result = review_gate(packet)
    assert result.outcome is GateOutcome.PASS


def test_default_gate_rc2_unknown_identity_fails_open_and_warns(caplog) -> None:
    from hermes_cli.jarvis_prime.gates import review_gate

    # No builder/reviewer identity on the packet: fail-open (PASS), warn.
    packet = _default_review_ready(risk_class="RC2")
    with caplog.at_level(logging.WARNING, logger="hermes.jarvis_prime.gates"):
        result = review_gate(packet)

    assert result.outcome is GateOutcome.PASS
    assert any("C19 fail-open" in r.getMessage() for r in caplog.records)


def test_default_gate_rc2_unknown_literal_reviewer_fails_open() -> None:
    from hermes_cli.jarvis_prime.gates import review_gate

    # The literal "unknown" reviewer normalizes to empty -> fail-open, PASS.
    packet = _default_review_ready(
        risk_class="RC2", acting_agent_id="agent-x", reviewer_worker="unknown"
    )
    result = review_gate(packet)
    assert result.outcome is GateOutcome.PASS


def test_default_gate_rc3_same_agent_fails_c19() -> None:
    from hermes_cli.jarvis_prime.gates import review_gate

    packet = _default_review_ready(
        risk_class="RC3", acting_agent_id="agent-x", reviewer_worker="agent-x"
    )
    result = review_gate(packet)
    assert result.outcome is GateOutcome.FAIL
    assert "C19 self-approval blocked" in result.reason


def test_default_gate_rc0_rc1_same_agent_unchanged() -> None:
    from hermes_cli.jarvis_prime.gates import review_gate

    # Below the C19 band: same agent is NOT gated; the gate passes on the
    # self-attested fields exactly as before.
    for rc in ("RC0", "RC1"):
        packet = _default_review_ready(
            risk_class=rc, acting_agent_id="agent-x", reviewer_worker="agent-x"
        )
        result = review_gate(packet)
        assert result.outcome is GateOutcome.PASS, rc


def test_default_gate_no_risk_class_defaults_below_c19_band() -> None:
    from hermes_cli.jarvis_prime.gates import review_gate

    # Absent risk_class defaults to RC1 -> below C19 band -> same agent passes.
    packet = _default_review_ready(
        acting_agent_id="agent-x", reviewer_worker="agent-x"
    )
    result = review_gate(packet)
    assert result.outcome is GateOutcome.PASS


def test_default_gate_c19_precedes_incomplete_review_fields() -> None:
    from hermes_cli.jarvis_prime.gates import review_gate

    # Even without diff_reviewed / contrarian_objection, a genuine RC2 same-agent
    # self-approval fails specifically on C19 (the offender is named), not merely
    # "review incomplete".
    packet = {"risk_class": "RC2", "acting_agent_id": "agent-x", "reviewer_worker": "agent-x"}
    result = review_gate(packet)
    assert result.outcome is GateOutcome.FAIL
    assert "C19 self-approval blocked" in result.reason
