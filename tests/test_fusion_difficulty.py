"""Tests for ACT-inspired fusion difficulty classifier.

Verifies that the difficulty classifier correctly routes queries to
different fusion depths, mirroring how Mythos's ACT halting mechanism
allocates compute per token.
"""

from __future__ import annotations

import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from agent.fusion_difficulty import (
    classify_difficulty,
    depth_to_config,
    DifficultyAssessment,
    FusionDepth,
)


# ── Basic classification tests ────────────────────────────────────────

def test_simple_greeting_skips_fusion():
    """A simple 'hi' should skip fusion entirely (ACT halt at depth 0)."""
    result = classify_difficulty(
        prompt="hi",
        response="Hello! How can I help you?",
        tool_iterations=0,
    )
    assert result.depth == FusionDepth.SKIP
    assert result.halted_early is True
    assert result.score < 0.25


def test_thanks_skips_fusion():
    """Gratitude responses are trivial — no need for MoA."""
    result = classify_difficulty(
        prompt="thanks",
        response="You're welcome!",
        tool_iterations=0,
    )
    assert result.depth == FusionDepth.SKIP


def test_what_is_gets_light_or_skip():
    """Simple factual questions should halt early."""
    result = classify_difficulty(
        prompt="What is the capital of France?",
        response="The capital of France is Paris.",
        tool_iterations=0,
    )
    # Should be SKIP or LIGHT — not full fusion
    assert result.depth <= FusionDepth.LIGHT
    assert result.halted_early is True


def test_code_review_gets_deep_fusion():
    """Complex code review queries should get the full MoA council."""
    prompt = (
        "Can you analyze this async Rust architecture and compare the trade-offs "
        "between tokio and async-std for a high-throughput inference server? "
        "I need to optimize the runtime for a recurrent transformer model with "
        "MoE routing. The main bottleneck is the kernel latency during the "
        "attention computation."
    )
    response = (
        "```rust\nasync fn process_batch(model: &Model, input: Tensor) -> Result<()> {\n"
        "    let cached = model.attention.forward(&input).await?;\n"
        "    let routed = model.moe.route(cached).await?;\n"
        "    Ok(())\n}\n```\n"
        "The tokio runtime provides superior scheduling for this workload..."
    )
    result = classify_difficulty(
        prompt=prompt,
        response=response,
        tool_iterations=8,
    )
    assert result.depth == FusionDepth.DEEP
    assert result.halted_early is False
    assert result.score >= 0.75


def test_medium_query_gets_standard():
    """A moderate question without heavy technical content gets standard fusion."""
    prompt = "Can you compare REST and GraphQL APIs? What are the trade-offs?"
    response = (
        "REST and GraphQL are both API architectures. REST uses HTTP methods "
        "like GET, POST, PUT, DELETE. GraphQL uses a single endpoint with queries. "
        "REST is simpler, GraphQL is more flexible."
    )
    result = classify_difficulty(
        prompt=prompt,
        response=response,
        tool_iterations=2,
    )
    # Should be LIGHT or STANDARD
    assert FusionDepth.LIGHT <= result.depth <= FusionDepth.STANDARD


def test_many_tool_iterations_increases_difficulty():
    """More tool calls = harder task (like more ACT loops needed)."""
    easy_prompt = "What is Python?"
    easy_response = "Python is a programming language."

    result_0 = classify_difficulty(easy_prompt, easy_response, tool_iterations=0)
    result_10 = classify_difficulty(easy_prompt, easy_response, tool_iterations=10)

    assert result_10.score > result_0.score


def test_long_technical_response_gets_deep():
    """A long, technical response with code should trigger deep fusion."""
    prompt = (
        "Design and implement a distributed cache protocol. "
        "Analyze the trade-offs between consistency models. "
        "Compare the approaches and optimize for latency."
    )
    response = (
        "```python\n"
        "class CacheNode:\n"
        "    def __init__(self, node_id: int, cluster: list):\n"
        "        self.node_id = node_id\n"
        "        self.cluster = cluster\n"
        "        self.cache = {}\n"
        "        self.lock = threading.Lock()\n"
        "    \n"
        "    def get(self, key: str) -> Optional[Any]:\n"
        "        with self.lock:\n"
        "            return self.cache.get(key)\n"
        "```\n"
        "The cache protocol uses a consistency hash to distribute keys across nodes. "
        "Each node maintains a local cache and a vector clock for conflict resolution. "
        "When a write occurs, the node broadcasts an invalidation message..."
    ) * 3  # Make it long
    result = classify_difficulty(prompt, response, tool_iterations=5)
    assert result.depth == FusionDepth.DEEP


# ── Depth-to-config translation tests ────────────────────────────────

def test_skip_depth_sets_single_mode():
    """SKIP depth should set mode to single (no fusion)."""
    assessment = DifficultyAssessment(
        score=0.1, depth=FusionDepth.SKIP, halted_early=True
    )
    base = {
        "mode": "fusion",
        "reference_models": ["model_a", "model_b", "model_c"],
        "rounds": 1,
    }
    cfg = depth_to_config(assessment, base)
    assert cfg["mode"] == "single"
    assert cfg["reference_models"] == []
    assert cfg["rounds"] == 0


def test_light_depth_uses_2_models():
    """LIGHT depth should use only 2 reference models."""
    assessment = DifficultyAssessment(
        score=0.35, depth=FusionDepth.LIGHT, halted_early=True
    )
    base = {
        "mode": "fusion",
        "reference_models": ["model_a", "model_b", "model_c"],
        "rounds": 1,
    }
    cfg = depth_to_config(assessment, base)
    assert len(cfg["reference_models"]) == 2
    assert cfg["rounds"] == 1


def test_standard_depth_uses_3_models():
    """STANDARD depth should use 3 reference models."""
    assessment = DifficultyAssessment(
        score=0.6, depth=FusionDepth.STANDARD, halted_early=False
    )
    base = {
        "mode": "fusion",
        "reference_models": ["model_a", "model_b", "model_c"],
        "rounds": 1,
    }
    cfg = depth_to_config(assessment, base)
    assert len(cfg["reference_models"]) == 3
    assert cfg["rounds"] == 1


def test_deep_depth_uses_all_models_and_2_rounds():
    """DEEP depth should use all models with at least 2 rounds."""
    assessment = DifficultyAssessment(
        score=0.85, depth=FusionDepth.DEEP, halted_early=False
    )
    base = {
        "mode": "fusion",
        "reference_models": ["model_a", "model_b", "model_c", "model_d"],
        "rounds": 1,
    }
    cfg = depth_to_config(assessment, base)
    assert len(cfg["reference_models"]) == 4
    assert cfg["rounds"] >= 2


# ── Signal tests ──────────────────────────────────────────────────────

def test_technical_density_signal():
    """Technical vocabulary should increase the difficulty score."""
    result = classify_difficulty(
        prompt="explain the neural network architecture",
        response="The model uses attention mechanism with transformer layers...",
        tool_iterations=0,
    )
    assert result.signals["technical_density"] > 0.3


def test_reasoning_markers_signal():
    """Analytical verbs should increase reasoning score."""
    result = classify_difficulty(
        prompt="analyze and compare the performance trade-offs",
        response="Comparison shows...",
        tool_iterations=0,
    )
    assert result.signals["reasoning_markers"] > 0.5


def test_question_complexity_signal():
    """Simple patterns should get low complexity scores."""
    result = classify_difficulty(
        prompt="hi",
        response="hello",
        tool_iterations=0,
    )
    assert result.signals["question_complexity"] < 0.2


# ── Monotonicity tests ───────────────────────────────────────────────

def test_difficulty_increases_with_prompt_length():
    """Longer prompts should not decrease difficulty."""
    short = classify_difficulty("hi", "hello", 0)
    long_prompt = (
        "I need to architect a distributed inference system for a recurrent "
        "transformer model. The system must handle MoE routing across multiple "
        "GPU nodes with fault tolerance. Can you design the protocol for "
        "coordinating expert selection across nodes? Consider the trade-offs "
        "between centralized and decentralized routing approaches."
    )
    long_response = "This is a complex system design question..." * 20
    long_result = classify_difficulty(long_prompt, long_response, 5)
    assert long_result.score > short.score


def test_fusion_depth_ordering():
    """FusionDepth enum should be ordered: SKIP < LIGHT < STANDARD < DEEP."""
    assert FusionDepth.SKIP < FusionDepth.LIGHT
    assert FusionDepth.LIGHT < FusionDepth.STANDARD
    assert FusionDepth.STANDARD < FusionDepth.DEEP


# ── Depth extrapolation tests ───────────────────────────────────────

def test_extrapolate_skip_returns_zero():
    """SKIP depth should extrapolate to 0 rounds."""
    from agent.fusion_difficulty import extrapolate_rounds
    assessment = DifficultyAssessment(score=0.1, depth=FusionDepth.SKIP, halted_early=True)
    assert extrapolate_rounds(assessment, base_rounds=1) == 0


def test_extrapolate_light_returns_one():
    """LIGHT depth should extrapolate to 1 round."""
    from agent.fusion_difficulty import extrapolate_rounds
    assessment = DifficultyAssessment(score=0.35, depth=FusionDepth.LIGHT, halted_early=True)
    assert extrapolate_rounds(assessment, base_rounds=1) == 1


def test_extrapolate_standard_returns_base():
    """STANDARD depth should return base_rounds."""
    from agent.fusion_difficulty import extrapolate_rounds
    assessment = DifficultyAssessment(score=0.6, depth=FusionDepth.STANDARD, halted_early=False)
    assert extrapolate_rounds(assessment, base_rounds=1) == 1
    assert extrapolate_rounds(assessment, base_rounds=2) == 2


def test_extrapolate_deep_adds_rounds():
    """DEEP depth should add extra rounds (like increasing loop count in Mythos)."""
    from agent.fusion_difficulty import extrapolate_rounds
    assessment = DifficultyAssessment(score=0.85, depth=FusionDepth.DEEP, halted_early=False)
    rounds = extrapolate_rounds(assessment, base_rounds=1)
    assert rounds > 1  # more than base


def test_extrapolate_deeper_score_more_rounds():
    """Higher difficulty score in DEEP territory should yield more rounds."""
    from agent.fusion_difficulty import extrapolate_rounds
    less_deep = DifficultyAssessment(score=0.76, depth=FusionDepth.DEEP, halted_early=False)
    very_deep = DifficultyAssessment(score=0.95, depth=FusionDepth.DEEP, halted_early=False)
    assert extrapolate_rounds(very_deep, 1) >= extrapolate_rounds(less_deep, 1)


def test_extrapolate_respects_max_rounds():
    """Extrapolation should be capped at max_rounds."""
    from agent.fusion_difficulty import extrapolate_rounds
    assessment = DifficultyAssessment(score=0.99, depth=FusionDepth.DEEP, halted_early=False)
    rounds = extrapolate_rounds(assessment, base_rounds=1, max_rounds=3)
    assert rounds <= 3


def test_extrapolate_analogous_to_mythos():
    """Depth extrapolation is like Mythos: train at T, infer at T+N.

    In Mythos, a model trained with 16 loops can run 32 or 64 at inference.
    Here, a query with base_rounds=1 can run 2-5 rounds depending on difficulty.
    The key property: MORE compute at inference for HARDER problems, zero
    additional training.
    """
    from agent.fusion_difficulty import extrapolate_rounds
    # Easy (train depth = base) → no extra compute
    easy = DifficultyAssessment(score=0.1, depth=FusionDepth.SKIP, halted_early=True)
    assert extrapolate_rounds(easy, base_rounds=1) == 0

    # Hard (train depth = base) → extrapolate to more compute
    hard = DifficultyAssessment(score=0.90, depth=FusionDepth.DEEP, halted_early=False)
    hard_rounds = extrapolate_rounds(hard, base_rounds=1, max_rounds=5)
    assert hard_rounds >= 2  # at least doubled
    assert hard_rounds <= 5  # capped
