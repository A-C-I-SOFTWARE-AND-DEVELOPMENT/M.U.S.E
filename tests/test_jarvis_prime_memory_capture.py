"""Tests for post-turn memory candidate capture (live-loop wiring)."""

from __future__ import annotations

from hermes_cli.jarvis_prime.memory_capture import (
    DURABLE_WORTHY,
    capture_to_tree,
    extract_candidates,
)
from hermes_cli.jarvis_prime.memory_tree import (
    ApprovalState,
    MemoryLayer,
    MemoryTreeStore,
    SourceTrust,
)


def _kinds(user_text, assistant_text=""):
    return {c.kind for c in extract_candidates(user_text, assistant_text)}


def test_extracts_user_preference() -> None:
    cands = extract_candidates("I prefer Material 3 with Compose.")
    assert cands and cands[0].kind == "user_preference"
    assert cands[0].owner_originated is True
    assert cands[0].source_trust is SourceTrust.OWNER
    assert cands[0].namespace == "jarvis/personal"


def test_extracts_project_decision_architecture_and_fix() -> None:
    text = (
        "We decided to use SSE for the cockpit. "
        "The system uses a stdlib router. "
        "The bug was a missing await; the tests now pass."
    )
    kinds = _kinds(text)
    assert "project_decision" in kinds
    assert "architecture_fact" in kinds
    assert "verified_code_fix" in kinds


def test_extracts_research_finding_and_failed_assumption() -> None:
    kinds = _kinds(
        "According to the docs, retries are capped. "
        "I was wrong about the default timeout."
    )
    assert "research_finding" in kinds
    assert "failed_assumption" in kinds


def test_durable_worthy_classification() -> None:
    assert "project_decision" in DURABLE_WORTHY
    assert "architecture_fact" in DURABLE_WORTHY
    assert "verified_code_fix" in DURABLE_WORTHY
    assert "user_preference" not in DURABLE_WORTHY
    assert "research_finding" not in DURABLE_WORTHY


def test_assistant_text_is_low_trust() -> None:
    cands = extract_candidates("", "We decided to ship on Friday.")
    assert cands
    assert all(c.source_trust is SourceTrust.COMMUNITY for c in cands)
    assert all(c.owner_originated is False for c in cands)


def test_capture_writes_session_proposed_nodes(tmp_path) -> None:
    store = MemoryTreeStore(path=tmp_path / "tree.jsonl")
    cands = extract_candidates("We decided to standardize on Material 3.")
    results = capture_to_tree(store, cands)
    assert results and all(r.ok for r in results)
    node = results[0].node
    assert node.layer is MemoryLayer.SESSION
    assert node.approval_state is ApprovalState.PROPOSED
    # Captured candidates are never durable until owner promotion.
    assert node.layer is not MemoryLayer.DURABLE
    assert node in store.proposed()


def test_capture_rejects_secret_content(tmp_path) -> None:
    store = MemoryTreeStore(path=tmp_path / "tree.jsonl")
    cands = extract_candidates(
        "I prefer the key api_key=sk-ABCDEFGHIJKLMNOPQRSTUV0123456789."
    )
    results = capture_to_tree(store, cands)
    assert results, "a candidate should be extracted"
    assert all(not r.ok for r in results)
    assert store.proposed() == []


def test_capture_rejects_chain_of_thought(tmp_path) -> None:
    store = MemoryTreeStore(path=tmp_path / "tree.jsonl")
    # CoT marker inside a sentence that also trips a cue.
    cands = extract_candidates(
        "I prefer this: let me think step by step about the plan."
    )
    results = capture_to_tree(store, cands)
    assert results
    assert all(not r.ok for r in results)


def test_no_candidates_from_smalltalk(tmp_path) -> None:
    assert extract_candidates("hello, how are you today?") == []


def test_durable_candidate_not_auto_durable_only_proposed(tmp_path) -> None:
    store = MemoryTreeStore(path=tmp_path / "tree.jsonl")
    cands = extract_candidates("We decided to deploy on Monday.")
    capture_to_tree(store, cands)
    # Nothing durable exists until the owner promotes it.
    assert store.search("deploy", layers=[MemoryLayer.DURABLE]) == []
    inbox = store.proposed()
    assert any("deploy" in n.text.lower() for n in inbox)
