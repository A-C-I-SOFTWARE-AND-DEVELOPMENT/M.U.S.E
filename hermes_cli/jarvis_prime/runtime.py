"""JARVIS Prime orchestrator runtime.

Ties persona + modes + awareness + gates + owner-auth + router into
a single ``JarvisPrime`` class. One turn of JARVIS Prime is:

    perceive → classify → decide → gate → delegate → speak

Each step is independently testable. The runtime is stdlib-only at
import time; LLM dispatch (model_router) and council delegation
(orchestrator job spawn) are lazy-imported inside ``delegate()`` so
the package loads in minimal environments.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping, Optional

from hermes_cli.jarvis_prime.awareness import (
    AwarenessSnapshot,
    perceive as _perceive,
)
from hermes_cli.jarvis_prime.epistemics import (
    AuditOutcome,
    AuditReport,
    audit_response,
)
from hermes_cli.jarvis_prime.gates import (
    GateOutcome,
    GateSummary,
    run_gate_summary,
)
from hermes_cli.jarvis_prime.memory import MemoryStore
from hermes_cli.jarvis_prime.memory_tree import MemoryTreeStore
from hermes_cli.jarvis_prime.modes import (
    ClassifierContext,
    Mode,
    ModeClassification,
    ModeClassifier,
)
from hermes_cli.jarvis_prime.owner_auth import OwnerAuth
from hermes_cli.jarvis_prime.persona import Persona, PersonaPrompt
from hermes_cli.jarvis_prime.reasoning import Inference, Reasoner
from hermes_cli.jarvis_prime.research import (
    ResearchBrief,
    ResearchQuestion,
    needs_research,
    open_brief,
)
from hermes_cli.jarvis_prime.router import RouteDecision, RouteTarget, Router
from hermes_cli.jarvis_prime.self_update import ProposalBook


def _memory_layers_default() -> bool:
    """Memory Tree live-loop wiring defaults ON; ``HERMES_MEMORY_LAYERS=0``
    (or false/no/off) reverts to legacy-only recollection for an exact
    rollback path."""

    raw = os.environ.get("HERMES_MEMORY_LAYERS")
    if raw is None:
        return True
    return raw.strip().lower() not in ("0", "false", "no", "off", "")


@dataclass
class JarvisConfig:
    persona: Persona = field(default_factory=Persona)
    classifier: ModeClassifier = field(default_factory=ModeClassifier)
    router: Router = field(default_factory=Router)
    owner_auth: OwnerAuth = field(default_factory=OwnerAuth)
    memory: MemoryStore = field(default_factory=MemoryStore)
    reasoner: Reasoner = field(default_factory=Reasoner)
    proposals: ProposalBook = field(default_factory=ProposalBook)
    confidence_floor: float = 0.65
    proactive_tick_enabled: bool = False
    briefing_window: str = "08:00 America/Toronto"
    notify_via: str = "none"  # "telegram" | "slack" | "email" | "none"
    # Memory Tree (MEM-2) live-loop wiring. ``memory_tree`` is lazily loaded
    # from the HERMES_HOME-aware default path on first use when None.
    memory_layers_enabled: bool = field(default_factory=_memory_layers_default)
    memory_tree: Optional[MemoryTreeStore] = None
    memory_token_budget: int = 512


@dataclass
class JarvisTurn:
    """One end-to-end turn of JARVIS Prime."""

    intent: str
    awareness: AwarenessSnapshot
    classification: ModeClassification
    persona_prompt: PersonaPrompt
    route: RouteDecision
    gate_summary: Optional[GateSummary]
    started_at: datetime
    finished_at: datetime
    recollection: str = ""
    research_brief: Optional[ResearchBrief] = None
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent": self.intent,
            "awareness": self.awareness.to_dict(),
            "classification": self.classification.to_dict(),
            "persona_prompt": self.persona_prompt.render(),
            "route": self.route.to_dict(),
            "gate_summary": self.gate_summary.to_dict() if self.gate_summary else None,
            "recollection": self.recollection,
            "research_brief": self.research_brief.to_dict() if self.research_brief else None,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat(),
            "notes": list(self.notes),
        }


class JarvisPrime:
    """The apex AI persona for Hermes Agent.

    Use directly:

        jp = JarvisPrime()
        turn = jp.handle("audit this repo")
        print(turn.persona_prompt.render())
        print(turn.route.rationale)

    Or wire into a gateway: see ``hermes_cli/main.py`` slash-command
    registration for the canonical activation path.
    """

    def __init__(self, config: Optional[JarvisConfig] = None) -> None:
        self.config = config or JarvisConfig()

    # ------------------------------------------------------------------
    # Perception
    # ------------------------------------------------------------------

    def perceive(self, timeout: float = 2.0) -> AwarenessSnapshot:
        return _perceive(timeout=timeout)

    # ------------------------------------------------------------------
    # Classification
    # ------------------------------------------------------------------

    def classify(
        self,
        intent: str,
        context: Optional[ClassifierContext] = None,
    ) -> ModeClassification:
        return self.config.classifier.classify(intent, context)

    # ------------------------------------------------------------------
    # Persona prompt
    # ------------------------------------------------------------------

    def build_prompt(
        self,
        mode: Mode,
        awareness: Optional[AwarenessSnapshot] = None,
        recollection_block: str = "",
    ) -> PersonaPrompt:
        return self.config.persona.build(
            mode=mode, awareness=awareness, recollection_block=recollection_block
        )

    # ------------------------------------------------------------------
    # Memory + recollection
    # ------------------------------------------------------------------

    def memory_tree(self) -> Optional[MemoryTreeStore]:
        """The live Memory Tree store (lazy-loaded), or None when layers off."""

        if not self.config.memory_layers_enabled:
            return None
        if self.config.memory_tree is None:
            try:
                self.config.memory_tree = MemoryTreeStore.load()
            except Exception:  # pragma: no cover - defensive (corrupt store)
                return None
        return self.config.memory_tree

    def recollect(self, query: str, limit: int = 5) -> str:
        """Recall relevant memory for the persona prompt.

        Augments — never replaces — the legacy flat ``MemoryStore`` block with
        a token-bounded, source-cited Memory Tree context pack. Contested facts
        and candidates still awaiting the owner's review gate (session/working
        PROPOSED captures from ``observe_turn``) are excluded by the pack, so an
        unreviewed memory can never steer a response. When memory layers are
        disabled the output is byte-identical to the legacy recollection.
        """

        legacy = self.config.memory.summarize_for_prompt(query, limit=limit)
        tree = self.memory_tree()
        if tree is None:
            return legacy
        try:
            pack = tree.context_pack(query, self.config.memory_token_budget)
        except Exception:  # pragma: no cover - defensive
            return legacy
        if not pack.sections:
            return legacy
        tree_block = pack.render()
        return f"{legacy}\n\n{tree_block}" if legacy else tree_block

    def observe_turn(
        self,
        user_text: str,
        assistant_text: str = "",
        *,
        source_uri: Optional[str] = None,
    ) -> dict[str, Any]:
        """Capture typed memory candidates after a completed turn.

        Best-effort and side-effect-bounded: candidates are written to the
        Memory Tree as **session-layer, PROPOSED** nodes (never auto-durable —
        owner promotes via ``promote_to_durable``). Secret / chain-of-thought
        content is rejected by the write policy. Never raises.

        Returns a small summary: ``{"captured": n, "rejected": m,
        "durable_worthy": k}`` (all zero when layers are disabled).
        """

        summary = {"captured": 0, "rejected": 0, "durable_worthy": 0}
        tree = self.memory_tree()
        if tree is None:
            return summary
        try:
            from hermes_cli.jarvis_prime.memory_capture import (
                capture_to_tree,
                extract_candidates,
            )

            candidates = extract_candidates(
                user_text, assistant_text, source_uri=source_uri
            )
            results = capture_to_tree(tree, candidates)
            for cand, result in zip(candidates, results):
                if result.ok:
                    summary["captured"] += 1
                    if cand.durable_worthy:
                        summary["durable_worthy"] += 1
                else:
                    summary["rejected"] += 1
        except Exception:  # pragma: no cover - capture never breaks a turn
            return summary
        return summary

    def remember(
        self,
        key: str,
        value: str,
        durability: str = "session",
        confidence: float = 1.0,
    ) -> None:
        self.config.memory.remember(
            key=key, value=value, durability=durability, confidence=confidence
        )

    # ------------------------------------------------------------------
    # Audit / anti-hallucination
    # ------------------------------------------------------------------

    def audit(
        self,
        response: str,
        confidence: float = 1.0,
        citations: Optional[list[str]] = None,
    ) -> AuditReport:
        return audit_response(
            response,
            provided_citations=citations,
            confidence=confidence,
            confidence_floor=self.config.confidence_floor,
        )

    # ------------------------------------------------------------------
    # Routing decision
    # ------------------------------------------------------------------

    def decide(
        self,
        mode: Mode,
        intent: str,
        awareness: Optional[AwarenessSnapshot] = None,
        risk_class: str = "RC1",
    ) -> RouteDecision:
        pending = tuple(self.config.owner_auth.pending_actions())
        return self.config.router.route(
            mode=mode,
            intent=intent,
            awareness=awareness,
            risk_class=risk_class,
            pending_owner_actions=pending,
        )

    # ------------------------------------------------------------------
    # Gate evaluation
    # ------------------------------------------------------------------

    def gate(self, packet: Mapping[str, Any]) -> GateSummary:
        return run_gate_summary(packet)

    # ------------------------------------------------------------------
    # Owner authorization
    # ------------------------------------------------------------------

    def authorize(self, phrase: str, action: Optional[str] = None) -> list[str]:
        granted = self.config.owner_auth.authorize(phrase, action=action)
        return [g.action for g in granted]

    # ------------------------------------------------------------------
    # Delegation — surface only; actual dispatch happens elsewhere.
    # ------------------------------------------------------------------

    def delegate(
        self,
        route: RouteDecision,
        packet: Optional[Mapping[str, Any]] = None,
    ) -> dict[str, Any]:
        """Produce the delegation envelope for downstream execution.

        Does NOT itself dispatch — returns a dict the caller hands to
        the orchestrator / model_router. Keeps this module side-effect-
        free for testing.
        """

        envelope: dict[str, Any] = {
            "target": route.target.value,
            "delegate_to": route.delegate_to,
            "rationale": route.rationale,
            "council_questions": list(route.council_questions),
            "packet": dict(packet) if packet else {},
            "requires_owner_authorization": route.requires_owner_authorization,
            "pending_actions": list(route.pending_actions),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Optional: pass model-router hint when the existing router is
        # available — kept best-effort so missing module doesn't break.
        try:
            from hermes_cli import model_router as _mr

            if route.target in (
                RouteTarget.AOS_COUNCIL,
                RouteTarget.CLAUDE_CODE_BUILDER,
                RouteTarget.CODEX_REVIEWER,
                RouteTarget.CODEX_BOUNDED_FIX,
            ):
                envelope["model_router_hint"] = {
                    "implementation": getattr(_mr, "PREFERRED_IMPLEMENTATION", "claude-code"),
                    "review": getattr(_mr, "PREFERRED_REVIEW", "codex"),
                }
        except Exception:  # pragma: no cover - optional
            pass

        return envelope

    # ------------------------------------------------------------------
    # Top-level handle
    # ------------------------------------------------------------------

    def handle(
        self,
        intent: str,
        context: Optional[ClassifierContext] = None,
        packet: Optional[Mapping[str, Any]] = None,
        skip_perceive: bool = False,
        skip_recollect: bool = False,
    ) -> JarvisTurn:
        """Full turn: perceive → recollect → classify → decide → gate.

        The recollection step pulls relevant durable + session memory
        and stuffs it into the persona prompt. The decide step
        triggers a ResearchBrief when classification confidence is
        below the floor AND there are no memory hits — JARVIS chooses
        research over guessing.
        """

        started = datetime.now(timezone.utc)
        awareness = AwarenessSnapshot() if skip_perceive else self.perceive()
        recollection = "" if skip_recollect else self.recollect(intent)
        classification = self.classify(intent, context=context)

        persona_prompt = self.build_prompt(
            classification.mode, awareness=awareness, recollection_block=recollection
        )
        route = self.decide(
            mode=classification.mode,
            intent=intent,
            awareness=awareness,
            risk_class=getattr(context, "risk_class", None) or "RC1",
        )

        # Open a ResearchBrief if confidence is too low and we have no
        # recollection — JARVIS escalates to research rather than guessing.
        research_brief: Optional[ResearchBrief] = None
        recollection_hits = len(recollection.splitlines()) - 1 if recollection else 0
        trigger = needs_research(
            confidence=classification.confidence,
            recollection_hits=max(0, recollection_hits),
            has_matching_rule=False,
            is_code_question=("def " in intent or "class " in intent or "code" in intent.lower()),
            confidence_floor=self.config.confidence_floor,
        )
        if trigger is not None:
            research_brief = open_brief(
                topic=intent[:120],
                triggered_by=trigger,
                questions=(
                    ResearchQuestion(
                        text=f"What is the user actually asking about: {intent[:140]}?",
                        why_it_matters="prevent hallucination on an unfamiliar topic",
                    ),
                    ResearchQuestion(
                        text="What evidence (file paths, docs, citations) supports the answer?",
                        why_it_matters="every claim must be cited per the epistemic rule",
                    ),
                ),
            )

        gate_summary = self.gate(packet) if packet else None
        finished = datetime.now(timezone.utc)
        return JarvisTurn(
            intent=intent,
            awareness=awareness,
            classification=classification,
            persona_prompt=persona_prompt,
            route=route,
            gate_summary=gate_summary,
            recollection=recollection,
            research_brief=research_brief,
            started_at=started,
            finished_at=finished,
        )

    # ------------------------------------------------------------------
    # Emergency stop — clear pending owner gates and disable autonomy
    # ------------------------------------------------------------------

    def stop(self, reason: str = "owner_requested") -> dict[str, Any]:
        """Emergency-stop primitive.

        Clears every pending owner-gate, disables the proactive tick, and
        journals a STOP record to session memory so any later audit
        of this process knows it was halted.

        Returns a small JSON-serialisable dict (used by the CLI
        ``stop`` subcommand and any UI surface).
        """

        pending = list(self.config.owner_auth.pending)
        cleared = len(pending)
        self.config.owner_auth.pending = []
        self.config.proactive_tick_enabled = False
        # Release every worker branch lease so a halted JARVIS never leaves
        # Claude Code / Codex holding a branch they can no longer act on.
        leases_cleared = 0
        try:
            from hermes_cli.jarvis_prime import worker_locks as _wl

            leases_cleared = _wl.clear_all_leases()
        except Exception:  # pragma: no cover - defensive
            pass
        try:
            self.config.memory.remember(
                key="emergency_stop",
                value=reason,
                durability="session",
                source="system",
                tags=("emergency_stop",),
            )
        except Exception:  # pragma: no cover - defensive
            pass
        return {
            "cleared": cleared,
            "tick_disabled": True,
            "reason": reason,
            "cleared_actions": [g.action for g in pending],
            "branch_leases_cleared": leases_cleared,
        }

    # ------------------------------------------------------------------
    # Handoff rendering — operational handoff template
    # ------------------------------------------------------------------

    @staticmethod
    def render_handoff(turn: JarvisTurn, result: str = "", next_step: str = "") -> str:
        actions = (
            f"classified={turn.classification.mode.value}; "
            f"routed={turn.route.target.value}"
        )
        if turn.route.delegate_to:
            actions += f" → {turn.route.delegate_to}"
        verification = (
            turn.gate_summary.render().splitlines()[-2:][0]
            if turn.gate_summary
            else "no work packet provided"
        )
        owner_gates = (
            ", ".join(turn.route.pending_actions) or "none pending"
        )
        return (
            f"Mission: {turn.intent}\n"
            f"Route selected: {turn.route.target.value}\n"
            f"Actions taken: {actions}\n"
            f"Verification: {verification}\n"
            f"Owner gates: {owner_gates}\n"
            f"Result: {result or 'see route'}\n"
            f"Next step: {next_step or turn.route.rationale}"
        )
