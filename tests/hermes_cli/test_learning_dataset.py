"""Tests for the JARVIS Learning Dataset Pipeline core."""

from __future__ import annotations

import json

import pytest

from hermes_cli.jarvis_prime.learning_dataset import (
    NEGATIVE_EXAMPLE,
    CandidateStatus,
    DatasetStore,
    Provenance,
    QualityGates,
    RejectedTrace,
    TraceType,
    has_residual_secret,
    strip_chain_of_thought,
)
from hermes_cli.jarvis_prime.memory_tree import SourceTrust


def _store(tmp_path) -> DatasetStore:
    return DatasetStore(path=tmp_path / "learning_dataset.jsonl")


def _prov(**kw) -> Provenance:
    kw.setdefault("source_kind", "manual")
    kw.setdefault("trust", SourceTrust.REPUTABLE)
    return Provenance(**kw)


def _coding_quality() -> QualityGates:
    return QualityGates(
        tests_passed=True, reviewer_passed=True, rollback_available=True
    )


# --- chain-of-thought stripping --------------------------------------------


def test_strip_chain_of_thought_removes_think_blocks():
    text = "Answer: 42\n<think>secret reasoning here</think>\nDone."
    out = strip_chain_of_thought(text)
    assert "secret reasoning" not in out
    assert "Answer: 42" in out
    assert "Done." in out


def test_strip_chain_of_thought_rejects_unclosed_scratchpad():
    with pytest.raises(RejectedTrace):
        strip_chain_of_thought("text <REASONING_SCRATCHPAD> still open")


# --- secret filters --------------------------------------------------------


def test_add_candidate_rejects_residual_private_key(tmp_path):
    store = _store(tmp_path)
    # An openai-style key embedded in a tool result.
    content = {"conversations": [{"from": "tool", "value": "key sk-" + "a" * 40}]}
    # redact masks it, so it should NOT raise on residual; assert it's scrubbed.
    cand = store.add_candidate(
        TraceType.CODING_TASK, content, _prov(), _coding_quality()
    )
    flat = json.dumps(cand.content)
    assert not has_residual_secret(flat)
    assert "sk-" + "a" * 40 not in flat


def test_private_key_block_is_redacted(tmp_path):
    store = _store(tmp_path)
    pem = "-----BEGIN RSA PRIVATE KEY-----\nABCDEF\n-----END RSA PRIVATE KEY-----"
    content = {"conversations": [{"from": "human", "value": pem}]}
    cand = store.add_candidate(
        TraceType.CODING_TASK, content, _prov(), _coding_quality()
    )
    flat = json.dumps(cand.content)
    assert "BEGIN RSA PRIVATE KEY" not in flat


# --- negative-example rule -------------------------------------------------


def test_failed_attempt_without_negative_label_refused(tmp_path):
    store = _store(tmp_path)
    with pytest.raises(RejectedTrace):
        store.add_candidate(
            TraceType.FAILED_ATTEMPT, {"diff": "broken"}, _prov(), QualityGates()
        )


def test_failed_attempt_with_negative_label_stored(tmp_path):
    store = _store(tmp_path)
    cand = store.add_candidate(
        TraceType.FAILED_ATTEMPT,
        {"diff": "broken"},
        _prov(),
        QualityGates(),
        labels=[NEGATIVE_EXAMPLE],
    )
    assert cand.is_negative
    assert cand.status == CandidateStatus.PENDING


# --- quality gates ---------------------------------------------------------


def test_coding_task_requires_gates(tmp_path):
    store = _store(tmp_path)
    with pytest.raises(RejectedTrace):
        store.add_candidate(
            TraceType.CODING_TASK,
            {"conversations": []},
            _prov(),
            QualityGates(tests_passed=True),  # missing reviewer + rollback
        )


def test_research_requires_citations_verified(tmp_path):
    store = _store(tmp_path)
    with pytest.raises(RejectedTrace):
        store.add_candidate(
            TraceType.RESEARCH_ANSWER,
            {"question": "q", "answer": "a"},
            _prov(citations=("https://example.org",)),
            QualityGates(citations_verified=False),
        )
    cand = store.add_candidate(
        TraceType.RESEARCH_ANSWER,
        {"question": "q", "answer": "a"},
        _prov(citations=("https://example.org",)),
        QualityGates(citations_verified=True),
    )
    assert cand.trace_type == TraceType.RESEARCH_ANSWER


# --- bulk scraped ----------------------------------------------------------


def test_bulk_scraped_refused(tmp_path):
    store = _store(tmp_path)
    big = {"text": "x" * 30_000}
    with pytest.raises(RejectedTrace):
        store.add_candidate(
            TraceType.RESEARCH_ANSWER,
            big,
            _prov(citations=(), trust=SourceTrust.UNVERIFIED),
            QualityGates(citations_verified=True),
        )


# --- owner approval + export ----------------------------------------------


def test_only_approved_traces_export(tmp_path):
    store = _store(tmp_path)
    cand = store.add_candidate(
        TraceType.CODING_TASK,
        {"conversations": [{"from": "human", "value": "hi"}]},
        _prov(),
        _coding_quality(),
    )
    out = tmp_path / "export.jsonl"
    # Pending → nothing exported.
    assert store.export_jsonl(out) == 0
    # Approve → exported with provenance + quality labels.
    store.approve(cand.id, note="looks good")
    assert store.export_jsonl(out) == 1
    rec = json.loads(out.read_text().splitlines()[0])
    assert rec["provenance"]["source_kind"] == "manual"
    assert rec["quality"]["tests_passed"] is True


def test_preference_pairs_pair_positive_and_negative(tmp_path):
    store = _store(tmp_path)
    pos = store.add_candidate(
        TraceType.CODING_TASK,
        {"diff": "good"},
        _prov(),
        _coding_quality(),
        task_key="task-1",
    )
    neg = store.add_candidate(
        TraceType.FAILED_ATTEMPT,
        {"diff": "bad"},
        _prov(),
        QualityGates(),
        labels=[NEGATIVE_EXAMPLE],
        task_key="task-1",
    )
    store.approve(pos.id)
    store.approve(neg.id)
    out = tmp_path / "pairs.jsonl"
    assert store.export_preference_pairs(out) == 1
    rec = json.loads(out.read_text().splitlines()[0])
    assert rec["chosen"]["diff"] == "good"
    assert rec["rejected"]["diff"] == "bad"


def test_persistence_round_trip(tmp_path):
    store = _store(tmp_path)
    store.add_candidate(
        TraceType.MOBILE_ACTION,
        {"action": "open_app"},
        _prov(),
        QualityGates(owner_approved=True),
    )
    reloaded = DatasetStore.load(tmp_path / "learning_dataset.jsonl")
    assert len(reloaded.candidates) == 1
    cand = next(iter(reloaded.candidates.values()))
    assert cand.trace_type == TraceType.MOBILE_ACTION
