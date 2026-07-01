"""Intent routing for muse

Honors the routing hierarchy from
``docs/jarvis-prime-operating-system.md``:

1. Jeremiah owns final judgment.
2. muse owns intake, challenge, routing, and handoff.
3. AOS Council owns multi-perspective judgment.
4. Domain specialists advise on bounded subject matter.
5. Skills encode repeatable procedures.
6. Workers execute bounded tasks and report evidence.
7. Personas simulate audiences or tone.
8. Product roles represent stakeholder needs.

The router takes a classified mode + intent + awareness and produces
a ``RouteDecision`` naming the next responsible target. Implementation
is deterministic and stdlib-only — the actual delegation happens
inside ``runtime.JarvisPrime.delegate``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from hermes_cli.jarvis_prime.awareness import AwarenessSnapshot
    from hermes_cli.jarvis_prime.modes import Mode


class RouteTarget(Enum):
    DIRECT_ANSWER = "direct_answer"
    AOS_COUNCIL = "aos_council"
    SPECIALIST = "specialist"
    SKILL = "skill"
    CLAUDE_CODE_BUILDER = "claude_code_builder"
    CODEX_REVIEWER = "codex_reviewer"
    CODEX_BOUNDED_FIX = "codex_bounded_fix"
    LOCAL_TEST_RUNNER = "local_test_runner"
    GITHUB_PR_PUBLISHER = "github_pr_publisher"
    OWNER_DECISION = "owner_decision"
    DEFER_TO_FOCUSED_MODE = "defer_to_focused_mode"


_COUNCIL_TRIGGERS: tuple[str, ...] = (
    "architecture", "product strategy", "security review", "compliance",
    "release readiness", "contrarian review", "regulated", "major tradeoff",
)

_SPECIALIST_DOMAINS: dict[str, tuple[str, ...]] = {
    "hazmat-command-specialist": (
        "49 cfr", "tdg", "erg", "placarding", "shipping papers",
        "hazmat", "ocr provenance", "driver/safety",
    ),
    "nourish-product-specialist": (
        "nutrition", "recipe", "meal logging", "behavior change",
        "food privacy", "nutrient math", "health claim",
    ),
    "logistics-specialist": (
        "trucking", "dispatch", "fleet", "terminal", "ltl",
        "carrier",
    ),
}


@dataclass(frozen=True)
class RouteDecision:
    target: RouteTarget
    rationale: str
    delegate_to: Optional[str] = None  # specialist or skill name
    council_questions: tuple[str, ...] = ()
    requires_owner_authorization: bool = False
    pending_actions: tuple[str, ...] = ()
    # Effort-class stamp (E0–E5), populated by ``Router.route``. Additive and
    # observational — it records the smallest-sufficient effort class for this
    # decision without altering which target/agents are dispatched. Stored as
    # the enum's string value (e.g. ``"E1"``) so the frozen dataclass stays
    # trivially serialisable; ``None`` only for decisions built outside the
    # router (e.g. hand-constructed test fixtures).
    effort_class: Optional[str] = None

    def to_dict(self) -> dict[str, object]:
        return {
            "target": self.target.value,
            "rationale": self.rationale,
            "delegate_to": self.delegate_to,
            "council_questions": list(self.council_questions),
            "requires_owner_authorization": self.requires_owner_authorization,
            "pending_actions": list(self.pending_actions),
            "effort_class": self.effort_class,
        }


@dataclass
class Router:
    """Map (mode, intent, awareness) → RouteDecision."""

    def route(
        self,
        mode: "Mode",
        intent: str,
        awareness: "Optional[AwarenessSnapshot]" = None,
        risk_class: str = "RC1",
        pending_owner_actions: tuple[str, ...] = (),
    ) -> RouteDecision:
        """Route to a target and stamp the smallest-sufficient effort class.

        The routing logic lives in :meth:`_route`; this wrapper is where the
        effort-class stamp is applied so *every* returned decision carries an
        ``effort_class`` unconditionally. Stamping is purely additive — it
        records the classification without changing the chosen target.
        """
        decision = self._route(
            mode=mode,
            intent=intent,
            awareness=awareness,
            risk_class=risk_class,
            pending_owner_actions=pending_owner_actions,
        )
        from dataclasses import replace

        from hermes_cli.jarvis_prime.effort_class import classify_effort

        return replace(decision, effort_class=classify_effort(decision).value)

    def _route(
        self,
        mode: "Mode",
        intent: str,
        awareness: "Optional[AwarenessSnapshot]" = None,
        risk_class: str = "RC1",
        pending_owner_actions: tuple[str, ...] = (),
    ) -> RouteDecision:
        from hermes_cli.jarvis_prime.modes import Mode as _Mode

        text = (intent or "").lower()

        if pending_owner_actions:
            return RouteDecision(
                target=RouteTarget.OWNER_DECISION,
                rationale="owner-gated actions pending authorization",
                requires_owner_authorization=True,
                pending_actions=pending_owner_actions,
            )

        if mode == _Mode.MOBILE_VOICE:
            return RouteDecision(
                target=RouteTarget.DEFER_TO_FOCUSED_MODE,
                rationale="mobile voice — capture short task packet; defer depth to focused mode",
            )

        if mode == _Mode.BUILDER:
            if any(
                k in text
                for k in (
                    "self-improve",
                    "self improve",
                    "improve yourself",
                    "improve your own",
                    "improve its own",
                    "improve jarvis",
                    "self-improvement",
                    "get better at",
                    "sia self",
                    # research-fabric / verifier-gated self-improvement intents
                    "research fabric",
                    "research-fabric",
                    "evolve",
                    "benchmark wall",
                    "autonomy charter",
                    "ratchet",
                    "op-count",
                    "verifier-gated",
                )
            ):
                return RouteDecision(
                    target=RouteTarget.SKILL,
                    rationale=(
                        "builder mode + self-improvement intent → research-fabric "
                        "skill (verifier-gated ratchet; sandboxed iteration with SIA; "
                        "auto-apply only inside an owner-signed charter, else proposal)"
                    ),
                    delegate_to="research-fabric",
                    requires_owner_authorization=True,
                )
            if any(k in text for k in ("review", "code review", "verdict", "second pass")):
                return RouteDecision(
                    target=RouteTarget.CODEX_REVIEWER,
                    rationale="builder mode + review intent → codex review packet",
                    delegate_to="codex-dispatch-governor",
                )
            if any(k in text for k in ("rollback", "revert")):
                return RouteDecision(
                    target=RouteTarget.CODEX_BOUNDED_FIX,
                    rationale="builder mode + rollback intent → codex bounded fix",
                    delegate_to="codex-dispatch-governor",
                )
            if "test" in text or "pytest" in text:
                return RouteDecision(
                    target=RouteTarget.LOCAL_TEST_RUNNER,
                    rationale="builder mode + test intent → local test runner",
                )
            if "pr" in text or "pull request" in text or "publish" in text:
                return RouteDecision(
                    target=RouteTarget.GITHUB_PR_PUBLISHER,
                    rationale="builder mode + PR/publish intent → github PR publisher (merge governed by LaunchGate)",
                )
            return RouteDecision(
                target=RouteTarget.CLAUDE_CODE_BUILDER,
                rationale="builder mode → claude code build packet",
                delegate_to="claude-code-builder",
            )

        if mode == _Mode.CRITIC:
            return RouteDecision(
                target=RouteTarget.SPECIALIST,
                rationale="critic mode → contrarian reviewer specialist",
                delegate_to="contrarian-reviewer",
            )

        if mode == _Mode.OPERATOR:
            for trigger in _COUNCIL_TRIGGERS:
                if trigger in text:
                    return RouteDecision(
                        target=RouteTarget.AOS_COUNCIL,
                        rationale=f"operator mode + council trigger '{trigger}'",
                        delegate_to="aos-council-director",
                        council_questions=(
                            "What is the smallest reviewable scope?",
                            "Who is the builder and who is the independent reviewer?",
                            "What is the rollback path?",
                        ),
                    )
            for specialist, keywords in _SPECIALIST_DOMAINS.items():
                if any(k in text for k in keywords):
                    return RouteDecision(
                        target=RouteTarget.SPECIALIST,
                        rationale=f"operator mode + specialist domain ({specialist})",
                        delegate_to=specialist,
                    )
            return RouteDecision(
                target=RouteTarget.DIRECT_ANSWER,
                rationale="operator mode, no council/specialist trigger — handle directly",
            )

        if mode == _Mode.STRATEGY:
            return RouteDecision(
                target=RouteTarget.AOS_COUNCIL,
                rationale="strategy mode → council for multi-perspective judgment",
                delegate_to="aos-council-director",
                council_questions=(
                    "What is the strategic tradeoff plainly named?",
                    "What is the highest-leverage path?",
                    "What should Jeremiah not do yet?",
                ),
            )

        # COMPANION mode — answer directly with empathy.
        return RouteDecision(
            target=RouteTarget.DIRECT_ANSWER,
            rationale="companion mode — direct, emotionally intelligent response",
        )
