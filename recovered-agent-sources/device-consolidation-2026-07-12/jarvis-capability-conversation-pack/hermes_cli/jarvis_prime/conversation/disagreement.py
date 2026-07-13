"""Disagreement and challenge phrasing for the conversation engine.

Jarvis Prime is loyal to the mission, not to the moment. When an idea is
weak, the response should disagree plainly. The choice between a
*gentle* and a *hard* challenge depends on how confident Jarvis is that
the idea is weak and how high-stakes the decision is.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ChallengeStrength(str, Enum):
    """How forcefully Jarvis pushes back."""

    NONE = "none"
    GENTLE = "gentle"
    HARD = "hard"


@dataclass(frozen=True)
class ChallengeBlock:
    """A disagreement section ready to drop into a response."""

    strength: ChallengeStrength
    opener: str
    objection: str
    stronger_version: str | None = None


_GENTLE_OPENERS: tuple[str, ...] = (
    "One thing to push on:",
    "A softer flag here:",
    "Worth pressure-testing:",
)


_HARD_OPENERS: tuple[str, ...] = (
    "I disagree.",
    "That is not the move.",
    "Honest take: this is the wrong shape.",
)


_CRITIQUE_REQUEST_MARKERS: tuple[str, ...] = (
    "critique",
    "critic",
    "tear apart",
    "rip this",
    "what is wrong with",
    "what's wrong with",
    "be honest",
    "honest take",
    "challenge me",
    "push back",
    "stress test",
    "stress-test",
    "blind spot",
    "weak spot",
    "what could go wrong",
)


def wants_critique(text: str) -> bool:
    """Return True when the user explicitly asked to be challenged."""
    if not text:
        return False
    lowered = text.lower()
    return any(marker in lowered for marker in _CRITIQUE_REQUEST_MARKERS)


def gentle_challenge(objection: str, stronger_version: str | None = None) -> ChallengeBlock:
    """Return a softly-phrased pushback block."""
    return ChallengeBlock(
        strength=ChallengeStrength.GENTLE,
        opener=_GENTLE_OPENERS[0],
        objection=objection.strip().rstrip("."),
        stronger_version=stronger_version,
    )


def hard_challenge(objection: str, stronger_version: str | None = None) -> ChallengeBlock:
    """Return a direct disagreement block led by the strongest objection."""
    return ChallengeBlock(
        strength=ChallengeStrength.HARD,
        opener=_HARD_OPENERS[0],
        objection=objection.strip().rstrip("."),
        stronger_version=stronger_version,
    )


def render_challenge(block: ChallengeBlock) -> str:
    """Render a ChallengeBlock to text."""
    if block.strength == ChallengeStrength.NONE:
        return ""

    lines = [block.opener, block.objection + "."]
    if block.stronger_version:
        lines.append("Stronger version: " + block.stronger_version.rstrip("."))
    return " ".join(lines) if block.strength == ChallengeStrength.GENTLE else "\n".join(lines)


__all__ = [
    "ChallengeStrength",
    "ChallengeBlock",
    "wants_critique",
    "gentle_challenge",
    "hard_challenge",
    "render_challenge",
]
