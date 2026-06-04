"""Backend selector: IntentGraph -> BackendDecision.

Mirrors ``model_router.route()``'s discipline — deterministic scoring, a full
audit trail (every candidate appears in ``scores`` or ``rejected``, nothing
silently dropped), a one-paragraph rationale, and a JSON ledger entry. It
**never executes** and reads only the graph's ``feature_vector()``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from hermes_cli.jarvis_prime.intent_graph import IntentGraph


class BackendTarget(str, Enum):
    REPO_WORK_PACKET = "repo_work_packet"
    AUTOMATION_FLOW = "automation_flow"
    # Reserved for later phases — always rejected in Phase-1 (kept for a
    # complete audit trail, never selectable).
    PYTHON = "python"
    RUST = "rust"
    SQL = "sql"


_PHASE1_SELECTABLE: frozenset[BackendTarget] = frozenset(
    {BackendTarget.REPO_WORK_PACKET, BackendTarget.AUTOMATION_FLOW}
)

# CLI hint strings -> target.
HINT_ALIASES: dict[str, BackendTarget] = {
    "work-packet": BackendTarget.REPO_WORK_PACKET,
    "repo_work_packet": BackendTarget.REPO_WORK_PACKET,
    "workflow": BackendTarget.AUTOMATION_FLOW,
    "automation": BackendTarget.AUTOMATION_FLOW,
    "automation_flow": BackendTarget.AUTOMATION_FLOW,
}


@dataclass(frozen=True)
class BackendScore:
    target: BackendTarget
    score: float
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return {"target": self.target.value, "score": round(self.score, 4),
                "rationale": self.rationale}


@dataclass(frozen=True)
class BackendContext:
    forced_target: Optional[BackendTarget] = None
    repo_root: str = "."


@dataclass(frozen=True)
class BackendDecision:
    selected: Optional[BackendTarget]
    scores: tuple[BackendScore, ...]
    rejected: dict[str, str]
    rationale: str
    ledger_entry: dict[str, Any] = field(default_factory=dict)
    blocked: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "selected": self.selected.value if self.selected else None,
            "scores": [s.to_dict() for s in self.scores],
            "rejected": dict(self.rejected),
            "rationale": self.rationale,
            "blocked": self.blocked,
        }


def select_backend(
    graph: IntentGraph,
    context: Optional[BackendContext] = None,
    *,
    hint: Optional[BackendTarget] = None,
) -> BackendDecision:
    context = context or BackendContext()
    fv = graph.feature_vector()
    rejected: dict[str, str] = {}

    # Reserved backends are never selectable in Phase-1 — but recorded.
    for t in BackendTarget:
        if t not in _PHASE1_SELECTABLE:
            rejected[t.value] = "not enabled in phase-1"

    # Hard block short-circuit (bypass / exfiltration detected upstream).
    if fv.get("blocked"):
        for t in _PHASE1_SELECTABLE:
            rejected[t.value] = "blocked: request attempts to bypass gates"
        return BackendDecision(
            selected=None,
            scores=(),
            rejected=rejected,
            rationale="blocked request — no backend selected",
            ledger_entry=_ledger_entry(graph, fv, None),
            blocked=True,
        )

    # Explicit override: CLI hint or a BACKEND_HINT node.
    forced = context.forced_target or hint
    if forced is None and fv.get("backend_hint"):
        forced = HINT_ALIASES.get(str(fv["backend_hint"]))
    if forced is not None and forced in _PHASE1_SELECTABLE:
        for t in _PHASE1_SELECTABLE:
            if t != forced:
                rejected[t.value] = "explicit hint selected another target"
        decision = BackendDecision(
            selected=forced,
            scores=(BackendScore(forced, 1.0, "explicit hint / forced target"),),
            rejected=rejected,
            rationale=f"{forced.value} chosen by explicit hint",
            ledger_entry=_ledger_entry(graph, fv, forced),
        )
        return decision

    # --- deterministic scoring -------------------------------------------
    wf = 0.0
    wf_reasons: list[str] = []
    if fv["has_trigger"]:
        wf += 0.5
        wf_reasons.append("event trigger present")
    if fv["non_repo_io"]:
        wf += 0.2
        wf_reasons.append("non-repo IO (email/ledger/alert)")

    rp = 0.0
    rp_reasons: list[str] = []
    if fv["edit_verbs"] > 0:
        rp += 0.4
        rp_reasons.append(f"{fv['edit_verbs']} repo-edit verb(s)")
    if fv["repo_scoped"]:
        rp += 0.2
        rp_reasons.append("repo-scoped targets/globs")
    if not fv["has_trigger"] and not fv["non_repo_io"]:
        rp += 0.1
        rp_reasons.append("no automation signals")

    scores = (
        BackendScore(BackendTarget.AUTOMATION_FLOW, wf,
                     "; ".join(wf_reasons) or "no workflow signals"),
        BackendScore(BackendTarget.REPO_WORK_PACKET, rp,
                     "; ".join(rp_reasons) or "no repo signals"),
    )
    # Deterministic tie-break: higher score, then REPO_WORK_PACKET (conservative,
    # gate-covered) wins ties via the value ordering below.
    ordered = sorted(
        scores,
        key=lambda s: (-s.score, 0 if s.target == BackendTarget.REPO_WORK_PACKET else 1),
    )
    selected = ordered[0].target
    for s in ordered[1:]:
        rejected[s.target.value] = f"lower score ({s.score:.2f} < {ordered[0].score:.2f})"

    rationale = (
        f"{selected.value} chosen (score {ordered[0].score:.2f}): "
        f"{ordered[0].rationale}"
    )
    return BackendDecision(
        selected=selected,
        scores=tuple(ordered),
        rejected=rejected,
        rationale=rationale,
        ledger_entry=_ledger_entry(graph, fv, selected),
    )


def _ledger_entry(
    graph: IntentGraph, fv: dict[str, Any], selected: Optional[BackendTarget]
) -> dict[str, Any]:
    return {
        "schema": "hermes.nlp.backend.v1",
        "graph_id": graph.graph_id,
        "features": fv,
        "selected": selected.value if selected else None,
    }


__all__ = [
    "BackendTarget",
    "BackendScore",
    "BackendContext",
    "BackendDecision",
    "select_backend",
    "HINT_ALIASES",
]
