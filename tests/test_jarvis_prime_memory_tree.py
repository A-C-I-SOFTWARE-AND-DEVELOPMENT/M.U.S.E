"""Tests for the JARVIS Memory Tree.

Two layers are covered:

* The lightweight, stateless :class:`MemoryTree` used by the CLI lane
  (kept backward compatible).
* The production :class:`MemoryTreeStore`: provenance, confidence floors,
  sensitivity, approval, contradiction/supersession, search ranking,
  context packing, persistence, malformed-line tolerance, and exports.
"""

from __future__ import annotations

from hermes_cli.jarvis_prime.memory_tree import (
    ApprovalState,
    ContradictionStatus,
    MemoryLayer,
    MemorySource,
    MemoryTree,
    MemoryTreeStore,
    SensitivityClass,
    SourceTrust,
    canonicalize_text,
    estimate_tokens,
    stable_memory_id,
)


# ---------------------------------------------------------------------------
# Legacy lightweight tree (unchanged contract)
# ---------------------------------------------------------------------------


def test_memory_tree_adds_and_searches_source_backed_chunks() -> None:
    tree = MemoryTree()
    chunk = tree.add(
        "JARVIS uses Hermes as the canonical operating backend.",
        namespace="jarvis/architecture",
        title="Hermes backend decision",
        source_uri="docs/jarvis-prime-operating-system.md",
        confidence=0.9,
        tags=("architecture",),
    )

    assert chunk is not None
    hits = tree.search("canonical Hermes backend")
    assert hits == [chunk]
    assert hits[0].source_uri == "docs/jarvis-prime-operating-system.md"


def test_memory_tree_outline_groups_by_namespace() -> None:
    tree = MemoryTree()
    tree.add("Owner gates stay active.", namespace="jarvis/safety", title="Owner gates")
    tree.add(
        "Research vault stores evidence.",
        namespace="jarvis/research",
        title="Research vault",
    )

    outline = tree.outline()

    assert "jarvis/research" in outline
    assert "jarvis/safety" in outline
    assert "Owner gates" in outline


def test_memory_tree_ignores_empty_text() -> None:
    tree = MemoryTree()
    assert tree.add("   ", namespace="jarvis", title="empty") is None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def test_helpers_are_deterministic() -> None:
    assert estimate_tokens("") == 0
    assert estimate_tokens("abcd") >= 1
    assert canonicalize_text("  a   b ") == "a b"
    a = stable_memory_id("ns", "title", "  body  text ")
    b = stable_memory_id("ns", "title", "body text")
    assert a == b  # canonicalized before hashing
    assert len(a) == 16


# ---------------------------------------------------------------------------
# Production store: layered writes
# ---------------------------------------------------------------------------


def _store(tmp_path):
    return MemoryTreeStore(path=tmp_path / "memtree.jsonl")


def test_working_and_session_writes_are_unconstrained(tmp_path) -> None:
    store = _store(tmp_path)
    r1 = store.write(
        "scratch note",
        namespace="jarvis/general",
        title="scratch",
        layer=MemoryLayer.WORKING,
    )
    r2 = store.write(
        "session note",
        namespace="jarvis/general",
        title="session",
        layer=MemoryLayer.SESSION,
    )
    assert r1.ok and r2.ok
    assert r1.node.layer is MemoryLayer.WORKING


def test_durable_write_requires_provenance(tmp_path) -> None:
    store = _store(tmp_path)
    result = store.write(
        "Hermes is the canonical backend.",
        namespace="jarvis/architecture",
        title="backend",
        layer=MemoryLayer.DURABLE,
        confidence=0.9,
    )
    assert result.ok is False
    assert any("provenance" in r for r in result.reasons)


def test_durable_write_with_source_succeeds(tmp_path) -> None:
    store = _store(tmp_path)
    result = store.write(
        "Hermes is the canonical backend.",
        namespace="jarvis/architecture",
        title="backend",
        layer=MemoryLayer.DURABLE,
        confidence=0.9,
        source_uri="docs/jarvis-prime-operating-system.md",
        source_trust=SourceTrust.PRIMARY,
    )
    assert result.ok is True
    assert result.node.layer is MemoryLayer.DURABLE


def test_low_confidence_durable_rejected_unless_owner_approved(tmp_path) -> None:
    store = _store(tmp_path)
    low = store.write(
        "Speculative fact.",
        namespace="jarvis/general",
        title="spec",
        layer=MemoryLayer.DURABLE,
        confidence=0.3,
        source_uri="some/doc.md",
    )
    assert low.ok is False
    assert any("confidence" in r for r in low.reasons)

    approved = store.write(
        "Owner-approved decision.",
        namespace="jarvis/decisions",
        title="decision",
        layer=MemoryLayer.DURABLE,
        confidence=0.3,
        owner_approved=True,
    )
    assert approved.ok is True
    assert approved.node.approval_state is ApprovalState.OWNER_APPROVED


def test_sensitive_secret_content_rejected(tmp_path) -> None:
    store = _store(tmp_path)
    secret = store.write(
        "api_key = sk-abcdefghijklmnop1234567890",
        namespace="jarvis/general",
        title="leak",
    )
    assert secret.ok is False
    assert any("secret" in r for r in secret.reasons)

    secret_class = store.write(
        "ordinary text",
        namespace="jarvis/general",
        title="x",
        sensitivity=SensitivityClass.SECRET,
    )
    assert secret_class.ok is False


def test_chain_of_thought_rejected(tmp_path) -> None:
    store = _store(tmp_path)
    cot = store.write(
        "Let me think step by step about the plan and then decide.",
        namespace="jarvis/general",
        title="reasoning",
    )
    assert cot.ok is False
    assert any("chain-of-thought" in r for r in cot.reasons)


def test_transient_emotion_downgraded_to_session(tmp_path) -> None:
    store = _store(tmp_path)
    result = store.write(
        "I feel frustrated right now about the build.",
        namespace="jarvis/personal",
        title="mood",
        layer=MemoryLayer.DURABLE,
        confidence=0.9,
        source_uri="chat",
    )
    assert result.ok is True
    assert result.node.layer is MemoryLayer.SESSION
    assert any("downgraded" in r for r in result.reasons)


def test_dry_run_does_not_persist(tmp_path) -> None:
    store = _store(tmp_path)
    result = store.write(
        "candidate fact",
        namespace="jarvis/general",
        title="c",
        layer=MemoryLayer.SESSION,
        dry_run=True,
    )
    assert result.ok is True
    assert store.nodes == {}


# ---------------------------------------------------------------------------
# Contradictions + supersession
# ---------------------------------------------------------------------------


def _durable(store, text, *, title, ns="jarvis/decisions", conf=0.9):
    return store.write(
        text,
        namespace=ns,
        title=title,
        subject=title,
        layer=MemoryLayer.DURABLE,
        confidence=conf,
        owner_approved=True,
    )


def test_conflicting_facts_create_contradiction_and_contest_both(tmp_path) -> None:
    store = _store(tmp_path)
    a = _durable(store, "We deploy on Friday.", title="deploy-day")
    b = _durable(store, "We deploy on Monday.", title="deploy-day")
    assert b.contradiction is not None
    assert store.get(a.node.id).contradiction_status is ContradictionStatus.CONTESTED
    assert store.get(b.node.id).contradiction_status is ContradictionStatus.CONTESTED


def test_no_silent_overwrite_same_subject_different_text(tmp_path) -> None:
    store = _store(tmp_path)
    a = _durable(store, "We deploy on Friday.", title="deploy-day")
    b = _durable(store, "We deploy on Monday.", title="deploy-day")
    # both records still present — neither silently overwritten
    assert store.get(a.node.id) is not None
    assert store.get(b.node.id) is not None
    assert a.node.id != b.node.id


def test_contradiction_resolution_supersedes_loser(tmp_path) -> None:
    store = _store(tmp_path)
    a = _durable(store, "We deploy on Friday.", title="deploy-day")
    b = _durable(store, "We deploy on Monday.", title="deploy-day")
    report = b.contradiction
    resolved = store.resolve_contradiction(
        report.id, winner_id=b.node.id, note="Monday confirmed"
    )
    assert resolved.status is ContradictionStatus.RESOLVED
    assert store.get(b.node.id).contradiction_status is ContradictionStatus.RESOLVED
    assert store.get(a.node.id).contradiction_status is ContradictionStatus.SUPERSEDED
    assert store.get(a.node.id).superseded_by == b.node.id


def test_contested_memory_excluded_from_default_search_and_context(tmp_path) -> None:
    store = _store(tmp_path)
    _durable(store, "We deploy on Friday.", title="deploy-day")
    _durable(store, "We deploy on Monday.", title="deploy-day")
    default_hits = store.search("deploy")
    assert default_hits == []
    with_contested = store.search("deploy", include_contested=True)
    assert len(with_contested) == 2

    pack = store.context_pack("deploy", token_budget=500)
    assert pack.sections == []
    assert pack.excluded_contested >= 2


# ---------------------------------------------------------------------------
# Search ranking + context pack
# ---------------------------------------------------------------------------


def test_search_ranks_owner_approved_and_trusted_higher(tmp_path) -> None:
    store = _store(tmp_path)
    store.write(
        "Hermes is the backend per the operating spec.",
        namespace="jarvis/architecture",
        title="backend-primary",
        layer=MemoryLayer.DURABLE,
        confidence=0.95,
        source_uri="docs/spec.md",
        source_trust=SourceTrust.PRIMARY,
    )
    store.write(
        "Someone on a forum mentioned a backend.",
        namespace="jarvis/architecture",
        title="backend-rumor",
        layer=MemoryLayer.SESSION,
        confidence=0.4,
        source_uri="forum",
        source_trust=SourceTrust.UNVERIFIED,
    )
    hits = store.search("backend")
    assert hits[0].node.title == "backend-primary"


def test_context_pack_includes_sources_and_respects_budget(tmp_path) -> None:
    store = _store(tmp_path)
    store.write(
        "Hermes is the canonical backend.",
        namespace="jarvis/architecture",
        title="backend",
        layer=MemoryLayer.DURABLE,
        confidence=0.95,
        sources=[
            MemorySource(
                uri="docs/spec.md",
                trust=SourceTrust.PRIMARY,
                excerpt="Hermes is the backend",
            )
        ],
    )
    pack = store.context_pack("backend", token_budget=500)
    assert pack.sections
    assert any("docs/spec.md" in s["sources"] for s in pack.sections)
    assert pack.used_tokens <= 500
    assert "docs/spec.md" in pack.render()

    tiny = store.context_pack("backend", token_budget=1)
    assert tiny.used_tokens <= 1


# ---------------------------------------------------------------------------
# Persistence + exports
# ---------------------------------------------------------------------------


def test_jsonl_persistence_round_trip(tmp_path) -> None:
    path = tmp_path / "memtree.jsonl"
    store = MemoryTreeStore(path=path)
    a = _durable(store, "We deploy on Friday.", title="deploy-day")
    b = _durable(store, "We deploy on Monday.", title="deploy-day")
    store.resolve_contradiction(b.contradiction.id, winner_id=b.node.id)
    assert path.exists()

    reloaded = MemoryTreeStore.load(path)
    assert len(reloaded.nodes) == 2
    assert reloaded.get(a.node.id).superseded_by == b.node.id
    assert reloaded.contradictions


def test_malformed_lines_tolerated_with_diagnostics(tmp_path) -> None:
    path = tmp_path / "memtree.jsonl"
    store = MemoryTreeStore(path=path)
    store.write(
        "good note", namespace="jarvis/general", title="good", layer=MemoryLayer.SESSION
    )
    with open(path, "a", encoding="utf-8") as fh:
        fh.write("this is not json\n")
        fh.write('{"type": "node", "missing": "id"}\n')

    reloaded = MemoryTreeStore.load(path)
    assert len(reloaded.nodes) == 1
    assert len(reloaded.load_diagnostics) == 2


def test_export_markdown_and_audit_cards(tmp_path) -> None:
    store = _store(tmp_path)
    store.write(
        "Hermes is the canonical backend.",
        namespace="jarvis/architecture",
        title="backend",
        layer=MemoryLayer.DURABLE,
        confidence=0.95,
        source_uri="docs/spec.md",
        source_trust=SourceTrust.PRIMARY,
    )
    md = store.export_markdown()
    assert "# JARVIS Memory Tree" in md
    assert "jarvis/architecture" in md
    assert "docs/spec.md" in md

    cards = store.export_audit_cards()
    assert len(cards) == 1
    assert cards[0]["sources"] == ["docs/spec.md"]
    assert cards[0]["trust"] == "primary"


def test_to_dict_from_dict_round_trip(tmp_path) -> None:
    store = _store(tmp_path)
    store.write(
        "note", namespace="jarvis/general", title="n", layer=MemoryLayer.SESSION
    )
    data = store.to_dict()
    clone = MemoryTreeStore.from_dict(data)
    assert len(clone.nodes) == 1
