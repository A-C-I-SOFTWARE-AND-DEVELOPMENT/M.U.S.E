"""Jarvis Prime conversation engine.

Wave 1 of the conversation layer: classify the input, pick a shape,
shape the response, then finalize. The engine is the single funnel for
any user-facing Jarvis Prime response.

Public surface:

- :func:`respond` — end-to-end engine entry point
- :class:`EngineResult` — what the engine returns
- :class:`ConversationContext` — classified input
- :class:`ResponseShape` — the eleven shapes
- :func:`finalize` — last-pass cleanup of a rendered response
"""

from hermes_cli.jarvis_prime.conversation.approval_language import (
    ApprovalAsk,
    DOUBLE_CONFIRM_PHRASE,
    OWNER_GATE_PHRASE,
    RiskLevel,
    classify_risk,
    needs_double_confirmation,
    render_approval,
    render_double_confirmation,
)
from hermes_cli.jarvis_prime.conversation.classifier import (
    ActionType,
    ConversationContext,
    classify,
    detect_action_type,
    detect_depth,
    detect_emotional_temperature,
    detect_surface,
    wants_voice_capture,
)
from hermes_cli.jarvis_prime.conversation.disagreement import (
    ChallengeBlock,
    ChallengeStrength,
    gentle_challenge,
    hard_challenge,
    render_challenge,
    wants_critique,
)
from hermes_cli.jarvis_prime.conversation.empathy import (
    EmpatheticOpening,
    empathetic_opening,
    grounded_acknowledgement,
    is_emotional_input,
)
from hermes_cli.jarvis_prime.conversation.engine import (
    EngineInputs,
    EngineResult,
    pick_shape,
    respond,
)
from hermes_cli.jarvis_prime.conversation.finalizer import (
    BLOCKED_BRANDS,
    FinalizationReport,
    finalize,
    scan_for_brand_leaks,
)
from hermes_cli.jarvis_prime.conversation.mobile_adapter import (
    MobileTaskCard,
    append_expansion_pointer,
    build_task_card,
    enforce_mobile_limits,
    is_mobile_surface,
    slugify,
)
from hermes_cli.jarvis_prime.conversation.response_shapes import (
    RenderedResponse,
    ResponseShape,
    SHAPE_SPECS,
    ShapeSpec,
)
from hermes_cli.jarvis_prime.conversation.tone import (
    EmotionalTemperature,
    ToneChoice,
    choose_tone,
    pick_opener,
)

__all__ = [
    # Engine
    "EngineInputs",
    "EngineResult",
    "respond",
    "pick_shape",
    # Classifier
    "ActionType",
    "ConversationContext",
    "classify",
    "detect_action_type",
    "detect_depth",
    "detect_emotional_temperature",
    "detect_surface",
    "wants_voice_capture",
    # Response shapes
    "ResponseShape",
    "ShapeSpec",
    "SHAPE_SPECS",
    "RenderedResponse",
    # Tone
    "EmotionalTemperature",
    "ToneChoice",
    "choose_tone",
    "pick_opener",
    # Empathy
    "EmpatheticOpening",
    "empathetic_opening",
    "grounded_acknowledgement",
    "is_emotional_input",
    # Disagreement
    "ChallengeBlock",
    "ChallengeStrength",
    "gentle_challenge",
    "hard_challenge",
    "render_challenge",
    "wants_critique",
    # Approval
    "ApprovalAsk",
    "RiskLevel",
    "classify_risk",
    "needs_double_confirmation",
    "render_approval",
    "render_double_confirmation",
    "OWNER_GATE_PHRASE",
    "DOUBLE_CONFIRM_PHRASE",
    # Mobile adapter
    "MobileTaskCard",
    "append_expansion_pointer",
    "build_task_card",
    "enforce_mobile_limits",
    "is_mobile_surface",
    "slugify",
    # Finalizer
    "BLOCKED_BRANDS",
    "FinalizationReport",
    "finalize",
    "scan_for_brand_leaks",
]
