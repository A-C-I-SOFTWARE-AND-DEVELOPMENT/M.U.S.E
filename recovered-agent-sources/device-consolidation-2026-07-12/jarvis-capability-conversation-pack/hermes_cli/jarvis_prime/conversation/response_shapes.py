"""Response shapes for the Jarvis Prime conversation engine.

A shape describes the *form* a response takes once mode, surface, and
intent are known. The engine picks a shape from this catalogue and the
finalizer renders it into final user-facing text.

There are eleven shapes:

- ``quick_ack`` — one-line acknowledgement, no analysis
- ``conversational_answer`` — short prose, partner tone
- ``gentle_challenge`` — softly push back on a weak idea
- ``hard_challenge`` — direct disagreement with the strongest objection
- ``mobile_task_card`` — six-field capture packet for mobile/voice
- ``status_update`` — short progress / state report
- ``approval_request`` — formal request for owner authorization
- ``serious_double_confirmation`` — two-step confirmation for high-risk
- ``deep_architecture`` — long structured technical answer
- ``implementation_packet`` — builder-mode handoff packet
- ``final_handoff`` — closing summary with what changed, verification, next
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ResponseShape(str, Enum):
    """Catalogue of the eleven Jarvis Prime response shapes."""

    QUICK_ACK = "quick_ack"
    CONVERSATIONAL_ANSWER = "conversational_answer"
    GENTLE_CHALLENGE = "gentle_challenge"
    HARD_CHALLENGE = "hard_challenge"
    MOBILE_TASK_CARD = "mobile_task_card"
    STATUS_UPDATE = "status_update"
    APPROVAL_REQUEST = "approval_request"
    SERIOUS_DOUBLE_CONFIRMATION = "serious_double_confirmation"
    DEEP_ARCHITECTURE = "deep_architecture"
    IMPLEMENTATION_PACKET = "implementation_packet"
    FINAL_HANDOFF = "final_handoff"


@dataclass(frozen=True)
class ShapeSpec:
    """Static description of a response shape."""

    shape: ResponseShape
    label: str
    purpose: str
    structured: bool
    max_lines: int
    requires_owner_gate: bool = False
    requires_double_confirm: bool = False
    notes: tuple[str, ...] = field(default_factory=tuple)


SHAPE_SPECS: dict[ResponseShape, ShapeSpec] = {
    ResponseShape.QUICK_ACK: ShapeSpec(
        shape=ResponseShape.QUICK_ACK,
        label="Quick acknowledgement",
        purpose="One line that lands the message without expanding it.",
        structured=False,
        max_lines=2,
    ),
    ResponseShape.CONVERSATIONAL_ANSWER: ShapeSpec(
        shape=ResponseShape.CONVERSATIONAL_ANSWER,
        label="Conversational answer",
        purpose="Partner-tone prose, two to six sentences, no headers.",
        structured=False,
        max_lines=12,
    ),
    ResponseShape.GENTLE_CHALLENGE: ShapeSpec(
        shape=ResponseShape.GENTLE_CHALLENGE,
        label="Gentle challenge",
        purpose="Push back softly on a weak idea while staying collaborative.",
        structured=False,
        max_lines=10,
    ),
    ResponseShape.HARD_CHALLENGE: ShapeSpec(
        shape=ResponseShape.HARD_CHALLENGE,
        label="Hard challenge",
        purpose="Direct disagreement led by the strongest objection.",
        structured=False,
        max_lines=14,
    ),
    ResponseShape.MOBILE_TASK_CARD: ShapeSpec(
        shape=ResponseShape.MOBILE_TASK_CARD,
        label="Mobile task card",
        purpose="Six-field capture packet for mobile and voice surfaces.",
        structured=True,
        max_lines=8,
    ),
    ResponseShape.STATUS_UPDATE: ShapeSpec(
        shape=ResponseShape.STATUS_UPDATE,
        label="Status update",
        purpose="Short progress or state report with a clear next step.",
        structured=False,
        max_lines=8,
    ),
    ResponseShape.APPROVAL_REQUEST: ShapeSpec(
        shape=ResponseShape.APPROVAL_REQUEST,
        label="Approval request",
        purpose="Formal owner-authorization request with explicit gate phrase.",
        structured=True,
        max_lines=10,
        requires_owner_gate=True,
    ),
    ResponseShape.SERIOUS_DOUBLE_CONFIRMATION: ShapeSpec(
        shape=ResponseShape.SERIOUS_DOUBLE_CONFIRMATION,
        label="Serious double confirmation",
        purpose="Two-step confirmation for high-risk or irreversible actions.",
        structured=True,
        max_lines=14,
        requires_owner_gate=True,
        requires_double_confirm=True,
    ),
    ResponseShape.DEEP_ARCHITECTURE: ShapeSpec(
        shape=ResponseShape.DEEP_ARCHITECTURE,
        label="Deep architecture answer",
        purpose="Long structured technical answer with sections and rationale.",
        structured=True,
        max_lines=400,
    ),
    ResponseShape.IMPLEMENTATION_PACKET: ShapeSpec(
        shape=ResponseShape.IMPLEMENTATION_PACKET,
        label="Implementation packet",
        purpose="Builder-mode handoff: files, verification, risks, next step.",
        structured=True,
        max_lines=80,
    ),
    ResponseShape.FINAL_HANDOFF: ShapeSpec(
        shape=ResponseShape.FINAL_HANDOFF,
        label="Final handoff",
        purpose="Closing summary: what changed, how verified, what is next.",
        structured=True,
        max_lines=20,
    ),
}


OWNER_GATE_PHRASE = "Yes, with authorization."
DOUBLE_CONFIRM_PHRASE = "Yes, with authorization — confirmed twice."


@dataclass
class RenderedResponse:
    """A response that has been shaped but not yet finalized.

    The finalizer takes this, strips internal route noise, runs the brand
    guard, and produces the final user-facing string.
    """

    shape: ResponseShape
    body: str
    suffix: str = ""
    internal_notes: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    structured: bool = False


__all__ = [
    "ResponseShape",
    "ShapeSpec",
    "SHAPE_SPECS",
    "OWNER_GATE_PHRASE",
    "DOUBLE_CONFIRM_PHRASE",
    "RenderedResponse",
]
