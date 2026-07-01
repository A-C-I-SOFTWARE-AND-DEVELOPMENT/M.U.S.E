"""Natural-language coder — bounded work-packet builder for muse

Turns a plain-English request into a bounded, reviewable, gate-compatible
work packet. It **never executes**; it only describes scope, risk,
verification, reviewer separation, owner gates, and rollback for
downstream workers (Claude Code builder, Codex reviewer, …).

Backward compatibility: the original :class:`CodingWorkPacket` fields
(``mission``, ``intent``, ``branch``, ``risk_class``, ``allowed_files``,
``acceptance_criteria``, ``verification_plan``, ``primary_worker``,
``reviewer_worker``, ``owner_gated_actions``) and the
``classify_intent`` / ``build_work_packet`` / ``requires_owner_gate``
helpers keep their established behavior. New, richer fields and helpers
are added alongside them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Mapping, Optional, Sequence


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class CodingIntent(Enum):
    RESEARCH = "research"
    AUDIT = "audit"
    IMPLEMENT = "implement"
    REVIEW = "review"
    TEST = "test"
    DOCUMENT = "document"
    REFACTOR = "refactor"
    MODEL_ROUTING = "model_routing"
    MEMORY = "memory"
    ANDROID = "android"
    AVATAR_PRESENCE = "avatar_presence"
    DEVICE_ACTION = "device_action"
    RELEASE = "release"
    SECURITY = "security"
    UPDATE = "update"
    UNKNOWN = "unknown"


class RiskClass(Enum):
    RC0 = "RC0"  # read-only / summarize
    RC1 = "RC1"  # docs / tests / narrow local-only code
    RC2 = "RC2"  # implementation / refactor with code changes
    RC3 = "RC3"  # device action, auth/security, external comms, merge/deploy, spend
    RC4 = "RC4"  # blocked: bypass-gate, exfiltration, harmful, destructive prod


class WorkerRole(Enum):
    BUILDER = "builder"
    REVIEWER = "reviewer"
    PLANNER = "planner"


class OwnerGate(Enum):
    MERGE_MAIN = "merge_main"
    DEPLOY = "deploy"
    PUBLISH = "publish"
    EXTERNAL_MESSAGE = "external_message"
    PURCHASE_OR_SPEND = "purchase_or_spend"
    OAUTH_OR_CREDENTIALS = "oauth_or_credentials"
    SECURITY_SENSITIVE_CHANGE = "security_sensitive_change"
    DESTRUCTIVE_FILE_OPERATION = "destructive_file_operation"
    ANDROID_ACCESSIBILITY_GESTURE = "android_accessibility_gesture"
    APP_STORE_OR_PUBLIC_RELEASE = "app_store_or_public_release"
    EXPLICIT_OR_MATURE_CONTENT_CONFIRMATION = "explicit_or_mature_content_confirmation"


# Maps detected owner gates to the canonical owner_auth vocabulary used by
# ``run_gate_summary`` / ``owner_approval_gate``.  Gates with no direct
# canonical equivalent map to the closest category so the gate packet stays
# valid rather than failing on an unknown category.
_GATE_TO_OWNER_AUTH: dict[OwnerGate, str] = {
    OwnerGate.MERGE_MAIN: "force_push",
    OwnerGate.DEPLOY: "production_deploy",
    OwnerGate.PUBLISH: "package_publish",
    OwnerGate.EXTERNAL_MESSAGE: "post_publicly",
    OwnerGate.PURCHASE_OR_SPEND: "spend_money",
    OwnerGate.OAUTH_OR_CREDENTIALS: "oauth_change",
    OwnerGate.SECURITY_SENSITIVE_CHANGE: "modify_secrets",
    OwnerGate.DESTRUCTIVE_FILE_OPERATION: "delete_recovered_sources",
    OwnerGate.ANDROID_ACCESSIBILITY_GESTURE: "app_store_submission",
    OwnerGate.APP_STORE_OR_PUBLIC_RELEASE: "app_store_submission",
    OwnerGate.EXPLICIT_OR_MATURE_CONTENT_CONFIRMATION: "regulated_claim",
}


class ModelLaneHint(Enum):
    FRONTIER = "frontier"
    CLAUDE = "claude"
    OPENAI_CODEX = "openai_codex"
    GEMINI = "gemini"
    LOCAL_OSS = "local_oss"


# ---------------------------------------------------------------------------
# Route decision
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RouteDecision:
    intent: CodingIntent
    risk_class: RiskClass
    primary_worker: str
    reviewer_worker: str
    model_lane_hint: ModelLaneHint
    owner_gates: tuple[OwnerGate, ...] = ()
    blocked: bool = False
    rationale: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "intent": self.intent.value,
            "risk_class": self.risk_class.value,
            "primary_worker": self.primary_worker,
            "reviewer_worker": self.reviewer_worker,
            "model_lane_hint": self.model_lane_hint.value,
            "owner_gates": [g.value for g in self.owner_gates],
            "blocked": self.blocked,
            "rationale": self.rationale,
        }


# ---------------------------------------------------------------------------
# Work packet + validation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CodingWorkPacket:
    mission: str
    intent: CodingIntent
    branch: str
    risk_class: str  # kept as RCx string for compatibility
    allowed_files: tuple[str, ...]
    acceptance_criteria: tuple[str, ...]
    verification_plan: tuple[str, ...]
    primary_worker: str = "claude-code-windows"
    reviewer_worker: str = "codex"
    owner_gated_actions: tuple[str, ...] = ()  # generic markers (compat)
    # --- richer fields ---
    normalized_intent: str = ""
    repo_root: str = "."
    forbidden_files: tuple[str, ...] = ()
    non_goals: tuple[str, ...] = ()
    assumptions: tuple[str, ...] = ()
    rollback_plan: tuple[str, ...] = ()
    owner_gates: tuple[OwnerGate, ...] = ()
    model_lane_hint: str = "claude"
    evidence_required: tuple[str, ...] = ()
    blocked: bool = False
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, object]:
        return {
            "mission": self.mission,
            "intent": self.intent.value,
            "normalized_intent": self.normalized_intent or self.intent.value,
            "branch": self.branch,
            "risk_class": self.risk_class,
            "repo_root": self.repo_root,
            "allowed_files": list(self.allowed_files),
            "forbidden_files": list(self.forbidden_files),
            "non_goals": list(self.non_goals),
            "assumptions": list(self.assumptions),
            "acceptance_criteria": list(self.acceptance_criteria),
            "verification_plan": list(self.verification_plan),
            "rollback_plan": list(self.rollback_plan),
            "owner_gated_actions": list(self.owner_gated_actions),
            "owner_gates": [g.value for g in self.owner_gates],
            "primary_worker": self.primary_worker,
            "reviewer_worker": self.reviewer_worker,
            # Acting/builder agent id (same value as primary_worker) so a
            # serialized packet carries the identity the C19 review gate reads.
            "acting_agent_id": self.primary_worker,
            "model_lane_hint": self.model_lane_hint,
            "evidence_required": list(self.evidence_required),
            "blocked": self.blocked,
            "generated_at": self.generated_at,
        }

    @property
    def packet_id(self) -> str:
        """Deterministic id over the *stable* packet fields.

        Excludes ``generated_at`` so the same logical packet always hashes the
        same. Strict gates bind an evidence bundle to this id, so a bundle
        collected for one packet cannot be replayed against another.
        """

        from hermes_cli.jarvis_prime.guardrail_evidence import (
            canonical_json,
            sha256_hex,
        )

        stable = {
            "mission": self.mission,
            "intent": self.intent.value,
            "normalized_intent": self.normalized_intent or self.intent.value,
            "branch": self.branch,
            "risk_class": self.risk_class,
            "repo_root": self.repo_root,
            "allowed_files": sorted(self.allowed_files),
            "owner_gates": sorted(g.value for g in self.owner_gates),
            "blocked": self.blocked,
        }
        return sha256_hex(canonical_json(stable))

    # -- explicit "planned" aliases -------------------------------------
    # These make it unambiguous that the packet describes *intent*, not
    # observed reality. Strict gates never read these as evidence.

    @property
    def planned_allowed_files(self) -> tuple[str, ...]:
        return self.allowed_files

    @property
    def planned_verification_commands(self) -> tuple[str, ...]:
        return self.verification_plan

    @property
    def planned_rollback(self) -> tuple[str, ...]:
        return self.rollback_plan

    def to_gate_packet(self) -> dict[str, object]:
        """Produce a dict consumable by ``gates.run_gate_summary``.

        This carries planning-, release-, and owner-gate fields (which are
        legitimately statements of intent), plus the ``packet_id`` and the
        *planned* verification/scope under explicit ``planned_*`` keys. It no
        longer fabricates observed-evidence fields (``files_changed``,
        ``diff_reviewed``, ``tests_run`` as if executed): in strict evidence
        mode those must come from a real evidence bundle, not the packet.
        """

        owner_actions = sorted({
            _GATE_TO_OWNER_AUTH[g] for g in self.owner_gates if g in _GATE_TO_OWNER_AUTH
        })
        return {
            "packet_id": self.packet_id,
            "repo_root": self.repo_root,
            "branch": self.branch,
            "risk_class": self.risk_class,
            "mission": self.mission,
            # Acting/builder agent id, in the same namespace as a review's
            # reviewer_id. Guardrail collectors thread this into
            # collect_git_diff_evidence(author_id=...) so the strict review
            # gate's Clause C19 builder != reviewer check enforces at RC2+.
            # The packet validator guarantees primary_worker != reviewer_worker
            # for RC2+, so a well-formed packet never self-blocks here.
            "acting_agent_id": self.primary_worker,
            "allowed_files": list(self.allowed_files),
            "non_goals": list(self.non_goals),
            "acceptance_criteria": list(self.acceptance_criteria),
            "verification_summary": list(self.verification_plan),
            "verification_plan": list(self.verification_plan),
            "rollback_plan": list(self.rollback_plan),
            "remaining_risks": list(self.non_goals) or ["see acceptance criteria"],
            "owner_gated_actions": owner_actions,
            # Planned (intent) fields — never treated as captured evidence.
            "planned_allowed_files": list(self.allowed_files),
            "planned_verification_commands": list(self.verification_plan),
            "planned_rollback": list(self.rollback_plan),
            "required_evidence": list(self.to_evidence_requirements()),
        }

    def to_evidence_requirements(self) -> tuple[str, ...]:
        """Artifact types this packet must produce before strict gates pass.

        Risk-scaled: RC1 needs little; RC2+ needs a real diff, secret scan,
        test (or accepted skip), review, and rollback; RC3+ additionally needs a
        challenge-bound owner grant; RC4 is blocked (refusal only, no plan).
        """

        from hermes_cli.jarvis_prime.guardrail_evidence import (
            ARTIFACT_GIT_DIFF,
            ARTIFACT_OWNER_GRANT,
            ARTIFACT_REVIEW,
            ARTIFACT_ROLLBACK,
            ARTIFACT_SECRET_SCAN,
            ARTIFACT_TEST_RESULT,
        )

        rc = (self.risk_class or "RC1").upper()
        if self.blocked or rc >= "RC4":
            return ()  # blocked: no executable plan, refusal/review only
        reqs: list[str] = []
        if rc >= "RC2":
            reqs.extend(
                [
                    ARTIFACT_GIT_DIFF,
                    ARTIFACT_SECRET_SCAN,
                    ARTIFACT_TEST_RESULT,
                    ARTIFACT_REVIEW,
                    ARTIFACT_ROLLBACK,
                ]
            )
        if rc >= "RC3":
            reqs.append(ARTIFACT_OWNER_GRANT)
        return tuple(reqs)


@dataclass(frozen=True)
class PacketValidationFinding:
    field: str
    severity: str  # "error" | "warning"
    message: str

    def to_dict(self) -> dict[str, object]:
        return {"field": self.field, "severity": self.severity, "message": self.message}


@dataclass(frozen=True)
class PacketValidationResult:
    ok: bool
    findings: tuple[PacketValidationFinding, ...] = ()

    @property
    def errors(self) -> tuple[PacketValidationFinding, ...]:
        return tuple(f for f in self.findings if f.severity == "error")

    @property
    def warnings(self) -> tuple[PacketValidationFinding, ...]:
        return tuple(f for f in self.findings if f.severity == "warning")

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "findings": [f.to_dict() for f in self.findings],
        }


# ---------------------------------------------------------------------------
# Keyword tables
# ---------------------------------------------------------------------------


_INTENT_KEYWORDS: tuple[tuple[CodingIntent, tuple[str, ...]], ...] = (
    (
        CodingIntent.AVATAR_PRESENCE,
        ("avatar", "floating", "mini version", "living", "corner overlay", "presence"),
    ),
    (
        CodingIntent.DEVICE_ACTION,
        (
            "tap",
            "click",
            "open app",
            "control phone",
            "facebook",
            "swipe",
            "gesture",
            "press the",
        ),
    ),
    (
        CodingIntent.ANDROID,
        ("android", "kotlin", "apk", "gradle", "accessibility service"),
    ),
    (
        CodingIntent.UPDATE,
        (
            "update hermes",
            "update the agent",
            "update jarvis",
            "sync fork",
            "sync my fork",
            "merge upstream",
            "pull upstream",
            "consolidate my branch",
            "consolidate branches",
        ),
    ),
    (
        CodingIntent.AUDIT,
        ("audit", "assess readiness", "review the repo end to end", "gap analysis"),
    ),
    (
        CodingIntent.RESEARCH,
        ("research", "deep search", "compare", "investigate", "dossier", "find out"),
    ),
    (
        CodingIntent.SECURITY,
        (
            "security",
            "vulnerab",
            "owasp",
            "exploit",
            "harden",
            "threat model",
            "credential",
        ),
    ),
    (
        CodingIntent.RELEASE,
        (
            "release",
            "publish",
            "deploy",
            "ship to prod",
            "merge to main",
            "cut a version",
        ),
    ),
    (
        CodingIntent.MODEL_ROUTING,
        (
            "model routing",
            "route to",
            "which model",
            "scorecard",
            "model lane",
            "choose a model",
        ),
    ),
    (
        CodingIntent.MEMORY,
        (
            "memory tree",
            "remember",
            "recall",
            "context pack",
            "memory os",
            "durable memory",
        ),
    ),
    (CodingIntent.REVIEW, ("review", "critique", "inspect", "code review")),
    (CodingIntent.TEST, ("test", "verify", "failing", "regression", "coverage")),
    (
        CodingIntent.DOCUMENT,
        ("doc", "readme", "guide", "explain", "write up", "onboarding"),
    ),
    (
        CodingIntent.REFACTOR,
        ("refactor", "clean up", "restructure", "rename", "extract"),
    ),
    (
        CodingIntent.IMPLEMENT,
        ("add", "implement", "build", "create", "wire", "support", "feature"),
    ),
)


_OWNER_GATE_KEYWORDS: tuple[tuple[OwnerGate, tuple[str, ...]], ...] = (
    (
        OwnerGate.MERGE_MAIN,
        ("merge to main", "merge main", "merge into main", "merge to master"),
    ),
    (
        OwnerGate.DEPLOY,
        ("deploy", "deployment", "ship to prod", "production deploy", "go live"),
    ),
    (
        OwnerGate.PUBLISH,
        ("publish", "npm publish", "pypi", "release to registry", "package publish"),
    ),
    (
        OwnerGate.EXTERNAL_MESSAGE,
        (
            "post to",
            "send a message",
            "tweet",
            "email",
            "dm ",
            "reply on",
            "post publicly",
            "post on",
        ),
    ),
    (
        OwnerGate.PURCHASE_OR_SPEND,
        ("buy", "purchase", "spend", "pay for", "subscribe", "checkout"),
    ),
    (
        OwnerGate.OAUTH_OR_CREDENTIALS,
        (
            "oauth",
            "api key",
            "credential",
            "rotate token",
            "sign in",
            "login flow",
            "secret",
        ),
    ),
    (
        OwnerGate.SECURITY_SENSITIVE_CHANGE,
        (
            "security policy",
            "permission model",
            "auth flow",
            "disable security",
            "bypass auth",
        ),
    ),
    (
        OwnerGate.DESTRUCTIVE_FILE_OPERATION,
        ("rm -rf", "delete all", "drop table", "wipe", "force delete", "purge"),
    ),
    (
        OwnerGate.ANDROID_ACCESSIBILITY_GESTURE,
        ("tap", "click", "swipe", "gesture", "control phone", "open app", "facebook"),
    ),
    (
        OwnerGate.APP_STORE_OR_PUBLIC_RELEASE,
        ("app store", "play store", "public release", "store submission"),
    ),
)


_BYPASS_PATTERNS = (
    re.compile(r"(?i)bypass (the )?owner gate"),
    re.compile(r"(?i)skip (the )?(owner )?approval"),
    re.compile(r"(?i)without (asking|owner) (approval|confirmation)"),
    re.compile(r"(?i)ignore (the )?(owner )?gates?"),
    re.compile(r"(?i)disable (the )?(owner )?gates?"),
    re.compile(
        r"(?i)\b(exfiltrate|steal|leak)\b.*\b(credential|secret|token|api[ _-]?key|key)\b"
    ),
)


# ---------------------------------------------------------------------------
# Classification + routing
# ---------------------------------------------------------------------------


def classify_intent(prompt: str, context: Optional[Mapping] = None) -> CodingIntent:
    text = (prompt or "").lower()
    if not text.strip():
        return CodingIntent.UNKNOWN
    for intent, keywords in _INTENT_KEYWORDS:
        if any(kw in text for kw in keywords):
            return intent
    return CodingIntent.IMPLEMENT


def parse_owner_gate_keywords(prompt: str) -> tuple[OwnerGate, ...]:
    """Extract owner-gate categories implied by the request."""

    text = (prompt or "").lower()
    gates: list[OwnerGate] = []
    for gate, keywords in _OWNER_GATE_KEYWORDS:
        if any(kw in text for kw in keywords):
            gates.append(gate)
    # De-duplicate, preserve order.
    return tuple(dict.fromkeys(gates))


def _is_blocked(prompt: str) -> bool:
    return any(pat.search(prompt or "") for pat in _BYPASS_PATTERNS)


def _risk_for(
    intent: CodingIntent, gates: Sequence[OwnerGate], blocked: bool
) -> RiskClass:
    if blocked:
        return RiskClass.RC4
    # Owner gates (external/irreversible) or device/release/security intents
    # are always RC3 — they touch the world, not just the repo.
    if gates or intent in (
        CodingIntent.DEVICE_ACTION,
        CodingIntent.AVATAR_PRESENCE,
        CodingIntent.RELEASE,
        CodingIntent.SECURITY,
    ):
        return RiskClass.RC3
    # Multi-file code changes without owner-gated side effects.
    if intent in (
        CodingIntent.REFACTOR,
        CodingIntent.MEMORY,
        CodingIntent.MODEL_ROUTING,
        CodingIntent.ANDROID,
    ):
        return RiskClass.RC2
    if intent in (CodingIntent.RESEARCH, CodingIntent.AUDIT, CodingIntent.REVIEW):
        return RiskClass.RC0
    # IMPLEMENT, TEST, DOCUMENT, UNKNOWN — narrow local-only code/docs/tests.
    return RiskClass.RC1


def route_request(prompt: str, context: Optional[Mapping] = None) -> RouteDecision:
    intent = classify_intent(prompt, context)
    blocked = _is_blocked(prompt)
    gates = parse_owner_gate_keywords(prompt)
    # Avatar/device intents always imply the accessibility gate downstream.
    if intent in (CodingIntent.AVATAR_PRESENCE, CodingIntent.DEVICE_ACTION):
        if OwnerGate.ANDROID_ACCESSIBILITY_GESTURE not in gates:
            gates = (*gates, OwnerGate.ANDROID_ACCESSIBILITY_GESTURE)
    risk = _risk_for(intent, gates, blocked)

    # Builder/reviewer separation. High-risk gets an independent frontier reviewer.
    builder = "claude-code-windows"
    reviewer = "codex"
    lane = ModelLaneHint.CLAUDE
    if risk in (RiskClass.RC3, RiskClass.RC4):
        reviewer = "gpt-5-codex-review"
        lane = ModelLaneHint.CLAUDE
    if intent in (CodingIntent.RESEARCH, CodingIntent.AUDIT):
        lane = ModelLaneHint.FRONTIER
    if intent == CodingIntent.MODEL_ROUTING:
        lane = ModelLaneHint.FRONTIER

    rationale = (
        "blocked: request attempts to bypass owner gates or exfiltrate secrets"
        if blocked
        else f"{intent.value} request routed at {risk.value}"
    )
    return RouteDecision(
        intent=intent,
        risk_class=risk,
        primary_worker=builder,
        reviewer_worker=reviewer,
        model_lane_hint=lane,
        owner_gates=gates,
        blocked=blocked,
        rationale=rationale,
    )


# ---------------------------------------------------------------------------
# Backward-compatible helper
# ---------------------------------------------------------------------------


def requires_owner_gate(prompt: str, intent: CodingIntent) -> bool:
    """Legacy boolean helper, preserved for older callers."""

    if intent in (CodingIntent.DEVICE_ACTION, CodingIntent.AVATAR_PRESENCE):
        return True
    if _is_blocked(prompt):
        return True
    return bool(parse_owner_gate_keywords(prompt))


# ---------------------------------------------------------------------------
# Scope tables (intent → allowed files / acceptance / verification / rollback)
# ---------------------------------------------------------------------------


def _allowed_files_for(intent: CodingIntent) -> tuple[str, ...]:
    if intent == CodingIntent.AVATAR_PRESENCE:
        return (
            "apps/android/**",
            "hermes_cli/jarvis_prime/companion_presence.py",
            "tests/test_jarvis_prime_companion_presence.py",
            "docs/jarvis_architecture/**",
        )
    if intent in (CodingIntent.DEVICE_ACTION, CodingIntent.ANDROID):
        return ("apps/android/**", "docs/implementation-packets/**")
    if intent in (CodingIntent.RESEARCH, CodingIntent.AUDIT):
        return ("docs/jarvis_research/**",)
    if intent == CodingIntent.DOCUMENT:
        return ("docs/**",)
    if intent == CodingIntent.TEST:
        return ("tests/**",)
    if intent == CodingIntent.MEMORY:
        return (
            "hermes_cli/jarvis_prime/memory_tree.py",
            "hermes_cli/jarvis_prime/memory.py",
            "tests/test_jarvis_prime_memory_tree.py",
            "docs/jarvis_architecture/**",
        )
    if intent == CodingIntent.MODEL_ROUTING:
        return (
            "hermes_cli/jarvis_prime/model_scorecard.py",
            "hermes_cli/jarvis_prime/router.py",
            "config/model-catalog.yaml",
            "docs/ai-intelligence/**",
            "tests/**",
        )
    if intent in (CodingIntent.RELEASE, CodingIntent.SECURITY):
        return ("hermes_cli/**", "tests/**", "docs/**")
    return ("hermes_cli/**", "tests/**", "docs/**")


def _forbidden_files_for(intent: CodingIntent) -> tuple[str, ...]:
    base = ("**/.env", "**/*credentials*", "**/secrets/**")
    if intent in (CodingIntent.RESEARCH, CodingIntent.AUDIT, CodingIntent.REVIEW):
        return base + ("hermes_cli/**", "apps/android/**", "gateway/**")
    if intent == CodingIntent.DOCUMENT:
        return base + ("hermes_cli/**", "apps/android/**")
    return base


def _acceptance_for(
    intent: CodingIntent, gates: Sequence[OwnerGate]
) -> tuple[str, ...]:
    base = (
        "changes stay inside allowed files",
        "builder and reviewer are separate workers",
        "tests run or a skip reason is recorded",
        "no secrets, credentials, or chain-of-thought committed",
    )
    if gates or intent in (CodingIntent.AVATAR_PRESENCE, CodingIntent.DEVICE_ACTION):
        base = base + (
            "real/external/irreversible actions stay behind explicit owner gates",
        )
    if intent in (CodingIntent.RESEARCH, CodingIntent.AUDIT):
        base = base + ("every claim cites a primary or official source",)
    return base


def _verification_for(intent: CodingIntent) -> tuple[str, ...]:
    if intent in (
        CodingIntent.AVATAR_PRESENCE,
        CodingIntent.DEVICE_ACTION,
        CodingIntent.ANDROID,
    ):
        return (
            "python -m compileall -q hermes_cli/jarvis_prime",
            "pytest -q tests/test_jarvis_prime_companion_presence.py",
            "run Android unit tests when the Android toolchain is available",
            "review privacy and permission boundaries",
        )
    if intent in (CodingIntent.RESEARCH, CodingIntent.AUDIT, CodingIntent.REVIEW):
        return (
            "verify every cited source resolves",
            "record vendor claims as vendor-reported",
        )
    if intent == CodingIntent.DOCUMENT:
        return ("verify documented commands run", "verify internal links resolve")
    return (
        "python -m compileall -q hermes_cli/jarvis_prime",
        "run focused pytest for touched modules",
    )


def _rollback_for(intent: CodingIntent) -> tuple[str, ...]:
    return (
        "work happens on an isolated feature branch (never main)",
        "revert the branch / drop the PR to fully undo",
        "no schema or irreversible migration without a separate owner gate",
    )


def _evidence_for(intent: CodingIntent) -> tuple[str, ...]:
    if intent in (CodingIntent.RESEARCH, CodingIntent.AUDIT):
        return ("cited primary sources", "freshness date per claim")
    if intent in (CodingIntent.IMPLEMENT, CodingIntent.REFACTOR, CodingIntent.MEMORY):
        return ("passing focused tests", "reviewer sign-off")
    return ("reviewer sign-off",)


def _slug(text: str) -> str:
    words = re.findall(r"[a-z0-9]+", (text or "").lower())[:8]
    return "-".join(words) or "task"


# ---------------------------------------------------------------------------
# Packet builder
# ---------------------------------------------------------------------------


def build_work_packet(
    prompt: str,
    repo_root: str = ".",
    branch_prefix: str = "jarvis",
    allowed_files: Optional[Sequence[str]] = None,
    forbidden_files: Optional[Sequence[str]] = None,
    context: Optional[Mapping] = None,
) -> CodingWorkPacket:
    route = route_request(prompt, context)
    intent = route.intent
    mission = (prompt or "").strip()

    allowed = (
        tuple(allowed_files)
        if allowed_files is not None
        else _allowed_files_for(intent)
    )
    forbidden = (
        tuple(forbidden_files)
        if forbidden_files is not None
        else _forbidden_files_for(intent)
    )

    # Owner-gated marker: keep the generic "owner_approval" token for
    # backward compatibility, present whenever any owner gate fires.
    gated = bool(route.owner_gates) or route.blocked
    owner_actions = ("owner_approval",) if gated else ()

    branch = f"{branch_prefix}/{_slug(prompt)}"

    return CodingWorkPacket(
        mission=mission,
        intent=intent,
        branch=branch,
        risk_class=route.risk_class.value,
        allowed_files=allowed,
        acceptance_criteria=_acceptance_for(intent, route.owner_gates),
        verification_plan=_verification_for(intent),
        primary_worker=route.primary_worker,
        reviewer_worker=route.reviewer_worker,
        owner_gated_actions=owner_actions,
        normalized_intent=intent.value,
        repo_root=repo_root,
        forbidden_files=forbidden,
        non_goals=_non_goals_for(intent),
        assumptions=("repo is in a clean state on a fresh feature branch",),
        rollback_plan=_rollback_for(intent),
        owner_gates=route.owner_gates,
        model_lane_hint=route.model_lane_hint.value,
        evidence_required=_evidence_for(intent),
        blocked=route.blocked,
    )


def _non_goals_for(intent: CodingIntent) -> tuple[str, ...]:
    base = (
        "no execution of owner-gated actions",
        "no edits outside allowed files",
        "no new heavyweight dependencies without justification",
    )
    if intent in (CodingIntent.RESEARCH, CodingIntent.AUDIT, CodingIntent.REVIEW):
        return ("no code changes — read-only lane",) + base
    return base


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


_WRITE_INTENTS = {
    CodingIntent.IMPLEMENT,
    CodingIntent.REFACTOR,
    CodingIntent.TEST,
    CodingIntent.DOCUMENT,
    CodingIntent.MEMORY,
    CodingIntent.MODEL_ROUTING,
    CodingIntent.ANDROID,
    CodingIntent.AVATAR_PRESENCE,
    CodingIntent.SECURITY,
    CodingIntent.RELEASE,
}

_UNSAFE_BRANCH = re.compile(r"[^A-Za-z0-9._/\-]")


def validate_work_packet(packet: CodingWorkPacket) -> PacketValidationResult:
    findings: list[PacketValidationFinding] = []

    def err(f: str, m: str) -> None:
        findings.append(PacketValidationFinding(f, "error", m))

    def warn(f: str, m: str) -> None:
        findings.append(PacketValidationFinding(f, "warning", m))

    is_write = packet.intent in _WRITE_INTENTS

    if not packet.mission.strip():
        err("mission", "mission is empty")

    # Branch safety.
    branch = packet.branch or ""
    if not branch:
        err("branch", "branch is missing")
    elif _UNSAFE_BRANCH.search(branch):
        err("branch", f"branch has unsafe characters: {branch!r}")
    if (
        branch in ("main", "master")
        or branch.endswith("/main")
        or branch.endswith("/master")
    ):
        err("branch", "branch targets main/master directly")

    if not packet.acceptance_criteria:
        err("acceptance_criteria", "acceptance criteria missing")
    if not packet.verification_plan:
        err("verification_plan", "verification plan missing")

    if is_write:
        if not packet.allowed_files:
            err("allowed_files", "allowed_files empty for a write intent")
        if not packet.rollback_plan:
            err("rollback_plan", "rollback plan missing for a write intent")

    # Builder/reviewer separation for RC2+.
    rc_order = {"RC0": 0, "RC1": 1, "RC2": 2, "RC3": 3, "RC4": 4}
    rc = rc_order.get(packet.risk_class, 1)
    if rc >= 2 and packet.primary_worker == packet.reviewer_worker:
        err("reviewer_worker", "builder and reviewer must differ for RC2+ changes")

    # Owner gates present but risk too low.
    if packet.owner_gates and rc < 3:
        err("risk_class", "owner-gated actions present but risk class below RC3")

    # Forbidden/allowed overlap.
    overlap = set(packet.forbidden_files) & set(packet.allowed_files)
    if overlap:
        err(
            "forbidden_files",
            f"forbidden files overlap allowed files: {sorted(overlap)}",
        )

    if packet.blocked or packet.risk_class == "RC4":
        err(
            "blocked",
            "request is blocked (bypass-gate / exfiltration / harmful) — plan only",
        )

    ok = not any(f.severity == "error" for f in findings)
    return PacketValidationResult(ok=ok, findings=tuple(findings))


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------


def render_packet_markdown(packet: CodingWorkPacket) -> str:
    def bullets(items: Sequence[str]) -> str:
        return "\n".join(f"- {i}" for i in items) if items else "- (none)"

    gate_lines = (
        "\n".join(f"- {g.value}" for g in packet.owner_gates)
        if packet.owner_gates
        else "- (none)"
    )
    blocked_note = (
        "\n> ⛔ **BLOCKED** — this request cannot be executed; it is a plan/review packet only.\n"
        if packet.blocked
        else ""
    )

    return f"""# Work Packet — {packet.intent.value}
{blocked_note}
**Mission:** {packet.mission}

**Risk class:** {packet.risk_class}  ·  **Branch:** `{packet.branch}`  ·  **Repo root:** `{packet.repo_root}`

**Workers:** builder=`{packet.primary_worker}`, reviewer=`{packet.reviewer_worker}`  ·  **Model lane:** {packet.model_lane_hint}

## Allowed files
{bullets(packet.allowed_files)}

## Forbidden files
{bullets(packet.forbidden_files)}

## Non-goals
{bullets(packet.non_goals)}

## Assumptions
{bullets(packet.assumptions)}

## Acceptance criteria
{bullets(packet.acceptance_criteria)}

## Verification plan
{bullets(packet.verification_plan)}

## Rollback plan
{bullets(packet.rollback_plan)}

## Owner gates
{gate_lines}

## Evidence required
{bullets(packet.evidence_required)}

_generated_at: {packet.generated_at}_
"""
