"""Jarvis Prime operating layer.

This package houses the Jarvis Prime decision, conversation, and routing
surface. It sits above the general agent runtime and below the owner's
final judgment.

Wave 1 (this layer) introduces the conversation engine: classification,
tone, response shapes, mobile/voice adaptation, approval language,
gentle and hard challenge, empathy, and the finalizer. The
:func:`render` entry point on :class:`JarvisContext` is the single
funnel for any final Jarvis Prime response.

Wave 3 (partial) introduces the capability graph and auto-routing. The
capabilities submodule is imported lazily and tolerantly: when its
implementation is incomplete, the conversation engine still works.
"""

from hermes_cli.jarvis_prime.modes import (
    MODE_DESCRIPTORS,
    Mode,
    ModeDescriptor,
    ModeInference,
    infer_mode,
)
from hermes_cli.jarvis_prime.persona import (
    FAKE_HUMAN_PHRASES,
    OWNER_LABEL,
    PERSONA,
    PRODUCT_NAME,
    PersonaProfile,
    PersonaTrait,
    YES_MAN_OPENERS,
    persona_do_list,
    persona_dont_list,
)
from hermes_cli.jarvis_prime.communication_style import (
    Depth,
    StylePreset,
    StyleSurface,
    style_for_mode,
    style_for_surface,
)
from hermes_cli.jarvis_prime.runtime import JarvisContext, render

__version__ = "0.2.0"

__all__ = [
    "__version__",
    # Persona / branding
    "PRODUCT_NAME",
    "OWNER_LABEL",
    "PersonaTrait",
    "PersonaProfile",
    "PERSONA",
    "FAKE_HUMAN_PHRASES",
    "YES_MAN_OPENERS",
    "persona_do_list",
    "persona_dont_list",
    # Modes
    "Mode",
    "ModeDescriptor",
    "ModeInference",
    "MODE_DESCRIPTORS",
    "infer_mode",
    # Communication style
    "Depth",
    "StylePreset",
    "StyleSurface",
    "style_for_mode",
    "style_for_surface",
    # Runtime entry points
    "JarvisContext",
    "render",
]


# Capabilities subsystem is imported tolerantly. When Wave 3 is fully
# implemented, the names below become available at the package root for
# backwards compatibility with prior callers.
_CAPABILITIES_AVAILABLE = False
try:
    from hermes_cli.jarvis_prime.capabilities import (  # type: ignore
        Capability,
        CapabilityGraph,
        CapabilityIndexer,
        CapabilitySelector,
        CapabilityType,
        RiskLevel,
        RouteDecision,
        RouteExplainer,
        Surface,
        UserRequest,
    )

    _CAPABILITIES_AVAILABLE = True
    __all__ += [
        "Capability",
        "CapabilityGraph",
        "CapabilityIndexer",
        "CapabilitySelector",
        "CapabilityType",
        "RiskLevel",
        "RouteDecision",
        "RouteExplainer",
        "Surface",
        "UserRequest",
    ]
except Exception:  # pragma: no cover - Wave 3 partial
    pass
