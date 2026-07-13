"""Data schemas for the Jarvis Prime capability graph and auto-routing.

Everything in this file is plain dataclasses / enums. No I/O, no behaviour.
The point is that other modules (graph, indexer, selector, route explainer)
share the same vocabulary and can be unit-tested without scaffolding.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class CapabilityType(str, Enum):
    """Typed buckets in the capability graph.

    The type controls how the selector treats a capability:

    - ``SKILL`` and ``RUNNABLE_AGENT`` and ``WORKER`` and
      ``DOMAIN_SPECIALIST`` can be selected to participate in a route.
    - ``PERSONA`` only influences tone -- it is never added to
      ``selected_workers`` or ``selected_council``.
    - ``PRODUCT_ROLE`` represents a viewpoint -- it is never executed.
    - ``ARCHIVE`` items are historical references and are filtered out
      of live routes.
    """

    SKILL = "skill"
    RUNNABLE_AGENT = "runnable_agent"
    DOMAIN_SPECIALIST = "domain_specialist"
    WORKER = "worker"
    PERSONA = "persona"
    PRODUCT_ROLE = "product_role"
    ARCHIVE = "archive"


class RiskLevel(str, Enum):
    """Coarse risk class used to gate owner-required actions."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Surface(str, Enum):
    """Where the request is coming from.

    Surfaces influence whether the route defers long output (mobile voice)
    or asks for confirmation (Slack vs desktop).
    """

    DESKTOP = "desktop"
    SLACK = "slack"
    TERMUX = "termux"
    MOBILE_VOICE = "mobile_voice"
    GITHUB = "github"
    UNKNOWN = "unknown"


class Intent(str, Enum):
    """Coarse intent buckets the selector recognises."""

    CASUAL = "casual"
    QUESTION = "question"
    PLANNING = "planning"
    BUILD = "build"
    REVIEW_OR_AUDIT = "review_or_audit"
    LAUNCH_READINESS = "launch_readiness"
    DOMAIN_REVIEW = "domain_review"
    MEMORY = "memory"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Capability:
    """A single node in the capability graph.

    ``id`` is the canonical short name used in routing decisions. ``tags``
    and ``domain`` drive keyword/semantic matching in the selector. The
    ``metadata`` dict holds raw entries from the operating registry or
    skill frontmatter so downstream consumers can introspect without
    re-reading the file.
    """

    id: str
    type: CapabilityType
    description: str
    domain: Optional[str] = None
    tags: tuple[str, ...] = ()
    activation_phrases: tuple[str, ...] = ()
    path: Optional[str] = None
    owner_gate_required: bool = False
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Edge:
    """A directed relationship between two capabilities.

    Edges are optional metadata. They let the selector ask "what worker
    typically executes this skill?" or "what specialist governs this
    domain?" without hard-coding the relationship.
    """

    source: str
    target: str
    relation: str
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class UserRequest:
    """A request handed to the selector.

    ``owner_present`` matters for owner-gated actions: in async surfaces
    (cron, webhook) the request can be evaluated but execution must wait
    for explicit authorization.
    """

    text: str
    surface: Surface = Surface.DESKTOP
    owner_present: bool = True


@dataclass
class RouteDecision:
    """The smallest capable route for a request.

    The selector populates all fields. ``rationale`` is a list of short
    bullet strings explaining why each non-empty selection was made;
    ``confidence`` is a coarse 0-1 score the explainer surfaces.
    """

    intent: Intent
    domain: Optional[str]
    risk: RiskLevel
    surface: Surface
    selected_skills: list[str] = field(default_factory=list)
    selected_council: list[str] = field(default_factory=list)
    selected_specialists: list[str] = field(default_factory=list)
    selected_workers: list[str] = field(default_factory=list)
    selected_memory: list[str] = field(default_factory=list)
    persona_influence: list[str] = field(default_factory=list)
    product_role_viewpoints: list[str] = field(default_factory=list)
    owner_gate_required: bool = False
    defer_heavy_output: bool = False
    rationale: list[str] = field(default_factory=list)
    confidence: float = 0.0


__all__ = [
    "Capability",
    "CapabilityType",
    "Edge",
    "Intent",
    "RiskLevel",
    "RouteDecision",
    "Surface",
    "UserRequest",
]
