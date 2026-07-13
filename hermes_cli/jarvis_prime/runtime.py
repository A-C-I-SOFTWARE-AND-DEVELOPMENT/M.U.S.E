"""muse orchestrator runtime.

Ties persona + modes + awareness + gates + owner-auth + router into
a single ``JarvisPrime`` class. One turn of muse is:

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


def _packet_get(packet: Mapping[str, Any], key: str, default: Any = None) -> Any:
    """Read ``key`` from a dict-like packet or a dataclass-like packet."""

    if isinstance(packet, Mapping):
        return packet.get(key, default)
    return getattr(packet, key, default)


def _memory_layers_default() -> bool:
    """Memory Tree live-loop wiring defaults ON; ``HERMES_MEMORY_LAYERS=0``
    (or false/no/off) reverts to legacy-only recollection for an exact
    rollback path."""

    raw = os.environ.get("HERMES_MEMORY_LAYERS")
    if raw is None:
        return True
    return raw.strip().lower() not in ("0", "false", "no", "off", "")


def _gemma_curator_default() -> bool:
    """The Gemma memory-curator lane defaults ON (it is proposed-only and
    inert without a configured runner). ``HERMES_JARVIS_GEMMA_CURATOR=0``
    (or false/no/off) disables it for an exact rollback path."""

    raw = os.environ.get("HERMES_JARVIS_GEMMA_CURATOR")
    if raw is None:
        return True
    return raw.strip().lower() not in ("0", "false", "no", "off", "")


# Sentinel: the auto-detected Gemma runner is resolved lazily, once per instance.
_GEMMA_UNSET: Any = object()


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
    # Optional dense-embedding retrieval lane for the Memory Tree (default off).
    # A positive weight activates a semantic-similarity term blended into the
    # tree's term-overlap search; 0.0 (with the env flag unset) is byte-for-byte
    # the legacy keyword search. Env override: HERMES_MEMORY_TREE_EMBEDDINGS /
    # HERMES_MEMORY_TREE_EMBED_WEIGHT (see memory_tree_embeddings.py).
    memory_tree_embedding_weight: float = 0.0
    # Gemma memory-curator lane (proposed-only). On by default but inert until a
    # ``gemma_runner`` is configured — so default behavior is byte-identical to
    # before. The runner is injectable: ``(prompt: str) -> str``.
    gemma_memory_curator_enabled: bool = field(default_factory=_gemma_curator_default)
    gemma_runner: Optional[Any] = None
    # Optional factory ``() -> Optional[runner]`` used to AUTO-build a runner when
    # ``gemma_runner`` is unset. Injected by tests/embedders; in production the
    # runtime falls back to local-Ollama detection (opt-in via the env flag).
    gemma_runner_factory: Optional[Any] = None


@dataclass
class JarvisTurn:
    """One end-to-end turn of muse"""

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
    # Optional model-route metadata (additive; populated when a model route was
    # resolved for the turn). ``None``/empty when not applicable.
    selected_model: Optional[str] = None
    selected_provider: Optional[str] = None
    selected_task_class: Optional[str] = None
    fallback_chain: list[str] = field(default_factory=list)
    scorecard_basis: Optional[str] = None
    gemma_variant: Optional[str] = None
    # Effort-class stamp (E0–E5) for this turn — the smallest-sufficient
    # effort class of the routing decision, promoted to a first-class,
    # auditable field on the per-turn trace. Mirrors ``route.effort_class``;
    # additive and observational only.
    effort_class: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent": self.intent,
            "awareness": self.awareness.to_dict(),
            "classification": self.classification.to_dict(),
            "persona_prompt": self.persona_prompt.render(),
            "route": self.route.to_dict(),
            "effort_class": self.effort_class,
            "gate_summary": self.gate_summary.to_dict() if self.gate_summary else None,
            "recollection": self.recollection,
            "research_brief": self.research_brief.to_dict() if self.research_brief else None,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat(),
            "notes": list(self.notes),
            "selected_model": self.selected_model,
            "selected_provider": self.selected_provider,
            "selected_task_class": self.selected_task_class,
            "fallback_chain": list(self.fallback_chain),
            "scorecard_basis": self.scorecard_basis,
            "gemma_variant": self.gemma_variant,
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
        self._gemma_runner_cache: Any = _GEMMA_UNSET

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
                store = MemoryTreeStore.load()
                if self.config.memory_tree_embedding_weight > 0:
                    store.embedding_weight = self.config.memory_tree_embedding_weight
                self.config.memory_tree = store
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
        base = legacy
        if tree is not None:
            try:
                pack = tree.context_pack(query, self.config.memory_token_budget)
            except Exception:  # pragma: no cover - defensive
                pack = None
            if pack is not None and pack.sections:
                tree_block = pack.render()
                base = f"{legacy}\n\n{tree_block}" if legacy else tree_block
        return self._augment_with_second_brain(query, base, limit=limit)

    def _augment_with_second_brain(
        self, query: str, base: str, *, limit: int = 5
    ) -> str:
        """Optionally append a Second Brain retrieval block to ``base``.

        Opt-in (``MUSE_SECOND_BRAIN``) and fail-safe: when the flag is unset, the
        module/backend isn't available, or retrieval yields nothing, ``base`` is
        returned **unchanged** — so the default path stays byte-identical. Like
        the Memory Tree above, the Second Brain *augments*, never replaces, the
        native recollection, and a failure can never break recall.
        """

        try:
            from hermes_cli.jarvis_prime import second_brain_bridge as sbb

            if not (sbb.enabled() and sbb.is_available()):
                return base
            ctx = sbb.retrieve_optional(query, top_k=limit)
        except Exception:  # pragma: no cover - defensive (never break recall)
            return base
        if ctx is None or not (ctx.text or "").strip():
            return base
        block = f"## second brain\n{ctx.text.strip()}"
        return f"{base}\n\n{block}" if base else block

    def _resolve_gemma_runner(self):
        """The Gemma curator runner — explicit ``config.gemma_runner`` wins;
        otherwise auto-detect a local Ollama Gemma when opted in
        (``HERMES_JARVIS_GEMMA_AUTO_RUNNER``). Default (no runner, auto off)
        stays inert: byte-identical to before."""

        cfg = self.config
        if not cfg.gemma_memory_curator_enabled:
            return None
        if cfg.gemma_runner is not None:
            return cfg.gemma_runner
        if self._gemma_runner_cache is _GEMMA_UNSET:
            self._gemma_runner_cache = self._build_auto_gemma_runner()
        return self._gemma_runner_cache

    def _build_auto_gemma_runner(self):
        factory = self.config.gemma_runner_factory
        try:
            if factory is not None:
                return factory()
            from hermes_cli.jarvis_prime.gemma_runner import (
                auto_runner_enabled,
                build_gemma_runner,
            )
            if not auto_runner_enabled():
                return None
            return build_gemma_runner()
        except Exception:  # detection never breaks a turn
            return None

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

        # Gemma memory-curator enhancement (proposed-only, owner-gated). This is
        # additive and inert unless a runner is configured, so the deterministic
        # baseline above is never weakened. Curator-proposed keys are added to
        # the summary ONLY when the curator actually ran.
        gemma_runner = self._resolve_gemma_runner()
        if gemma_runner is not None:
            try:
                from hermes_cli.jarvis_prime.gemma_memory_curator import (
                    capture_curator_proposals,
                    curate,
                    strip_gemma_thought_blocks,
                )

                turn_text = strip_gemma_thought_blocks(
                    f"{user_text}\n\n{assistant_text}".strip()
                )
                proposals = curate(
                    turn_text,
                    source_uri=source_uri,
                    deterministic_candidates=candidates,
                    runner=gemma_runner,
                )
                gem_results = capture_curator_proposals(
                    tree, proposals, source_uri=source_uri
                )
                summary["gemma_proposed"] = sum(1 for r in gem_results if r.ok)
                summary["gemma_rejected"] = sum(1 for r in gem_results if not r.ok)
            except Exception:  # pragma: no cover - curation never breaks a turn
                pass
        return summary

    def record_route_outcome(
        self,
        *,
        model: str,
        task_class: str,
        provider: str = "unknown",
        risk_class: str = "RC1",
        latency_ms: Optional[float] = None,
        tokens_in: Optional[int] = None,
        tokens_out: Optional[int] = None,
        tests_passed: Optional[int] = None,
        tests_failed: Optional[int] = None,
        owner_corrections: Optional[int] = None,
        hallucination_corrections: Optional[int] = None,
        memory_usefulness: Optional[float] = None,
        citation_accuracy: Optional[float] = None,
        tool_reliability: Optional[float] = None,
        context_length: Optional[int] = None,
        book: Optional[Any] = None,
        persist: bool = True,
    ) -> Optional[Any]:
        """Record a model scorecard for a completed turn — evidence only.

        Returns the recorded ``ModelScorecard`` or ``None`` when no real signal
        was supplied. Unknown values stay unknown/neutral; nothing is fabricated.
        This is what lets scorecards (later) promote/demote a model per lane.
        """
        signals = (
            latency_ms, tokens_in, tokens_out, tests_passed, tests_failed,
            owner_corrections, hallucination_corrections, memory_usefulness,
            citation_accuracy, tool_reliability, context_length,
        )
        if all(s is None for s in signals):
            return None
        try:
            from hermes_cli.jarvis_prime.model_scorecard import (
                ModelScorecard,
                ScorecardBook,
            )

            card = ModelScorecard(
                model=model,
                provider=provider,
                task_type=task_class,
                risk_class=risk_class,
                latency_ms=latency_ms,
                tokens_in=int(tokens_in or 0),
                tokens_out=int(tokens_out or 0),
                tests_passed=int(tests_passed or 0),
                tests_failed=int(tests_failed or 0),
                owner_corrections=int(owner_corrections or 0),
                hallucination_corrections=int(hallucination_corrections or 0),
                memory_usefulness=memory_usefulness,
                citation_accuracy=citation_accuracy,
                tool_reliability=tool_reliability,
                context_length=int(context_length or 0),
            )
            book = book if book is not None else ScorecardBook.load()
            book.record(card, persist=persist)
            return card
        except Exception:  # pragma: no cover - telemetry never breaks a turn
            return None

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

    def gate(
        self,
        packet: Mapping[str, Any],
        evidence_bundle: Any = None,
        strict_evidence: bool = True,
    ) -> GateSummary:
        """Evaluate a work packet's gates.

        Strict, evidence-bound gates run by default whenever a real evidence
        bundle is supplied; with no bundle the call falls back to the legacy
        packet-level gates so existing planning flows are unaffected. When strict
        gates run, the summary is journaled to the tamper-evident guardrail
        ledger (best-effort — a ledger failure never blocks evaluation).
        """

        use_strict = strict_evidence and evidence_bundle is not None
        summary = run_gate_summary(
            packet,
            evidence_bundle=evidence_bundle,
            strict_evidence=use_strict,
        )
        if use_strict:
            try:
                from hermes_cli.jarvis_prime.guardrail_evidence import GuardrailLedger

                GuardrailLedger().append(
                    "gate_summary",
                    str(_packet_get(packet, "packet_id") or _packet_get(packet, "branch") or ""),
                    {
                        "overall": summary.overall.value,
                        "remaining_risk": summary.remaining_risk,
                        "results": [r.to_dict() for r in summary.results],
                    },
                )
            except Exception:  # pragma: no cover - defensive
                pass
        return summary

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
            "effort_class": route.effort_class,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Bind the delegation to verifiable-guardrail context so the downstream
        # worker knows which evidence it must produce and which ledger head it
        # is building on. All best-effort — never break delegation on failure.
        if packet:
            pid = _packet_get(packet, "packet_id")
            if pid:
                envelope["packet_id"] = pid
            req = _packet_get(packet, "required_evidence")
            if req:
                envelope["required_evidence"] = list(req)
        try:
            from hermes_cli.jarvis_prime.guardrail_evidence import GuardrailLedger

            envelope["ledger_latest_hash"] = GuardrailLedger().latest_hash()
        except Exception:  # pragma: no cover - defensive
            pass
        if route.requires_owner_authorization:
            challenges = getattr(self.config.owner_auth, "challenges", {}) or {}
            envelope["owner_challenge_ids"] = list(challenges.keys())

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
            effort_class=route.effort_class,
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
        result: dict[str, Any] = {
            "cleared": cleared,
            "tick_disabled": True,
            "reason": reason,
            "cleared_actions": [g.action for g in pending],
            "branch_leases_cleared": leases_cleared,
        }
        # Append a tamper-evident emergency-stop record to the guardrail ledger
        # so any later audit can prove this process was halted. A ledger failure
        # must never crash the stop primitive — surface it as a warning instead.
        try:
            from hermes_cli.jarvis_prime.guardrail_evidence import GuardrailLedger

            record = GuardrailLedger().append(
                "emergency_stop",
                reason,
                {
                    "reason": reason,
                    "cleared_actions": [g.action for g in pending],
                    "branch_leases_cleared": leases_cleared,
                },
            )
            result["ledger_record_hash"] = record.record_hash
        except Exception as exc:  # pragma: no cover - defensive
            result["ledger_warning"] = f"failed to journal emergency stop: {exc}"
        return result

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
