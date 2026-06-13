"""Constitution amendment engine — the structural asset-lock (Vol VI Part 6).

The three anti-goals (C35 not-a-slot-machine, C36 not-a-dependency, C37
not-an-oracle) plus C34 (the inviolable verifier wall) are **non-amendable**:
:func:`evaluate_amendment` refuses any proposal touching them unconditionally —
no scale, quorum size, or "strengthening" framing creates an exception. This is
the constitutional analogue of a foundation asset-lock, applied pre-emptively
(the OpenAI Nov-2023 / HashiCorp lesson: mission-by-goodwill loses to capital).

For allowed proposals the engine returns the scale-graded process from the
Volume VI governance table: solo = ceremonial phrase; team = quorum; community
= RFC + supermajority; enterprise = versioned customer-visible covenant with a
notice period.

The engine **adjudicates and records only** — it never applies an amendment.
Applying an allowed amendment remains a human edit to
``docs/jarvis-constitution.md`` plus ``constitution.py`` (consistent with C34:
the agent never gains write access to the thing that judges it).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping, Optional

from hermes_cli.jarvis_prime import constitution
from hermes_cli.jarvis_prime.constitution import Severity
from hermes_cli.jarvis_prime.guardrail_evidence import GuardrailLedger

from . import KIND_AMENDMENT_DECISION

# The asset-locked core. C34 is included deliberately: the verifier wall that
# protects this engine must itself be locked, or the lock is circularly
# bypassable (amend C34 first, then everything else).
NON_AMENDABLE_CLAUSE_IDS: frozenset[str] = frozenset({"C34", "C35", "C36", "C37"})

VALID_AMENDMENT_KINDS = ("add", "modify", "retire")


class Scale(str, Enum):
    """Deployment scales A–E from the Volume VI scaling matrix."""

    A_SOLO = "A_solo"
    B_TEAM = "B_team"
    C_COMMUNITY = "C_community"
    D_STARTUP = "D_startup"
    E_ENTERPRISE = "E_enterprise"


@dataclass(frozen=True)
class AmendmentProcess:
    """The process knobs an allowed amendment must go through at a scale."""

    name: str  # ceremonial_phrase | quorum | rfc_supermajority | versioned_covenant
    required_quorum: Optional[tuple[int, int]]  # (m, n) when applicable
    notice_period_days: int


AMENDMENT_PROCESS_BY_SCALE: dict[Scale, AmendmentProcess] = {
    Scale.A_SOLO: AmendmentProcess("ceremonial_phrase", None, 0),
    Scale.B_TEAM: AmendmentProcess("quorum", (2, 3), 0),
    Scale.C_COMMUNITY: AmendmentProcess("rfc_supermajority", (2, 3), 0),
    Scale.D_STARTUP: AmendmentProcess("versioned_covenant", (2, 3), 14),
    Scale.E_ENTERPRISE: AmendmentProcess("versioned_covenant", (2, 3), 30),
}


def amendment_process_for_scale(scale: Scale) -> AmendmentProcess:
    return AMENDMENT_PROCESS_BY_SCALE[scale]


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class AmendmentProposal:
    """A proposed change to the Constitution, awaiting adjudication."""

    proposal_id: str
    clause_ids: tuple[str, ...]
    kind: str  # add | modify | retire
    rationale: str
    proposed_text: str
    scale: Scale
    created_at: str

    @classmethod
    def build(
        cls,
        *,
        clause_ids: tuple[str, ...] | list[str],
        kind: str,
        rationale: str = "",
        proposed_text: str = "",
        scale: Scale = Scale.A_SOLO,
        proposal_id: Optional[str] = None,
    ) -> "AmendmentProposal":
        return cls(
            proposal_id=proposal_id or f"amend_{uuid.uuid4().hex[:16]}",
            clause_ids=tuple(clause_ids),
            kind=kind,
            rationale=rationale,
            proposed_text=proposed_text,
            scale=scale,
            created_at=_utc_iso(),
        )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "AmendmentProposal":
        return cls(
            proposal_id=str(data.get("proposal_id") or f"amend_{uuid.uuid4().hex[:16]}"),
            clause_ids=tuple(str(c) for c in data.get("clause_ids", [])),
            kind=str(data.get("kind", "")),
            rationale=str(data.get("rationale", "")),
            proposed_text=str(data.get("proposed_text", "")),
            scale=Scale(str(data.get("scale", Scale.A_SOLO.value))),
            created_at=str(data.get("created_at") or _utc_iso()),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "clause_ids": list(self.clause_ids),
            "kind": self.kind,
            "rationale": self.rationale,
            "proposed_text": self.proposed_text,
            "scale": self.scale.value,
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class AmendmentDecision:
    """The engine's verdict on one proposal."""

    proposal_id: str
    allowed: bool
    reason: str
    required_process: str
    required_quorum: Optional[tuple[int, int]]
    notice_period_days: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "allowed": self.allowed,
            "reason": self.reason,
            "required_process": self.required_process,
            "required_quorum": list(self.required_quorum) if self.required_quorum else None,
            "notice_period_days": self.notice_period_days,
        }


def evaluate_amendment(
    proposal: AmendmentProposal,
    *,
    ledger: Optional[GuardrailLedger] = None,
) -> AmendmentDecision:
    """Adjudicate ``proposal``; never apply it.

    Refusal of non-amendable clauses is checked first and unconditionally:
    there is no scale, quorum, or kind (including "strengthening" modifies)
    that reaches past it.
    """

    process = amendment_process_for_scale(proposal.scale)
    known_ids = set(constitution.clause_ids())

    def _decide(allowed: bool, reason: str) -> AmendmentDecision:
        decision = AmendmentDecision(
            proposal_id=proposal.proposal_id,
            allowed=allowed,
            reason=reason,
            required_process=process.name if allowed else "none",
            required_quorum=process.required_quorum if allowed else None,
            notice_period_days=process.notice_period_days if allowed else 0,
        )
        if ledger is not None:
            ledger.append(KIND_AMENDMENT_DECISION, proposal.proposal_id, decision.to_dict())
        return decision

    locked = sorted(set(proposal.clause_ids) & NON_AMENDABLE_CLAUSE_IDS)
    if locked:
        return _decide(
            False,
            "touches non-amendable clause(s) "
            + ", ".join(locked)
            + " — asset-locked at every scale, quorum, and kind",
        )

    if proposal.kind not in VALID_AMENDMENT_KINDS:
        return _decide(False, f"unknown amendment kind {proposal.kind!r}")

    if not proposal.clause_ids:
        return _decide(False, "proposal names no clause ids")

    if proposal.kind == "add":
        duplicated = sorted(set(proposal.clause_ids) & known_ids)
        if duplicated:
            return _decide(
                False,
                "add proposal reuses existing clause id(s) "
                + ", ".join(duplicated)
                + " — clause ids are append-only, never reused",
            )
    else:
        unknown = sorted(set(proposal.clause_ids) - known_ids)
        if unknown:
            return _decide(
                False,
                f"{proposal.kind} proposal references unknown clause id(s) " + ", ".join(unknown),
            )
        if proposal.kind == "retire":
            fatal = sorted(
                cid
                for cid in proposal.clause_ids
                if constitution.clause(cid).severity == Severity.FATAL
            )
            if fatal:
                return _decide(
                    False,
                    "retire proposal targets fatal clause(s) " + ", ".join(fatal),
                )

    return _decide(
        True,
        f"allowed; requires {process.name} at scale {proposal.scale.value}",
    )


__all__ = [
    "NON_AMENDABLE_CLAUSE_IDS",
    "VALID_AMENDMENT_KINDS",
    "Scale",
    "AmendmentProcess",
    "AMENDMENT_PROCESS_BY_SCALE",
    "amendment_process_for_scale",
    "AmendmentProposal",
    "AmendmentDecision",
    "evaluate_amendment",
]
