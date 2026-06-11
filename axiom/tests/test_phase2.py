"""Phase 2 — the memory plane goes live: the Mind facade, the
contradiction path, and disk persistence across a process kill.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from axiom.core.ledger import Ledger
from axiom.memory.beliefs import ENTRENCH_OWNER, OwnerRequired
from axiom.memory.fsrs_memory import TIER_WORKING
from axiom.memory.mind import Mind


def test_mind_observe_and_recall(tmp_path):
    ledger = Ledger(str(tmp_path / "ledger.db"))
    mind = Mind(tmp_path, ledger)
    mind.observe("the gateway listens on port 8088", source_grade="verified")
    mind.observe("the forge uses glicko-2 ratings", source_grade="verified")
    mind.observe("lunch was a sandwich", source_grade="hearsay")

    hits = mind.recall("what is the gateway port?", k=2)
    assert hits, "recall must return results"
    assert "gateway" in hits[0]["content"]


def test_mind_verification_grades_memory(tmp_path):
    ledger = Ledger(str(tmp_path / "ledger.db"))
    mind = Mind(tmp_path, ledger)
    mid = mind.observe("water boils at 100C", source_grade="verified")
    when = datetime.now(timezone.utc)
    tier = TIER_WORKING
    for _ in range(12):
        tiers = mind.on_verification([mid], passed=True, review_datetime=when)
        tier = tiers[mid]
        when += timedelta(days=14)
        if tier != TIER_WORKING:
            break
    assert tier != TIER_WORKING  # confirmation promotes

    tiers = mind.on_verification([mid], passed=False, review_datetime=when)
    assert tiers[mid] == TIER_WORKING  # contradiction demotes


def test_mind_contradiction_raises_and_ledgers(tmp_path):
    ledger = Ledger(str(tmp_path / "ledger.db"))
    mind = Mind(tmp_path, ledger)
    owner_belief = mind.believe(
        "deploys are frozen on fridays", entrenchment=ENTRENCH_OWNER
    )
    with pytest.raises(OwnerRequired):
        mind.observe(
            "deploy any day is fine",
            source_grade="hearsay",
            contradicts=owner_belief,
        )
    reports = ledger.events("contradiction_report")
    assert reports, "the contradiction must be ledgered"
    assert reports[0]["payload"]["belief_id"] == owner_belief
    # The entrenched belief is untouched.
    assert mind.beliefs.get(owner_belief)["status"] == "ACTIVE"
    assert ledger.verify_chain() is True


def test_mind_weak_belief_is_revised_with_lineage(tmp_path):
    ledger = Ledger(str(tmp_path / "ledger.db"))
    mind = Mind(tmp_path, ledger)
    weak = mind.believe("port is 8088")  # default entrenchment
    result = mind.observe(
        "port is 9090", source_grade="verified", contradicts=weak
    )
    assert mind.beliefs.get(weak)["status"] == "SUPERSEDED"
    chain = mind.beliefs.lineage(weak)
    assert chain[-1]["statement"] == "port is 9090"
    assert result is not None


def test_mind_persistence_across_restart(tmp_path):
    """EXIT GATE: kill the process mid-session (simulated), reopen,
    nothing lost, chain valid."""
    ledger = Ledger(str(tmp_path / "ledger.db"))
    mind = Mind(tmp_path, ledger)
    mid = mind.observe("the registry is content-addressed",
                       source_grade="verified")
    when = datetime.now(timezone.utc)
    last_tier = None
    for _ in range(12):
        tiers = mind.on_verification([mid], passed=True, review_datetime=when)
        last_tier = tiers[mid]
        when += timedelta(days=14)
    bid = mind.believe("never push to main directly",
                       entrenchment=ENTRENCH_OWNER)
    r_before = mind.memories.retrievability(mid, at=when)

    # Simulated kill: drop every object without any orderly shutdown.
    del mind, ledger

    ledger2 = Ledger(str(tmp_path / "ledger.db"))
    mind2 = Mind(tmp_path, ledger2)
    m = mind2.memories.get(mid)
    assert m["tier"] == last_tier  # tier survived
    assert m["content"] == "the registry is content-addressed"
    assert mind2.beliefs.get(bid)["status"] == "ACTIVE"
    assert mind2.beliefs.get(bid)["entrenchment"] == ENTRENCH_OWNER
    r_after = mind2.memories.retrievability(mid, at=when)
    assert r_after == pytest.approx(r_before, abs=1e-9)  # schedule survived
    assert ledger2.verify_chain() is True  # chain valid after the kill
