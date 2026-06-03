"""Cockpit Learning Queue endpoints — list / decide (owner-gated) / export."""

from __future__ import annotations

from pathlib import Path

import pytest

from gateway.cockpit import handlers as h
from hermes_cli.jarvis_prime.learning_dataset import (
    CandidateStatus,
    DatasetStore,
    Provenance,
    QualityGates,
    TraceType,
)
from hermes_cli.jarvis_prime.memory_tree import SourceTrust
from hermes_cli.jarvis_prime.owner_auth import AUTHORIZATION_PHRASE


@pytest.fixture()
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    return tmp_path


def _seed(home: Path):
    store = DatasetStore(path=home / "jarvis_prime" / "learning_dataset.jsonl")
    cand = store.add_candidate(
        TraceType.RESEARCH_ANSWER,
        {"question": "q", "answer": "a"},
        Provenance(
            source_kind="research_vault",
            source_uri="https://example.org",
            citations=("https://example.org",),
            trust=SourceTrust.PRIMARY,
        ),
        QualityGates(citations_verified=True),
    )
    return cand


def test_learning_list_empty(home):
    res = h.learning_list(h.Request(method="GET", path="x"))
    assert res.status == 200
    assert res.payload["learning"] == []


def test_learning_list_returns_card(home):
    cand = _seed(home)
    res = h.learning_list(h.Request(method="GET", path="x"))
    assert res.status == 200
    cards = res.payload["learning"]
    assert len(cards) == 1
    card = cards[0]
    assert card["id"] == cand.id
    assert card["trace_type"] == "research_answer_trace"
    assert card["provenance"]["citations"] == ["https://example.org"]
    assert card["quality"]["citations_verified"] is True


def test_learning_decide_requires_owner_phrase(home):
    cand = _seed(home)
    res = h.learning_decide(
        h.Request(
            method="POST",
            path="x",
            body={"decision": "approve"},  # no phrase
            path_params={"id": cand.id},
        )
    )
    assert res.status == 403


def test_learning_decide_approves_with_phrase(home):
    cand = _seed(home)
    res = h.learning_decide(
        h.Request(
            method="POST",
            path="x",
            body={"decision": "approve", "authorization": AUTHORIZATION_PHRASE},
            path_params={"id": cand.id},
        )
    )
    assert res.status == 200
    assert res.payload["status"] == "approve"
    reloaded = DatasetStore.load(home / "jarvis_prime" / "learning_dataset.jsonl")
    assert reloaded.get(cand.id).status == CandidateStatus.APPROVED


def test_learning_decide_reject_no_phrase(home):
    cand = _seed(home)
    res = h.learning_decide(
        h.Request(
            method="POST",
            path="x",
            body={"decision": "reject"},
            path_params={"id": cand.id},
        )
    )
    assert res.status == 200
    reloaded = DatasetStore.load(home / "jarvis_prime" / "learning_dataset.jsonl")
    assert reloaded.get(cand.id).status == CandidateStatus.REJECTED


def test_learning_decide_unknown_id(home):
    res = h.learning_decide(
        h.Request(
            method="POST",
            path="x",
            body={"decision": "reject"},
            path_params={"id": "nope"},
        )
    )
    assert res.status == 404


def test_learning_export_counts(home):
    cand = _seed(home)
    store = DatasetStore.load(home / "jarvis_prime" / "learning_dataset.jsonl")
    store.approve(cand.id)
    res = h.learning_export(h.Request(method="GET", path="x"))
    assert res.status == 200
    assert res.payload["approved"] == 1
    assert res.payload["exportable"] == 1
    assert "jsonl" in res.payload["formats"]
