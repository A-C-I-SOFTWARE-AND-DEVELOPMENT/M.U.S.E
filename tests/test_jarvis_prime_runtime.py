"""Integration tests for hermes_cli.jarvis_prime.runtime — JarvisPrime."""

from __future__ import annotations

from pathlib import Path

import pytest

from hermes_cli.jarvis_prime.memory import MemoryStore
from hermes_cli.jarvis_prime.memory_tree import (
    ApprovalState,
    MemoryLayer,
    MemoryTreeStore,
)
from hermes_cli.jarvis_prime.modes import ClassifierContext, Mode
from hermes_cli.jarvis_prime.runtime import JarvisConfig, JarvisPrime


@pytest.fixture
def jp(tmp_path: Path) -> JarvisPrime:
    # Isolate both the legacy store and the Memory Tree under tmp_path so the
    # default-ON layers wiring never reads the real ~/.hermes during tests.
    config = JarvisConfig(
        memory=MemoryStore(journal_path=tmp_path / "memory.jsonl"),
        memory_tree=MemoryTreeStore(path=tmp_path / "memory_tree.jsonl"),
    )
    return JarvisPrime(config=config)


def test_handle_returns_complete_turn(jp: JarvisPrime) -> None:
    turn = jp.handle("audit the repo for blockers", skip_perceive=True)
    assert turn.classification.mode == Mode.OPERATOR
    assert turn.route is not None
    assert turn.persona_prompt is not None
    assert turn.started_at <= turn.finished_at


def test_handle_explicit_mode_override(jp: JarvisPrime) -> None:
    ctx = ClassifierContext(explicit_mode=Mode.CRITIC)
    turn = jp.handle("any intent", context=ctx, skip_perceive=True)
    assert turn.classification.mode == Mode.CRITIC


def test_handle_recollection_injected_into_prompt(jp: JarvisPrime) -> None:
    jp.remember(
        "mission",
        "ship JARVIS Prime v1.0.0",
        durability="durable",
        confidence=0.95,
    )
    turn = jp.handle("ship the v1 release", skip_perceive=True)
    rendered = turn.persona_prompt.render()
    assert "RECOLLECTION" in rendered
    assert "JARVIS Prime" in rendered


def test_handle_triggers_research_for_unfamiliar_topic(jp: JarvisPrime) -> None:
    turn = jp.handle(
        "explain post-quantum cryptography in detail",
        skip_perceive=True,
    )
    assert turn.research_brief is not None
    assert turn.research_brief.triggered_by in (
        "no_recollection", "unfamiliar_topic", "low_confidence", "code_unknown",
    )


def test_handle_owner_pending_routes_to_owner_decision(jp: JarvisPrime) -> None:
    jp.config.owner_auth.request("package_publish", rationale="release")
    turn = jp.handle("ship the release", skip_perceive=True)
    assert turn.route.target.value == "owner_decision"
    assert turn.route.requires_owner_authorization is True


def test_authorize_clears_pending_action(jp: JarvisPrime) -> None:
    jp.config.owner_auth.request("production_deploy", rationale="hot fix")
    granted = jp.authorize("Yes, with authorization.")
    assert granted == ["production_deploy"]
    assert jp.config.owner_auth.pending_actions() == []


def test_authorize_rejects_loose_phrase(jp: JarvisPrime) -> None:
    jp.config.owner_auth.request("production_deploy", rationale="hot fix")
    assert jp.authorize("go for it") == []
    assert jp.config.owner_auth.pending_actions() == ["production_deploy"]


def test_audit_calibrated_response_passes(jp: JarvisPrime) -> None:
    report = jp.audit("I'm not certain — let me check the repo first.", confidence=0.9)
    assert report.outcome.value == "pass"


def test_audit_low_confidence_demands_research(jp: JarvisPrime) -> None:
    report = jp.audit("definite claim with no hedge", confidence=0.2)
    assert report.outcome.value == "needs_research"


def test_render_handoff_includes_canonical_lines(jp: JarvisPrime) -> None:
    turn = jp.handle("audit repo", skip_perceive=True)
    handoff = jp.render_handoff(turn, result="done", next_step="open PR")
    for label in (
        "Mission:", "Route selected:", "Actions taken:",
        "Verification:", "Owner gates:", "Result:", "Next step:",
    ):
        assert label in handoff


def test_perceive_returns_snapshot(jp: JarvisPrime) -> None:
    snap = jp.perceive(timeout=1.0)
    # Don't assert specific contents — just that the snapshot is well-formed.
    assert snap.timestamp is not None
    assert isinstance(snap.summary(), str)


# ---------------------------------------------------------------------------
# Memory Tree live-loop wiring (MEM-2): recollection augmentation + capture
# ---------------------------------------------------------------------------


def test_recollect_augments_with_cited_memory_tree_pack(jp: JarvisPrime) -> None:
    tree = jp.memory_tree()
    assert tree is not None
    tree.write(
        "Hermes is the canonical backend per the operating spec.",
        namespace="jarvis/architecture",
        title="backend-primary",
        layer=MemoryLayer.DURABLE,
        confidence=0.95,
        source_uri="docs/jarvis-prime-operating-system.md",
        owner_approved=True,
    )
    block = jp.recollect("which backend is canonical")
    assert "CONTEXT PACK" in block
    # The pack cites its source — memory never becomes the source of truth.
    assert "docs/jarvis-prime-operating-system.md" in block


def test_recollect_is_legacy_only_when_layers_disabled(tmp_path: Path) -> None:
    config = JarvisConfig(
        memory=MemoryStore(journal_path=tmp_path / "memory.jsonl"),
        memory_tree=MemoryTreeStore(path=tmp_path / "memory_tree.jsonl"),
        memory_layers_enabled=False,
    )
    jp = JarvisPrime(config=config)
    assert jp.memory_tree() is None
    jp.config.memory_tree.write(
        "Hermes is the canonical backend.",
        namespace="jarvis/architecture",
        title="backend",
        layer=MemoryLayer.DURABLE,
        confidence=0.95,
        owner_approved=True,
    )
    # Flag off → the Tree pack is never appended (byte-identical legacy path).
    assert "CONTEXT PACK" not in jp.recollect("backend")


def test_observe_turn_captures_proposed_candidates(jp: JarvisPrime) -> None:
    summary = jp.observe_turn(
        "We decided to standardize on Material 3.", "Understood."
    )
    assert summary["captured"] >= 1
    assert summary["durable_worthy"] >= 1
    tree = jp.memory_tree()
    proposed = tree.proposed()
    assert proposed, "captured candidate should land in the proposed inbox"
    assert all(n.approval_state is ApprovalState.PROPOSED for n in proposed)
    assert all(n.layer is MemoryLayer.SESSION for n in proposed)


def test_captured_candidate_does_not_leak_into_recall(jp: JarvisPrime) -> None:
    """A capture from one turn must not feed the next turn's prompt unreviewed.

    Regression for the review gate: ``observe_turn`` writes session/proposed
    candidates pending the owner's approval. Before approval they must be
    absent from ``recollect`` so an unreviewed memory cannot steer responses.
    """

    jp.observe_turn("We decided to standardize on Material 3.", "Understood.")
    tree = jp.memory_tree()
    captured = tree.proposed()
    assert captured, "precondition: the turn produced a proposed candidate"

    # The freshly captured (unapproved) fact is excluded from live recall.
    block = jp.recollect("what did we standardize on")
    assert "Material 3" not in block

    # After the owner approves it, the same fact becomes recall-eligible.
    for node in captured:
        tree.set_approval(node.id, ApprovalState.OWNER_APPROVED)
    assert "Material 3" in jp.recollect("what did we standardize on")


def test_observe_turn_rejects_secret_and_never_raises(jp: JarvisPrime) -> None:
    summary = jp.observe_turn(
        "I prefer the token api_key=sk-ABCDEFGHIJKLMNOPQRSTUV0123456789."
    )
    assert summary["captured"] == 0
    assert summary["rejected"] >= 1
    assert jp.memory_tree().proposed() == []


def test_observe_turn_noop_when_layers_disabled(tmp_path: Path) -> None:
    config = JarvisConfig(
        memory=MemoryStore(journal_path=tmp_path / "memory.jsonl"),
        memory_layers_enabled=False,
    )
    jp = JarvisPrime(config=config)
    summary = jp.observe_turn("We decided to deploy on Monday.")
    assert summary == {"captured": 0, "rejected": 0, "durable_worthy": 0}
