"""Tests for the DB-free fusion ranker (faithful port of Second Brain's _rank)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from hermes_cli.jarvis_prime.fusion_ranker import (
    FusionCandidate,
    FusionWeights,
    fuse,
    recency_score,
)

_NOW = datetime(2026, 6, 16, tzinfo=timezone.utc)


def test_recency_half_life_decay():
    assert recency_score(_NOW, now=_NOW, half_life_days=30.0) == 1.0
    half = recency_score(_NOW - timedelta(days=30), now=_NOW, half_life_days=30.0)
    assert abs(half - 0.5) < 1e-9
    # Future timestamps clamp to age 0 → 1.0; missing timestamp → 0.0.
    assert recency_score(_NOW + timedelta(days=5), now=_NOW, half_life_days=30.0) == 1.0
    assert recency_score(None, now=_NOW, half_life_days=30.0) == 0.0


def test_priority_score_matches_the_blend_formula():
    # similarity 1, confidence 1, recency 1 (created now) → 0.5 + 0.3 + 0.2 = 1.0
    c = FusionCandidate(id="a", similarity=1.0, confidence=1.0, created_at=_NOW)
    [ranked] = fuse([c], now=_NOW)
    assert abs(ranked.priority_score - 1.0) < 1e-9
    assert ranked.recency == 1.0


def test_ranks_best_first_and_flags_hybrid():
    strong = {"id": "strong", "similarity": 0.9, "confidence": 0.8, "created_at": _NOW,
              "sources": ["vector", "graph"]}
    weak = {"id": "weak", "similarity": 0.1, "confidence": 0.0}
    ranked = fuse([weak, strong], now=_NOW)
    assert [c.id for c in ranked] == ["strong", "weak"]
    assert ranked[0].hybrid is True   # multi-source
    assert ranked[1].hybrid is False  # single/no source


def test_similarity_is_clamped():
    # An out-of-range similarity (anti-correlated / >1) is clamped into [0, 1].
    over = FusionCandidate(id="o", similarity=5.0)
    under = FusionCandidate(id="u", similarity=-3.0)
    ranked = {c.id: c for c in fuse([over, under], now=_NOW)}
    assert ranked["o"].priority_score == 0.5 * 1.0   # clamped to 1.0
    assert ranked["u"].priority_score == 0.0          # clamped to 0.0


def test_weights_from_env(monkeypatch):
    monkeypatch.setenv("SECOND_BRAIN_W_SIMILARITY", "1.0")
    monkeypatch.setenv("SECOND_BRAIN_W_CONFIDENCE", "0.0")
    monkeypatch.setenv("SECOND_BRAIN_W_RECENCY", "0.0")
    w = FusionWeights.from_env()
    assert (w.similarity, w.confidence, w.recency) == (1.0, 0.0, 0.0)
    [c] = fuse([FusionCandidate(id="x", similarity=0.7, confidence=1.0)], weights=w, now=_NOW)
    assert abs(c.priority_score - 0.7) < 1e-9  # only similarity counts


def test_accepts_dicts_and_objects():
    class _R:
        id = "obj"
        similarity = 0.5
        confidence = 0.5

    ranked = fuse([{"id": "d", "similarity": 0.5, "confidence": 0.5}, _R()], now=_NOW)
    assert {c.id for c in ranked} == {"d", "obj"}
