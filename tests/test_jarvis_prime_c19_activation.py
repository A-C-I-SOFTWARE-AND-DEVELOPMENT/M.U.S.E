"""C19 activation: the acting-agent id is threaded from the work packet all the
way to the git_diff evidence ``author_id`` at the production assembly sites, so
the strict review gate's Clause C19 (builder != reviewer) actually enforces at
RC2+ instead of failing open.

Before this wiring the packet producer never emitted an acting-agent id, so the
production assembly sites (``nlp_refine.run_execution_refinement`` and
``guardrails_cli._collect``) always called ``collect_git_diff_evidence`` with a
blank ``author_id`` — C19 could only fail open. These tests drive the REAL
producer (``build_work_packet`` -> ``CodingWorkPacket.to_gate_packet``) and the
REAL collector the way the production sites call it, then run the REAL gate.
"""

from __future__ import annotations

import logging

from hermes_cli.jarvis_prime.gates import GateOutcome, strict_review_gate
from hermes_cli.jarvis_prime.guardrail_collectors import (
    collect_git_diff_evidence,
    collect_review_evidence,
)
from hermes_cli.jarvis_prime.guardrail_evidence import GuardrailEvidenceBundle
from hermes_cli.jarvis_prime.natural_language_coder import build_work_packet


def _read_author_id_like_production(gate_packet: dict) -> str:
    """Mirror how nlp_refine / guardrails_cli read the acting agent id."""

    return str(
        gate_packet.get("acting_agent_id") or gate_packet.get("author_id") or ""
    ).strip()


def _assemble_git_diff_like_production(gate_packet: dict, repo_root: str):
    """Reproduce the production assembly of git_diff evidence.

    This is exactly what ``nlp_refine.run_execution_refinement`` (line ~134-138)
    and ``guardrails_cli._collect`` (line ~255-261) do: read the acting agent id
    off the packet and thread it into ``collect_git_diff_evidence(author_id=)``.
    """

    author_id = _read_author_id_like_production(gate_packet)
    allowed = tuple(gate_packet.get("allowed_files", ()) or ())
    return collect_git_diff_evidence(repo_root, allowed, author_id=author_id)


def test_packet_threads_acting_agent_id_to_git_diff_author(tmp_path) -> None:
    # The real producer emits acting_agent_id; the production assembly reads it
    # and the resulting git_diff evidence carries it as author_id.
    packet = build_work_packet("refactor the router module", repo_root=str(tmp_path))
    gate_packet = packet.to_gate_packet()

    diff_art = _assemble_git_diff_like_production(gate_packet, str(tmp_path))

    assert diff_art.payload["author_id"] == packet.primary_worker
    assert diff_art.payload["author_id"] != ""


def test_rc2_self_review_fails_end_to_end_through_real_assembly(tmp_path) -> None:
    # An RC2 flow where the SAME agent both authored the diff and reviewed it now
    # FAILS C19 end-to-end — driven through the real packet producer, the real
    # production git_diff assembly, and the real gate. This is the behavior C19
    # activation is meant to enforce (previously a silent fail-open).
    packet = build_work_packet("refactor the router module", repo_root=str(tmp_path))
    assert packet.risk_class == "RC2"
    gate_packet = packet.to_gate_packet()
    builder = packet.primary_worker

    bundle = GuardrailEvidenceBundle(packet_id=str(gate_packet["packet_id"]))
    bundle.add(_assemble_git_diff_like_production(gate_packet, str(tmp_path)))
    # The reviewer is (illegitimately) the same agent that built the change.
    bundle.add(
        collect_review_evidence(
            review_text="scope checked, logic sound",
            reviewer_id=builder,
            diff_hash="deadbeef",
            verdict="approve",
            risk_class="RC2",
            contrarian_notes=("consider negative inputs",),
        )
    )

    result = strict_review_gate(gate_packet, bundle)

    assert result.outcome is GateOutcome.FAIL
    assert "C19" in result.reason
    assert builder in result.reason


def test_rc2_distinct_reviewer_passes_end_to_end_through_real_assembly(
    tmp_path,
) -> None:
    # The default, well-formed flow: builder (primary_worker) != reviewer
    # (reviewer_worker). C19 does NOT block it — activation is safe.
    packet = build_work_packet("refactor the router module", repo_root=str(tmp_path))
    assert packet.risk_class == "RC2"
    assert packet.primary_worker != packet.reviewer_worker
    gate_packet = packet.to_gate_packet()

    bundle = GuardrailEvidenceBundle(packet_id=str(gate_packet["packet_id"]))
    bundle.add(_assemble_git_diff_like_production(gate_packet, str(tmp_path)))
    bundle.add(
        collect_review_evidence(
            review_text="scope checked, logic sound",
            reviewer_id=packet.reviewer_worker,
            diff_hash="deadbeef",
            verdict="approve",
            risk_class="RC2",
            contrarian_notes=("consider negative inputs",),
        )
    )

    result = strict_review_gate(gate_packet, bundle)

    assert result.outcome is GateOutcome.PASS
    assert result.reason == "reviewer verdict: approve"


def test_rc2_missing_acting_agent_id_still_fails_open(tmp_path, caplog) -> None:
    # Any path that still lacks the acting agent id (packet key absent) must
    # degrade safely: the gate fails OPEN (PASS) with an observable warning,
    # not into a break. This proves the wiring did not remove the safety net.
    packet = build_work_packet("refactor the router module", repo_root=str(tmp_path))
    gate_packet = packet.to_gate_packet()
    # Simulate a legacy/partial packet that never carried the id.
    gate_packet.pop("acting_agent_id", None)
    assert _read_author_id_like_production(gate_packet) == ""

    bundle = GuardrailEvidenceBundle(packet_id=str(gate_packet["packet_id"]))
    bundle.add(_assemble_git_diff_like_production(gate_packet, str(tmp_path)))
    bundle.add(
        collect_review_evidence(
            review_text="scope checked, logic sound",
            reviewer_id=packet.reviewer_worker,
            diff_hash="deadbeef",
            verdict="approve",
            risk_class="RC2",
            contrarian_notes=("consider negative inputs",),
        )
    )

    with caplog.at_level(logging.WARNING, logger="hermes.jarvis_prime.gates"):
        result = strict_review_gate(gate_packet, bundle)

    assert result.outcome is GateOutcome.PASS
    assert any("C19 fail-open" in r.getMessage() for r in caplog.records)
