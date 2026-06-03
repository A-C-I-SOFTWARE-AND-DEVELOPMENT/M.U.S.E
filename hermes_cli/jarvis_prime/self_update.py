"""Self-update proposals for JARVIS Prime.

The user asked JARVIS to "update its own skills and agents to as
well as itself". This module produces structured *proposals* —
JARVIS does NOT silently rewrite his own runtime. Every change to
his SKILL.md, his agents, or his code is:

1. Proposed via ``Proposal`` with rationale + diff intent.
2. Sent to ``self_improvement.write_retrospective`` for ledger entry.
3. Held until owner authorization (``Yes, with authorization.``).
4. Applied via the standard PR flow (Claude Code builder + Codex
   reviewer) — not by JARVIS himself.

This is the "loyal but autonomous" pattern: JARVIS surfaces what he
thinks he should learn; owner decides what actually changes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class ProposalKind(Enum):
    SKILL_UPDATE = "skill_update"          # update an existing SKILL.md
    NEW_SKILL = "new_skill"                # create a new skill
    AGENT_UPDATE = "agent_update"          # update a .claude/agents/*.md
    NEW_AGENT = "new_agent"                # create a new subagent
    ROUTING_RULE_UPDATE = "routing_rule_update"  # tweak model-routing-policy
    SELF_RUNTIME_UPDATE = "self_runtime_update"  # change hermes_cli/jarvis_prime/*
    MEMORY_PROMOTION = "memory_promotion"  # promote session → durable memory
    GATE_UPDATE = "gate_update"            # tweak a verification gate
    MODEL_REGISTRY_UPDATE = "model_registry_update"  # REG-1: sync config/model-catalog.yaml


class ProposalStatus(Enum):
    PROPOSED = "proposed"
    NEEDS_OWNER_APPROVAL = "needs_owner_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    APPLIED = "applied"


@dataclass(frozen=True)
class ProposalEvidence:
    """One piece of evidence supporting a proposal."""

    kind: str  # "user_correction" | "retro" | "router_miss" | "research_finding"
    text: str
    citation: Optional[str] = None
    confidence: float = 1.0


@dataclass
class Proposal:
    kind: ProposalKind
    target_path: str            # file path the proposal would touch
    rationale: str              # plain-English why
    diff_intent: str            # high-level "what" — not a literal patch
    evidence: tuple[ProposalEvidence, ...] = ()
    risk_class: str = "RC1"
    requires_owner_approval: bool = True
    status: ProposalStatus = ProposalStatus.PROPOSED
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: Optional[datetime] = None
    owner_decision_note: Optional[str] = None

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind.value,
            "target_path": self.target_path,
            "rationale": self.rationale,
            "diff_intent": self.diff_intent,
            "evidence": [
                {"kind": e.kind, "text": e.text, "citation": e.citation, "confidence": e.confidence}
                for e in self.evidence
            ],
            "risk_class": self.risk_class,
            "requires_owner_approval": self.requires_owner_approval,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "owner_decision_note": self.owner_decision_note,
        }

    def approve(self, note: str = "") -> None:
        self.status = ProposalStatus.APPROVED
        self.resolved_at = datetime.now(timezone.utc)
        self.owner_decision_note = note

    def reject(self, note: str = "") -> None:
        self.status = ProposalStatus.REJECTED
        self.resolved_at = datetime.now(timezone.utc)
        self.owner_decision_note = note

    def mark_applied(self, applied_commit_sha: Optional[str] = None) -> None:
        self.status = ProposalStatus.APPLIED
        self.resolved_at = datetime.now(timezone.utc)
        if applied_commit_sha:
            self.owner_decision_note = (
                self.owner_decision_note or ""
            ) + f" [applied at {applied_commit_sha}]"


@dataclass
class ProposalBook:
    """A simple in-process queue of Proposals.

    The runtime can persist the book to ``~/.hermes/jarvis_prime/
    proposals.jsonl`` using ``dump``. Owner reviews via
    ``hermes proposal list`` (wire-up out of scope here; see CLI in
    ``__main__.py`` for the JSON list mode).
    """

    proposals: list[Proposal] = field(default_factory=list)

    def propose(
        self,
        kind: ProposalKind,
        target_path: str,
        rationale: str,
        diff_intent: str,
        evidence: tuple[ProposalEvidence, ...] = (),
        risk_class: str = "RC1",
    ) -> Proposal:
        p = Proposal(
            kind=kind,
            target_path=target_path,
            rationale=rationale,
            diff_intent=diff_intent,
            evidence=evidence,
            risk_class=risk_class,
        )
        # RC3+ proposals always need owner approval.
        if risk_class in {"RC3", "RC4"}:
            p.status = ProposalStatus.NEEDS_OWNER_APPROVAL
        self.proposals.append(p)
        return p

    def pending(self) -> list[Proposal]:
        return [
            p
            for p in self.proposals
            if p.status in (ProposalStatus.PROPOSED, ProposalStatus.NEEDS_OWNER_APPROVAL)
        ]

    def applied(self) -> list[Proposal]:
        return [p for p in self.proposals if p.status == ProposalStatus.APPLIED]

    def render_for_owner(self) -> str:
        pending = self.pending()
        if not pending:
            return "No JARVIS Prime self-update proposals pending."
        lines = ["JARVIS PRIME — PENDING SELF-UPDATE PROPOSALS"]
        for i, p in enumerate(pending, start=1):
            lines.append(
                f"{i}. [{p.kind.value} @ {p.target_path}] (risk={p.risk_class})\n"
                f"   why: {p.rationale}\n"
                f"   what: {p.diff_intent}\n"
                f"   evidence: {len(p.evidence)} item(s)"
            )
        return "\n".join(lines)
