"""The scaling decision tree, kill criteria, and evaluation matrix (Vol VI Part 7).

The roadmap is not a fixed ladder but a resource-conditional decision tree
whose **default branch is "stay solo-plus-agents"** — per the Startup Genome
finding that 74% of high-growth internet startups fail from *premature*
scaling, not under-scaling. Four honest kill criteria gate every scale-up:

- K1: no proving-ground user who needs MUSE specifically (no PMF),
- K2: the verifier gates still need constant manual intervention (the
  management layer isn't trustworthy enough to manage a team),
- K3: a funding term touches the anti-goals (the slot-machine red line),
- K4: coordination cost exceeds what MUSE's workers already deliver.

Any triggered criterion forces the recommendation back to Scale A. The
evaluation matrix and mechanism unlocks are the Volume VI tables, verbatim.
Recommendations are evidence (optionally ledgered), not actions — scaling
itself remains a human decision.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Optional

from hermes_cli.jarvis_prime.guardrail_evidence import GuardrailLedger

from . import KIND_SCALE_RECOMMENDATION
from .amendment import Scale, amendment_process_for_scale


@dataclass(frozen=True)
class ScaleSignals:
    """Observable inputs to the decision tree. Defaults describe solo reality."""

    collaborator_count: int = 0
    has_proving_ground_user: bool = False
    gates_need_constant_manual_intervention: bool = False
    funding_term_touches_anti_goals: bool = False
    coordination_hours_weekly: float = 0.0
    worker_throughput_hours_weekly: float = 0.0
    seeking_funding: bool = False
    external_customers: int = 0
    regulated_deployment: bool = False
    community_contributors: int = 0

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ScaleSignals":
        kwargs: dict[str, Any] = {}
        for name, fld in cls.__dataclass_fields__.items():
            if name not in data:
                continue
            value = data[name]
            # Every field defaults to a bool, int, or float; coerce to match.
            if isinstance(fld.default, bool):
                kwargs[name] = bool(value)
            elif isinstance(fld.default, int):
                kwargs[name] = int(value)
            else:
                kwargs[name] = float(value)
        return cls(**kwargs)

    def to_dict(self) -> dict[str, Any]:
        return {name: getattr(self, name) for name in self.__dataclass_fields__}


@dataclass(frozen=True)
class KillCriterion:
    criterion_id: str
    title: str
    predicate: Callable[[ScaleSignals], bool]
    detail: str


@dataclass(frozen=True)
class KillFinding:
    criterion_id: str
    title: str
    triggered: bool
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "criterion_id": self.criterion_id,
            "title": self.title,
            "triggered": self.triggered,
            "detail": self.detail,
        }


def _wants_to_scale(signals: ScaleSignals) -> bool:
    return (
        signals.collaborator_count > 0
        or signals.seeking_funding
        or signals.external_customers > 0
    )


KILL_CRITERIA: tuple[KillCriterion, ...] = (
    KillCriterion(
        "K1",
        "No proving-ground user",
        lambda s: _wants_to_scale(s) and not s.has_proving_ground_user,
        "No paying or regulated proving-ground user needs MUSE specifically — "
        "hiring would be efficiently executing the irrelevant.",
    ),
    KillCriterion(
        "K2",
        "Gates not trustworthy",
        lambda s: s.gates_need_constant_manual_intervention,
        "The verifier gates still require constant manual intervention; the "
        "management layer is not trustworthy enough to manage a human team.",
    ),
    KillCriterion(
        "K3",
        "Anti-goal funding term",
        lambda s: s.funding_term_touches_anti_goals,
        "A funding term touches the anti-goals (slot-machine red line) — "
        "refuse the money, not the Constitution.",
    ),
    KillCriterion(
        "K4",
        "Coordination exceeds worker throughput",
        lambda s: 0.0
        < s.worker_throughput_hours_weekly
        < s.coordination_hours_weekly,
        "The coordination cost of additional humans exceeds the throughput "
        "MUSE's workers already provide.",
    ),
)


def evaluate_kill_criteria(signals: ScaleSignals) -> list[KillFinding]:
    return [
        KillFinding(
            criterion_id=c.criterion_id,
            title=c.title,
            triggered=c.predicate(signals),
            detail=c.detail,
        )
        for c in KILL_CRITERIA
    ]


# The Volume VI evaluation matrix, verbatim (1 = poor, 5 = excellent).
EVALUATION_MATRIX: dict[Scale, dict[str, int]] = {
    Scale.A_SOLO: {
        "capability_ceiling": 2,
        "governance_integrity": 5,
        "anti_goal_resilience": 5,
        "time_to_vision": 2,
        "sovereignty": 5,
    },
    Scale.B_TEAM: {
        "capability_ceiling": 4,
        "governance_integrity": 4,
        "anti_goal_resilience": 4,
        "time_to_vision": 3,
        "sovereignty": 4,
    },
    Scale.C_COMMUNITY: {
        "capability_ceiling": 4,
        "governance_integrity": 3,
        "anti_goal_resilience": 2,
        "time_to_vision": 3,
        "sovereignty": 3,
    },
    Scale.D_STARTUP: {
        "capability_ceiling": 5,
        "governance_integrity": 2,
        "anti_goal_resilience": 2,
        "time_to_vision": 5,
        "sovereignty": 2,
    },
    Scale.E_ENTERPRISE: {
        "capability_ceiling": 5,
        "governance_integrity": 3,
        "anti_goal_resilience": 3,
        "time_to_vision": 4,
        "sovereignty": 2,
    },
}

# Which Vol VI mechanisms each scale unlocks (cumulative).
MECHANISM_UNLOCKS: dict[Scale, frozenset[str]] = {
    Scale.A_SOLO: frozenset(),
    Scale.B_TEAM: frozenset({"quorum_auth", "ledger_multisig", "dedicated_gpu_forge"}),
    Scale.C_COMMUNITY: frozenset(
        {
            "quorum_auth",
            "ledger_multisig",
            "dedicated_gpu_forge",
            "trust_ladder",
            "forge_federated_intake",
            "rfc_amendments",
            "registry_marketplace",
        }
    ),
    Scale.D_STARTUP: frozenset(
        {
            "quorum_auth",
            "ledger_multisig",
            "dedicated_gpu_forge",
            "trust_ladder",
            "forge_federated_intake",
            "rfc_amendments",
            "registry_marketplace",
            "platform_team",
            "safety_hire",
            "ray_k8s_forge",
        }
    ),
    Scale.E_ENTERPRISE: frozenset(
        {
            "quorum_auth",
            "ledger_multisig",
            "dedicated_gpu_forge",
            "trust_ladder",
            "forge_federated_intake",
            "rfc_amendments",
            "registry_marketplace",
            "platform_team",
            "safety_hire",
            "ray_k8s_forge",
            "per_tenant_isolation",
            "conformity_assessment",
            "threshold_sig_killswitch",
        }
    ),
}


@dataclass(frozen=True)
class ScaleRecommendation:
    recommended: Scale
    decision_path: tuple[str, ...]
    kill_findings: tuple[KillFinding, ...] = field(default_factory=tuple)
    matrix_row: Mapping[str, int] = field(default_factory=dict)
    unlocked_mechanisms: tuple[str, ...] = ()
    amendment_process: str = ""
    rationale: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "recommended": self.recommended.value,
            "decision_path": list(self.decision_path),
            "kill_findings": [f.to_dict() for f in self.kill_findings],
            "matrix_row": dict(self.matrix_row),
            "unlocked_mechanisms": sorted(self.unlocked_mechanisms),
            "amendment_process": self.amendment_process,
            "rationale": self.rationale,
        }


def recommend_scale(
    signals: ScaleSignals,
    *,
    ledger: Optional[GuardrailLedger] = None,
) -> ScaleRecommendation:
    """Walk the Part-7 decision tree; every step is a recorded IF/THEN line."""

    path: list[str] = []
    rationale_parts: list[str] = []
    findings = evaluate_kill_criteria(signals)
    triggered = [f for f in findings if f.triggered]

    if triggered:
        ids = ", ".join(f.criterion_id for f in triggered)
        path.append(
            f"IF any kill criterion is triggered ({ids}) THEN stay solo — "
            "premature scaling, not patience, is what kills builders."
        )
        recommended = Scale.A_SOLO
        rationale_parts.append(
            "Kill criteria triggered: " + "; ".join(f.title for f in triggered)
        )
    elif signals.external_customers > 0 and signals.regulated_deployment:
        path.append(
            "IF regulated external customers exist THEN Scale E — per-tenant "
            "isolation, conformity assessment, threshold-sig kill switch."
        )
        recommended = Scale.E_ENTERPRISE
    elif signals.community_contributors >= 50:
        path.append(
            "IF community traction (~50+ contributors) THEN Scale C — publish "
            "the RFC process + trust ladder; registry-verified marketplace; "
            "move the Constitution into a foundation."
        )
        recommended = Scale.C_COMMUNITY
    elif signals.collaborator_count > 10:
        path.append(
            "IF the team exceeds ~10 THEN Scale D — form the platform team; "
            "first dedicated safety/evals + security hire arrives here."
        )
        recommended = Scale.D_STARTUP
    elif 1 <= signals.collaborator_count <= 10:
        path.append(
            "IF 1-10 collaborators THEN Scale B — parallelize, don't "
            "re-architect: Forge infra / voice / Command Center workstreams; "
            "team-quorum amendment + signed team keys on the ledger."
        )
        recommended = Scale.B_TEAM
    else:
        path.append(
            "IF solo THEN stay solo-plus-agents — MUSE's workers are the team "
            "and the verifier gates are the management layer (the default)."
        )
        recommended = Scale.A_SOLO

    if signals.seeking_funding and recommended != Scale.A_SOLO:
        path.append(
            "IF seeking funding THEN stand up the mission-lock BEFORE the "
            "round closes (PBC + golden share; slot-machine anti-goal as a "
            "term-sheet red line) — it cannot be retrofitted under pressure."
        )
        rationale_parts.append("Mission-lock before any dollar is accepted.")

    process = amendment_process_for_scale(recommended)
    recommendation = ScaleRecommendation(
        recommended=recommended,
        decision_path=tuple(path),
        kill_findings=tuple(findings),
        matrix_row=EVALUATION_MATRIX[recommended],
        unlocked_mechanisms=tuple(sorted(MECHANISM_UNLOCKS[recommended])),
        amendment_process=process.name,
        rationale=" ".join(rationale_parts) or "Scale only on unambiguous evidence.",
    )
    if ledger is not None:
        ledger.append(
            KIND_SCALE_RECOMMENDATION,
            recommended.value,
            {"signals": signals.to_dict(), **recommendation.to_dict()},
        )
    return recommendation


__all__ = [
    "Scale",
    "ScaleSignals",
    "KillCriterion",
    "KillFinding",
    "KILL_CRITERIA",
    "evaluate_kill_criteria",
    "EVALUATION_MATRIX",
    "MECHANISM_UNLOCKS",
    "ScaleRecommendation",
    "recommend_scale",
]
