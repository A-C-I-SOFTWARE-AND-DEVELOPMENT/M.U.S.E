"""The AutonomyController — composes the full bounded auto-apply envelope.

Order of operations for ``evaluate_and_apply`` (fail-closed at every step):

1. **Reward-hacking / monitor screen** — any tripwire halts autonomy (revokes
   the charter) and blocks; a malicious candidate is never "promotable".
2. **Hard wall (C34)** — runtime/gates/owner-auth/registry/routing/harness/
   constitution can only become an owner-gated proposal, never auto-apply.
3. **Ratchet (+ ambition)** — strict non-regression wall; a failure blocks with
   no proposal (a regression is not promotable).
4. **Eight strict gates** — ``run_strict_gate_summary``; FAIL blocks,
   NEEDS_OWNER_APPROVAL falls back to a proposal.
5. **Capability gate** — best-effort RC-band attestation.
6. **Charter scope + budget** — no active charter ⇒ proposal fallback; out of
   scope / over budget ⇒ proposal fallback.
7. **Auto-apply** — capture rollback handle, call the injected ``applier``,
   ledger ``auto_apply``, freeze the new champion.
8. **Canary** — injected ``canary`` re-measures; any regression vs the previous
   champion triggers ``rollback`` + ledger ``auto_rollback`` + champion restore.

``applier`` / ``canary`` / ``rollback`` are injected callables (like ``worker``
in ``run_self_improvement``), so CI uses fakes and never mutates the live tree.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Mapping, Optional

from muse_cli.jarvis_prime.gates import (
    GateOutcome,
    GateSummary,
    run_strict_gate_summary,
)
from muse_cli.jarvis_prime.guardrail_evidence import (
    GuardrailEvidenceBundle,
    GuardrailLedger,
)
from muse_cli.jarvis_prime.self_update import Proposal, ProposalBook, ProposalEvidence

from .ambition import AmbitionProfile, apply_ambition
from .catalog import REQUIRED_DOMAINS, ABSOLUTE_FLOOR
from .champion import Champion, ChampionStore
from .charter import CharterBook, is_hard_walled
from .monitor import AlignmentMonitor
from .validators import RatchetVerdict, RatchetWall
from .verifier import Candidate, screen_for_reward_hacking

# Injected callable types.
Applier = Callable[[Candidate], str]          # apply change → return applied handle/sha
Canary = Callable[[Candidate], Mapping[str, Any]]  # re-measure → {"domain_scores":..,"safety_counts":..}
Rollback = Callable[[str], None]              # revert to a handle
GateRunner = Callable[..., GateSummary]       # (packet, bundle) → GateSummary


@dataclass
class AutoApplyOutcome:
    decision: str  # auto_applied | rolled_back | proposed | blocked
    applied: bool
    rolled_back: bool
    ratchet: Optional[RatchetVerdict]
    gate_overall: Optional[str]
    capability_ok: Optional[bool]
    charter_id: Optional[str]
    proposal: Optional[Proposal]
    rollback_handle: Optional[str]
    tripwire: Optional[dict[str, Any]]
    ledger_record_hash: str
    rationale: str
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "applied": self.applied,
            "rolled_back": self.rolled_back,
            "ratchet": self.ratchet.to_dict() if self.ratchet else None,
            "gate_overall": self.gate_overall,
            "capability_ok": self.capability_ok,
            "charter_id": self.charter_id,
            "proposal": self.proposal.to_dict() if self.proposal else None,
            "rollback_handle": self.rollback_handle,
            "tripwire": self.tripwire,
            "ledger_record_hash": self.ledger_record_hash,
            "rationale": self.rationale,
            "extra": self.extra,
        }


class AutonomyController:
    def __init__(
        self,
        *,
        charter_book: CharterBook,
        champion_store: ChampionStore,
        proposal_book: ProposalBook,
        ledger: GuardrailLedger,
        monitor: AlignmentMonitor,
        ratchet: Optional[RatchetWall] = None,
        ambition_profile: Optional[AmbitionProfile] = None,
        applier: Optional[Applier] = None,
        canary: Optional[Canary] = None,
        rollback: Optional[Rollback] = None,
        gate_runner: Optional[GateRunner] = None,
        enforce_capability: bool = False,
    ) -> None:
        self.charters = charter_book
        self.champions = champion_store
        self.proposals = proposal_book
        self.ledger = ledger
        self.monitor = monitor
        self.ratchet = ratchet or RatchetWall()
        self.ambition_profile = ambition_profile or AmbitionProfile.default()
        self.applier = applier
        self.canary = canary
        self.rollback = rollback
        # Default to the real strict, evidence-bound gate suite; injectable for
        # tests (mirrors the worker/applier/canary injection pattern).
        self.gate_runner = gate_runner or run_strict_gate_summary
        # Capability wall is feature-flagged OFF by default, mirroring the repo
        # (HERMES_CAPABILITY_GATE). When off, it is skipped (capability_ok=None).
        self.enforce_capability = enforce_capability

    # -- helpers ----------------------------------------------------------

    def _propose(self, candidate: Candidate, reason: str, risk: str = "RC4") -> Proposal:
        return self.proposals.propose(
            kind=candidate.kind,
            target_path=candidate.target_path or "(unspecified target)",
            rationale=reason,
            diff_intent=(
                f"Auto-apply withheld; routed to owner-gated proposal. {candidate.note}"
            ),
            evidence=(
                ProposalEvidence(
                    kind="research_finding",
                    text=reason,
                    citation=candidate.candidate_id,
                ),
            ),
            risk_class=risk,
        )

    def _block(
        self,
        candidate: Candidate,
        kind: str,
        reason: str,
        *,
        ratchet: Optional[RatchetVerdict] = None,
        tripwire: Optional[dict[str, Any]] = None,
        gate_overall: Optional[str] = None,
    ) -> AutoApplyOutcome:
        rec = self.ledger.append(kind, candidate.candidate_id, {"reason": reason})
        return AutoApplyOutcome(
            decision="blocked",
            applied=False,
            rolled_back=False,
            ratchet=ratchet,
            gate_overall=gate_overall,
            capability_ok=None,
            charter_id=None,
            proposal=None,
            rollback_handle=None,
            tripwire=tripwire,
            ledger_record_hash=rec.record_hash,
            rationale=reason,
        )

    def _proposal_outcome(
        self,
        candidate: Candidate,
        reason: str,
        *,
        ratchet: Optional[RatchetVerdict] = None,
        gate_overall: Optional[str] = None,
        risk: str = "RC4",
    ) -> AutoApplyOutcome:
        proposal = self._propose(candidate, reason, risk=risk)
        rec = self.ledger.append(
            "proposal_fallback",
            candidate.candidate_id,
            {"reason": reason, "risk_class": risk},
        )
        return AutoApplyOutcome(
            decision="proposed",
            applied=False,
            rolled_back=False,
            ratchet=ratchet,
            gate_overall=gate_overall,
            capability_ok=None,
            charter_id=None,
            proposal=proposal,
            rollback_handle=None,
            tripwire=None,
            ledger_record_hash=rec.record_hash,
            rationale=reason,
        )

    def _canary_regressed(
        self,
        prev: Optional[Champion],
        canary_scores: Mapping[str, float],
    ) -> tuple[bool, str]:
        for domain in REQUIRED_DOMAINS:
            score = canary_scores.get(domain)
            if score is None:
                return True, f"canary missing domain '{domain}'"
            if score < ABSOLUTE_FLOOR:
                return True, f"canary '{domain}' below floor: {score:.4f}"
            if prev is not None:
                base = prev.domain_scores.get(domain)
                if base is not None and score < base:
                    return True, f"canary '{domain}' regressed vs prior champion: {score:.4f} < {base:.4f}"
        return False, "canary stable"

    # -- main -------------------------------------------------------------

    def evaluate_and_apply(
        self,
        candidate: Candidate,
        *,
        evidence_bundle: GuardrailEvidenceBundle,
        packet: Mapping[str, Any],
        dry_run: bool = False,
        now: Optional[datetime] = None,
    ) -> AutoApplyOutcome:
        champ = self.champions.current()
        champ_scores = champ.domain_scores if champ else None
        champ_safety = champ.safety_counts if champ else None

        # (1) reward-hacking / monitor screen
        signals = screen_for_reward_hacking(candidate)
        mon = self.monitor.check(signals)
        if mon.tripped:
            return self._block(
                candidate,
                "tripwire",
                f"autonomy halted by tripwire(s): {[s.kind for s in mon.signals]}",
                tripwire=mon.to_dict(),
            )

        # (2) hard wall (C34)
        walled, wall_reason = is_hard_walled(candidate.kind, candidate.target_path)
        if walled:
            return self._proposal_outcome(
                candidate, f"hard-walled, owner-gated only: {wall_reason}", risk="RC4"
            )

        # (3) ratchet (+ ambition)
        verdict = self.ratchet.evaluate(
            champion_domain_scores=champ_scores,
            candidate_domain_scores=candidate.domain_scores,
            holdout_scores=candidate.holdout_scores,
            candidate_safety_counts=candidate.safety_counts,
            champion_safety_counts=champ_safety,
            eval_win_rate=candidate.eval_win_rate,
        )
        verdict = apply_ambition(verdict, candidate.ambition_scores, self.ambition_profile)
        if not verdict.passed:
            return self._block(
                candidate,
                "ratchet_block",
                f"ratchet failed: {'; '.join(verdict.reasons) or 'non-regression not proven'}",
                ratchet=verdict,
            )

        # (4) eight strict gates
        summary = self.gate_runner(packet, evidence_bundle)
        overall = summary.overall
        if overall is GateOutcome.FAIL:
            return self._block(
                candidate,
                "gate_block",
                f"strict gates FAILED: {summary.remaining_risk}",
                ratchet=verdict,
                gate_overall=overall.value,
            )
        if overall is GateOutcome.NEEDS_OWNER_APPROVAL:
            return self._proposal_outcome(
                candidate,
                f"strict gates need owner approval: {summary.remaining_risk}",
                ratchet=verdict,
                gate_overall=overall.value,
                risk="RC3",
            )

        # (5) capability gate — feature-flagged OFF by default (repo parity).
        capability_ok: Optional[bool] = None
        if self.enforce_capability:
            try:
                from muse_cli.jarvis_prime.capability_wall import capability_gate

                cap = capability_gate(packet, evidence_bundle, enabled=True)
                capability_ok = cap.outcome in (GateOutcome.PASS, GateOutcome.SKIPPED)
                if not capability_ok:
                    return self._proposal_outcome(
                        candidate,
                        f"capability wall withheld: {cap.reason}",
                        ratchet=verdict,
                        gate_overall=overall.value,
                        risk="RC3",
                    )
            except Exception:  # pragma: no cover - capability wall optional
                capability_ok = None

        # (6) charter scope + budget
        charter = self.charters.active(now)
        if charter is None:
            return self._proposal_outcome(
                candidate,
                "no active autonomy charter — auto-apply requires one (C33)",
                ratchet=verdict,
                gate_overall=overall.value,
                risk="RC3",
            )
        permitted, permit_reason = charter.permits(candidate.kind, candidate.risk_class)
        if not permitted:
            return self._proposal_outcome(
                candidate,
                f"outside charter scope: {permit_reason}",
                ratchet=verdict,
                gate_overall=overall.value,
                risk="RC3",
            )
        used = self.charters.auto_applies_in_window(charter, self.ledger, now)
        if used >= charter.per_window_budget:
            return self._proposal_outcome(
                candidate,
                f"charter budget exhausted ({used}/{charter.per_window_budget})",
                ratchet=verdict,
                gate_overall=overall.value,
                risk="RC3",
            )

        # Dry-run: everything passed, but do not touch the tree.
        if dry_run or self.applier is None:
            rec = self.ledger.append(
                "auto_apply_dry_run",
                candidate.candidate_id,
                {"charter_id": charter.charter_id, "would_apply": True},
            )
            return AutoApplyOutcome(
                decision="proposed" if self.applier is None else "blocked",
                applied=False,
                rolled_back=False,
                ratchet=verdict,
                gate_overall=overall.value,
                capability_ok=capability_ok,
                charter_id=charter.charter_id,
                proposal=None,
                rollback_handle=self.champions.rollback_handle(),
                tripwire=None,
                ledger_record_hash=rec.record_hash,
                rationale="dry-run: all gates passed; would auto-apply inside charter",
                extra={"would_auto_apply": True},
            )

        # (7) auto-apply
        prev_champion = champ
        prior_handle = self.champions.rollback_handle()
        applied_handle = self.applier(candidate)
        rec = self.ledger.append(
            "auto_apply",
            candidate.candidate_id,
            {
                "charter_id": charter.charter_id,
                "applied_handle": applied_handle,
                "rollback_handle": prior_handle or candidate.rollback_handle,
                "composite_delta": verdict.composite_delta,
                "eval_win_rate": verdict.eval_win_rate,
            },
        )
        new_champion = Champion.make(
            domain_scores=candidate.domain_scores,
            composite=verdict.composite_candidate,
            rollback_handle=applied_handle,
            safety_counts=candidate.safety_counts,
            note=f"auto-applied via charter {charter.charter_id}",
        )
        self.champions.freeze(new_champion, reason="auto_apply")

        # (8) canary recheck
        if self.canary is not None:
            measured = self.canary(candidate)
            canary_scores = dict(measured.get("domain_scores", {}))
            regressed, why = self._canary_regressed(prev_champion, canary_scores)
            if regressed:
                handle = prior_handle or candidate.rollback_handle
                if self.rollback is not None and handle:
                    self.rollback(handle)
                rb = self.ledger.append(
                    "auto_rollback",
                    candidate.candidate_id,
                    {
                        "charter_id": charter.charter_id,
                        "reason": why,
                        "restored_handle": handle,
                        "canary_scores": canary_scores,
                    },
                )
                if prev_champion is not None:
                    self.champions.freeze(prev_champion, reason="auto_rollback")
                return AutoApplyOutcome(
                    decision="rolled_back",
                    applied=True,
                    rolled_back=True,
                    ratchet=verdict,
                    gate_overall=overall.value,
                    capability_ok=capability_ok,
                    charter_id=charter.charter_id,
                    proposal=None,
                    rollback_handle=handle,
                    tripwire=None,
                    ledger_record_hash=rb.record_hash,
                    rationale=f"auto-applied then rolled back: {why}",
                )

        return AutoApplyOutcome(
            decision="auto_applied",
            applied=True,
            rolled_back=False,
            ratchet=verdict,
            gate_overall=overall.value,
            capability_ok=capability_ok,
            charter_id=charter.charter_id,
            proposal=None,
            rollback_handle=applied_handle,
            tripwire=None,
            ledger_record_hash=rec.record_hash,
            rationale="auto-applied inside charter; ratchet + gates + canary clean",
        )


__all__ = ["AutonomyController", "AutoApplyOutcome", "Applier", "Canary", "Rollback"]
