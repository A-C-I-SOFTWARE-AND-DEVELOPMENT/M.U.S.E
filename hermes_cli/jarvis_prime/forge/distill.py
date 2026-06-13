"""Winner distillation through the federation poison filter (Vol VI Part 5).

Tournament winners become distillation candidates — but **through the same
intake path as federated peers' contributions**: re-verified locally (a
corrupted report cannot smuggle an incorrect winner), content-hash attested,
symbolically gated, band-checked, and stored as PENDING for owner approval.
One intake path, no side door.
"""

from __future__ import annotations

from typing import Any, Optional

from hermes_cli.jarvis_prime.federation.attestation import ArtifactAttestation
from hermes_cli.jarvis_prime.federation.forge_intake import (
    IntakeDecision,
    admit_to_distillation,
    evaluate_contribution,
    trajectory_sha256,
)
from hermes_cli.jarvis_prime.federation.trust_ladder import (
    ContributorRecord,
    ContributorStore,
)
from hermes_cli.jarvis_prime.guardrail_evidence import GuardrailLedger
from hermes_cli.jarvis_prime.learning_dataset import DatasetStore
from hermes_cli.jarvis_prime.research_fabric.verifier.algorithms import (
    AlgorithmTask,
    score_algorithm_candidate,
)

from .registry import CandidateRegistry
from .tournament import TournamentReport


def winner_trajectories(
    report: TournamentReport,
    registry: CandidateRegistry,
    *,
    top_k: int = 3,
) -> list[dict[str, Any]]:
    """Top-K candidates by post-tournament rating, as plain trajectories."""

    ranked = sorted(report.ratings_after.items(), key=lambda item: -item[1])
    trajectories: list[dict[str, Any]] = []
    for candidate_id, rating in ranked[:top_k]:
        record = registry.resolve(candidate_id)
        opcounts = [
            d.a_opcount if d.a == candidate_id else d.b_opcount
            for d in report.duels
            if candidate_id in (d.a, d.b)
        ]
        opcount = next((o for o in opcounts if o is not None), None)
        trajectories.append(
            {
                "task_id": record.task_id,
                "candidate_id": candidate_id,
                "code": record.code,
                "opcount": opcount,
                "rating": round(rating, 2),
                "payload_sha256": record.payload_sha256,
            }
        )
    return trajectories


def distill_winners(
    report: TournamentReport,
    registry: CandidateRegistry,
    task: AlgorithmTask,
    *,
    contributor: ContributorRecord,
    dataset_store: DatasetStore,
    node_id: str = "local",
    store: Optional[ContributorStore] = None,
    ledger: Optional[GuardrailLedger] = None,
    top_k: int = 3,
) -> list[IntakeDecision]:
    """Route each tournament winner through the poison filter into the dataset."""

    decisions: list[IntakeDecision] = []
    for trajectory in winner_trajectories(report, registry, top_k=top_k):
        # Never trust the report: re-run the verifier on the resolved code.
        record = registry.resolve(str(trajectory["candidate_id"]))
        verifier_passed = score_algorithm_candidate(record.code, task).accepted
        attestation = ArtifactAttestation(
            node_id=node_id,
            artifact_type="test_result",
            subject=record.task_id,
            payload_sha256=trajectory_sha256(trajectory),
            created_at=trajectory.get("created_at", "") or record.created_at,
        )
        decision = evaluate_contribution(
            trajectory,
            contributor=contributor,
            verifier_passed=verifier_passed,
            attestation=attestation,
            store=store,
            ledger=ledger,
        )
        decisions.append(decision)
        if decision.admitted:
            admit_to_distillation(
                trajectory,
                decision,
                dataset_store,
                source_uri=f"forge://{report.task_id}/{trajectory['candidate_id']}",
            )
    return decisions


__all__ = ["winner_trajectories", "distill_winners"]
