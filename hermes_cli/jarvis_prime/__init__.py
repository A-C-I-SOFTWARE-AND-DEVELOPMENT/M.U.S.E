"""muse — Jeremiah Echerd's local-first AI operating partner.

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
    ApprovalState,
    ContextPack,
    ContradictionReport,
    ContradictionStatus,
    MemoryChunk,
    MemoryLayer,
    MemoryNamespace,
    MemoryNode,
    MemorySearchResult,
    MemorySource,
    MemoryTree,
    MemoryTreeStore,
    MemoryWritePolicy,
    MemoryWriteResult,
    SensitivityClass,
    SourceTrust,
    canonicalize_text,
    estimate_tokens,
    stable_memory_id,
)
from hermes_cli.jarvis_prime.modes import (
    Mode,
    ModeClassification,
    ModeClassifier,
)
from hermes_cli.jarvis_prime.natural_language_coder import (
    CodingIntent,
    CodingWorkPacket,
    ModelLaneHint,
    OwnerGate as CodingOwnerGate,
    PacketValidationFinding,
    PacketValidationResult,
    RiskClass,
    RouteDecision as CodingRouteDecision,
    WorkerRole,
    build_work_packet,
    classify_intent,
    parse_owner_gate_keywords,
    render_packet_markdown,
    requires_owner_gate,
    route_request,
    validate_work_packet,
)
from hermes_cli.jarvis_prime.model_scorecard import (
    ModelScorecard,
    ScorecardBook,
    local_endpoint_packet,
)
from hermes_cli.jarvis_prime.task_router import (
    ModelRouteDecision,
    TaskClass,
    all_routes,
    route_for_task,
)
from hermes_cli.jarvis_prime.monitor_collectors import (
    collect_context as collect_monitor_context,
    collect_memory_contradictions,
    collect_model_failures,
    collect_pending_proposals,
    collect_repo_state,
)
from hermes_cli.jarvis_prime.monitors import (
    Monitor,
    MonitorBoard,
    MonitorResult,
    Severity as MonitorSeverity,
)
from hermes_cli.jarvis_prime.owner_auth import (
    AUTHORIZATION_PHRASE,
    OWNER_GATED_ACTIONS,
    OwnerAuth,
    OwnerGate,
)
from hermes_cli.jarvis_prime.owner_brief import (
    OwnerBrief,
    build_owner_brief,
)
from hermes_cli.jarvis_prime.proposal_executor import (
    ExecutionPlan,
    ProposalNotApproved,
    build_execution_plan,
    validate_execution_plan,
)
from hermes_cli.jarvis_prime.research_vault import (
    CourseArtifactCard,
    EvidenceStrength,
    ModelBenchmarkCard,
    OSSPracticeCard,
    ResearchArtifact,
    ResearchVault,
    SkillProposalCard,
    SourceType,
)
from hermes_cli.jarvis_prime.tokenjuice import (
    CompiledContext,
    ContextSection,
    TokenJuiceCompiler,
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
    "ApprovalState",
    "AuditOutcome",
    "AuditReport",
    "AwarenessMemoryRecord",
    "AwarenessSnapshot",
    "BoundaryError",
    "CodingIntent",
    "CodingOwnerGate",
    "CodingRouteDecision",
    "CodingWorkPacket",
    "CompanionPresencePolicy",
    "CompiledContext",
    "ContextPack",
    "ContextSection",
    "ContradictionReport",
    "ContradictionStatus",
    "CourseArtifactCard",
    "EvidenceStrength",
    "ExecutionPlan",
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
    "MemoryLayer",
    "MemoryNamespace",
    "MemoryNode",
    "MemoryRecord",
    "MemorySearchResult",
    "MemorySource",
    "MemoryStore",
    "MemoryTree",
    "MemoryTreeStore",
    "MemoryWritePolicy",
    "MemoryWriteResult",
    "ModelBenchmarkCard",
    "ModelLaneHint",
    "ModelScorecard",
    "Mode",
    "Monitor",
    "MonitorBoard",
    "MonitorResult",
    "MonitorSeverity",
    "ModeClassification",
    "ModeClassifier",
    "OPERATOR_FORMAT",
    "OSSPracticeCard",
    "OWNER_GATED_ACTIONS",
    "OwnerAuth",
    "OwnerBrief",
    "OwnerGate",
    "PacketValidationFinding",
    "PacketValidationResult",
    "Persona",
    "PersonaPrompt",
    "Premise",
    "PresenceSignals",
    "PresenceState",
    "Proposal",
    "ProposalBook",
    "ProposalEvidence",
    "ProposalKind",
    "ProposalNotApproved",
    "ProposalStatus",
    "Reasoner",
    "ReasoningKind",
    "ResearchBrief",
    "ResearchQuestion",
    "ResearchArtifact",
    "ResearchScope",
    "ResearchVault",
    "RiskClass",
    "RouteDecision",
    "RouteTarget",
    "Router",
    "Rule",
    "ModelRouteDecision",
    "TaskClass",
    "all_routes",
    "route_for_task",
    "ScorecardBook",
    "SensitivityClass",
    "SkillProposalCard",
    "SourceTrust",
    "SourceType",
    "TaskAnimationPlan",
    "TokenJuiceCompiler",
    "TelemetrySnapshot",
    "UserProfile",
    "WORK_PACKET_REQUIRED_FIELDS",
    "WORK_PACKET_RISK_CLASSES",
    "WorkPacket",
    "WorkPacketValidationFinding",
    "WorkerRole",
    "audit_response",
    "build_execution_plan",
    "build_owner_brief",
    "build_work_packet",
    "canonicalize_text",
    "classify_intent",
    "collect_memory_contradictions",
    "collect_model_failures",
    "collect_monitor_context",
    "collect_pending_proposals",
    "collect_repo_state",
    "deduce",
    "default_avatar_traits",
    "estimate_tokens",
    "induce",
    "local_endpoint_packet",
    "needs_research",
    "open_brief",
    "parse_owner_gate_keywords",
    "perceive",
    "render_packet_markdown",
    "requires_owner_gate",
    "route_request",
    "run_gate_summary",
    "should_research",
    "stable_memory_id",
    "validate_execution_plan",
    "validate_work_packet",
]

__version__ = "1.0.0"


def __getattr__(name: str):
    if name == "JarvisPrime":
        from hermes_cli.jarvis_prime.runtime import JarvisPrime

        return JarvisPrime
    raise AttributeError(f"module 'hermes_cli.jarvis_prime' has no attribute {name!r}")
