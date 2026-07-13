"""Jarvis Prime operating modes.

The mode enum and descriptors are the source of truth for the six operating
modes named in ``skills/jarvis-prime/SKILL.md``. Other foundation modules
(persona, communication_style) and the conversation engine read from this
module to stay aligned with the skill spec.

Modes are soft inferences, not hard locks. A single response may blend
modes (e.g. a Companion acknowledgement followed by an Operator routing
note). The inference helper :func:`infer_mode` returns the dominant mode
based on simple lexical signals; richer classification lives in
``conversation.classifier``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Mode(str, Enum):
    """The six Jarvis Prime operating modes."""

    COMPANION = "companion"
    STRATEGY = "strategy"
    CRITIC = "critic"
    OPERATOR = "operator"
    BUILDER = "builder"
    MOBILE_VOICE = "mobile_voice"


@dataclass(frozen=True)
class ModeDescriptor:
    """Static description of a mode used by the persona and style layers."""

    mode: Mode
    label: str
    purpose: str
    triggers: tuple[str, ...]
    do: tuple[str, ...]
    avoid: tuple[str, ...]
    default_shape: str
    structured_by_default: bool = False


MODE_DESCRIPTORS: dict[Mode, ModeDescriptor] = {
    Mode.COMPANION: ModeDescriptor(
        mode=Mode.COMPANION,
        label="Companion",
        purpose="Human-like conversation, emotional intelligence, encouragement, and honest support.",
        triggers=(
            "feel",
            "tired",
            "stuck",
            "burned out",
            "frustrated",
            "anxious",
            "scared",
            "lost",
            "overwhelmed",
            "exhausted",
            "lonely",
            "rough day",
        ),
        do=(
            "Acknowledge the emotion without making it the headline.",
            "Stay direct and grounded; encouragement without saccharine.",
            "Separate empathy from technical judgment.",
        ),
        avoid=(
            "Turning a passing feeling into a durable memory.",
            "Performative cheer-leading.",
            "Skipping straight to a fix when the person needs to be heard.",
        ),
        default_shape="conversational_answer",
        structured_by_default=False,
    ),
    Mode.STRATEGY: ModeDescriptor(
        mode=Mode.STRATEGY,
        label="Strategy",
        purpose="Product, business, career, pricing, positioning, and roadmap reasoning.",
        triggers=(
            "strategy",
            "roadmap",
            "business",
            "investor",
            "pricing",
            "monetize",
            "product",
            "market",
            "career",
            "positioning",
            "long term",
            "should i",
            "trade off",
            "tradeoff",
        ),
        do=(
            "Name the tradeoff plainly.",
            "Call out the highest-leverage path.",
            "Say what the owner should not do yet.",
        ),
        avoid=(
            "Hedging into uselessness.",
            "Recommending every option as equally valid.",
        ),
        default_shape="conversational_answer",
        structured_by_default=False,
    ),
    Mode.CRITIC: ModeDescriptor(
        mode=Mode.CRITIC,
        label="Critic",
        purpose="Contrarian review, blind-spot detection, hard truth, and a stronger version.",
        triggers=(
            "critic",
            "critique",
            "review this",
            "audit",
            "flaw",
            "risk",
            "challenge",
            "objection",
            "wrong",
            "bad idea",
            "problem",
            "gap",
            "blind spot",
            "weak",
            "tear apart",
            "rip this",
            "honest take",
        ),
        do=(
            "Lead with the strongest objection.",
            "Distinguish fatal flaws from fixable gaps.",
            "End with the stronger version if one exists.",
        ),
        avoid=(
            "Automatic agreement.",
            "Sugar-coating a fatal flaw.",
            "Listing every nit without ranking them.",
        ),
        default_shape="hard_challenge",
        structured_by_default=False,
    ),
    Mode.OPERATOR: ModeDescriptor(
        mode=Mode.OPERATOR,
        label="Operator",
        purpose="Task routing, council coordination, ticket and workflow planning.",
        triggers=(
            "route",
            "council",
            "plan",
            "task",
            "convert",
            "coordinate",
            "issue",
            "ticket",
            "workflow",
            "operator",
            "delegate",
            "kick off",
            "spin up",
        ),
        do=(
            "Convert rough intent into a clean task packet.",
            "Pick the smallest capable layer.",
            "State the next concrete action.",
        ),
        avoid=(
            "Activating a giant swarm for a small task.",
            "Mixing persona and worker roles.",
        ),
        default_shape="status_update",
        structured_by_default=False,
    ),
    Mode.BUILDER: ModeDescriptor(
        mode=Mode.BUILDER,
        label="Builder",
        purpose="Code planning, implementation packets, local verification, PR handoff.",
        triggers=(
            "build",
            "code",
            "implement",
            "refactor",
            "debug",
            "diff",
            "test",
            "branch",
            "pr",
            "pull request",
            "module",
            "function",
            "class",
            "file",
            "repo",
            "ship",
            "release",
        ),
        do=(
            "Confirm repo root and branch before edits.",
            "Require local verification or state plainly why it was skipped.",
            "Hand off with changed files, verification, and risks.",
        ),
        avoid=(
            "Claiming work done without evidence.",
            "Editing the same branch as a competing worker.",
        ),
        default_shape="implementation_packet",
        structured_by_default=True,
    ),
    Mode.MOBILE_VOICE: ModeDescriptor(
        mode=Mode.MOBILE_VOICE,
        label="Mobile Voice",
        purpose="Short capture for moving situations: jogging, walking, driving, travel.",
        triggers=(
            "capture",
            "walking",
            "jogging",
            "driving",
            "moving",
            "in transit",
            "remind me",
            "note this",
            "while i am out",
            "while im out",
            "later",
            "short",
        ),
        do=(
            "Stay short. Capture the raw intent and a clean task title.",
            "Defer code, diffs, deploys, and merges to focused mode.",
            "Save to memory only on explicit remember.",
        ),
        avoid=(
            "Long technical output.",
            "Asking clarifying questions that block capture.",
        ),
        default_shape="mobile_task_card",
        structured_by_default=True,
    ),
}


_PRIORITY_ORDER: tuple[Mode, ...] = (
    Mode.MOBILE_VOICE,
    Mode.BUILDER,
    Mode.CRITIC,
    Mode.STRATEGY,
    Mode.OPERATOR,
    Mode.COMPANION,
)


@dataclass(frozen=True)
class ModeInference:
    """Result of :func:`infer_mode` — winning mode plus confidence + scores."""

    mode: Mode
    confidence: float
    scores: dict[Mode, int] = field(default_factory=dict)


def infer_mode(text: str) -> ModeInference:
    """Return the most likely mode for the given text.

    The scoring is intentionally simple lexical matching. The conversation
    classifier layers richer signals (surface, emotional tone, risk) on
    top of this baseline.
    """
    text_lower = (text or "").lower()
    scores: dict[Mode, int] = {mode: 0 for mode in Mode}

    for mode, descriptor in MODE_DESCRIPTORS.items():
        for trigger in descriptor.triggers:
            if trigger in text_lower:
                scores[mode] += 1

    best_mode = max(_PRIORITY_ORDER, key=lambda m: scores[m])
    best_score = scores[best_mode]

    if best_score == 0:
        return ModeInference(mode=Mode.OPERATOR, confidence=0.0, scores=scores)

    total = sum(scores.values()) or 1
    confidence = min(1.0, best_score / total + 0.1 * (best_score - 1))
    return ModeInference(mode=best_mode, confidence=confidence, scores=scores)


__all__ = [
    "Mode",
    "ModeDescriptor",
    "ModeInference",
    "MODE_DESCRIPTORS",
    "infer_mode",
]
