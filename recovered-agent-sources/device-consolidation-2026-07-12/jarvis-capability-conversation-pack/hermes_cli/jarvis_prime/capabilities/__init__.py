"""Capability graph and auto-routing for JARVIS Prime.

The capability graph is a typed registry of everything Jarvis can call on:

- ``skill`` -- procedure-encoded skills (``skills/<name>/SKILL.md``)
- ``runnable_agent`` -- AOS council members that can be dispatched
- ``domain_specialist`` -- advisors for bounded subject matter
- ``worker`` -- bounded executors (Claude Code, Codex, test runner, ...)
- ``persona`` -- tone/voice/audience overlays (not workers)
- ``product_role`` -- stakeholder viewpoints (not agents)
- ``archive`` -- preserved historical sources (never routed live)

The selector reads the loaded graph plus the request text/surface and
emits a :class:`RouteDecision` describing the smallest capable route.
The route explainer renders that decision in the operating handoff
format JARVIS Prime uses everywhere else.
"""

from hermes_cli.jarvis_prime.capabilities.graph import CapabilityGraph
from hermes_cli.jarvis_prime.capabilities.indexer import CapabilityIndexer
from hermes_cli.jarvis_prime.capabilities.route_explainer import RouteExplainer
from hermes_cli.jarvis_prime.capabilities.schemas import (
    Capability,
    CapabilityType,
    Edge,
    Intent,
    RiskLevel,
    RouteDecision,
    Surface,
    UserRequest,
)
from hermes_cli.jarvis_prime.capabilities.selector import CapabilitySelector

__all__ = [
    "Capability",
    "CapabilityGraph",
    "CapabilityIndexer",
    "CapabilitySelector",
    "CapabilityType",
    "Edge",
    "Intent",
    "RiskLevel",
    "RouteDecision",
    "RouteExplainer",
    "Surface",
    "UserRequest",
]
