"""JARVIS Prime router.

The router is the thin call site that other parts of Hermes use to ask
"where should this request go?". It delegates to the capability selector
and returns a structured ``RouteDecision`` plus a rendered explanation.

Wave 3 makes auto-routing the default: no activation phrase is required.
The selector inspects the request text, the surface (Slack, Termux,
mobile voice, desktop), and the loaded capability graph to pick the
smallest capable route.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from hermes_cli.jarvis_prime.capabilities import (
    RouteDecision,
    Surface,
)
from hermes_cli.jarvis_prime.runtime import JarvisPrimeRuntime, get_runtime


@dataclass(frozen=True)
class RoutingResult:
    """Pair the structured decision with a human-readable explanation."""

    decision: RouteDecision
    explanation: str


class JarvisRouter:
    """Public routing entry point for callers outside the capabilities package."""

    def __init__(self, runtime: Optional[JarvisPrimeRuntime] = None) -> None:
        self._runtime = runtime or get_runtime()

    def route(
        self,
        text: str,
        surface: Surface = Surface.DESKTOP,
        owner_present: bool = True,
    ) -> RoutingResult:
        decision = self._runtime.route(text=text, surface=surface, owner_present=owner_present)
        explanation = self._runtime.explain(decision)
        return RoutingResult(decision=decision, explanation=explanation)


def route(
    text: str,
    surface: Surface = Surface.DESKTOP,
    owner_present: bool = True,
) -> RoutingResult:
    """Module-level convenience that uses the default runtime."""
    return JarvisRouter().route(text=text, surface=surface, owner_present=owner_present)


__all__ = ["JarvisRouter", "RoutingResult", "route"]
