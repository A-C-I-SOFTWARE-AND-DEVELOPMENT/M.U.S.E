"""Ambition layer — additive, bar-raising objective dimensions.

The owner wants a frontier-seeking, long-horizon, creative, human-compassionate
disposition. We encode that as *extra selectivity on top of the safety floor*:
ambition can only ever make promotion **harder**, never easier.

Contract (enforced by tests):

* :func:`apply_ambition` may flip a ``passed=True`` verdict to ``False`` (adding
  reasons), but can **never** flip ``False`` -> ``True``.
* It never mutates the safety-bearing fields of the verdict
  (``floor_violations``, ``safety_regressions``, ``dropped_domains``).

So "100-year value / creativity / compassion" raise the bar without ever being
able to trade away a safety gate. This is the structural answer to "be ambitious
but never worsen itself".
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Mapping

from .validators import RatchetVerdict

AMBITION_DIMENSIONS: tuple[str, ...] = (
    "frontier_seeking",
    "long_horizon_value",
    "creativity",
    "human_compassion",
)


@dataclass(frozen=True)
class AmbitionProfile:
    """Per-dimension minimum scores a challenger must additionally clear."""

    required_minimums: Mapping[str, float]

    @classmethod
    def default(cls) -> "AmbitionProfile":
        # Modest defaults: ambition is opt-in strictness, not a wall by itself.
        return cls(required_minimums={d: 0.0 for d in AMBITION_DIMENSIONS})


def apply_ambition(
    verdict: RatchetVerdict,
    ambition_scores: Mapping[str, float],
    profile: AmbitionProfile,
) -> RatchetVerdict:
    """AND an extra ambition requirement onto an already-computed verdict.

    Returns a new verdict. Can only narrow ``passed`` (True -> False); never
    widens it, and never touches the safety fields.
    """

    # If the ratchet already failed, ambition cannot rescue it — return as-is.
    if not verdict.passed:
        return verdict

    shortfalls: list[str] = []
    for dim, minimum in profile.required_minimums.items():
        score = ambition_scores.get(dim)
        if score is None:
            if minimum > 0.0:
                shortfalls.append(f"ambition '{dim}' score missing (need >= {minimum:.2f})")
            continue
        if score < minimum:
            shortfalls.append(
                f"ambition '{dim}' {score:.3f} < required {minimum:.2f}"
            )

    if not shortfalls:
        return verdict

    # Narrow to fail; preserve every safety field untouched.
    return replace(
        verdict,
        passed=False,
        reasons=verdict.reasons + tuple(shortfalls),
    )


__all__ = ["AMBITION_DIMENSIONS", "AmbitionProfile", "apply_ambition"]
