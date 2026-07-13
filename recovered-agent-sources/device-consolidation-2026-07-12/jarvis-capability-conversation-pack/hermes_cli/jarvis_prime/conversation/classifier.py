"""Classifier for the Jarvis Prime conversation engine.

The classifier ingests a raw user message plus optional surface metadata
and produces a :class:`ConversationContext` — the structured input the
engine reads to pick a shape, tone, and depth. Classification is
intentionally lightweight: lexical signals plus surface hints, no model
calls. Richer classification can layer on top later.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping, Optional

from hermes_cli.jarvis_prime.communication_style import Depth, StyleSurface
from hermes_cli.jarvis_prime.modes import Mode, infer_mode
from hermes_cli.jarvis_prime.conversation.approval_language import (
    RiskLevel,
    classify_risk,
)
from hermes_cli.jarvis_prime.conversation.disagreement import wants_critique
from hermes_cli.jarvis_prime.conversation.empathy import is_emotional_input
from hermes_cli.jarvis_prime.conversation.tone import EmotionalTemperature


class ActionType(str, Enum):
    """What the user is asking Jarvis to do."""

    QUESTION = "question"
    REQUEST = "request"
    BRAINSTORM = "brainstorm"
    CRITIQUE_REQUEST = "critique_request"
    EXECUTE = "execute"
    SUPPORT_REQUEST = "support_request"
    STATUS_CHECK = "status_check"
    APPROVAL_REQUEST = "approval_request"


_BRAINSTORM_MARKERS = (
    "brainstorm",
    "ideas",
    "what could we",
    "what are some",
    "throw out",
    "throw some",
    "spitball",
)
_EXECUTE_MARKERS = (
    "do it",
    "go ahead",
    "ship it",
    "run it",
    "execute",
    "kick it off",
    "proceed",
    "deploy",
    "push",
    "merge",
    "delete",
    "drop",
    "rotate",
    "publish",
    "release",
)
_STATUS_MARKERS = (
    "status",
    "where are we",
    "what's left",
    "what is left",
    "are we done",
    "progress",
    "did it",
    "did you",
    "still running",
    "still going",
)
_APPROVAL_MARKERS = (
    "approve",
    "approval",
    "authorize",
    "authorise",
    "permission to",
    "owner gate",
    "can i go ahead",
    "okay to proceed",
    "ok to proceed",
)
_SUPPORT_MARKERS = (
    "i feel",
    "i'm tired",
    "i am tired",
    "burned out",
    "burnt out",
    "rough day",
    "i need support",
    "talk me through",
    "hold space",
    "i'm stuck",
    "i am stuck",
)


_VOICE_MARKERS = (
    "i'm walking",
    "im walking",
    "i'm jogging",
    "im jogging",
    "i'm driving",
    "im driving",
    "while moving",
    "while i'm out",
    "while im out",
    "voice note",
)


_EMOTION_BUCKETS: tuple[tuple[EmotionalTemperature, tuple[str, ...]], ...] = (
    (
        EmotionalTemperature.FRUSTRATED,
        ("frustrated", "annoyed", "pissed", "fed up", "angry", "irritated"),
    ),
    (
        EmotionalTemperature.SAD,
        ("sad", "down", "depressed", "low", "lonely", "rough day", "hurts"),
    ),
    (
        EmotionalTemperature.ANXIOUS,
        ("anxious", "worried", "scared", "afraid", "overwhelmed", "nervous", "panicking"),
    ),
    (
        EmotionalTemperature.EXCITED,
        ("excited", "pumped", "love this", "fired up", "stoked", "buzzing"),
    ),
)


def detect_emotional_temperature(text: str) -> EmotionalTemperature:
    """Bucket the user input into a coarse emotional temperature."""
    if not text:
        return EmotionalTemperature.NEUTRAL
    lowered = text.lower()
    for temperature, markers in _EMOTION_BUCKETS:
        if any(marker in lowered for marker in markers):
            return temperature
    if is_emotional_input(text):
        return EmotionalTemperature.ANXIOUS
    return EmotionalTemperature.NEUTRAL


def detect_action_type(text: str) -> ActionType:
    """Pick a coarse action type from the user input."""
    if not text:
        return ActionType.QUESTION
    lowered = text.lower()

    if any(marker in lowered for marker in _APPROVAL_MARKERS):
        return ActionType.APPROVAL_REQUEST
    if any(marker in lowered for marker in _STATUS_MARKERS):
        return ActionType.STATUS_CHECK
    if any(marker in lowered for marker in _SUPPORT_MARKERS):
        return ActionType.SUPPORT_REQUEST
    if any(marker in lowered for marker in _EXECUTE_MARKERS):
        return ActionType.EXECUTE
    if wants_critique(text):
        return ActionType.CRITIQUE_REQUEST
    if any(marker in lowered for marker in _BRAINSTORM_MARKERS):
        return ActionType.BRAINSTORM
    if lowered.endswith("?"):
        return ActionType.QUESTION
    return ActionType.REQUEST


def detect_surface(metadata: Optional[Mapping[str, object]]) -> StyleSurface:
    """Infer the surface from optional message metadata.

    Falls back to FOCUSED when nothing useful is supplied.
    """
    if not metadata:
        return StyleSurface.FOCUSED

    raw = str(metadata.get("surface") or metadata.get("source") or "").lower().strip()
    if raw in {"mobile", "phone", "dm", "ios", "android"}:
        return StyleSurface.MOBILE
    if raw == "termux":
        return StyleSurface.TERMUX
    if raw == "slack":
        return StyleSurface.SLACK
    if raw in {"app", "web", "desktop_app"}:
        return StyleSurface.APP
    if raw in {"voice", "tts", "stt"}:
        return StyleSurface.VOICE
    if raw in {"desktop", "focused", "terminal", "cli"}:
        return StyleSurface.FOCUSED

    channel_type = str(metadata.get("channel_type") or "").lower()
    platform = str(metadata.get("platform") or "").lower()

    if platform == "slack":
        return StyleSurface.SLACK
    if platform in {"termux", "android"}:
        return StyleSurface.TERMUX
    if channel_type == "im":
        return StyleSurface.MOBILE

    text = str(metadata.get("text") or "")
    if text and len(text) < 80 and "\n" not in text:
        return StyleSurface.MOBILE
    return StyleSurface.FOCUSED


def detect_depth(text: str, surface: StyleSurface) -> Depth:
    """Pick a target depth from text + surface."""
    if surface in {StyleSurface.MOBILE, StyleSurface.TERMUX, StyleSurface.VOICE}:
        return Depth.BRIEF

    if not text:
        return Depth.NORMAL
    lowered = text.lower()

    deep_markers = (
        "design doc",
        "full design",
        "deep dive",
        "architect",
        "architecture",
        "research",
        "comprehensive",
        "spec out",
        "write the plan",
        "detailed plan",
        "implementation plan",
        "build plan",
        "long form",
        "long-form",
    )
    if any(marker in lowered for marker in deep_markers):
        return Depth.DEEP

    if len(text) > 280:
        return Depth.DEEP
    if len(text) < 80:
        return Depth.BRIEF
    return Depth.NORMAL


def wants_voice_capture(text: str) -> bool:
    """Heuristic for explicit voice-capture phrasing."""
    if not text:
        return False
    lowered = text.lower()
    return any(marker in lowered for marker in _VOICE_MARKERS)


@dataclass(frozen=True)
class ConversationContext:
    """Everything the engine needs to pick a shape and tone."""

    user_input: str
    mode: Mode
    surface: StyleSurface
    depth: Depth
    emotional_temperature: EmotionalTemperature
    risk: RiskLevel
    action_type: ActionType
    wants_critique: bool
    is_emotional: bool
    structured_preferred: bool
    metadata: Mapping[str, object] = field(default_factory=dict)


def classify(
    user_input: str,
    metadata: Optional[Mapping[str, object]] = None,
) -> ConversationContext:
    """Build a :class:`ConversationContext` from raw input + metadata."""
    text = user_input or ""
    surface = detect_surface(metadata)

    if wants_voice_capture(text):
        surface = StyleSurface.VOICE

    mode = infer_mode(text).mode
    if surface in {StyleSurface.MOBILE, StyleSurface.TERMUX, StyleSurface.VOICE}:
        if mode != Mode.BUILDER and mode != Mode.CRITIC:
            mode = Mode.MOBILE_VOICE

    depth = detect_depth(text, surface)
    risk = classify_risk(text)
    action = detect_action_type(text)
    temperature = detect_emotional_temperature(text)
    emotional = is_emotional_input(text) or temperature in {
        EmotionalTemperature.SAD,
        EmotionalTemperature.ANXIOUS,
        EmotionalTemperature.FRUSTRATED,
    }
    if emotional and mode == Mode.MOBILE_VOICE and surface == StyleSurface.FOCUSED:
        mode = Mode.COMPANION
    if emotional and surface == StyleSurface.FOCUSED and mode not in {Mode.BUILDER, Mode.CRITIC}:
        mode = Mode.COMPANION

    structured_preferred = (
        depth == Depth.DEEP
        or mode == Mode.BUILDER
        or mode == Mode.MOBILE_VOICE
        or action == ActionType.APPROVAL_REQUEST
        or action == ActionType.STATUS_CHECK
    )

    return ConversationContext(
        user_input=text,
        mode=mode,
        surface=surface,
        depth=depth,
        emotional_temperature=temperature,
        risk=risk,
        action_type=action,
        wants_critique=wants_critique(text),
        is_emotional=emotional,
        structured_preferred=structured_preferred,
        metadata=metadata or {},
    )


__all__ = [
    "ActionType",
    "ConversationContext",
    "classify",
    "detect_action_type",
    "detect_depth",
    "detect_emotional_temperature",
    "detect_surface",
    "wants_voice_capture",
]
