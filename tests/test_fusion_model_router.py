"""Tests for MoE-inspired model routing (Mythos/DeepSeek-V3 MoE analog)."""

from __future__ import annotations

import sys
import time
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from agent.fusion_model_router import (
    MoEModelRouter,
    ModelUsageStats,
    QueryType,
    MODEL_SPECIALIZATIONS,
)


# ── Query classification tests ───────────────────────────────────────

def test_classify_code_query():
    """Code queries should be classified as CODE."""
    router = MoEModelRouter(["anthropic/claude-opus-4.6", "deepseek/deepseek-r1"])
    qt = router.classify_query("Debug this Python function: def foo(): return bar", "")
    assert qt == QueryType.CODE


def test_classify_math_query():
    """Math queries should be classified as MATH."""
    router = MoEModelRouter(["anthropic/claude-opus-4.6", "deepseek/deepseek-r1"])
    qt = router.classify_query("Integrate the derivative of x^2 and prove the theorem", "")
    assert qt == QueryType.MATH


def test_classify_creative_query():
    """Creative queries should be classified as CREATIVE."""
    router = MoEModelRouter(["anthropic/claude-opus-4.6"])
    qt = router.classify_query("Write a creative story about a character in a dream", "")
    assert qt == QueryType.CREATIVE


def test_classify_multilingual_query():
    """Multilingual queries should be detected."""
    router = MoEModelRouter(["anthropic/claude-opus-4.6"])
    qt = router.classify_query("Translate this to Spanish please", "")
    assert qt == QueryType.MULTILINGUAL


def test_classify_general_query():
    """Queries with no strong signal should be GENERAL."""
    router = MoEModelRouter(["anthropic/claude-opus-4.6"])
    qt = router.classify_query("I like turtles", "")
    assert qt == QueryType.GENERAL


# ── Model scoring tests ──────────────────────────────────────────────

def test_score_models_returns_scores_for_all():
    """All available models should get a score."""
    router = MoEModelRouter([
        "anthropic/claude-opus-4.6",
        "google/gemini-2.5-pro",
        "deepseek/deepseek-r1",
    ])
    scores = router.score_models(QueryType.CODE)
    assert len(scores) == 3
    for model in router.available_models:
        assert model in scores
        assert 0 <= scores[model] <= 1


def test_deepseek_scores_high_on_math():
    """DeepSeek-R1 should score highest on MATH."""
    router = MoEModelRouter([
        "anthropic/claude-opus-4.6",
        "google/gemini-2.5-pro",
        "deepseek/deepseek-r1",
    ])
    scores = router.score_models(QueryType.MATH)
    assert scores["deepseek/deepseek-r1"] >= scores["anthropic/claude-opus-4.6"]


def test_unknown_model_gets_default_score():
    """Unknown models should get the default score."""
    router = MoEModelRouter(["some/unknown-model"])
    scores = router.score_models(QueryType.CODE)
    assert scores["some/unknown-model"] == 0.75  # _DEFAULT_SCORE


# ── Routing tests ────────────────────────────────────────────────────

def test_route_returns_top_k_models():
    """Router should return exactly top_k models."""
    router = MoEModelRouter([
        "anthropic/claude-opus-4.6",
        "google/gemini-2.5-pro",
        "deepseek/deepseek-r1",
    ])
    selected, qt, scores = router.route("Debug this code", "def foo(): pass", top_k=2)
    assert len(selected) == 2
    assert qt == QueryType.CODE


def test_route_includes_anchor_model():
    """Anchor model should always be included (like shared expert)."""
    router = MoEModelRouter(
        ["anthropic/claude-opus-4.6", "google/gemini-2.5-pro", "deepseek/deepseek-r1"],
        anchor_model="anthropic/claude-opus-4.6",
    )
    selected, _, _ = router.route("Any query", "", top_k=2)
    assert "anthropic/claude-opus-4.6" in selected


def test_route_returns_query_type():
    """Route should return the classified query type."""
    router = MoEModelRouter(["anthropic/claude-opus-4.6"])
    _, qt, _ = router.route("def foo(): pass", "", top_k=1)
    assert qt == QueryType.CODE


# ── Load balancing tests ─────────────────────────────────────────────

def test_record_usage_updates_stats():
    """Recording usage should update model stats."""
    router = MoEModelRouter(["model_a", "model_b"])
    router.record_usage("model_a")
    assert router.stats["model_a"].total_calls == 1


def test_rate_limit_creates_negative_bias():
    """Rate limit hits should create negative bias for that model."""
    router = MoEModelRouter(["model_a", "model_b"])
    initial_bias = router.bias["model_a"]
    router.record_usage("model_a", rate_limited=True)
    assert router.bias["model_a"] < initial_bias


def test_error_creates_small_negative_bias():
    """Errors should create a small negative bias."""
    router = MoEModelRouter(["model_a", "model_b"])
    initial_bias = router.bias["model_a"]
    router.record_usage("model_a", success=False)
    assert router.bias["model_a"] < initial_bias


def test_bias_clamped_to_range():
    """Bias should never exceed [-0.5, 0.5]."""
    router = MoEModelRouter(["model_a", "model_b"])
    # Hammer model_a with rate limits
    for _ in range(100):
        router.record_usage("model_a", rate_limited=True)
    assert -0.5 <= router.bias["model_a"] <= 0.5


def test_underused_model_gets_positive_bias():
    """A model that's never called should get a positive bias boost."""
    router = MoEModelRouter(["model_a", "model_b"])
    # Only call model_a
    for _ in range(20):
        router.record_usage("model_a")
    # model_b should have positive bias (underused)
    assert router.bias["model_b"] > 0


# ── Status tests ─────────────────────────────────────────────────────

def test_get_status_returns_complete_info():
    """Status should include all relevant fields."""
    router = MoEModelRouter(
        ["model_a", "model_b"],
        anchor_model="model_a",
    )
    router.record_usage("model_a")
    status = router.get_status()
    assert "available_models" in status
    assert "anchor_model" in status
    assert "bias" in status
    assert "usage" in status
    assert status["anchor_model"] == "model_a"
    assert status["usage"]["model_a"]["total_calls"] == 1


# ── Model specialization table tests ─────────────────────────────────

def test_all_query_types_have_scores():
    """Every model in the table should have scores for all query types."""
    for model, specs in MODEL_SPECIALIZATIONS.items():
        for qt in QueryType:
            assert qt in specs, f"{model} missing {qt}"


def test_specialization_scores_in_range():
    """All specialization scores should be in [0, 1]."""
    for model, specs in MODEL_SPECIALIZATIONS.items():
        for qt, score in specs.items():
            assert 0 <= score <= 1, f"{model}.{qt} = {score} out of range"
