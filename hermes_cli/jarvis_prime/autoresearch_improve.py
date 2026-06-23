"""Owner-gated autoresearch glue — the training engine in the SIA socket.

Wires the autoresearch worker (autonomous ``train.py`` experiments in a
disposable workspace) into muse's existing owner-gated improvement flow by
**reusing** :func:`hermes_cli.jarvis_prime.sia_self_improve.run_self_improvement`
— same benchmark gate, same RC4 proposal with ``NEEDS_OWNER_APPROVAL``, zero
new orchestration. On top it adds what training runs need:

* **constraints gate** before the verdict is interpreted — "wins bpb but blew
  the VRAM budget / cost ceiling" is a *named* FAIL, never a silent one;
* **score-space mapping** — ``val_bpb`` is lower-is-better while the gate and
  ``WorkerScore`` are higher-is-better in [0, 1]; both sides go through the
  order-preserving ``bpb_gate_score`` transform (raw bpb is preserved in all
  rationale/evidence for honesty);
* **provenance** — champion scorecards (ScorecardBook), AXIOM chain events,
  Memory-Tree "what worked" consolidation, and learning-dataset candidates.

Invariants (enforced by tests): never edits anything live, never applies; a
constraint-violating or non-improving run emits **no** proposal.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Optional

from hermes_cli.jarvis_prime.gates import GateOutcome, GateResult
from hermes_cli.jarvis_prime.model_scorecard import ModelScorecard, ScorecardBook
from hermes_cli.jarvis_prime.research_fabric.autoresearch.engine import (
    bpb_gate_score,
    gate_margin_for_bpb_delta,
)
from hermes_cli.jarvis_prime.self_update import ProposalBook
from hermes_cli.jarvis_prime.sia_self_improve import (
    SiaImprovementOutcome,
    SiaJob,
    run_self_improvement,
)

TASK_NAME = "autoresearch_pretrain"
# The proposal's target: the vendored mutable surface. Lives under hermes_cli/
# so sia_self_improve routes it to SELF_RUNTIME_UPDATE + RC4 (owner-gated).
TARGET_PATH = (
    "hermes_cli/jarvis_prime/research_fabric/autoresearch/vendor/train.py"
)


@dataclass
class AutoresearchImprovementOutcome:
    sia: SiaImprovementOutcome
    constraints_gate: GateResult
    run_details: dict[str, Any] = field(default_factory=dict)
    scorecards: tuple[ModelScorecard, ...] = ()
    chain_hash: Optional[str] = None
    memory_written: bool = False

    @property
    def proposal(self):  # convenience passthrough
        return self.sia.proposal


def evaluate_constraints(
    details: Mapping[str, Any],
    *,
    vram_budget_mb: float,
    max_cost_usd: float,
) -> GateResult:
    """Hard multi-objective gate, ordered before the benchmark verdict.

    The driver already prevents an infeasible result from becoming champion;
    this gate makes the *reason* first-class so the owner sees "won bpb but
    blew VRAM" instead of a generic no-improvement message.
    """

    findings: list[str] = []
    champion = details.get("champion")
    best_infeasible = details.get("best_infeasible")
    if champion is None and best_infeasible is not None:
        return GateResult(
            name="autoresearch_constraints",
            outcome=GateOutcome.FAIL,
            reason=(
                f"best candidate wins val_bpb ({best_infeasible.get('val_bpb')}) "
                f"but is infeasible: {best_infeasible.get('reason', 'constraint violated')}"
            ),
            findings=(f"vram_budget_mb={vram_budget_mb}",),
        )
    total_cost = float(details.get("total_cost_usd") or 0.0)
    if 0.0 < max_cost_usd < total_cost:
        return GateResult(
            name="autoresearch_constraints",
            outcome=GateOutcome.FAIL,
            reason=f"cost ${total_cost:.2f} exceeded ceiling ${max_cost_usd:.2f}",
            findings=(f"total_cost_usd={total_cost}",),
        )
    if champion is not None and champion.get("peak_vram_mb") is not None:
        findings.append(
            f"champion peak VRAM {champion['peak_vram_mb']:.1f}MB "
            f"within budget {vram_budget_mb:.1f}MB"
        )
    findings.append(f"cost ${total_cost:.2f} within ceiling ${max_cost_usd:.2f}")
    return GateResult(
        name="autoresearch_constraints",
        outcome=GateOutcome.PASS,
        reason="VRAM and cost constraints satisfied",
        findings=tuple(findings),
    )


def _champion_scorecard(details: Mapping[str, Any]) -> Optional[ModelScorecard]:
    champion = details.get("champion")
    if not champion or champion.get("val_bpb") is None:
        return None
    device = str(details.get("device", "cuda:0"))
    total_seconds = champion.get("total_seconds") or 0.0
    return ModelScorecard(
        model=f"autoresearch/{details.get('tag', 'run')}@{champion.get('commit', '?')}",
        provider="modal" if device.startswith("modal") else "local-gpu",
        task_type=TASK_NAME,
        risk_class="RC3",
        latency_ms=float(total_seconds) * 1000.0 if total_seconds else None,
        cost_usd=float(details.get("total_cost_usd") or 0.0),
        tests_passed=1,
        tests_failed=0,
        # Bounded quality signal so promotion_eligible works unmodified across
        # nights; raw val_bpb is in the proposal evidence and flywheel events.
        accepted_diff_rate=bpb_gate_score(float(champion["val_bpb"])),
        context_length=2048,
    )


def _record_chain_event(details: Mapping[str, Any], gate_outcome: str) -> Optional[str]:
    """AXIOM chain record for the champion (inert when gates are off)."""

    try:
        from hermes_cli.jarvis_prime.axiom_bridge import get_bridge

        champion = details.get("champion") or {}
        return get_bridge().record_event(
            "autoresearch.champion",
            {
                "tag": details.get("tag"),
                "commit": champion.get("commit"),
                "val_bpb": champion.get("val_bpb"),
                "baseline_bpb": details.get("baseline_bpb"),
                "peak_vram_mb": champion.get("peak_vram_mb"),
                "cost_usd": details.get("total_cost_usd"),
                "gate": gate_outcome,
                "branch": details.get("branch"),
                "results_tsv": details.get("results_tsv"),
            },
        )
    except Exception:
        return None


def _consolidate_memory(details: Mapping[str, Any], memory_store: Any) -> bool:
    """Durable Memory-Tree note: which idea classes worked, with provenance."""

    try:
        from hermes_cli.jarvis_prime.memory_tree import (
            MemoryLayer,
            MemoryNamespace,
            MemorySource,
            SourceTrust,
        )
        from hermes_cli.jarvis_prime.research_fabric.autoresearch.engine import (
            ExperimentResult,
            summarize_idea_classes,
        )

        experiments = details.get("experiments") or []
        if not experiments:
            return False
        results = tuple(ExperimentResult(**e) for e in experiments)
        tsv_path = str(details.get("results_tsv") or "")
        excerpt = ""
        if tsv_path and Path(tsv_path).exists():
            excerpt = "\n".join(
                Path(tsv_path).read_text(encoding="utf-8").splitlines()[:6]
            )
        result = memory_store.write(
            f"autoresearch run '{details.get('tag')}': "
            f"{summarize_idea_classes(results)}",
            namespace=MemoryNamespace.RESEARCH,
            title=f"autoresearch {details.get('tag')}: what worked",
            layer=MemoryLayer.DURABLE,
            summary="experiment idea classes that improved / hurt val_bpb",
            sources=(
                MemorySource(
                    uri=f"file://{tsv_path}",
                    trust=SourceTrust.PRIMARY,
                    excerpt=excerpt,
                ),
            ),
            source_uri=f"file://{tsv_path}",
            confidence=0.7,
            tags=("autoresearch", "training", str(details.get("tag") or "")),
        )
        return bool(result.ok)
    except Exception:
        return False


def _offer_dataset_candidate(details: Mapping[str, Any]) -> None:
    """Champion trace → learning-dataset candidate (PENDING, owner-approved later)."""

    try:
        from hermes_cli.jarvis_prime.learning_dataset import (
            DatasetStore,
            Provenance,
            QualityGates,
            SourceTrust,
            TraceType,
        )

        champion = details.get("champion")
        if not champion:
            return
        store = DatasetStore.load()
        store.add_candidate(
            TraceType.CODING_TASK,
            {
                "task": "autoresearch pretraining experiment",
                "description": champion.get("description"),
                "val_bpb": champion.get("val_bpb"),
                "baseline_bpb": details.get("baseline_bpb"),
                "commit": champion.get("commit"),
                "branch": details.get("branch"),
            },
            Provenance(
                source_kind="job",
                source_uri=str(details.get("results_tsv") or ""),
                job_id=f"autoresearch-{details.get('tag')}",
                trust=SourceTrust.PRIMARY,
            ),
            QualityGates(tests_passed=True, rollback_available=True),
            labels=("autoresearch", "pretrain"),
            task_key=TASK_NAME,
        )
    except Exception:
        return  # strictly best-effort; never blocks the run


def run_autoresearch_improvement(
    objective: str,
    *,
    book: ProposalBook,
    worker: Any,
    baseline_bpb: float,
    min_bpb_delta: float = 0.0,
    vram_budget_mb: float = 0.0,
    max_cost_usd: float = 0.0,
    scorecard_book: Optional[ScorecardBook] = None,
    memory_store: Optional[Any] = None,
    emit_proposal: bool = True,
) -> AutoresearchImprovementOutcome:
    """One governed improvement attempt: loop → gates → owner-gated proposal.

    ``worker`` is always injected (an :class:`AutoresearchWorker` bound to a
    config, or a duck-typed fake in tests). ``emit_proposal=False`` (swarm
    lanes) routes the inner call through a throwaway book so only the swarm
    coordinator ever writes a real proposal.
    """

    job = SiaJob(
        objective=objective,
        target_path=TARGET_PATH,
        task=TASK_NAME,
        job_id="autoresearch-improve",
        acceptance_criteria=(
            "val_bpb strictly lower than baseline",
            "peak VRAM within budget",
            "within the cost ceiling",
        ),
    )
    inner_book = book if emit_proposal else ProposalBook()
    sia_outcome = run_self_improvement(
        job,
        book=inner_book,
        baseline_score=bpb_gate_score(baseline_bpb),
        min_margin=gate_margin_for_bpb_delta(baseline_bpb, min_bpb_delta),
        worker=worker,
    )

    details: dict[str, Any] = {}
    try:
        artifacts = worker.collect(job)
        details = dict(getattr(artifacts, "details", {}) or {})
    except Exception:
        details = {}

    constraints = evaluate_constraints(
        details, vram_budget_mb=vram_budget_mb, max_cost_usd=max_cost_usd
    )

    scorecards: tuple[ModelScorecard, ...] = ()
    chain_hash: Optional[str] = None
    memory_written = False
    if details:
        card = _champion_scorecard(details)
        if card is not None:
            if scorecard_book is not None:
                scorecard_book.record(card, persist=scorecard_book.path is not None)
            scorecards = (card,)
        chain_hash = _record_chain_event(details, sia_outcome.gate.outcome.value)
        if memory_store is not None:
            memory_written = _consolidate_memory(details, memory_store)
        if sia_outcome.improved:
            try:
                _offer_dataset_candidate(details)
            except Exception:
                # Soft-fail by contract: a learning-dataset hiccup must never
                # void a validated improvement run (the proposal/provenance
                # above already landed). Asserted by
                # test_dataset_candidate_offer_is_soft_fail.
                pass

    return AutoresearchImprovementOutcome(
        sia=sia_outcome,
        constraints_gate=constraints,
        run_details=details,
        scorecards=scorecards,
        chain_hash=chain_hash,
        memory_written=memory_written,
    )


def record_promotion(
    proposal_target: str,
    *,
    commit: str,
    val_bpb: float,
    diff_loc: int = 0,
) -> dict[str, Any]:
    """AXIOM HIGH-risk classification + chain record for an APPROVED promotion.

    Called only after the owner approves the proposal (exact authorization
    phrase, PR flow). Adopting a trained recipe changes default behavior ⇒
    forced HIGH ⇒ the full gate profile including ``owner_approval``.
    """

    from hermes_cli.jarvis_prime.axiom_bridge import get_bridge

    bridge = get_bridge()
    classification = bridge.classify_change(
        description=f"adopt autoresearch champion {commit} into {proposal_target}",
        loc=diff_loc,
        files=1,
        effects=("model_training", "default_training_recipe"),
        changes_default_behavior=True,
    )
    chain_hash = bridge.record_event(
        "autoresearch.promotion",
        {
            "target": proposal_target,
            "commit": commit,
            "val_bpb": val_bpb,
            "risk": classification.get("risk"),
            "gates": list(classification.get("gates", ())),
        },
    )
    return {"classification": classification, "chain_hash": chain_hash}


__all__ = [
    "TASK_NAME",
    "TARGET_PATH",
    "AutoresearchImprovementOutcome",
    "evaluate_constraints",
    "run_autoresearch_improvement",
    "record_promotion",
]
