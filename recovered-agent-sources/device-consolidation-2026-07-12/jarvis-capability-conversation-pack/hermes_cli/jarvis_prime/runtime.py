"""Jarvis Prime runtime.

This module is the long-running operating surface for Jarvis Prime. It
owns two things:

1. The capability-graph routing entry point (Wave 3 partial — only
   loaded when the underlying selector and explainer modules are
   available). Callers that need routing use :func:`get_runtime`.
2. The conversation engine entry point (Wave 1). Callers that just want
   a finalized response from a user message use :func:`render`.

The two layers are independent. Importing this module does not require
the capability graph to be fully implemented; missing pieces degrade
to a no-op routing result rather than a hard import failure.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Optional

from hermes_cli.jarvis_prime.communication_style import (
    Depth,
    StylePreset,
    StyleSurface,
    style_for_mode,
)
from hermes_cli.jarvis_prime.modes import Mode
from hermes_cli.jarvis_prime.conversation.engine import (
    EngineInputs,
    EngineResult,
    respond,
)


# ---------------------------------------------------------------------------
# Capability-graph runtime (optional — Wave 3 partial implementation)
# ---------------------------------------------------------------------------


def _project_root() -> Path:
    """Locate the hermes-agent project root."""
    override = os.environ.get("HERMES_PROJECT_ROOT")
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[2]


_CAPABILITIES_AVAILABLE = False
_capabilities_import_error: Optional[Exception] = None
try:
    from hermes_cli.jarvis_prime.capabilities import (  # type: ignore
        CapabilityGraph,
        CapabilityIndexer,
        CapabilitySelector,
        RouteDecision,
        RouteExplainer,
        Surface,
        UserRequest,
    )

    _CAPABILITIES_AVAILABLE = True
except Exception as exc:  # pragma: no cover - exercised when Wave 3 partial
    _capabilities_import_error = exc
    CapabilityGraph = Any  # type: ignore
    CapabilityIndexer = Any  # type: ignore
    CapabilitySelector = Any  # type: ignore
    RouteDecision = Any  # type: ignore
    RouteExplainer = Any  # type: ignore
    Surface = Any  # type: ignore
    UserRequest = Any  # type: ignore


class JarvisPrimeRuntime:
    """Hold the loaded capability graph and a selector for routing."""

    def __init__(
        self,
        project_root: Optional[Path] = None,
        graph: Optional["CapabilityGraph"] = None,
    ) -> None:
        if not _CAPABILITIES_AVAILABLE:
            raise RuntimeError(
                "JarvisPrimeRuntime requires the capabilities subsystem to be "
                "fully implemented. Use jarvis_prime.runtime.render() for the "
                "conversation engine entry point instead."
            )
        self._project_root = project_root or _project_root()
        if graph is None:
            indexer = CapabilityIndexer(self._project_root)
            graph = indexer.build()
        self._graph = graph
        self._selector = CapabilitySelector(graph)
        self._explainer = RouteExplainer()

    @property
    def graph(self) -> "CapabilityGraph":
        return self._graph

    @property
    def selector(self) -> "CapabilitySelector":
        return self._selector

    def route(
        self,
        text: str,
        surface: "Surface" = None,
        owner_present: bool = True,
    ) -> "RouteDecision":
        if surface is None:
            surface = Surface.DESKTOP  # type: ignore[union-attr]
        request = UserRequest(text=text, surface=surface, owner_present=owner_present)
        return self._selector.select(request)

    def explain(self, decision: "RouteDecision") -> str:
        return self._explainer.explain(decision)


_default_runtime: Optional[JarvisPrimeRuntime] = None


def get_runtime() -> JarvisPrimeRuntime:
    """Return a process-wide default routing runtime, lazily constructed."""
    global _default_runtime
    if _default_runtime is None:
        _default_runtime = JarvisPrimeRuntime()
    return _default_runtime


# ---------------------------------------------------------------------------
# Conversation engine entry point (Wave 1)
# ---------------------------------------------------------------------------


@dataclass
class JarvisContext:
    """The minimal context the conversation engine needs from a caller.

    ``surface_metadata`` is the raw metadata dict produced by a gateway
    adapter (Slack, Termux, web app). The classifier inspects it to
    detect mobile vs focused surfaces. ``answer_body`` is the technical
    content the caller wants Jarvis Prime to deliver — the engine wraps
    it in the right tone, shape, and finalization pass.
    """

    user_input: str
    surface_metadata: Mapping[str, object] = field(default_factory=dict)
    answer_body: Optional[str] = None
    proposed_action: Optional[str] = None
    blast_radius: Optional[str] = None
    rollback: Optional[str] = None
    objection: Optional[str] = None
    stronger_version: Optional[str] = None
    expose_internal: bool = False


def render(context: JarvisContext) -> EngineResult:
    """Run the conversation engine for a single turn.

    Every final Jarvis Prime response should pass through this entry
    point before display. Returns an :class:`EngineResult` whose
    ``final_text`` is the user-facing string.
    """
    inputs = EngineInputs(
        content=context.answer_body,
        proposed_action=context.proposed_action,
        blast_radius=context.blast_radius,
        rollback=context.rollback,
        objection=context.objection,
        stronger_version=context.stronger_version,
    )
    return respond(
        context.user_input,
        metadata=context.surface_metadata,
        inputs=inputs,
        expose_internal=context.expose_internal,
    )


__all__ = [
    "JarvisPrimeRuntime",
    "get_runtime",
    "JarvisContext",
    "render",
]
