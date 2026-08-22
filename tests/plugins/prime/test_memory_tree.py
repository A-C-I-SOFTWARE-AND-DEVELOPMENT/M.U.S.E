"""prime memory_tree — write policy, layers, search, contradictions, exports.

Every test drives the real :class:`MemoryTreeStore` against a JSONL file in
``tmp_path``; nothing is mocked.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from plugins.prime.memory_tree import (
    ApprovalState,
    ContradictionStatus,
    MemoryLayer,
    MemoryTreeStore,
    MemoryWritePolicy,
    SensitivityClass,
    SourceTrust,
    canonicalize_text,
    estimate_tokens,
    stable_memory_id,
)


@pytest.fixture
def store(tmp_path):
    return MemoryTreeStore(path=tmp_path / "memory_tree.jsonl")


def durable(store, text, *, title, confidence=0.9, **kw):
    """Commit a durable fact the write gate will accept."""

    kw.setdefault("namespace", "prime/test")
    kw.setdefault("source_uri", "docs/source.md")
    return store.write(
        text, title=title, layer=MemoryLayer.DURABLE, confidence=confidence, **kw
    )


# ── helpers ──────────────────────────────────────────────────────────────────


def test_estimate_tokens_is_monotonic_and_zero_for_empty():
    assert estimate_tokens("") == 0
    assert estimate_tokens("a") == 1
    assert estimate_tokens("x" * 400) == 100
    assert estimate_tokens("hello world") <= estimate_tokens("hello world again")


def test_canonicalize_collapses_whitespace():
    assert canonicalize_text("  a\n\tb   c ") == "a b c"
    assert canonicalize_text(None) == ""


def test_stable_memory_id_is_deterministic_and_whitespace_insensitive():
    a = stable_memory_id("ns", "Title", "the  fact")
    b = stable_memory_id("ns", "Title", "the fact")
    assert a == b == stable_memory_id("ns", "Title", "\nthe fact\n")
    assert a != stable_memory_id("other", "Title", "the fact")
    assert len(a) == 16


# ── write policy: hard rejections ────────────────────────────────────────────


def test_empty_write_is_refused(store):
    result = store.write("", namespace="ns", title="nothing")
    assert result.ok is False
    assert result.reasons == ("empty text",)
    assert store.nodes == {}


@pytest.mark.parametrize(
    "secret",
    [
        "-----BEGIN RSA PRIVATE KEY-----",
        "AKIAIOSFODNN7EXAMPLE",
        "sk-abcdefghijklmnopqrstuvwx",
        "ghp_abcdefghijklmnopqrstuvwxyz12",
        "xoxb-1234567890-abcdefghij",
        "api_key = hunter2hunter2",
        "Authorization: Bearer abcdefghijklmnopqrst",
    ],
)
def test_secret_like_content_is_never_stored(store, secret):
    result = store.write(secret, namespace="ns", title="oops")
    assert result.ok is False
    assert "secret-like pattern" in result.reasons[0]
    assert store.nodes == {}


def test_secret_in_the_summary_is_also_caught(store):
    result = store.write(
        "harmless body", namespace="ns", title="t", summary="password: hunter2hunter2"
    )
    assert result.ok is False


@pytest.mark.parametrize(
    "text",
    [
        "chain of thought: first I considered ...",
        "Let me think step by step about the config",
        "my internal reasoning was that the cache is cold",
        "thinking out loud here",
    ],
)
def test_chain_of_thought_is_refused(store, text):
    result = store.write(text, namespace="ns", title="cot")
    assert result.ok is False
    assert result.reasons == ("chain-of-thought content is not stored",)


def test_secret_sensitivity_class_is_refused(store):
    result = store.write(
        "nothing obviously secret here",
        namespace="ns",
        title="t",
        sensitivity=SensitivityClass.SECRET,
    )
    assert result.ok is False
    assert result.reasons == ("secret-class content is never stored",)


# ── write policy: the durable gate ───────────────────────────────────────────


def test_durable_write_requires_provenance_or_approval(store):
    result = store.write(
        "the cache lives under HERMES_HOME",
        namespace="ns",
        title="cache",
        layer=MemoryLayer.DURABLE,
        confidence=0.9,
    )
    assert result.ok is False
    assert "provenance or operator approval" in result.reasons[0]


def test_durable_write_accepts_operator_approval_without_provenance(store):
    result = store.write(
        "the cache lives under HERMES_HOME",
        namespace="ns",
        title="cache",
        layer=MemoryLayer.DURABLE,
        confidence=0.1,  # below the floor, but the operator approved it
        operator_approved=True,
    )
    assert result.ok is True
    assert result.node.approval_state == ApprovalState.OPERATOR_APPROVED
    assert result.node.layer == MemoryLayer.DURABLE


def test_durable_write_below_the_confidence_floor_is_refused(store):
    result = durable(store, "a shaky claim", title="shaky", confidence=0.4)
    assert result.ok is False
    assert "below floor" in result.reasons[0]
    assert "operator approval required" in result.reasons[0]


def test_confidence_floor_is_configurable(tmp_path):
    store = MemoryTreeStore(
        path=tmp_path / "m.jsonl",
        policy=MemoryWritePolicy(durable_confidence_floor=0.2),
    )
    assert durable(store, "a shaky claim", title="shaky", confidence=0.4).ok is True


def test_session_layer_needs_no_provenance(store):
    result = store.write("a passing observation", namespace="ns", title="obs")
    assert result.ok is True
    assert result.node.layer == MemoryLayer.SESSION
    assert result.effective_layer == MemoryLayer.SESSION


def test_transient_emotion_is_downgraded_not_stored_durably(store):
    result = durable(store, "I feel great about this release", title="mood")
    assert result.ok is True
    assert result.effective_layer == MemoryLayer.SESSION
    assert result.node.layer == MemoryLayer.SESSION
    assert "downgraded transient emotional state" in result.reasons[0]


def test_emotion_tag_also_triggers_the_downgrade(store):
    result = durable(store, "the release shipped", title="mood", tags=["emotion"])
    assert result.node.layer == MemoryLayer.SESSION


def test_dry_run_validates_without_storing(store):
    result = store.write(
        "a fact", namespace="ns", title="t", dry_run=True, confidence=0.9
    )
    assert result.ok is True
    assert result.node is not None
    assert store.nodes == {}
    assert not (store.path).exists()


def test_confidence_is_clamped(store):
    node = store.write("x", namespace="ns", title="t", confidence=7.5).node
    assert node.confidence == 1.0


def test_summary_defaults_to_the_first_sentence(store):
    node = store.write(
        "The cache is local. It is safe to delete.", namespace="ns", title="t"
    ).node
    assert node.summary == "The cache is local."


# ── contradictions ───────────────────────────────────────────────────────────


def test_conflicting_durable_facts_contest_each_other(store):
    first = durable(store, "The cache lives under HERMES_HOME", title="cache location")
    second = durable(store, "The cache lives in /var/cache", title="cache location")

    report = second.contradiction
    assert report is not None
    assert report.status == ContradictionStatus.CONTESTED
    assert {report.node_a_id, report.node_b_id} == {first.node.id, second.node.id}
    assert store.nodes[first.node.id].contested is True
    assert store.nodes[second.node.id].contested is True
    assert [r.id for r in store.open_contradictions()] == [report.id]


def test_identical_durable_rewrite_is_idempotent(store):
    first = durable(store, "The cache lives under HERMES_HOME", title="cache location")
    again = durable(store, "The cache lives under HERMES_HOME", title="cache location")
    assert again.contradiction is None
    assert again.node.id == first.node.id
    assert len(store.nodes) == 1


def test_a_different_subject_does_not_contradict(store):
    durable(store, "The cache lives under HERMES_HOME", title="cache location")
    other = durable(store, "The vault lives in /var/vault", title="vault location")
    assert other.contradiction is None


def test_a_different_namespace_does_not_contradict(store):
    durable(store, "A", title="cache location", namespace="ns/one")
    other = durable(store, "B", title="cache location", namespace="ns/two")
    assert other.contradiction is None


def test_low_confidence_durable_facts_do_not_contest(tmp_path):
    # Floor the durable gate so a low-confidence durable write is accepted,
    # then confirm the *contest* floor still keeps it out of contradictions.
    store = MemoryTreeStore(
        path=tmp_path / "m.jsonl",
        policy=MemoryWritePolicy(durable_confidence_floor=0.1),
    )
    durable(store, "A", title="cache location", confidence=0.9)
    weak = durable(store, "B", title="cache location", confidence=0.2)
    assert weak.contradiction is None
    assert store.open_contradictions() == []


def test_session_writes_never_contest(store):
    store.write("A", namespace="ns", title="cache location", confidence=0.9)
    second = store.write("B", namespace="ns", title="cache location", confidence=0.9)
    assert second.contradiction is None
    assert store.open_contradictions() == []


def test_explicit_subject_groups_differently_titled_facts(store):
    durable(store, "A", title="first note", subject="cache location")
    clash = durable(store, "B", title="second note", subject="cache location")
    assert clash.contradiction is not None


def test_resolving_a_contradiction_supersedes_the_loser(store):
    first = durable(store, "A", title="cache location")
    second = durable(store, "B", title="cache location")
    report = store.resolve_contradiction(
        second.contradiction.id, second.node.id, "newer measurement"
    )

    winner = store.nodes[second.node.id]
    loser = store.nodes[first.node.id]
    assert report.status == ContradictionStatus.RESOLVED
    assert report.winner_id == second.node.id
    assert report.resolution_note == "newer measurement"
    assert report.resolved_at
    assert winner.contradiction_status == ContradictionStatus.RESOLVED
    assert winner.approval_state == ApprovalState.OPERATOR_APPROVED
    assert winner.supersedes == (first.node.id,)
    assert loser.contradiction_status == ContradictionStatus.SUPERSEDED
    assert loser.superseded_by == second.node.id
    assert loser.active is False
    assert store.open_contradictions() == []


def test_resolving_with_an_unrelated_winner_raises(store):
    durable(store, "A", title="cache location")
    second = durable(store, "B", title="cache location")
    with pytest.raises(ValueError):
        store.resolve_contradiction(second.contradiction.id, "not-a-node")


def test_a_superseded_node_is_not_contested_again(store):
    first = durable(store, "A", title="cache location")
    second = durable(store, "B", title="cache location")
    store.resolve_contradiction(second.contradiction.id, second.node.id)
    third = durable(store, "C", title="cache location")
    # The superseded loser is skipped; only the live winner can contest.
    assert third.contradiction is not None
    assert first.node.id not in (
        third.contradiction.node_a_id,
        third.contradiction.node_b_id,
    )


def test_rewriting_a_contested_fact_does_not_duplicate_the_report(store):
    """A repeat write must not open a second report for the same pair.

    The report id used to be derived from ``other.id + node.id``, so writing
    the same fact again produced the mirrored key and a duplicate report.
    """

    durable(store, "A cache fact", title="cache location")
    durable(store, "B cache fact", title="cache location")
    assert len(store.contradictions) == 1

    again = durable(store, "A cache fact", title="cache location")
    assert again.contradiction is None  # already contested; nothing new
    assert len(store.contradictions) == 1
    assert len(store.open_contradictions()) == 1
    assert len(store.nodes) == 2


def test_rewriting_a_superseded_fact_does_not_resurrect_it(store):
    """The operator's resolution outlives a repeat write of the loser.

    The node id is a function of (namespace, title, canonical text), so
    re-writing a superseded fact verbatim rebuilt the record from scratch —
    clearing ``superseded_by``, making it active again, and re-contesting the
    winner. Both facts then vanished from search.
    """

    first = durable(store, "A cache fact", title="cache location")
    second = durable(store, "B cache fact", title="cache location")
    store.resolve_contradiction(second.contradiction.id, second.node.id, "b wins")

    rewritten = durable(store, "A cache fact", title="cache location")

    loser = store.nodes[first.node.id]
    winner = store.nodes[second.node.id]
    assert rewritten.contradiction is None
    assert loser.superseded_by == second.node.id
    assert loser.contradiction_status == ContradictionStatus.SUPERSEDED
    assert loser.active is False
    assert winner.contradiction_status == ContradictionStatus.RESOLVED
    assert store.open_contradictions() == []
    assert [h.node.id for h in store.search("cache fact")] == [second.node.id]


def test_a_repeat_write_keeps_an_earlier_operator_approval(store):
    approved = store.write(
        "the cache lives under HERMES_HOME",
        namespace="ns",
        title="cache",
        layer=MemoryLayer.DURABLE,
        confidence=0.9,
        operator_approved=True,
    )
    assert approved.node.approval_state == ApprovalState.OPERATOR_APPROVED
    again = store.write(
        "the cache lives under HERMES_HOME",
        namespace="ns",
        title="cache",
        layer=MemoryLayer.DURABLE,
        confidence=0.9,
        source_uri="docs/source.md",  # provenance this time, no --approve
    )
    assert again.node.approval_state == ApprovalState.OPERATOR_APPROVED
    assert again.node.created_at == approved.node.created_at


def test_promoting_a_session_fact_to_durable_still_contests(store):
    """A repeat write skips contradiction detection — unless it is the write
    that makes the fact durable for the first time."""

    store.write("A cache fact", namespace="prime/test", title="cache location")
    durable(store, "B cache fact", title="cache location")
    promoted = durable(store, "A cache fact", title="cache location")
    assert promoted.contradiction is not None


# ── search ───────────────────────────────────────────────────────────────────


def test_search_ranks_by_overlap_and_hides_non_matches(store):
    durable(store, "The prime cache lives under HERMES_HOME", title="cache location")
    store.write("Unrelated note about paint", namespace="prime/test", title="paint")

    hits = store.search("cache HERMES_HOME")
    assert [h.node.title for h in hits] == ["cache location"]
    assert hits[0].score > 0
    assert "cache" in hits[0].matched_terms


def test_durable_outranks_session_for_the_same_terms(store):
    # Everything except the layer is held equal — same confidence, same
    # provenance, same trust — so only the layer bonus can decide the order.
    # (With a stronger durable fixture the assertion passes even when the
    # layer bonus is zero, which makes it prove nothing about layering.)
    store.write(
        "The cache is durable",
        namespace="prime/test",
        title="durable cache",
        layer=MemoryLayer.DURABLE,
        source_uri="docs/source.md",
        confidence=0.9,
    )
    store.write(
        "The cache is transient",
        namespace="prime/test",
        title="session cache",
        layer=MemoryLayer.SESSION,
        source_uri="docs/source.md",
        confidence=0.9,
    )
    hits = store.search("cache")
    assert [h.node.layer for h in hits] == [MemoryLayer.DURABLE, MemoryLayer.SESSION]


def test_search_filters_by_namespace_and_layer(store):
    durable(store, "alpha cache", title="a", namespace="ns/one")
    durable(store, "beta cache", title="b", namespace="ns/two")
    assert [h.node.title for h in store.search("cache", namespaces=["ns/two"])] == ["b"]
    assert store.search("cache", layers=[MemoryLayer.WORKING]) == []


def test_contested_nodes_are_hidden_unless_asked_for(store):
    durable(store, "A cache fact", title="cache location")
    durable(store, "B cache fact", title="cache location")
    assert store.search("cache") == []
    assert len(store.search("cache", include_contested=True)) == 2


def test_superseded_nodes_never_surface(store):
    first = durable(store, "A cache fact", title="cache location")
    second = durable(store, "B cache fact", title="cache location")
    store.resolve_contradiction(second.contradiction.id, second.node.id)
    hits = store.search("cache")
    assert [h.node.id for h in hits] == [second.node.id]
    assert first.node.id not in {h.node.id for h in hits}


def test_stale_nodes_are_penalised(store):
    past = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
    future = (datetime.now(timezone.utc) + timedelta(days=5)).isoformat()
    durable(store, "cache fact one", title="fresh", freshness_due=future)
    durable(store, "cache fact one", title="stale", freshness_due=past)
    hits = store.search("cache fact")
    assert hits[0].node.title == "fresh"


def test_source_trust_weights_the_ranking(store):
    durable(
        store, "cache fact", title="trusted", source_trust=SourceTrust.PRIMARY
    )
    durable(
        store, "cache fact", title="unverified", source_trust=SourceTrust.UNVERIFIED
    )
    hits = store.search("cache fact")
    assert hits[0].node.title == "trusted"


def test_search_limit_is_honoured(store):
    for i in range(5):
        durable(store, f"cache fact {i}", title=f"note {i}")
    assert len(store.search("cache", limit=2)) == 2


def test_search_result_to_dict(store):
    durable(store, "cache fact", title="note")
    d = store.search("cache")[0].to_dict()
    assert set(d) == {"node", "score", "matched_terms"}
    assert d["node"]["title"] == "note"


def test_get_returns_the_node_or_none(store):
    node = durable(store, "cache fact", title="note").node
    assert store.get(node.id) is node
    assert store.get("nope") is None


# ── persistence ──────────────────────────────────────────────────────────────


def test_write_persists_and_reloads(tmp_path):
    path = tmp_path / "memory_tree.jsonl"
    store = MemoryTreeStore(path=path)
    first = durable(store, "A cache fact", title="cache location")
    second = durable(store, "B cache fact", title="cache location")

    reloaded = MemoryTreeStore.load(path)
    assert set(reloaded.nodes) == {first.node.id, second.node.id}
    assert reloaded.nodes[first.node.id].source_uri == "docs/source.md"
    assert reloaded.nodes[first.node.id].layer == MemoryLayer.DURABLE
    assert [r.id for r in reloaded.open_contradictions()] == [
        second.contradiction.id
    ]
    assert reloaded.load_diagnostics == []


def test_persisted_records_are_typed_jsonl(tmp_path):
    path = tmp_path / "memory_tree.jsonl"
    store = MemoryTreeStore(path=path)
    durable(store, "A", title="cache location")
    durable(store, "B", title="cache location")
    kinds = [json.loads(line)["type"] for line in path.read_text().splitlines()]
    assert kinds == ["node", "node", "contradiction"]


def test_loading_a_missing_file_yields_an_empty_store(tmp_path):
    store = MemoryTreeStore.load(tmp_path / "absent.jsonl")
    assert store.nodes == {} and store.contradictions == {}


def test_malformed_lines_are_reported_not_fatal(tmp_path):
    path = tmp_path / "memory_tree.jsonl"
    good = MemoryTreeStore(path=path)
    durable(good, "A cache fact", title="note")
    path.write_text(
        path.read_text() + "not json\n" + json.dumps({"type": "node"}) + "\n",
        encoding="utf-8",
    )
    store = MemoryTreeStore.load(path)
    assert len(store.nodes) == 1
    assert len(store.load_diagnostics) == 2
    assert "malformed JSON" in store.load_diagnostics[0]


def test_persist_false_skips_the_file(tmp_path):
    path = tmp_path / "memory_tree.jsonl"
    store = MemoryTreeStore(path=path)
    store.write("a fact", namespace="ns", title="t", persist=False)
    assert store.nodes
    assert not path.exists()


def test_default_path_follows_hermes_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    store = MemoryTreeStore()
    store.write("a fact", namespace="ns", title="t")
    assert (tmp_path / "prime" / "memory_tree.jsonl").exists()


# ── exports ──────────────────────────────────────────────────────────────────


def test_export_markdown_carries_provenance_and_flags(store):
    durable(store, "A cache fact", title="cache location")
    durable(store, "B cache fact", title="cache location")
    md = store.export_markdown()
    assert "# Memory Tree" in md
    assert "## prime/test" in md
    assert "source: docs/source.md" in md
    assert "CONTESTED" in md
    assert "layer=durable" in md


def test_export_markdown_filters_by_namespace(store):
    durable(store, "alpha", title="a", namespace="ns/one")
    durable(store, "beta", title="b", namespace="ns/two")
    md = store.export_markdown("ns/one")
    assert "ns/one" in md and "ns/two" not in md


def test_audit_cards_expose_the_reviewable_fields(store):
    durable(store, "A cache fact", title="cache location")
    card = store.export_audit_cards()[0]
    assert card["claim"] == "A cache fact"
    assert card["sources"] == ["docs/source.md"]
    assert card["approval_state"] == "proposed"
    assert card["contradiction_status"] == "none"
    assert card["confidence"] == 0.9


def test_outline_groups_by_namespace_and_marks_contested(store):
    durable(store, "A cache fact", title="cache location")
    durable(store, "B cache fact", title="cache location")
    durable(store, "other", title="unrelated", namespace="ns/other")
    outline = store.outline()
    assert "- ns/other" in outline
    assert "- prime/test" in outline
    assert outline.count("[contested]") == 2


def test_node_to_dict_round_trips(store):
    node = durable(store, "A cache fact", title="cache location").node
    from plugins.prime.memory_tree import MemoryNode

    assert MemoryNode.from_dict(node.to_dict()).to_dict() == node.to_dict()
