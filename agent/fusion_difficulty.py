"""
ACT-Inspired Difficulty Classifier for Fusion Routing.

Directly inspired by Mythos's Adaptive Computation Time (ACT) halting
mechanism (Graves, 2016). In Mythos, easy tokens halt early (fewer loop
iterations) and hard tokens run all iterations. Here, the same principle
is applied to Axiom's fusion pipeline:

    Easy query   → halt immediately → skip fusion (return original)
    Medium query → halt after 1     → light fusion (1-2 models, 1 round)
    Hard query   → never halts       → full fusion (all models, max rounds)

Difficulty signals (analogous to the hidden-state features that feed
ACT's halting sigmoid in Mythos):

    1. Prompt length          — short prompts are usually simple questions
    2. Technical vocabulary   — code, math, system design terms increase depth
    3. Reasoning markers      — "compare", "analyze", "design", "implement"
    4. Tool iteration count   — more tool calls = more complex task
    5. Response length        — longer responses indicate complex topics
    6. Question structure     — factual lookup vs multi-step reasoning

The classifier produces a difficulty score in [0, 1] and maps it to
a FusionDepth level, mirroring how ACT's cumulative halt probability
maps to early exit vs full depth.
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class FusionDepth(IntEnum):
    """Fusion depth levels — directly analogous to ACT loop iterations.

    Higher depth = more models consulted = more compute spent refining,
    exactly like more loop iterations in Mythos's recurrent block.

    SKIP    → 0 iterations (easy token halts at loop 0)
    LIGHT   → 1-2 models, 1 round (token halts after a few loops)
    STANDARD → 3 models, 1 round (default fusion)
    DEEP    → all models, 2+ rounds (hard token runs all loops)
    """

    SKIP = 0       # Return original response, no fusion
    LIGHT = 1      # 1-2 reference models, 1 round
    STANDARD = 2   # 3 reference models, 1 round (default MoA)
    DEEP = 3       # All configured models, 2+ rounds


# ── Difficulty signal weights ────────────────────────────────────────
# These map to the same intuition as ACT's halting network: each signal
# contributes evidence about whether the token (query) needs more compute.
#
# The weights are intentionally transparent and tunable — no learned
# parameters, just heuristic features. This keeps the classifier
# interpretable and zero-cost (no model call needed to assess difficulty).

_SIGNAL_WEIGHTS = {
    "prompt_length": 0.15,
    "technical_density": 0.25,
    "reasoning_markers": 0.20,
    "tool_iterations": 0.20,
    "response_length": 0.10,
    "question_complexity": 0.10,
}

# Thresholds mapping difficulty score → FusionDepth.
# Analogous to ACT's act_threshold (cumulative halt probability cutoff).
#
# difficulty < 0.25 → SKIP   (halt immediately, like ACT p > threshold at loop 0)
# difficulty < 0.50 → LIGHT  (halt after minimal compute)
# difficulty < 0.75 → STANDARD (default fusion depth)
# difficulty >= 0.75 → DEEP  (run full depth, never halts early)

_DEPTH_THRESHOLDS = {
    FusionDepth.SKIP: 0.25,
    FusionDepth.LIGHT: 0.50,
    FusionDepth.STANDARD: 0.75,
}


# ── Signal detectors ─────────────────────────────────────────────────

# Technical vocabulary that signals a complex query
_TECHNICAL_PATTERNS = re.compile(
    r"\b("
    r"algorithm|architecture|async|await|benchmark|binary|bootstrap|buffer|cache|"
    r"callback|class|compiler|concurrency|coroutine|cpu|crash|debug|delegate|"
    r"deploy|docker|driver|endpoint|exception|filesystem|framework|function|"
    r"garbage|gradient|gpu|handler|hash|heap|inference|inject|kernel|latency|"
    r"lock|memory|model|mutex|neural|object|optimi[sz]|parse|pointer|process|"
    r"protocol|race|recurrent|recursive|refactor|registry|runtime|schema|"
    r"serialization|server|shader|socket|stack|sync|syntax|tensor|thread|"
    r"tokeni[sz]|training|transform|vector|weight|workflow"
    r")\b",
    re.IGNORECASE,
)

# Reasoning markers — verbs that indicate multi-step analytical thinking
_REASONING_MARKERS = re.compile(
    r"\b("
    r"analyze|architect|compare|contrast|design|diagnose|differentiate|"
    r"debug|implement|integrate|investigate|optimize|plan|reason|"
    r"refactor|review|strategi[sz]e|synthesi[sz]e|troubleshoot|"
    r"why|how does|how would|what if|trade.?off|pros and cons"
    r")\b",
    re.IGNORECASE,
)

# Code indicators — presence suggests technical depth
_CODE_INDICATORS = re.compile(
    r"(```|def |class |import |from |function |const |let |var |"
    r"public |private |async |await |return |if |else |for |while |"
    r"try |catch |throw |=>|->|::|\{\{|\}\}|\$\(|lambda)",
    re.IGNORECASE,
)

# Simple question patterns — usually factual lookups
_SIMPLE_PATTERNS = re.compile(
    r"^(what is|what.s a|who is|when is|where is|define|tell me about|"
    r"what does .{1,20} mean|how do you spell|what.s the time|"
    r"hi|hey|hello|thanks|thank you|ok|okay|sure|yes|no|cool|nice|got it"
    r")\b",
    re.IGNORECASE,
)


@dataclass
class DifficultyAssessment:
    """Result of difficulty classification — analogous to ACT's halting state.

    Attributes:
        score: Overall difficulty in [0, 1]. Like ACT's cumulative halt
               probability, but inverted: higher = harder = more compute.
        depth: The FusionDepth level selected, like ACT's loop count.
        signals: Individual signal scores for transparency/debugging.
        halted_early: True when depth < STANDARD (the query "halted" before
                      running the full fusion pipeline).
    """

    score: float
    depth: FusionDepth
    signals: Dict[str, float] = field(default_factory=dict)
    halted_early: bool = False

    def __repr__(self) -> str:
        return (
            f"DifficultyAssessment(score={self.score:.3f}, "
            f"depth={self.depth.name}, halted_early={self.halted_early})"
        )


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def _signal_prompt_length(prompt: str) -> float:
    """Short prompts are usually simple; long prompts tend to be complex.

    Maps prompt length to [0, 1] via a soft saturating function.
    ~50 chars → 0.3, ~200 chars → 0.6, ~500+ chars → ~0.85
    """
    n = len(prompt)
    return _clamp(1.0 - 50.0 / (50.0 + n))


def _signal_technical_density(prompt: str, response: str) -> float:
    """Fraction of text that contains technical vocabulary or code.

    Combines: technical term density + code indicator presence.
    """
    combined = f"{prompt} {response}"
    total_words = len(combined.split())
    if total_words == 0:
        return 0.0

    tech_hits = len(_TECHNICAL_PATTERNS.findall(combined))
    code_hits = len(_CODE_INDICATORS.findall(combined))

    # Normalize: ~1 tech term per 20 words is high density
    tech_density = _clamp(tech_hits / max(total_words / 20, 1))
    # Code presence is a strong signal
    code_signal = _clamp(code_hits / 10.0)

    return _clamp(0.6 * tech_density + 0.4 * code_signal)


def _signal_reasoning_markers(prompt: str) -> float:
    """Presence of analytical/reasoning verbs indicates multi-step thinking."""
    hits = len(_REASONING_MARKERS.findall(prompt))
    # 1-2 hits = moderate, 3+ = strong
    return _clamp(hits / 3.0)


def _signal_tool_iterations(tool_iterations: int) -> float:
    """More tool calls = more complex task (like more ACT loops needed).

    0 calls → 0.0 (simple Q&A)
    1-3 calls → 0.3-0.5 (light work)
    5+ calls → 0.8+ (heavy multi-step task)
    """
    if tool_iterations <= 0:
        return 0.0
    return _clamp(1.0 - 5.0 / (5.0 + tool_iterations * 2))


def _signal_response_length(response: str) -> float:
    """Longer responses indicate more complex topics.

    < 200 chars → 0.2 (quick answer)
    ~ 1000 chars → 0.5 (moderate)
    ~ 3000+ chars → 0.8 (deep explanation)
    """
    n = len(response)
    return _clamp(1.0 - 200.0 / (200.0 + n))


def _signal_question_complexity(prompt: str) -> float:
    """Classify question structure: simple lookup vs multi-step reasoning.

    Simple patterns ("what is X", "hi", "thanks") → low complexity.
    Multi-clause questions, comparative structures → high complexity.
    """
    # Check for simple patterns first
    if _SIMPLE_PATTERNS.search(prompt.strip()):
        return 0.1

    # Count question marks — multiple questions = higher complexity
    q_marks = prompt.count("?")
    multi_q = _clamp((q_marks - 1) / 3.0)

    # Sentence count as a proxy for multi-part questions
    sentences = max(len(re.split(r"[.!?]+", prompt)) - 1, 1)
    multi_part = _clamp((sentences - 1) / 4.0)

    # Check for comparative/connective structures
    has_comparison = bool(
        re.search(r"\b(vs|versus|compared? to|better than|worse than|instead of)\b",
                  prompt, re.IGNORECASE))
    has_conditionals = bool(
        re.search(r"\b(if|unless|assuming|suppose|given that|in case)\b",
                  prompt, re.IGNORECASE))

    score = 0.3 + 0.25 * multi_q + 0.25 * multi_part
    if has_comparison:
        score += 0.15
    if has_conditionals:
        score += 0.10

    return _clamp(score)


def classify_difficulty(
    prompt: str,
    response: str = "",
    tool_iterations: int = 0,
    config: Optional[Dict[str, Any]] = None,
) -> DifficultyAssessment:
    """Classify query difficulty and select fusion depth.

    This is the ACT halting function for Axiom's fusion pipeline.
    Instead of a learned sigmoid over hidden states, it uses transparent
    heuristic signals to decide how much fusion compute to allocate.

    Args:
        prompt: The user's original query
        response: The model's initial response (if available)
        tool_iterations: Number of tool calls made during this turn
        config: Optional config dict with custom thresholds/weights

    Returns:
        DifficultyAssessment with score, depth, and per-signal breakdown
    """
    cfg = config or {}
    weights = cfg.get("signal_weights", _SIGNAL_WEIGHTS)
    thresholds = cfg.get("depth_thresholds", _DEPTH_THRESHOLDS)

    # Compute individual signals
    signals = {
        "prompt_length": _signal_prompt_length(prompt),
        "technical_density": _signal_technical_density(prompt, response),
        "reasoning_markers": _signal_reasoning_markers(prompt),
        "tool_iterations": _signal_tool_iterations(tool_iterations),
        "response_length": _signal_response_length(response),
        "question_complexity": _signal_question_complexity(prompt),
    }

    # Weighted combination — analogous to ACT's linear projection
    # followed by sigmoid, but here we use a direct weighted sum
    # (signals are already normalized to [0, 1])
    score = sum(
        weights.get(name, 0) * value
        for name, value in signals.items()
    )

    # Normalize by total weight to keep score in [0, 1]
    total_weight = sum(weights.values()) or 1.0
    score = _clamp(score / total_weight)

    # Map score to fusion depth — analogous to ACT cumulative halt check
    if score < thresholds.get(FusionDepth.SKIP, 0.25):
        depth = FusionDepth.SKIP
    elif score < thresholds.get(FusionDepth.LIGHT, 0.50):
        depth = FusionDepth.LIGHT
    elif score < thresholds.get(FusionDepth.STANDARD, 0.75):
        depth = FusionDepth.STANDARD
    else:
        depth = FusionDepth.DEEP

    halted_early = depth < FusionDepth.STANDARD

    logger.debug(
        "Difficulty: score=%.3f depth=%s halted=%s signals=%s",
        score, depth.name, halted_early,
        {k: round(v, 3) for k, v in signals.items()},
    )

    return DifficultyAssessment(
        score=score,
        depth=depth,
        signals=signals,
        halted_early=halted_early,
    )


def extrapolate_rounds(
    assessment: DifficultyAssessment,
    base_rounds: int,
    max_rounds: int = 5,
) -> int:
    """Depth extrapolation — increase fusion rounds for hard queries.

    Directly inspired by Mythos's depth extrapolation: a model trained
    with T=16 loop iterations can run T=32 or T=64 at inference for
    harder problems, with zero additional training.

    Here, the base round count is extrapolated based on difficulty:
    - Easy (SKIP): 0 rounds
    - Light: 1 round (base)
    - Standard: base_rounds (usually 1)
    - Deep: base_rounds + 1-3 extra rounds, capped at max_rounds

    Like Mythos, this happens at inference time with no retraining —
    the fusion pipeline simply runs more rounds for harder queries.

    Args:
        assessment: The difficulty assessment
        base_rounds: Default number of fusion rounds
        max_rounds: Maximum allowed rounds (safety cap)

    Returns:
        Number of rounds to run
    """
    if assessment.depth == FusionDepth.SKIP:
        return 0
    elif assessment.depth == FusionDepth.LIGHT:
        return 1
    elif assessment.depth == FusionDepth.STANDARD:
        return base_rounds
    else:  # DEEP
        # Extrapolate: add rounds proportional to how far above the
        # DEEP threshold the score is. Like increasing loop count
        # proportional to problem difficulty.
        excess = assessment.score - 0.75  # how far into DEEP territory
        extra_rounds = int(excess * 10)  # up to ~2.5 extra rounds
        return min(base_rounds + 1 + extra_rounds, max_rounds)


def depth_to_config(
    assessment: DifficultyAssessment,
    base_config: Dict[str, Any],
) -> Dict[str, Any]:
    """Translate a FusionDepth into concrete MoA parameters.

    Like Mythos choosing how many loop iterations to run, this selects
    how many reference models and rounds to use for the fusion pipeline.

    Args:
        assessment: The difficulty assessment
        base_config: The base fusion config (reference_models, rounds, etc.)

    Returns:
        A modified config dict with model count and rounds adjusted
    """
    cfg = dict(base_config)
    all_models = base_config.get("reference_models", [])
    base_rounds = base_config.get("rounds", 1)

    if assessment.depth == FusionDepth.SKIP:
        # No fusion at all — return original response
        cfg["mode"] = "single"
        cfg["reference_models"] = []
        cfg["rounds"] = 0

    elif assessment.depth == FusionDepth.LIGHT:
        # Light fusion: 1-2 models, 1 round
        cfg["reference_models"] = all_models[:2]
        cfg["rounds"] = 1

    elif assessment.depth == FusionDepth.STANDARD:
        # Standard fusion: 3 models, 1 round (default MoA)
        cfg["reference_models"] = all_models[:3]
        cfg["rounds"] = 1

    elif assessment.depth == FusionDepth.DEEP:
        # Deep fusion: all models, extrapolated rounds (like increasing
        # loop count at inference in Mythos for harder problems)
        cfg["reference_models"] = all_models
        # Use depth extrapolation to compute rounds
        from agent.fusion_difficulty import extrapolate_rounds
        cfg["rounds"] = extrapolate_rounds(assessment, base_rounds, max_rounds=5)

    return cfg
