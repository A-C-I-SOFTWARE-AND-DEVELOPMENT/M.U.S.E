"""AlphaEvolve/FunSearch-style evolutionary improvement on the algorithms lane.

The full thesis in miniature: propose variants -> execute-verify (correctness is
a hard gate) -> keep the verifiably *better* one (lower op-count) -> evolve. This
is the same loop that produced AlphaTensor / AlphaDev / AlphaEvolve, run against
the purest verifier we have (op-count is exact and deterministic).

A candidate may only become the new best if it is **correct on the held-out
cases** AND strictly reduces the op-count metric — a monotone ratchet, so the
evolved program can never be worse than the baseline. Every accepted step is
recorded to the hash-chained ledger and (optionally) the diversity archive.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from muse_cli.jarvis_prime.guardrail_evidence import GuardrailLedger

from ..archive.store import ArchiveStore, new_member
from ..verifier.algorithms import AlgorithmTask, measure_opcount, score_algorithm_candidate

# Given the current best code, propose candidate variants (mutations/rewrites).
VariantProposer = Callable[[str], list[str]]


@dataclass
class EvolveStep:
    generation: int
    accepted: bool
    opcount: Optional[int]
    note: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "generation": self.generation,
            "accepted": self.accepted,
            "opcount": self.opcount,
            "note": self.note,
        }


@dataclass
class EvolveResult:
    task_id: str
    baseline_opcount: Optional[int]
    best_opcount: Optional[int]
    best_code: str
    improved: bool
    generations_run: int
    steps: list[EvolveStep] = field(default_factory=list)

    @property
    def reduction(self) -> Optional[int]:
        if self.baseline_opcount is None or self.best_opcount is None:
            return None
        return self.baseline_opcount - self.best_opcount

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "baseline_opcount": self.baseline_opcount,
            "best_opcount": self.best_opcount,
            "improved": self.improved,
            "reduction": self.reduction,
            "generations_run": self.generations_run,
            "steps": [s.to_dict() for s in self.steps],
            "best_code": self.best_code,
        }


def evolve(
    task: AlgorithmTask,
    baseline_code: str,
    propose_variants: VariantProposer,
    *,
    generations: int = 5,
    ledger: Optional[GuardrailLedger] = None,
    archive: Optional[ArchiveStore] = None,
) -> EvolveResult:
    """Evolve ``baseline_code`` toward a correct, lower-op-count solution.

    When ``archive`` is supplied, every accepted improvement is recorded as an
    :class:`ArchiveMember` chained to the prior best (lineage), so a later search
    can branch from any stepping stone rather than only the reigning champion.
    """

    # The baseline must itself be correct, or there is nothing to ratchet from.
    base_score = score_algorithm_candidate(baseline_code, task)
    if not base_score.accepted:
        return EvolveResult(
            task_id=task.task_id,
            baseline_opcount=None,
            best_opcount=None,
            best_code=baseline_code,
            improved=False,
            generations_run=0,
            steps=[EvolveStep(0, False, None, "baseline is not correct")],
        )

    best_code = baseline_code
    best_op = measure_opcount(baseline_code, task)

    parent_id: Optional[str] = None
    if archive is not None:
        base_member = archive.add(
            new_member(
                parent_id=None,
                config={"task_id": task.task_id, "opcount": best_op, "role": "baseline"},
                composite=base_score.correctness,
                domain_scores={"correctness": base_score.correctness},
                note=f"baseline op-count {best_op}",
            )
        )
        parent_id = base_member.member_id

    result = EvolveResult(
        task_id=task.task_id,
        baseline_opcount=best_op,
        best_opcount=best_op,
        best_code=best_code,
        improved=False,
        generations_run=0,
    )

    for gen in range(1, generations + 1):
        result.generations_run = gen
        variants = propose_variants(best_code)
        gen_improved = False
        for code in variants:
            score = score_algorithm_candidate(code, task)
            if not score.accepted:
                result.steps.append(EvolveStep(gen, False, None, "incorrect variant"))
                continue
            op = measure_opcount(code, task)
            if op is not None and best_op is not None and op < best_op:
                best_code, best_op = code, op
                result.best_code, result.best_opcount = code, op
                result.improved = True
                gen_improved = True
                result.steps.append(EvolveStep(gen, True, op, f"new best op-count {op}"))
                if ledger is not None:
                    ledger.append(
                        "evolve_accept",
                        task.task_id,
                        {"generation": gen, "opcount": op, "baseline": result.baseline_opcount},
                    )
                if archive is not None:
                    member = archive.add(
                        new_member(
                            parent_id=parent_id,
                            config={"task_id": task.task_id, "opcount": op, "generation": gen},
                            composite=score.correctness,
                            domain_scores={"correctness": score.correctness},
                            note=f"evolved op-count {op} (gen {gen})",
                        )
                    )
                    parent_id = member.member_id
            else:
                result.steps.append(EvolveStep(gen, False, op, "no op-count improvement"))
        if not gen_improved:
            # Converged: no variant beat the current best this generation.
            break

    return result


__all__ = ["VariantProposer", "EvolveStep", "EvolveResult", "evolve"]
