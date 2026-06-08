"""Tests for hermes_cli.jarvis_prime.self_update — owner-gated proposal flow."""

from __future__ import annotations

from hermes_cli.jarvis_prime.self_update import (
    Proposal,
    ProposalBook,
    ProposalEvidence,
    ProposalKind,
    ProposalStatus,
)


def test_propose_skill_update_returns_proposal() -> None:
    book = ProposalBook()
    p = book.propose(
        kind=ProposalKind.SKILL_UPDATE,
        target_path="skills/jarvis-prime/SKILL.md",
        rationale="user repeatedly asks about budget gates; add a sub-section",
        diff_intent="insert 'Budget gates' under Owner Gates",
        evidence=(
            ProposalEvidence(
                kind="user_correction",
                text="user asked 'why didn't you ask about budget?' twice",
            ),
        ),
    )
    assert p.status == ProposalStatus.PROPOSED
    assert book.pending() == [p]


def test_propose_rc3_needs_owner_approval() -> None:
    book = ProposalBook()
    p = book.propose(
        kind=ProposalKind.ROUTING_RULE_UPDATE,
        target_path="docs/ai-intelligence/model-routing-policy.md",
        rationale="codex preferred ahead of aider for python now",
        diff_intent="swap precedence in routing policy",
        risk_class="RC3",
    )
    assert p.status == ProposalStatus.NEEDS_OWNER_APPROVAL


def test_approve_moves_to_approved() -> None:
    book = ProposalBook()
    p = book.propose(
        kind=ProposalKind.AGENT_UPDATE,
        target_path=".claude/agents/contrarian-reviewer.md",
        rationale="refine activation trigger",
        diff_intent="tighten 'when not to use' section",
    )
    p.approve("owner reviewed during weekly sync")
    assert p.status == ProposalStatus.APPROVED


def test_reject_moves_to_rejected() -> None:
    book = ProposalBook()
    p = book.propose(
        kind=ProposalKind.NEW_AGENT,
        target_path=".claude/agents/over-eager-helper.md",
        rationale="we could use another helper",
        diff_intent="create a new always-active agent",
    )
    p.reject("violates 'don't expand always-active by default'")
    assert p.status == ProposalStatus.REJECTED


def test_render_for_owner_lists_pending() -> None:
    book = ProposalBook()
    book.propose(
        kind=ProposalKind.SKILL_UPDATE,
        target_path="skills/jarvis-prime/SKILL.md",
        rationale="refine companion mode rules",
        diff_intent="add 'do not save anger' clarification",
    )
    rendered = book.render_for_owner()
    assert "PENDING SELF-UPDATE PROPOSALS" in rendered
    assert "skill_update" in rendered
    assert "skills/jarvis-prime/SKILL.md" in rendered


def test_render_empty_when_no_pending() -> None:
    book = ProposalBook()
    assert "No MUSE self-update proposals pending." == book.render_for_owner()


def test_mark_applied_records_commit_sha() -> None:
    book = ProposalBook()
    p = book.propose(
        kind=ProposalKind.SKILL_UPDATE,
        target_path="skills/jarvis-prime/SKILL.md",
        rationale="r",
        diff_intent="d",
    )
    p.approve("ok")
    p.mark_applied("abc1234")
    assert p.status == ProposalStatus.APPLIED
    assert "abc1234" in (p.owner_decision_note or "")
