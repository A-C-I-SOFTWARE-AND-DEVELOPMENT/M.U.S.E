"""Gemma 4 — memory curator safety tests.

The curator may *enhance* capture but never weaken the gates: proposals are
SESSION/PROPOSED, low-trust, owner-gated; thought blocks are stripped; secrets
are rejected; unapproved proposals stay out of live recall.
"""

from __future__ import annotations

from pathlib import Path

from muse_cli.jarvis_prime.gemma_memory_curator import (
    GemmaCuratorProposal,
    capture_curator_proposals,
    curate,
    strip_gemma_thought_blocks,
)
from muse_cli.jarvis_prime.memory_tree import (
    ApprovalState,
    MemoryLayer,
    MemoryTreeStore,
    SourceTrust,
)


def test_strip_gemma_thought_blocks() -> None:
    raw = "<think>plan to do X step by step</think>The final answer is 42."
    cleaned = strip_gemma_thought_blocks(raw)
    assert "plan to do X" not in cleaned
    assert "<think>" not in cleaned
    assert "42" in cleaned
    # Reasoning preface form.
    raw2 = "Reasoning: lots of chain of thought here\n\nDark mode is preferred."
    cleaned2 = strip_gemma_thought_blocks(raw2)
    assert "chain of thought" not in cleaned2
    assert "Dark mode" in cleaned2


def test_curate_is_noop_without_runner() -> None:
    assert curate("anything", runner=None) == []


def test_curate_with_fake_runner_strips_thoughts_and_proposes() -> None:
    def fake_runner(_prompt: str) -> str:
        return (
            "<think>internal scratch</think>"
            '[{"title": "Dark mode", "summary": "User prefers dark mode", '
            '"namespace": "jarvis/personal", "confidence": 0.9}]'
        )

    proposals = curate("user said something", runner=fake_runner)
    assert len(proposals) == 1
    p = proposals[0]
    # Trust is clamped below the durable floor regardless of model-claimed conf.
    assert p.confidence <= 0.45
    assert "scratch" not in p.summary


def test_curator_proposals_write_session_proposed_low_trust(tmp_path: Path) -> None:
    store = MemoryTreeStore(path=tmp_path / "tree.jsonl")
    proposal = GemmaCuratorProposal(
        title="Dark mode", summary="User prefers dark mode", namespace="jarvis/personal"
    )
    # The candidate itself is low-trust and non-durable-worthy.
    cand = proposal.to_candidate()
    assert cand.owner_originated is False
    assert cand.source_trust is SourceTrust.COMMUNITY
    assert cand.confidence <= 0.45
    assert not cand.durable_worthy

    results = capture_curator_proposals(store, [proposal])
    assert results and results[0].ok
    node = results[0].node
    assert node is not None
    assert node.layer is MemoryLayer.SESSION
    assert node.approval_state is ApprovalState.PROPOSED
    # It is in the proposed inbox, not durable.
    assert any(n.id == node.id for n in store.proposed())


def test_gemma_memory_excluded_from_recall_until_owner_approves(tmp_path: Path) -> None:
    store = MemoryTreeStore(path=tmp_path / "tree.jsonl")
    proposal = GemmaCuratorProposal(
        title="Standardize", summary="We standardize on Material 3 for the UI",
        namespace="jarvis/decisions",
    )
    results = capture_curator_proposals(store, [proposal])
    node = results[0].node
    assert node is not None

    # Unapproved → excluded from live recall (include_pending=False).
    hits = store.search("Material 3", include_pending=False)
    assert all(h.node.id != node.id for h in hits)

    # Owner approves → becomes recall-eligible.
    store.set_approval(node.id, ApprovalState.OWNER_APPROVED)
    hits2 = store.search("Material 3", include_pending=False)
    assert any(h.node.id == node.id for h in hits2)


def test_secret_like_gemma_output_is_rejected(tmp_path: Path) -> None:
    store = MemoryTreeStore(path=tmp_path / "tree.jsonl")
    proposal = GemmaCuratorProposal(
        title="leak",
        summary="the key is api_key=sk-ABCDEFGHIJKLMNOPQRSTUV0123456789",
        namespace="jarvis/general",
    )
    results = capture_curator_proposals(store, [proposal])
    assert results and not results[0].ok
    assert store.proposed() == []
