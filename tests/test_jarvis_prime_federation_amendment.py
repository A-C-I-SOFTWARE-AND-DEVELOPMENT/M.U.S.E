"""Tests for the constitution amendment engine (federation/amendment.py).

The load-bearing property: non-amendable clauses are refused at every scale,
under every kind — the structural asset-lock has no exception path.
"""

from pathlib import Path

from hermes_cli.jarvis_prime import constitution
from hermes_cli.jarvis_prime.constitution import Severity
from hermes_cli.jarvis_prime.federation import KIND_AMENDMENT_DECISION
from hermes_cli.jarvis_prime.federation.amendment import (
    NON_AMENDABLE_CLAUSE_IDS,
    AmendmentProposal,
    Scale,
    amendment_process_for_scale,
    evaluate_amendment,
)
from hermes_cli.jarvis_prime.guardrail_evidence import GuardrailLedger

_DOC = Path(__file__).resolve().parents[1] / "docs" / "jarvis-constitution.md"


def test_anti_goal_clauses_exist_and_are_fatal():
    for cid in ("C35", "C36", "C37"):
        c = constitution.clause(cid)
        assert c.article == "IX"
        assert c.severity == Severity.FATAL
        assert cid in NON_AMENDABLE_CLAUSE_IDS
    assert "C34" in NON_AMENDABLE_CLAUSE_IDS
    assert constitution.version() == "1.1"


def test_spec_doc_contains_article_ix():
    text = _DOC.read_text(encoding="utf-8")
    for cid in ("C35", "C36", "C37"):
        assert f"**{cid}**" in text
    assert "Constitution **v1.1**" in text
    assert "non-amendable" in text.lower()


def test_non_amendable_refused_at_every_scale_and_kind():
    for scale in Scale:
        for cid in sorted(NON_AMENDABLE_CLAUSE_IDS):
            for kind in ("modify", "retire", "add"):
                proposal = AmendmentProposal.build(
                    clause_ids=(cid,),
                    kind=kind,
                    rationale="strengthen the clause",
                    scale=scale,
                )
                decision = evaluate_amendment(proposal)
                assert not decision.allowed, f"{cid}/{kind}@{scale} must be refused"
                assert cid in decision.reason
                assert decision.required_process == "none"


def test_locked_clause_hidden_in_batch_is_still_refused():
    proposal = AmendmentProposal.build(
        clause_ids=("C30", "C35"), kind="modify", scale=Scale.E_ENTERPRISE
    )
    decision = evaluate_amendment(proposal)
    assert not decision.allowed
    assert "C35" in decision.reason


def test_allowed_addition_returns_scale_process():
    expected = {
        Scale.A_SOLO: ("ceremonial_phrase", None, 0),
        Scale.B_TEAM: ("quorum", (2, 3), 0),
        Scale.C_COMMUNITY: ("rfc_supermajority", (2, 3), 0),
        Scale.D_STARTUP: ("versioned_covenant", (2, 3), 14),
        Scale.E_ENTERPRISE: ("versioned_covenant", (2, 3), 30),
    }
    for scale, (name, quorum, notice) in expected.items():
        proposal = AmendmentProposal.build(
            clause_ids=("C38",), kind="add", proposed_text="New clause.", scale=scale
        )
        decision = evaluate_amendment(proposal)
        assert decision.allowed
        assert decision.required_process == name
        assert decision.required_quorum == quorum
        assert decision.notice_period_days == notice
        process = amendment_process_for_scale(scale)
        assert process.name == name


def test_add_reusing_existing_id_refused():
    decision = evaluate_amendment(AmendmentProposal.build(clause_ids=("C9",), kind="add"))
    assert not decision.allowed
    assert "append-only" in decision.reason


def test_modify_unknown_clause_refused():
    decision = evaluate_amendment(AmendmentProposal.build(clause_ids=("C999",), kind="modify"))
    assert not decision.allowed
    assert "unknown" in decision.reason


def test_retire_fatal_clause_refused():
    # C5 is FATAL but not in the non-amendable set — retiring it is still refused.
    decision = evaluate_amendment(AmendmentProposal.build(clause_ids=("C5",), kind="retire"))
    assert not decision.allowed
    assert "fatal" in decision.reason.lower()


def test_modify_of_minor_clause_is_allowed():
    decision = evaluate_amendment(
        AmendmentProposal.build(clause_ids=("C30",), kind="modify", scale=Scale.B_TEAM)
    )
    assert decision.allowed
    assert decision.required_process == "quorum"


def test_empty_and_unknown_kind_refused():
    assert not evaluate_amendment(AmendmentProposal.build(clause_ids=(), kind="modify")).allowed
    assert not evaluate_amendment(
        AmendmentProposal.build(clause_ids=("C30",), kind="rewrite")
    ).allowed


def test_decisions_are_ledgered_and_chain_stays_valid(tmp_path):
    ledger = GuardrailLedger(tmp_path / "ledger.jsonl")
    refused = evaluate_amendment(
        AmendmentProposal.build(clause_ids=("C35",), kind="modify"), ledger=ledger
    )
    allowed = evaluate_amendment(
        AmendmentProposal.build(clause_ids=("C38",), kind="add"), ledger=ledger
    )
    records = ledger.read_all()
    assert [r.kind for r in records] == [KIND_AMENDMENT_DECISION] * 2
    assert records[0].subject == refused.proposal_id
    assert records[0].payload["allowed"] is False
    assert records[1].subject == allowed.proposal_id
    assert records[1].payload["allowed"] is True
    assert ledger.verify_chain().ok


def test_proposal_dict_round_trip():
    proposal = AmendmentProposal.build(
        clause_ids=("C38",), kind="add", rationale="r", proposed_text="t", scale=Scale.C_COMMUNITY
    )
    restored = AmendmentProposal.from_dict(proposal.to_dict())
    assert restored == proposal
