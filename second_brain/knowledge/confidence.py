"""Confidence scoring and adjustment (Layer 5 — Governance & Lifecycle).

Confidence is a bounded scalar in ``(0, 1)`` attached to every
:class:`~knowledge.models.MemoryNode`. It is set at ingestion and adjusted
over the node's lifetime by reinforcement, time decay, corroboration, and
conflict. All functions here are pure; :class:`ConfidenceEngine` simply binds
a :class:`~knowledge.config.LifecycleConfig` so callers need not thread
parameters everywhere. No global state is used.
"""

from __future__ import annotations

import logging
import math
from typing import Optional

from .config import LifecycleConfig

logger = logging.getLogger(__name__)

__all__ = ["clamp", "ConfidenceEngine"]


def clamp(value: float, low: float, high: float) -> float:
    """Clamp ``value`` into the inclusive ``[low, high]`` interval."""
    if low > high:
        raise ValueError(f"invalid clamp bounds: low={low} > high={high}")
    return max(low, min(high, value))


class ConfidenceEngine:
    """Compute and adjust node confidence using a lifecycle policy."""

    def __init__(self, config: Optional[LifecycleConfig] = None) -> None:
        self._config = config or LifecycleConfig()

    @property
    def config(self) -> LifecycleConfig:
        return self._config

    # -- initial scoring --------------------------------------------------- #
    def initial_confidence(
        self,
        *,
        source_trust: float = 0.6,
        extraction_quality: float = 0.5,
        content_tokens: int = 0,
    ) -> float:
        """Estimate a node's initial confidence at ingestion time.

        Combines three signals:

        * ``source_trust`` — caller-supplied trust in the source (0..1).
        * ``extraction_quality`` — how clean the extraction was (0..1).
        * a length prior — extremely short fragments are slightly discounted
          because they carry less verifiable context.
        """
        source_trust = clamp(source_trust, 0.0, 1.0)
        extraction_quality = clamp(extraction_quality, 0.0, 1.0)
        length_prior = 1.0 if content_tokens >= 24 else 0.7 + (content_tokens / 80.0)
        length_prior = clamp(length_prior, 0.5, 1.0)
        raw = (0.55 * source_trust) + (0.30 * extraction_quality) + (0.15 * length_prior)
        return clamp(raw, self._config.confidence_floor, self._config.confidence_ceiling)

    # -- adjustments ------------------------------------------------------- #
    def apply_reinforcement(self, current: float, *, times: int = 1) -> float:
        """Boost confidence when a node is corroborated or re-accessed.

        Uses diminishing returns so repeated reinforcement asymptotes toward
        the ceiling rather than saturating immediately.
        """
        boosted = current
        for _ in range(max(0, times)):
            headroom = self._config.confidence_ceiling - boosted
            boosted += headroom * self._config.reinforcement_boost
        return clamp(boosted, self._config.confidence_floor, self._config.confidence_ceiling)

    def apply_time_decay(self, current: float, *, age_days: float) -> float:
        """Decay confidence toward the floor via exponential half-life."""
        if age_days <= 0:
            return current
        half_life = max(1e-6, self._config.confidence_half_life_days)
        factor = 0.5 ** (age_days / half_life)
        floor = self._config.confidence_floor
        decayed = floor + (current - floor) * factor
        return clamp(decayed, floor, self._config.confidence_ceiling)

    def adjust_for_corroboration(self, current: float, *, corroborations: int) -> float:
        """Raise confidence using noisy-OR aggregation over corroborations.

        Each independent corroboration contributes evidence; the combined
        confidence is ``1 - (1 - current) * prod(1 - w)``.
        """
        if corroborations <= 0:
            return current
        per_witness = 0.15
        combined_miss = 1.0 - current
        for _ in range(corroborations):
            combined_miss *= 1.0 - per_witness
        result = 1.0 - combined_miss
        return clamp(result, self._config.confidence_floor, self._config.confidence_ceiling)

    def penalize_conflict(self, current: float, *, severity: float = 0.5) -> float:
        """Reduce confidence when a node is contradicted by other knowledge."""
        severity = clamp(severity, 0.0, 1.0)
        penalized = current * (1.0 - 0.5 * severity)
        return clamp(penalized, self._config.confidence_floor, self._config.confidence_ceiling)

    def recency_weight(self, *, age_days: float, half_life_days: float) -> float:
        """Map an age in days to a recency weight in ``(0, 1]``."""
        if age_days <= 0:
            return 1.0
        half_life = max(1e-6, half_life_days)
        return math.pow(0.5, age_days / half_life)
