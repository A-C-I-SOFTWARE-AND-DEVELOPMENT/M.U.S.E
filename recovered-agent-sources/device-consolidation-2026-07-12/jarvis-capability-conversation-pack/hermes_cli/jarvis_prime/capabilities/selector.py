"""Auto-routing selector for JARVIS Prime.

Given a :class:`UserRequest` and a loaded :class:`CapabilityGraph` the
selector emits a :class:`RouteDecision`. The selector follows the rules
laid out in ``skills/jarvis-prime/SKILL.md`` and the operating registry
policies:

- Jarvis is one visible assistant; the selector does not activate
  hundreds of agents.
- The smallest capable route wins. Casual conversation routes to nothing.
- The AOS council is only added when the request needs multi-perspective
  judgment.
- Personas influence tone but never appear in ``selected_workers`` or
  ``selected_council``.
- Product roles represent viewpoints; they never execute.
- Workers execute but never decide; the selector adds a worker only when
  there is an execution lane (build, audit, migration, etc.).
- The council size is bounded by the registry policy
  (``default_slack_council_max``, default 6).

The selector is intentionally deterministic and keyword-driven. The goal
is not perfect NLP; it is to remove the activation phrase requirement
and emit a defensible route that the route explainer can render.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from hermes_cli.jarvis_prime.capabilities.graph import CapabilityGraph
from hermes_cli.jarvis_prime.capabilities.schemas import (
    Capability,
    CapabilityType,
    Intent,
    RiskLevel,
    RouteDecision,
    Surface,
    UserRequest,
)


_COUNCIL_MAX_DEFAULT = 6


@dataclass(frozen=True)
class _SignalMatch:
    """Tracks why a capability was selected (used to build rationale)."""

    capability_id: str
    reason: str


class CapabilitySelector:
    """Decide which capabilities should participate in a route."""

    def __init__(self, graph: CapabilityGraph, council_max: int = _COUNCIL_MAX_DEFAULT) -> None:
        self._graph = graph
        self._council_max = max(1, int(council_max))

    # ------------------------------------------------------------------

    def select(self, request: UserRequest) -> RouteDecision:
        text_lc = request.text.lower().strip()

        intent = self._classify_intent(text_lc)
        domain = self._detect_domain(text_lc)
        risk = self._assess_risk(text_lc, intent, domain)
        defer_heavy = request.surface == Surface.MOBILE_VOICE

        rationale: list[str] = []
        confidence = 0.45  # start neutral; bump as we add signals

        selected_skills: list[str] = []
        selected_council: list[str] = []
        selected_specialists: list[str] = []
        selected_workers: list[str] = []
        selected_memory: list[str] = []

        # --- domain specialists (highest signal, always considered first) ---
        for cap, why in self._select_specialists(text_lc, intent, domain):
            selected_specialists.append(cap.id)
            rationale.append(f"specialist {cap.id}: {why}")
            confidence += 0.1

        # --- skills (procedural know-how) -----------------------------------
        for cap, why in self._select_skills(text_lc, intent, domain):
            if cap.id not in selected_skills:
                selected_skills.append(cap.id)
                rationale.append(f"skill {cap.id}: {why}")
                confidence += 0.05

        # --- workers (execution lanes) --------------------------------------
        for cap, why in self._select_workers(text_lc, intent):
            if cap.id not in selected_workers:
                selected_workers.append(cap.id)
                rationale.append(f"worker {cap.id}: {why}")
                confidence += 0.05

        # --- council (multi-perspective judgment) ---------------------------
        if self._needs_council(text_lc, intent, risk, selected_specialists, selected_workers):
            council, why = self._select_council(intent, risk)
            selected_council.extend(council)
            rationale.append(why)
            confidence += 0.05
        elif intent == Intent.CASUAL:
            rationale.append("casual talk: no council activation")

        # --- memory hooks ---------------------------------------------------
        if intent in {Intent.PLANNING, Intent.BUILD, Intent.LAUNCH_READINESS}:
            selected_memory.append("durable-preferences")
        if intent in {Intent.REVIEW_OR_AUDIT, Intent.LAUNCH_READINESS}:
            selected_memory.append("project-conventions")
        if selected_memory:
            rationale.append("memory: hook " + ", ".join(selected_memory))

        # --- persona / product role overlays (never workers/agents) --------
        persona_influence = [p.id for p in self._graph.personas]
        product_role_viewpoints = [r.id for r in self._graph.product_roles]
        if intent == Intent.DOMAIN_REVIEW and persona_influence:
            rationale.append("personas overlay tone only, no execution")
        if product_role_viewpoints and intent in {Intent.LAUNCH_READINESS, Intent.DOMAIN_REVIEW}:
            rationale.append("product roles surface stakeholder viewpoints, not execution")

        # --- owner gate -----------------------------------------------------
        owner_gate_required = (
            risk == RiskLevel.HIGH
            or any(self._is_owner_gated(s) for s in selected_specialists)
            or intent == Intent.LAUNCH_READINESS
        )
        if owner_gate_required:
            rationale.append("owner gate: required before execution")

        # --- mobile voice defer --------------------------------------------
        if defer_heavy:
            rationale.append("mobile voice: defer heavy output until focused mode")

        # --- enforce council max -------------------------------------------
        if len(selected_council) > self._council_max:
            selected_council = selected_council[: self._council_max]
            rationale.append(f"council capped at {self._council_max} per registry policy")

        # --- confidence floor / ceiling ------------------------------------
        confidence = max(0.1, min(0.99, confidence))

        return RouteDecision(
            intent=intent,
            domain=domain,
            risk=risk,
            surface=request.surface,
            selected_skills=selected_skills,
            selected_council=selected_council,
            selected_specialists=selected_specialists,
            selected_workers=selected_workers,
            selected_memory=selected_memory,
            persona_influence=persona_influence,
            product_role_viewpoints=product_role_viewpoints,
            owner_gate_required=owner_gate_required,
            defer_heavy_output=defer_heavy,
            rationale=rationale,
            confidence=round(confidence, 2),
        )

    # ------------------------------------------------------------------
    # intent / domain / risk classification
    # ------------------------------------------------------------------

    _BUILD_PATTERNS = (
        r"\bbuild (this|a|the) ",
        r"\bimplement ",
        r"\bship (this|the) ",
        r"\badd (a|the) feature",
        r"\bcode (this|the) ",
        r"\brefactor ",
        r"\bmigrate ",
    )

    _AUDIT_PATTERNS = (
        r"\baudit (this|the|our|my) ",
        r"\breview (this|the) repo",
        r"\bsecurity review",
        r"\bcompliance review",
    )

    _LAUNCH_PATTERNS = (
        r"\bis (this|it) (launch|release) ready",
        r"\blaunch readiness",
        r"\brelease readiness",
        r"\bgo[-/ ]?no[-/ ]?go",
        r"\bready (to|for) (ship|launch|release)",
        r"\bpilot readiness",
    )

    _PLAN_PATTERNS = (
        r"\bplan (this|the|a) ",
        r"\bdesign (this|the|a) ",
        r"\bhow should we ",
        r"\broadmap",
        r"\bstrategy ",
    )

    _CASUAL_PATTERNS = (
        r"^(hi|hey|hello|yo|sup|morning|good morning|good evening)\b",
        r"\bhow are you\b",
        r"\bwhat'?s up\b",
        r"\bthanks?\b",
        r"\bthank you\b",
    )

    _DOMAIN_PATTERNS: tuple[tuple[str, str], ...] = (
        ("regulated hazmat", r"\bhaz[ -]?mat\b|\bdangerous goods\b|\bplacard\b|\berg\b|\b49 cfr\b|\btdg\b"),
        ("nutrition product", r"\bnourish\b|\bnutrition\b|\bmeal plan\b|\bnutrient\b|\bcalorie\b"),
        ("psychology and UX", r"\bux\b|\bonboarding\b|\bfriction\b|\bbehavior\b|\bmotivation\b"),
        ("security", r"\bauthz?\b|\bsecrets?\b|\boauth\b|\bjwt\b|\bcsrf\b|\bvulnerab\w+\b|\binjection\b"),
        ("architecture", r"\barchitecture\b|\bscaling\b|\bdata model\b|\bservice boundary\b"),
        ("research", r"\bcitation\b|\bevidence\b|\bsource\b|\bcompetitor\b|\bmarket\b"),
        ("business", r"\bpricing\b|\bpackaging\b|\bgo[- ]to[- ]market\b|\bsales\b|\bmonetiz\w+\b"),
        ("release", r"\brelease\b|\blaunch\b|\bship\b|\bdeploy\b|\bproduction\b"),
    )

    def _classify_intent(self, text: str) -> Intent:
        if not text:
            return Intent.UNKNOWN
        if _matches_any(text, self._LAUNCH_PATTERNS):
            return Intent.LAUNCH_READINESS
        if _matches_any(text, self._AUDIT_PATTERNS):
            return Intent.REVIEW_OR_AUDIT
        if _matches_any(text, self._BUILD_PATTERNS):
            return Intent.BUILD
        if _matches_any(text, self._PLAN_PATTERNS):
            return Intent.PLANNING
        if _matches_any(text, self._CASUAL_PATTERNS):
            return Intent.CASUAL
        # Domain-specific words without a verb still imply a domain review.
        for _, pattern in self._DOMAIN_PATTERNS:
            if re.search(pattern, text):
                return Intent.DOMAIN_REVIEW
        if "?" in text or text.startswith("what") or text.startswith("why") or text.startswith("how"):
            return Intent.QUESTION
        return Intent.UNKNOWN

    def _detect_domain(self, text: str) -> Optional[str]:
        for name, pattern in self._DOMAIN_PATTERNS:
            if re.search(pattern, text):
                return name
        return None

    def _assess_risk(self, text: str, intent: Intent, domain: Optional[str]) -> RiskLevel:
        if intent == Intent.LAUNCH_READINESS:
            return RiskLevel.HIGH
        if domain in {"regulated hazmat", "security"}:
            return RiskLevel.HIGH
        if intent in {Intent.REVIEW_OR_AUDIT, Intent.BUILD}:
            return RiskLevel.MEDIUM
        if intent in {Intent.CASUAL, Intent.QUESTION, Intent.UNKNOWN}:
            return RiskLevel.LOW
        return RiskLevel.MEDIUM

    # ------------------------------------------------------------------
    # capability selection
    # ------------------------------------------------------------------

    def _select_specialists(
        self,
        text: str,
        intent: Intent,
        domain: Optional[str],
    ) -> list[tuple[Capability, str]]:
        out: list[tuple[Capability, str]] = []
        specialists = self._graph.domain_specialists

        # Direct domain match wins first.
        for spec in specialists:
            if spec.domain and domain and spec.domain == domain:
                out.append((spec, f"matches domain {domain!r}"))

        # Launch readiness always brings the release judge.
        if intent == Intent.LAUNCH_READINESS:
            for spec in specialists:
                if spec.domain == "release" and not any(s.id == spec.id for s, _ in out):
                    out.append((spec, "launch-readiness intent"))

        # Nourish requests want both nutrition and UX advisors per
        # docs/jarvis-prime-operating-system.md.
        if domain == "nutrition product":
            for spec in specialists:
                if spec.domain == "psychology and UX" and not any(s.id == spec.id for s, _ in out):
                    out.append((spec, "nutrition flow benefits from UX review"))

        return out

    def _select_skills(
        self,
        text: str,
        intent: Intent,
        domain: Optional[str],
    ) -> list[tuple[Capability, str]]:
        out: list[tuple[Capability, str]] = []
        skills = self._graph.skills

        # Helper: lookup by id with a fallback no-op when the skill isn't loaded.
        def _add(skill_id: str, reason: str) -> None:
            cap = self._graph.get(skill_id)
            if cap is None or cap.type != CapabilityType.SKILL:
                return
            if not any(c.id == cap.id for c, _ in out):
                out.append((cap, reason))

        if intent == Intent.LAUNCH_READINESS:
            _add("pilot-readiness", "release/risk/evidence path for launch readiness")
            _add("pr-readiness-handoff", "owner handoff before release")
        if intent == Intent.REVIEW_OR_AUDIT:
            _add("post-merge-verification", "audit workflow")
            _add("bug-fix-protocol", "audit may surface bugs")
        if intent == Intent.BUILD:
            _add("bug-fix-protocol", "build work needs evidence-first guardrails")
        if domain == "regulated hazmat":
            _add("hazmat-citation-check", "hazmat claim requires cited sources")
        if domain == "security":
            _add("security-authz-change", "security work routes through authz skill")
            _add("threat-modeling", "security-sensitive change benefits from a threat model")
        if domain == "business":
            _add("pricing-study", "pricing-related intent")
        if domain == "research":
            _add("research-dossier", "research request")
            _add("claims-substantiation", "claims need substantiation")
        if intent == Intent.PLANNING:
            _add("claims-substantiation", "plans referencing claims must be substantiated")
        # Always anchor on the jarvis-prime skill so the persona is loaded
        # when the runtime is invoked from outside the CLI (Slack, mobile).
        _add("jarvis-prime", "anchor: jarvis-prime governs intake and handoff")
        return out

    def _select_workers(
        self,
        text: str,
        intent: Intent,
    ) -> list[tuple[Capability, str]]:
        out: list[tuple[Capability, str]] = []

        def _add(worker_id: str, reason: str) -> None:
            cap = self._graph.get(worker_id)
            if cap is None or cap.type != CapabilityType.WORKER:
                return
            if not any(c.id == cap.id for c, _ in out):
                out.append((cap, reason))

        if intent == Intent.BUILD:
            _add("claude-code-worker", "primary builder lane for build intent")
            _add("test-verification-worker", "build requires evidence")
        if intent == Intent.REVIEW_OR_AUDIT:
            _add("repo-audit-worker", "audit intent has a dedicated worker")
        if intent == Intent.LAUNCH_READINESS:
            _add("test-verification-worker", "launch readiness collects test evidence")
        if intent == Intent.PLANNING and "migrat" in text:
            _add("migration-worker", "migration planning has an execution lane")
        return out

    # ------------------------------------------------------------------
    # council
    # ------------------------------------------------------------------

    def _needs_council(
        self,
        text: str,
        intent: Intent,
        risk: RiskLevel,
        specialists: list[str],
        workers: list[str],
    ) -> bool:
        if intent == Intent.CASUAL:
            return False
        if intent in {Intent.LAUNCH_READINESS, Intent.REVIEW_OR_AUDIT}:
            return True
        if risk == RiskLevel.HIGH:
            return True
        if intent in {Intent.PLANNING, Intent.DOMAIN_REVIEW} and len(specialists) >= 2:
            return True
        return False

    _COUNCIL_BY_INTENT: dict[Intent, tuple[str, ...]] = {
        Intent.LAUNCH_READINESS: (
            "council-director",
            "evidence-architect",
            "assurance-risk-director",
            "delivery-scope-controller",
            "contrarian-reviewer",
        ),
        Intent.REVIEW_OR_AUDIT: (
            "council-director",
            "evidence-architect",
            "assurance-risk-director",
            "contrarian-reviewer",
        ),
        Intent.PLANNING: (
            "council-director",
            "evidence-architect",
            "delivery-scope-controller",
            "product-experience-architect",
        ),
        Intent.DOMAIN_REVIEW: (
            "council-director",
            "product-experience-architect",
            "evidence-architect",
        ),
    }

    def _select_council(
        self,
        intent: Intent,
        risk: RiskLevel,
    ) -> tuple[list[str], str]:
        wanted = list(self._COUNCIL_BY_INTENT.get(intent, ("council-director",)))
        # Always include the contrarian for HIGH risk.
        if risk == RiskLevel.HIGH and "contrarian-reviewer" not in wanted:
            wanted.append("contrarian-reviewer")
        # Filter to what the graph actually contains and respect the council cap.
        present_ids = {c.id for c in self._graph.runnable_council}
        filtered = [w for w in wanted if w in present_ids]
        if not filtered:
            return [], "council requested but no runnable agents indexed"
        return filtered[: self._council_max], (
            f"council: {len(filtered)} members for {intent.value} (max {self._council_max})"
        )

    # ------------------------------------------------------------------
    # introspection helpers
    # ------------------------------------------------------------------

    def _is_owner_gated(self, capability_id: str) -> bool:
        cap = self._graph.get(capability_id)
        return bool(cap and cap.owner_gate_required)


def _matches_any(text: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(p, text) for p in patterns)


__all__ = ["CapabilitySelector"]
