"""Tests for post-turn memory candidate capture (live-loop wiring)."""

from __future__ import annotations

from hermes_cli.jarvis_prime.memory_capture import (
    CANDIDATE_KINDS,
    DO_NOT_STORE,
    DURABLE_WORTHY,
    KIND_ALIASES,
    REPO_CONVENTION,
    VALID_KINDS,
    MemoryCandidate,
    canonical_kind,
    capture_to_tree,
    extract_candidates,
    is_valid_kind,
)
from hermes_cli.jarvis_prime.memory_tree import (
    ApprovalState,
    MemoryLayer,
    MemoryNamespace,
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
    assert node.layer is MemoryLayer.SESSION  # ty: ignore[unresolved-attribute]  # mock/duck-typed test fixture
    assert node.approval_state is ApprovalState.PROPOSED  # ty: ignore[unresolved-attribute]  # mock/duck-typed test fixture
    # Captured candidates are never durable until owner promotion.
    assert node.layer is not MemoryLayer.DURABLE  # ty: ignore[unresolved-attribute]  # mock/duck-typed test fixture
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


# ---------------------------------------------------------------------------
# vNext taxonomy: recommended six named kinds (additive, backward-compatible)
# ---------------------------------------------------------------------------


def test_recommended_six_kinds_are_recognized() -> None:
    # The canonical taxonomy is exactly the recommended six named kinds.
    assert CANDIDATE_KINDS == {
        "durable_preference",
        "project_direction",
        "workflow_lesson",
        "repo_convention",
        "temporary_context",
        "do_not_store",
    }
    for kind in CANDIDATE_KINDS:
        assert is_valid_kind(kind), kind


def test_legacy_kind_names_still_validate_and_alias() -> None:
    # Backward compatibility: the pre-rename names remain valid and resolve to
    # their recommended-taxonomy equivalents so no persisted data breaks.
    assert canonical_kind("user_preference") == "durable_preference"
    assert canonical_kind("project_decision") == "project_direction"
    assert canonical_kind("failed_assumption") == "workflow_lesson"
    for legacy in KIND_ALIASES:
        assert is_valid_kind(legacy), legacy
    # Finer-grained legacy kinds remain valid on their own (no forced rename).
    for legacy in ("architecture_fact", "verified_code_fix", "research_finding"):
        assert is_valid_kind(legacy)
        assert canonical_kind(legacy) == legacy
    # Every legacy alias is a subset of the recognized kinds.
    assert set(KIND_ALIASES) <= VALID_KINDS


def test_legacy_capture_still_emits_legacy_kind_names() -> None:
    # Default runtime behavior for existing kinds is byte-for-byte unchanged:
    # the deterministic cues still emit the legacy stored ``kind`` values, and
    # the recommended name is available via ``canonical_kind`` only.
    cands = extract_candidates("I prefer Material 3 with Compose.")
    assert cands[0].kind == "user_preference"
    assert cands[0].canonical_kind == "durable_preference"


def test_repo_convention_is_accepted_and_round_trips(tmp_path) -> None:
    # ``repo_convention`` is a first-class recommended kind with no legacy
    # predecessor. It is detected, is durable-worthy, and round-trips through
    # the proposed inbox carrying its typed kind.
    cands = extract_candidates("Our convention is snake_case for module names.")
    assert cands and cands[0].kind == REPO_CONVENTION
    assert cands[0].canonical_kind == REPO_CONVENTION
    assert cands[0].namespace == MemoryNamespace.CODE_PRACTICE.value
    assert REPO_CONVENTION in DURABLE_WORTHY
    assert cands[0].durable_worthy is True

    store = MemoryTreeStore(path=tmp_path / "tree.jsonl")
    results = capture_to_tree(store, cands)
    assert results and all(r.ok for r in results)
    node = results[0].node
    assert node.layer is MemoryLayer.SESSION  # ty: ignore[unresolved-attribute]
    assert node.approval_state is ApprovalState.PROPOSED  # ty: ignore[unresolved-attribute]
    assert REPO_CONVENTION in node.tags  # ty: ignore[unresolved-attribute]
    assert node in store.proposed()


def test_repo_convention_does_not_disturb_existing_cue_precedence() -> None:
    # The additive repo_convention cue is last, so a sentence an earlier cue
    # already claimed keeps its original kind (byte-for-byte precedence).
    cands = extract_candidates("The router lives in runtime.py.")
    assert cands and cands[0].kind == "architecture_fact"


def test_do_not_store_is_a_valid_named_kind_for_a_proposal() -> None:
    # ``do_not_store`` is now a NAMED kind that a candidate can carry (so MUSE
    # can categorize every candidate), not merely an unnamed reject policy.
    assert is_valid_kind(DO_NOT_STORE)
    assert DO_NOT_STORE in CANDIDATE_KINDS
    cand = MemoryCandidate(
        kind=DO_NOT_STORE,
        namespace=MemoryNamespace.GENERAL.value,
        title="do not store: password reset link",
        text="Here is a one-time link the user pasted.",
        confidence=0.5,
        source_trust=SourceTrust.OWNER,
        owner_originated=True,
    )
    assert cand.is_do_not_store is True
    assert cand.canonical_kind == DO_NOT_STORE


def test_do_not_store_candidate_is_rejected_at_write(tmp_path) -> None:
    # Reject-at-write enforcement is unchanged: a do_not_store candidate is
    # never persisted, mirroring the store's secret/CoT reject policy.
    store = MemoryTreeStore(path=tmp_path / "tree.jsonl")
    cand = MemoryCandidate(
        kind=DO_NOT_STORE,
        namespace=MemoryNamespace.GENERAL.value,
        title="do not store: transient chatter",
        text="Just some ephemeral small talk to not remember.",
        confidence=0.5,
        source_trust=SourceTrust.OWNER,
        owner_originated=True,
    )
    results = capture_to_tree(store, [cand])
    assert results and all(not r.ok for r in results)
    assert any("do_not_store" in r.reasons[0] for r in results)
    assert store.proposed() == []


def test_candidate_carries_typed_kind_through_proposed_surface(tmp_path) -> None:
    # A candidate's typed kind survives the proposed -> (owner-gated) surface:
    # promotion stays owner-gated and the promoted node keeps its kind tag.
    store = MemoryTreeStore(path=tmp_path / "tree.jsonl")
    cands = extract_candidates("Our convention is one test module per source file.")
    results = capture_to_tree(store, cands)
    assert results and results[0].ok
    node = results[0].node
    assert REPO_CONVENTION in node.tags  # ty: ignore[unresolved-attribute]
    # Still only proposed — never silently promoted.
    assert node.approval_state is ApprovalState.PROPOSED  # ty: ignore[unresolved-attribute]
    assert store.search(
        "convention", layers=[MemoryLayer.DURABLE]
    ) == []
    # Owner-gated promotion preserves the typed kind tag.
    promoted = store.promote_to_durable(node.id)  # ty: ignore[unresolved-attribute]
    assert promoted.ok
    assert REPO_CONVENTION in promoted.node.tags  # ty: ignore[unresolved-attribute]


# ---------------------------------------------------------------------------
# Load-bearing safety invariants (guard tests)
# ---------------------------------------------------------------------------


def test_extract_candidates_never_emits_do_not_store() -> None:
    # ``do_not_store`` is only ever set *explicitly* on a hand-built candidate;
    # the deterministic extractor must never auto-emit it. This is what makes
    # the capture_to_tree reject-at-write path safe: a caller cannot smuggle a
    # do_not_store categorization in through ordinary extraction, and secret-
    # looking text is rejected by the store's own policy, not by a magic kind.
    samples = (
        "I prefer the key api_key=sk-ABCDEFGHIJKLMNOPQRSTUV0123456789.",
        "My password is hunter2 and I never want to say it again.",
        "We decided to standardize on Material 3.",
        "The system uses a stdlib router.",
        "hello, how are you today?",
        "Our convention is snake_case for module names.",
        "According to the docs, retries are capped.",
        "I was wrong about the default timeout.",
    )
    for text in samples:
        kinds = {c.kind for c in extract_candidates(text)}
        assert DO_NOT_STORE not in kinds, text
        # Also assert on the canonical form, since a legacy kind could in
        # principle resolve onto a canonical name.
        canonical = {c.canonical_kind for c in extract_candidates(text)}
        assert DO_NOT_STORE not in canonical, text


def test_capture_to_tree_result_alignment_with_do_not_store_interleaved(
    tmp_path,
) -> None:
    # runtime.py relies on ``zip(candidates, results)`` for reporting, so
    # capture_to_tree MUST return exactly one result per input candidate, in
    # order — including for do_not_store candidates that never touch the store.
    store = MemoryTreeStore(path=tmp_path / "tree.jsonl")
    storable = extract_candidates("We decided to deploy on Monday.")
    assert len(storable) == 1
    storable_cand = storable[0]
    do_not_store_cand = MemoryCandidate(
        kind=DO_NOT_STORE,
        namespace=MemoryNamespace.GENERAL.value,
        title="do not store: ephemeral chatter",
        text="Just some ephemeral small talk to not remember.",
        confidence=0.5,
        source_trust=SourceTrust.OWNER,
        owner_originated=True,
    )
    candidates = [storable_cand, do_not_store_cand]

    results = capture_to_tree(store, candidates)

    # One result per input candidate, positionally aligned (the zip contract).
    assert len(results) == len(candidates)
    storable_result, do_not_store_result = results

    # The storable candidate is written to the proposed inbox.
    assert storable_result.ok
    node = storable_result.node
    assert node.approval_state is ApprovalState.PROPOSED  # ty: ignore[unresolved-attribute]
    assert node in store.proposed()

    # The do_not_store candidate is rejected and never persisted.
    assert not do_not_store_result.ok
    assert do_not_store_result.node is None
    assert any("do_not_store" in r for r in do_not_store_result.reasons)
    assert store.proposed() == [node]
