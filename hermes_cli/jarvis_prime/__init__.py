"""JARVIS Prime — Jeremiah Echerd's local-first AI operating partner.

Six-mode runtime (Companion / Strategy / Critic / Operator / Builder /
Mobile Voice) for Hermes Agent. Spec lives in
``docs/jarvis-prime-operating-system.md`` and the activation skill at
``skills/jarvis-prime/SKILL.md``. This package implements the runtime
the README spec layer reserved a slot for.

Public API:

- ``JarvisPrime`` — the orchestrator.
- ``Mode`` / ``ModeClassifier`` — six modes + intent classifier.
- ``Gate`` / ``GateResult`` / ``run_gate_summary`` — eight gates.
- ``OwnerAuth`` — owner-authorization phrase enforcement.
- ``AwarenessSnapshot`` — six-stream live perception.
- ``Persona`` — voice/identity system prompt builder.

The package is stdlib-only at import time so it loads in Termux and
slim CI images. Optional plugin backends (memory, gateway, github,
model router) are imported lazily inside ``runtime`` and ``awareness``.
"""

from __future__ import annotations

from hermes_cli.jarvis_prime.awareness import (
    AwarenessSnapshot,
    GatewayState,
    GitHubSnapshot,
    JobStatus,
    MemoryRecord as AwarenessMemoryRecord,
    TelemetrySnapshot,
    UserProfile,
    perceive,
)
from hermes_cli.jarvis_prime.companion_presence import (
    ActionRisk,
    AnimationStep,
    CompanionPresencePolicy,
    PresenceSignals,
    PresenceState,
    TaskAnimationPlan,
    default_avatar_traits,
)
from hermes_cli.jarvis_prime.epistemics import (
    AuditOutcome,
    AuditReport,
    audit_response,
)
from hermes_cli.jarvis_prime.gates import (
    Gate,
    GateOutcome,
    GateResult,
    GateSummary,
    run_gate_summary,
)
from hermes_cli.jarvis_prime.memory import (
    MemoryRecord,
    MemoryStore,
)
from hermes_cli.jarvis_prime.memory_tree import (
    MemoryChunk,
    MemoryTree,
)
from hermes_cli.jarvis_prime.modes import (
    Mode,
    ModeClassification,
    ModeClassifier,
)
from hermes_cli.jarvis_prime.natural_language_coder import (
    CodingIntent,
    CodingWorkPacket,
    build_work_packet,
    classify_intent,
    requires_owner_gate,
)
from hermes_cli.jarvis_prime.owner_auth import (
    AUTHORIZATION_PHRASE,
    OWNER_GATED_ACTIONS,
    OwnerAuth,
    OwnerGate,
)
from hermes_cli.jarvis_prime.persona import (
    DEFAULT_FORMAT,
    MOBILE_VOICE_FORMAT,
    OPERATOR_FORMAT,
    Persona,
    PersonaPrompt,
)
from hermes_cli.jarvis_prime.reasoning import (
    Inference,
    Premise,
    Reasoner,
    ReasoningKind,
    Rule,
    deduce,
    induce,
    should_research,
)
from hermes_cli.jarvis_prime.research import (
    ResearchBrief,
    ResearchQuestion,
    ResearchScope,
    needs_research,
    open_brief,
)
from hermes_cli.jarvis_prime.router import (
    RouteDecision,
    RouteTarget,
    Router,
)
from hermes_cli.jarvis_prime.self_update import (
    Proposal,
    ProposalBook,
    ProposalEvidence,
    ProposalKind,
    ProposalStatus,
)
from hermes_cli.jarvis_prime.work_packet import (
    REQUIRED_FIELDS as WORK_PACKET_REQUIRED_FIELDS,
    VALID_RISK_CLASSES as WORK_PACKET_RISK_CLASSES,
    WorkPacket,
    WorkPacketValidationFinding,
)
from hermes_cli.jarvis_prime.goal_boundary import (
    BoundaryError,
    Decision as LoopDecision,
    GoalBoundary,
    LoopController,
    LoopVerdict,
    StopReason,
)
from hermes_cli.jarvis_prime.navigation import (
    EditSite,
    IssueLocalizer,
    NavigationResult,
    Navigator,
)

__all__ = [
    "AUTHORIZATION_PHRASE",
    "ActionRisk",
    "AnimationStep",
    "AuditOutcome",
    "AuditReport",
    "AwarenessMemoryRecord",
    "AwarenessSnapshot",
    "BoundaryError",
    "CodingIntent",
    "CodingWorkPacket",
    "CompanionPresencePolicy",
    "DEFAULT_FORMAT",
    "EditSite",
    "Gate",
    "GateOutcome",
    "GateResult",
    "GateSummary",
    "GatewayState",
    "GitHubSnapshot",
    "GoalBoundary",
    "Inference",
    "IssueLocalizer",
    "JarvisPrime",
    "JobStatus",
    "LoopController",
    "LoopDecision",
    "LoopVerdict",
    "NavigationResult",
    "Navigator",
    "StopReason",
    "MOBILE_VOICE_FORMAT",
    "MemoryChunk",
    "MemoryRecord",
    "MemoryStore",
    "MemoryTree",
    "Mode",
    "ModeClassification",
    "ModeClassifier",
    "OPERATOR_FORMAT",
    "OWNER_GATED_ACTIONS",
    "OwnerAuth",
    "OwnerGate",
    "Persona",
    "PersonaPrompt",
    "Premise",
    "PresenceSignals",
    "PresenceState",
    "Proposal",
    "ProposalBook",
    "ProposalEvidence",
    "ProposalKind",
    "ProposalStatus",
    "Reasoner",
    "ReasoningKind",
    "ResearchBrief",
    "ResearchQuestion",
    "ResearchScope",
    "RouteDecision",
    "RouteTarget",
    "Router",
    "Rule",
    "TaskAnimationPlan",
    "TelemetrySnapshot",
    "UserProfile",
    "WORK_PACKET_REQUIRED_FIELDS",
    "WORK_PACKET_RISK_CLASSES",
    "WorkPacket",
    "WorkPacketValidationFinding",
    "audit_response",
    "build_work_packet",
    "classify_intent",
    "deduce",
    "default_avatar_traits",
    "induce",
    "needs_research",
    "open_brief",
    "perceive",
    "requires_owner_gate",
    "run_gate_summary",
    "should_research",
]

__version__ = "1.0.0"


def __getattr__(name: str):
    if name == "JarvisPrime":
        from hermes_cli.jarvis_prime.runtime import JarvisPrime

        return JarvisPrime
    raise AttributeError(f"module 'hermes_cli.jarvis_prime' has no attribute {name!r}")
