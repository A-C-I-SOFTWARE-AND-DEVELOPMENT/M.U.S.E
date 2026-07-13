"""Conversation engine for Jarvis Prime.

The engine is the orchestrator that ties together classification, tone,
response shapes, the mobile adapter, approval language, disagreement,
empathy, and the finalizer. The public entry point is :func:`respond`,
which takes a user input plus optional metadata and returns a finalized,
ready-to-display string.

The engine is intentionally a thin coordinator. Each behaviour lives in
its own module so it can be tested in isolation; the engine's job is to
pick the right shape for the context and let the modules render their
parts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Optional

from hermes_cli.jarvis_prime.communication_style import (
    Depth,
    StylePreset,
    StyleSurface,
    style_for_mode,
)
from hermes_cli.jarvis_prime.modes import Mode

from hermes_cli.jarvis_prime.conversation.approval_language import (
    ApprovalAsk,
    RiskLevel,
    needs_double_confirmation,
    render_approval,
    render_double_confirmation,
)
from hermes_cli.jarvis_prime.conversation.classifier import (
    ActionType,
    ConversationContext,
    classify,
)
from hermes_cli.jarvis_prime.conversation.disagreement import (
    ChallengeBlock,
    hard_challenge,
    gentle_challenge,
    render_challenge,
    wants_critique,
)
from hermes_cli.jarvis_prime.conversation.empathy import (
    EmpatheticOpening,
    empathetic_opening,
)
from hermes_cli.jarvis_prime.conversation.finalizer import (
    FinalizationReport,
    finalize,
)
from hermes_cli.jarvis_prime.conversation.mobile_adapter import (
    build_task_card,
    enforce_mobile_limits,
    is_mobile_surface,
)
from hermes_cli.jarvis_prime.conversation.response_shapes import (
    OWNER_GATE_PHRASE,
    RenderedResponse,
    ResponseShape,
    SHAPE_SPECS,
)
from hermes_cli.jarvis_prime.conversation.tone import (
    EmotionalTemperature,
    ToneChoice,
    choose_tone,
)


@dataclass(frozen=True)
class EngineInputs:
    """Optional inputs the engine can use beyond the user text.

    ``content`` is the technical answer body. If absent, the engine
    falls back to a minimal partner-tone placeholder so callers can wire
    classification + shape selection without an LLM in the loop.
    """

    content: Optional[str] = None
    proposed_action: Optional[str] = None
    blast_radius: Optional[str] = None
    rollback: Optional[str] = None
    objection: Optional[str] = None
    stronger_version: Optional[str] = None


@dataclass
class EngineResult:
    """Everything the engine produces for one turn."""

    final_text: str
    shape: ResponseShape
    context: ConversationContext
    tone: ToneChoice
    style: StylePreset
    finalization: FinalizationReport
    challenge: Optional[ChallengeBlock] = None
    empathy: Optional[EmpatheticOpening] = None
    approval: Optional[ApprovalAsk] = None


def pick_shape(context: ConversationContext) -> ResponseShape:
    """Choose the response shape from the classification context."""
    action = context.action_type
    mode = context.mode
    surface = context.surface

    if action == ActionType.APPROVAL_REQUEST or context.risk in {RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL}:
        if context.risk in {RiskLevel.HIGH, RiskLevel.CRITICAL}:
            return ResponseShape.SERIOUS_DOUBLE_CONFIRMATION
        return ResponseShape.APPROVAL_REQUEST

    if action == ActionType.STATUS_CHECK:
        return ResponseShape.STATUS_UPDATE

    if action == ActionType.SUPPORT_REQUEST or (context.is_emotional and mode == Mode.COMPANION):
        return ResponseShape.CONVERSATIONAL_ANSWER

    if action == ActionType.CRITIQUE_REQUEST or mode == Mode.CRITIC:
        return ResponseShape.HARD_CHALLENGE

    if mode == Mode.MOBILE_VOICE or is_mobile_surface(surface):
        return ResponseShape.MOBILE_TASK_CARD

    if mode == Mode.BUILDER:
        if context.depth == Depth.DEEP:
            return ResponseShape.IMPLEMENTATION_PACKET
        return ResponseShape.CONVERSATIONAL_ANSWER

    if context.depth == Depth.DEEP and mode in {Mode.STRATEGY, Mode.OPERATOR}:
        return ResponseShape.DEEP_ARCHITECTURE

    if action == ActionType.QUESTION and context.depth == Depth.BRIEF:
        return ResponseShape.CONVERSATIONAL_ANSWER

    if action == ActionType.QUESTION:
        return ResponseShape.CONVERSATIONAL_ANSWER

    return ResponseShape.CONVERSATIONAL_ANSWER


def _maybe_challenge(
    context: ConversationContext,
    inputs: EngineInputs,
) -> Optional[ChallengeBlock]:
    """Decide whether to attach a challenge block to the response."""
    if not (context.wants_critique or context.mode == Mode.CRITIC):
        return None
    objection = inputs.objection or (
        "The framing skips the strongest objection; "
        "share the assumption you are leaning on and we will pressure-test it."
    )
    if context.mode == Mode.CRITIC or wants_critique(context.user_input):
        return hard_challenge(objection, inputs.stronger_version)
    return gentle_challenge(objection, inputs.stronger_version)


def _maybe_empathy(context: ConversationContext) -> Optional[EmpatheticOpening]:
    """Attach a grounded empathetic opening when warranted."""
    if not context.is_emotional:
        return None
    if context.mode not in {Mode.COMPANION, Mode.MOBILE_VOICE}:
        return None
    return empathetic_opening(context.emotional_temperature)


def _render_body(
    shape: ResponseShape,
    context: ConversationContext,
    tone: ToneChoice,
    inputs: EngineInputs,
    challenge: Optional[ChallengeBlock],
    empathy: Optional[EmpatheticOpening],
) -> RenderedResponse:
    """Compose the body of the response based on the chosen shape."""
    spec = SHAPE_SPECS[shape]
    content = (inputs.content or "").strip()

    if shape == ResponseShape.MOBILE_TASK_CARD:
        card = build_task_card(context.user_input)
        body = card.render()
        return RenderedResponse(shape=shape, body=body, structured=True)

    if shape == ResponseShape.APPROVAL_REQUEST:
        action = inputs.proposed_action or context.user_input.strip()
        ask = render_approval(action, context.risk, inputs.blast_radius, inputs.rollback)
        return RenderedResponse(shape=shape, body=ask.body, structured=True)

    if shape == ResponseShape.SERIOUS_DOUBLE_CONFIRMATION:
        action = inputs.proposed_action or context.user_input.strip()
        ask = render_double_confirmation(action, context.risk, inputs.blast_radius, inputs.rollback)
        return RenderedResponse(shape=shape, body=ask.body, structured=True)

    if shape == ResponseShape.STATUS_UPDATE:
        body_lines = [
            f"{tone.opener}",
            content or "No new state to report.",
            "Next step: confirm whether to proceed or hold.",
        ]
        return RenderedResponse(shape=shape, body="\n".join(body_lines).strip(), structured=False)

    if shape == ResponseShape.HARD_CHALLENGE:
        block = challenge or hard_challenge(
            inputs.objection or "The strongest objection here has not been named yet.",
            inputs.stronger_version,
        )
        body_lines = [tone.opener, render_challenge(block)]
        if content:
            body_lines.append(content)
        return RenderedResponse(shape=shape, body="\n".join(line for line in body_lines if line).strip(), structured=False)

    if shape == ResponseShape.GENTLE_CHALLENGE:
        block = challenge or gentle_challenge(
            inputs.objection or "There is a softer pressure-test worth running first.",
            inputs.stronger_version,
        )
        body_lines = [tone.opener, render_challenge(block)]
        if content:
            body_lines.append(content)
        return RenderedResponse(shape=shape, body="\n".join(line for line in body_lines if line).strip(), structured=False)

    if shape == ResponseShape.IMPLEMENTATION_PACKET:
        body_lines = [
            tone.opener,
            content or "Builder packet body to be filled by the caller.",
            "Verification: state the command run and the result.",
            "Risks: list anything that could regress.",
            "Next step: hand off or merge.",
        ]
        return RenderedResponse(shape=shape, body="\n".join(body_lines).strip(), structured=True)

    if shape == ResponseShape.DEEP_ARCHITECTURE:
        body_lines = [
            tone.opener,
            "Context:",
            content or "Deep architecture body to be filled by the caller.",
            "Tradeoffs:",
            "- Name the tradeoff that matters most.",
            "Recommendation:",
            "- State the highest-leverage path.",
        ]
        return RenderedResponse(shape=shape, body="\n".join(body_lines).strip(), structured=True)

    if shape == ResponseShape.QUICK_ACK:
        body = tone.opener
        return RenderedResponse(shape=shape, body=body, structured=False)

    if shape == ResponseShape.FINAL_HANDOFF:
        body_lines = [
            tone.opener,
            content or "Handoff body to be filled by the caller.",
            "What changed: stated above.",
            "Verification: stated above.",
            "Next step: confirm or kick off.",
        ]
        return RenderedResponse(shape=shape, body="\n".join(body_lines).strip(), structured=True)

    # Default: CONVERSATIONAL_ANSWER
    lines: list[str] = []
    if empathy is not None:
        lines.append(empathy.acknowledgement)
    else:
        lines.append(tone.opener)

    if content:
        lines.append(content)
    elif context.mode == Mode.COMPANION:
        lines.append("Want to walk it through together?")
    else:
        lines.append("Tell me the piece that matters most and we will move from there.")

    if empathy is not None and empathy.followup:
        lines.append(empathy.followup)

    return RenderedResponse(shape=shape, body="\n".join(line for line in lines if line).strip(), structured=False)


def respond(
    user_input: str,
    *,
    metadata: Optional[Mapping[str, object]] = None,
    inputs: Optional[EngineInputs] = None,
    expose_internal: bool = False,
) -> EngineResult:
    """Run the conversation engine end-to-end and return a final result."""
    inputs = inputs or EngineInputs()
    context = classify(user_input, metadata)
    style = style_for_mode(context.mode, context.surface, context.depth)
    tone = choose_tone(context.mode, context.emotional_temperature, seed=user_input)

    challenge = _maybe_challenge(context, inputs)
    empathy = _maybe_empathy(context)
    shape = pick_shape(context)

    rendered = _render_body(shape, context, tone, inputs, challenge, empathy)

    max_lines = style.max_lines if shape != ResponseShape.DEEP_ARCHITECTURE else None
    final_text, report = finalize(
        rendered,
        expose_internal=expose_internal,
        max_lines=max_lines,
    )

    if is_mobile_surface(context.surface):
        final_text = enforce_mobile_limits(final_text, context.surface, max_lines=style.max_lines)
        if not final_text.endswith("\n"):
            final_text += "\n"

    approval: Optional[ApprovalAsk] = None
    if shape == ResponseShape.APPROVAL_REQUEST:
        approval = render_approval(
            inputs.proposed_action or context.user_input,
            context.risk,
            inputs.blast_radius,
            inputs.rollback,
        )
    elif shape == ResponseShape.SERIOUS_DOUBLE_CONFIRMATION:
        approval = render_double_confirmation(
            inputs.proposed_action or context.user_input,
            context.risk,
            inputs.blast_radius,
            inputs.rollback,
        )

    return EngineResult(
        final_text=final_text,
        shape=shape,
        context=context,
        tone=tone,
        style=style,
        finalization=report,
        challenge=challenge,
        empathy=empathy,
        approval=approval,
    )


__all__ = [
    "EngineInputs",
    "EngineResult",
    "pick_shape",
    "respond",
    "OWNER_GATE_PHRASE",
]
