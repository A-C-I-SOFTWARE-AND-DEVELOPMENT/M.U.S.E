"""Grounded empathy for the Jarvis Prime conversation engine.

Empathy in Jarvis Prime is *grounded* — it acknowledges the emotion
without dramatising it, never claims feelings of its own, and separates
support from technical judgment. The helpers here produce the empathetic
opening for a companion-mode response and decide whether a follow-up
should be a question, a small concrete suggestion, or simply more space
for the person.
"""

from __future__ import annotations

from dataclasses import dataclass

from hermes_cli.jarvis_prime.conversation.tone import EmotionalTemperature


_ACKNOWLEDGEMENTS: dict[EmotionalTemperature, tuple[str, ...]] = {
    EmotionalTemperature.SAD: (
        "That sounds heavy.",
        "That is a real weight to carry.",
    ),
    EmotionalTemperature.FRUSTRATED: (
        "That is frustrating, and the frustration makes sense.",
        "Reasonable to be frustrated about that.",
    ),
    EmotionalTemperature.ANXIOUS: (
        "The unease here is fair.",
        "That kind of pressure is real.",
    ),
    EmotionalTemperature.EXCITED: (
        "Good energy here.",
        "There is something real in this.",
    ),
    EmotionalTemperature.CALM: (
        "Heard.",
    ),
    EmotionalTemperature.NEUTRAL: (
        "Heard.",
    ),
}


_FOLLOWUPS: dict[EmotionalTemperature, tuple[str, ...]] = {
    EmotionalTemperature.SAD: (
        "What would help most right now — space to think, or one small concrete step?",
    ),
    EmotionalTemperature.FRUSTRATED: (
        "Want to name the part that is most in the way?",
    ),
    EmotionalTemperature.ANXIOUS: (
        "Want to break this into one small piece we can move on today?",
    ),
    EmotionalTemperature.EXCITED: (
        "Want me to stress-test the strongest version of this?",
    ),
    EmotionalTemperature.CALM: (
        "What is the next move you are weighing?",
    ),
    EmotionalTemperature.NEUTRAL: (),
}


@dataclass(frozen=True)
class EmpatheticOpening:
    """The opening lines of a companion-mode response."""

    acknowledgement: str
    followup: str
    avoids_drama: bool = True
    claims_no_feelings: bool = True


def grounded_acknowledgement(temperature: EmotionalTemperature) -> str:
    """Return a grounded one-line acknowledgement for the temperature."""
    options = _ACKNOWLEDGEMENTS.get(temperature, _ACKNOWLEDGEMENTS[EmotionalTemperature.NEUTRAL])
    return options[0]


def empathetic_opening(temperature: EmotionalTemperature) -> EmpatheticOpening:
    """Build a grounded opening for a companion-mode response."""
    ack = grounded_acknowledgement(temperature)
    followups = _FOLLOWUPS.get(temperature, ())
    followup = followups[0] if followups else ""
    return EmpatheticOpening(acknowledgement=ack, followup=followup)


def is_emotional_input(text: str) -> bool:
    """Quick check used by the classifier to gate empathy."""
    if not text:
        return False
    lowered = text.lower()
    signals = (
        "i feel",
        "i am tired",
        "i'm tired",
        "burned out",
        "burnt out",
        "exhausted",
        "stuck",
        "lost",
        "overwhelmed",
        "lonely",
        "rough day",
        "frustrated",
        "anxious",
        "scared",
        "afraid",
        "i can't",
        "i cannot",
        "i give up",
        "i'm done",
    )
    return any(signal in lowered for signal in signals)


__all__ = [
    "EmpatheticOpening",
    "grounded_acknowledgement",
    "empathetic_opening",
    "is_emotional_input",
]
