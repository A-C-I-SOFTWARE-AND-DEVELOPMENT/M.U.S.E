"""Tone primitives for the conversation engine.

The tone module exposes small reusable helpers (sentence pickers, opener
selectors) that other shapes draw from. Keeping these centralised means
the warm-but-not-fake voice stays consistent across companion, strategy,
critic, operator, and builder responses.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from enum import Enum

from hermes_cli.jarvis_prime.modes import Mode


class EmotionalTemperature(str, Enum):
    """Detected emotional temperature of the user input."""

    CALM = "calm"
    NEUTRAL = "neutral"
    EXCITED = "excited"
    ANXIOUS = "anxious"
    FRUSTRATED = "frustrated"
    SAD = "sad"


# Openers calibrated to feel like a partner, not a service desk or chatbot.
_PARTNER_OPENERS: dict[Mode, tuple[str, ...]] = {
    Mode.COMPANION: (
        "Heard.",
        "Okay, I am with you on this.",
        "I hear you.",
    ),
    Mode.STRATEGY: (
        "Here is the tradeoff.",
        "The honest read:",
        "Stepping back:",
    ),
    Mode.CRITIC: (
        "Honest take:",
        "I disagree.",
        "There is a stronger version of this.",
    ),
    Mode.OPERATOR: (
        "Routing it.",
        "Next concrete action:",
        "Picking it up.",
    ),
    Mode.BUILDER: (
        "Builder packet.",
        "Build plan:",
        "On the build.",
    ),
    Mode.MOBILE_VOICE: (
        "Captured.",
        "Got it. Quick note:",
        "Saved as a packet.",
    ),
}


@dataclass(frozen=True)
class ToneChoice:
    """A tone choice for a single response."""

    opener: str
    emotional_temperature: EmotionalTemperature
    warmth: float
    directness: float


def pick_opener(mode: Mode, seed: str | None = None) -> str:
    """Pick a partner-tone opener for the given mode.

    Deterministic when seed is provided so tests do not flake.
    """
    options = _PARTNER_OPENERS.get(mode) or _PARTNER_OPENERS[Mode.OPERATOR]
    if seed is not None:
        rng = random.Random(seed)
        return rng.choice(options)
    return options[0]


def choose_tone(
    mode: Mode,
    emotional_temperature: EmotionalTemperature,
    seed: str | None = None,
) -> ToneChoice:
    """Pick a tone for the response."""
    warmth = 0.5
    directness = 0.7

    if emotional_temperature in {
        EmotionalTemperature.SAD,
        EmotionalTemperature.ANXIOUS,
        EmotionalTemperature.FRUSTRATED,
    }:
        warmth = 0.8
        directness = 0.5

    if mode == Mode.COMPANION:
        warmth = max(warmth, 0.75)
    if mode == Mode.CRITIC:
        directness = 0.95
        warmth = min(warmth, 0.45)
    if mode == Mode.BUILDER:
        warmth = 0.4
        directness = 0.9

    return ToneChoice(
        opener=pick_opener(mode, seed=seed),
        emotional_temperature=emotional_temperature,
        warmth=warmth,
        directness=directness,
    )


__all__ = [
    "EmotionalTemperature",
    "ToneChoice",
    "pick_opener",
    "choose_tone",
]
