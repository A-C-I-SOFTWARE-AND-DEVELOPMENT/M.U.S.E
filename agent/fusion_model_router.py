"""
MoE-Inspired Model Router — query-aware model selection with load balancing.

Directly inspired by Mythos's Mixture-of-Experts routing (DeepSeek-V3 style).
In Mythos, each token is routed to the top-K experts out of N based on a
router network, with aux-loss-free load balancing ensuring no expert is
over- or under-utilized.

Here, each query is routed to the best-suited models out of the available
pool based on query type, with a bias-based load balancer ensuring no
single API provider is overloaded.

MYTHOS MoE → AXIOM MODEL ROUTING MAP:
    Token → Model query
    Expert → API model (Claude, Gemini, DeepSeek, etc.)
    Router network → Query type classifier (heuristic)
    Top-K selection → Top-K model selection by suitability score
    Aux-loss-free bias → EMA-based provider load bias
    Shared experts → Always-included "anchor" model
    Router bias update → Provider usage tracking + bias adjustment

KEY INNOVATION (from DeepSeek-V3):
    The bias shifts SELECTION but not SCORING. A model's suitability
    score is based on query type, but the final selection includes a
    bias term that pushes underutilized models to be selected more.
    This prevents rate-limit exhaustion on popular providers while
    maintaining quality.
"""

from __future__ import annotations

import logging
import re
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class QueryType(Enum):
    """Query type categories — analogous to expert specializations in MoE.

    Each model (expert) has different strengths for different query types.
    The router classifies the query and selects models accordingly.
    """

    CODE = "code"                # Programming, debugging, architecture
    MATH = "math"                # Mathematics, logic, formal reasoning
    CREATIVE = "creative"        # Writing, brainstorming, storytelling
    ANALYTICAL = "analytical"    # Analysis, comparison, research
    FACTUAL = "factual"          # Quick facts, definitions, lookups
    MULTILINGUAL = "multilingual"  # Non-English, translation
    VISION = "vision"            # Image understanding (if multimodal)
    GENERAL = "general"          # Default — any model can handle


# ── Model specialization scores ──────────────────────────────────────
# Each model gets a suitability score [0, 1] per query type.
# This is like the router logits in MoE — before bias adjustment.
#
# These are heuristic scores based on each model family's known strengths.
# In a production system, these could be learned from feedback data.

MODEL_SPECIALIZATIONS: Dict[str, Dict[QueryType, float]] = {
    "anthropic/claude-opus-4.6": {
        QueryType.CODE: 0.95,
        QueryType.MATH: 0.80,
        QueryType.CREATIVE: 0.90,
        QueryType.ANALYTICAL: 0.95,
        QueryType.FACTUAL: 0.85,
        QueryType.MULTILINGUAL: 0.80,
        QueryType.VISION: 0.75,
        QueryType.GENERAL: 0.95,
    },
    "anthropic/claude-sonnet-4": {
        QueryType.CODE: 0.85,
        QueryType.MATH: 0.70,
        QueryType.CREATIVE: 0.85,
        QueryType.ANALYTICAL: 0.85,
        QueryType.FACTUAL: 0.85,
        QueryType.MULTILINGUAL: 0.75,
        QueryType.VISION: 0.80,
        QueryType.GENERAL: 0.85,
    },
    "google/gemini-2.5-pro": {
        QueryType.CODE: 0.80,
        QueryType.MATH: 0.85,
        QueryType.CREATIVE: 0.85,
        QueryType.ANALYTICAL: 0.80,
        QueryType.FACTUAL: 0.90,
        QueryType.MULTILINGUAL: 0.95,
        QueryType.VISION: 0.95,
        QueryType.GENERAL: 0.85,
    },
    "deepseek/deepseek-r1": {
        QueryType.CODE: 0.90,
        QueryType.MATH: 0.98,
        QueryType.CREATIVE: 0.60,
        QueryType.ANALYTICAL: 0.85,
        QueryType.FACTUAL: 0.75,
        QueryType.MULTILINGUAL: 0.65,
        QueryType.VISION: 0.30,
        QueryType.GENERAL: 0.75,
    },
    "openai/gpt-4o": {
        QueryType.CODE: 0.85,
        QueryType.MATH: 0.85,
        QueryType.CREATIVE: 0.85,
        QueryType.ANALYTICAL: 0.85,
        QueryType.FACTUAL: 0.90,
        QueryType.MULTILINGUAL: 0.85,
        QueryType.VISION: 0.90,
        QueryType.GENERAL: 0.90,
    },
    "meta-llama/llama-4-maverick": {
        QueryType.CODE: 0.80,
        QueryType.MATH: 0.75,
        QueryType.CREATIVE: 0.80,
        QueryType.ANALYTICAL: 0.80,
        QueryType.FACTUAL: 0.80,
        QueryType.MULTILINGUAL: 0.80,
        QueryType.VISION: 0.70,
        QueryType.GENERAL: 0.80,
    },
    "x-ai/grok-4": {
        QueryType.CODE: 0.82,
        QueryType.MATH: 0.82,
        QueryType.CREATIVE: 0.85,
        QueryType.ANALYTICAL: 0.82,
        QueryType.FACTUAL: 0.88,
        QueryType.MULTILINGUAL: 0.75,
        QueryType.VISION: 0.65,
        QueryType.GENERAL: 0.82,
    },
}

# Default model if not in the specialization table
_DEFAULT_SCORE = 0.75


@dataclass
class ModelUsageStats:
    """Track usage per model for load balancing.

    Like the expert frequency counter in DeepSeek-V2's balance loss.
    Used to compute the aux-loss-free bias: underused models get a
    positive bias boost, overused models get a negative bias.
    """

    total_calls: int = 0
    recent_calls: deque = field(default_factory=lambda: deque(maxlen=100))
    last_call_time: float = 0.0
    rate_limit_hits: int = 0
    errors: int = 0

    def record_call(self, timestamp: Optional[float] = None) -> None:
        """Record a model call for load balancing."""
        ts = timestamp or time.time()
        self.total_calls += 1
        self.recent_calls.append(ts)
        self.last_call_time = ts

    def record_rate_limit(self) -> None:
        """Record a rate limit hit — increases the negative bias."""
        self.rate_limit_hits += 1

    def record_error(self) -> None:
        """Record an error — slightly increases the negative bias."""
        self.errors += 1

    def recent_rate(self, window_seconds: float = 60.0) -> float:
        """Calls per second in the recent window."""
        now = time.time()
        cutoff = now - window_seconds
        recent = sum(1 for ts in self.recent_calls if ts > cutoff)
        return recent / window_seconds if window_seconds > 0 else 0.0


class MoEModelRouter:
    """MoE-inspired model router with aux-loss-free load balancing.

    Like Mythos's MoEFFN, this:
    1. Classifies the "token" (query) to determine which "experts" (models)
       are best suited
    2. Scores each model based on specialization (like router logits)
    3. Adds a load-balancing bias (not in gradient graph) to shift selection
    4. Selects top-K models (like top-K expert routing)
    5. Always includes shared "anchor" model(s) (like shared experts)

    The bias update is EMA-based (exponential moving average), mimicking
    how DeepSeek-V3 updates the aux-loss-free bias from routing statistics.
    """

    def __init__(
        self,
        available_models: List[str],
        anchor_model: Optional[str] = None,
        bias_update_rate: float = 0.01,
        rate_limit_penalty: float = 0.5,
        error_penalty: float = 0.1,
    ):
        """Initialize the router.

        Args:
            available_models: List of model IDs to route between
            anchor_model: Always-included model (like shared expert)
            bias_update_rate: EMA rate for bias updates
            rate_limit_penalty: Bias penalty per rate limit hit
            error_penalty: Bias penalty per error
        """
        self.available_models = list(available_models)
        self.anchor_model = anchor_model or (
            available_models[0] if available_models else None
        )
        self.bias_update_rate = bias_update_rate
        self.rate_limit_penalty = rate_limit_penalty
        self.error_penalty = error_penalty

        # Per-model usage stats (for load balancing)
        self.stats: Dict[str, ModelUsageStats] = {
            model: ModelUsageStats() for model in available_models
        }

        # Aux-loss-free bias: not a learned parameter, updated from usage stats
        # Like DeepSeek-V3's router_bias — shifts selection, not scores
        self.bias: Dict[str, float] = {model: 0.0 for model in available_models}

        # EMA of routing frequency per model (for bias computation)
        self.ema_frequency: Dict[str, float] = {
            model: 1.0 / len(available_models) if available_models else 0.0
            for model in available_models
        }

    # Precompiled at class scope: hoisted out of classify_query() hot path.
    # Original code recompiled all 7 patterns on every call (4-7x slowdown).
    _CODE_RE = re.compile(
        r"(```|def |class |import |function |const |let |var |"
        r"async |await |return |=>|->|::|lambda|compile|debug|"
        r"refactor|implement|api|endpoint|deploy|docker|kubernetes|"
        r"git |commit|merge|pull request|stack trace|error|exception)",
        re.IGNORECASE,
    )
    _MATH_RE = re.compile(
        r"(\bintegrate\b|\bderivative\b|\bequation\b|\bmatrix\b|"
        r"\bvector\b|\bproof\b|\btheorem\b|\balgorithm\b|"
        r"\bprobability\b|\bstatistic\b|\boptimi[sz]\b|"
        r"\blinear algebra\b|\bcalculus\b|\bgeometry\b|"
        r"\d+\s*[+\-*/^]\s*\d+|\bmod\b|\bmodulo\b)",
        re.IGNORECASE,
    )
    _CREATIVE_RE = re.compile(
        r"(\bwrite a story\b|\bpoem\b|\bcreative\b|\bbrainstorm\b|"
        r"\bfiction\b|\bnarrative\b|\bcharacter\b|\bplot\b|"
        r"\bscreenplay\b|\bsong\b|\bscript\b|\bdialogue\b|"
        r"\bimagine\b|\bdream\b|\bmetaphor\b)",
        re.IGNORECASE,
    )
    _MULTILINGUAL_RE = re.compile(
        r"(\btranslate\b|\bin (spanish|french|german|chinese|japanese|"
        r"korean|russian|arabic|hindi|portuguese|italian)\b|"
        r"\bmultilingual\b|\bi18n\b|\bl10n\b|"
        r"[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff\uac00-\ud7af"
        r"\u0400-\u04ff\u0600-\u06ff\u0900-\u097f])",
        re.IGNORECASE,
    )
    _ANALYTICAL_RE = re.compile(
        r"(\banalyz\b|\bcompar\b|\bcontrast\b|\bevaluat\b|"
        r"\bassess\b|\binvestigat\b|\bresearch\b|\btrade.?off\b|"
        r"\bpros and cons\b|\bwhy does\b|\bhow does\b|"
        r"\bwhat if\b|\bsynthesi[sz]\b)",
        re.IGNORECASE,
    )
    _FACTUAL_RE = re.compile(
        r"^(\bwhat is\b|\bwho is\b|\bwhen is\b|\bwhere is\b|"
        r"\bdefine\b|\btell me about\b|\bwhat does\b)",
        re.IGNORECASE,
    )

    def classify_query(self, prompt: str, response: str = "") -> QueryType:
        """Classify the query type — like the router network in MoE.

        Uses heuristic pattern matching to determine which "experts"
        (models) are best suited for this query.

        Args:
            prompt: The user's query
            response: Optional response (for additional context)

        Returns:
            QueryType enum value
        """
        combined = f"{prompt} {response}".lower()

        code_score = len(self._CODE_RE.findall(combined))
        math_score = len(self._MATH_RE.findall(combined))
        creative_score = len(self._CREATIVE_RE.findall(combined))
        multilingual_score = len(self._MULTILINGUAL_RE.findall(combined))
        analytical_score = len(self._ANALYTICAL_RE.findall(combined))
        factual_score = 1 if self._FACTUAL_RE.search(prompt.strip()) else 0

        # Select the dominant type
        scores = {
            QueryType.CODE: code_score,
            QueryType.MATH: math_score,
            QueryType.CREATIVE: creative_score,
            QueryType.MULTILINGUAL: multilingual_score,
            QueryType.ANALYTICAL: analytical_score,
            QueryType.FACTUAL: factual_score,
        }

        best_type = max(scores, key=scores.get)
        best_score = scores[best_type]

        if best_score == 0:
            return QueryType.GENERAL

        return best_type

    def score_models(
        self,
        query_type: QueryType,
    ) -> Dict[str, float]:
        """Score each model for the given query type.

        Like the router producing logits for each expert. These scores
        are based on model specializations and do NOT include the bias.

        Args:
            query_type: The classified query type

        Returns:
            Dict of model_id → suitability score [0, 1]
        """
        scores = {}
        for model in self.available_models:
            specs = MODEL_SPECIALIZATIONS.get(model, {})
            score = specs.get(query_type, _DEFAULT_SCORE)
            scores[model] = score
        return scores

    def route(
        self,
        prompt: str,
        response: str = "",
        top_k: int = 3,
    ) -> Tuple[List[str], QueryType, Dict[str, float]]:
        """Route a query to the best-suited models.

        Like Mythos's MoE routing: classify → score → add bias → top-K select.

        Args:
            prompt: The user's query
            response: Optional response for context
            top_k: Number of models to select

        Returns:
            Tuple of (selected_models, query_type, scores)
        """
        # 1. Classify query (like router network forward pass)
        query_type = self.classify_query(prompt, response)

        # 2. Score models (like router logits)
        scores = self.score_models(query_type)

        # 3. Add aux-loss-free bias (shifts selection, not scores)
        biased_scores = {
            model: scores[model] + self.bias.get(model, 0.0)
            for model in self.available_models
        }

        # 4. Always include anchor model (like shared experts)
        selected = []
        if self.anchor_model and self.anchor_model in self.available_models:
            selected.append(self.anchor_model)

        # 5. Select top-K from remaining models
        remaining = [
            (model, score)
            for model, score in biased_scores.items()
            if model not in selected
        ]
        remaining.sort(key=lambda x: x[1], reverse=True)

        for model, _ in remaining:
            if len(selected) >= top_k:
                break
            selected.append(model)

        logger.info(
            "MoE routing: query_type=%s selected=%s scores=%s bias=%s",
            query_type.value, selected,
            {k: round(v, 3) for k, v in scores.items()},
            {k: round(v, 3) for k, v in self.bias.items()},
        )

        return selected, query_type, scores

    def record_usage(
        self,
        model: str,
        success: bool = True,
        rate_limited: bool = False,
        timestamp: Optional[float] = None,
    ) -> None:
        """Record model usage for load balancing.

        Like updating the expert frequency counter in DeepSeek-V2.
        The bias is updated EMA-style from these stats.

        Args:
            model: Model ID that was used
            success: Whether the call succeeded
            rate_limited: Whether the call hit a rate limit
            timestamp: Optional timestamp (defaults to now)
        """
        if model not in self.stats:
            self.stats[model] = ModelUsageStats()

        self.stats[model].record_call(timestamp)

        if rate_limited:
            self.stats[model].record_rate_limit()
            # Immediate penalty for rate limiting (like bias update in V3)
            self.bias[model] -= self.rate_limit_penalty
            logger.warning(
                "MoE router: rate limit on %s, bias adjusted to %.3f",
                model, self.bias[model],
            )

        if not success:
            self.stats[model].record_error()
            self.bias[model] -= self.error_penalty

        # Update EMA frequency and rebalance bias
        self._update_bias()

    def _update_bias(self) -> None:
        """Update the aux-loss-free bias from usage statistics.

        Like DeepSeek-V3's bias update: models that are used less than
        the average get a positive bias boost (more likely to be selected),
        models that are used more get a negative bias (less likely).

        The bias does NOT affect the suitability scores — only selection.
        This is the key insight: load balancing without quality degradation.
        """
        if not self.available_models:
            return

        total_recent = sum(
            self.stats[m].recent_rate() for m in self.available_models
        )
        if total_recent == 0:
            return

        avg_rate = total_recent / len(self.available_models)

        for model in self.available_models:
            model_rate = self.stats[model].recent_rate()
            # EMA update of frequency
            self.ema_frequency[model] = (
                (1 - self.bias_update_rate) * self.ema_frequency[model]
                + self.bias_update_rate * (model_rate / total_recent)
            )

            # Bias: if model is used less than average, boost it
            # If used more than average, penalize it
            freq_ratio = self.ema_frequency[model] / (1.0 / len(self.available_models))
            target_bias = (1.0 - freq_ratio) * 0.1  # small adjustment

            # EMA the bias toward target (smooth updates)
            self.bias[model] = (
                (1 - self.bias_update_rate) * self.bias[model]
                + self.bias_update_rate * target_bias
            )

            # Clamp bias to reasonable range
            self.bias[model] = max(-0.5, min(0.5, self.bias[model]))

    def get_status(self) -> Dict[str, Any]:
        """Get router status for display/debugging."""
        return {
            "available_models": self.available_models,
            "anchor_model": self.anchor_model,
            "bias": {k: round(v, 4) for k, v in self.bias.items()},
            "usage": {
                m: {
                    "total_calls": s.total_calls,
                    "recent_rate": round(s.recent_rate(), 3),
                    "rate_limits": s.rate_limit_hits,
                    "errors": s.errors,
                }
                for m, s in self.stats.items()
            },
        }
