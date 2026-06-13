"""Tests for winner distillation through the poison filter."""

import random

from hermes_cli.jarvis_prime.federation.trust_ladder import (
    ContributorBand,
    ContributorRecord,
)
from hermes_cli.jarvis_prime.forge.registry import CandidateRecord, CandidateRegistry
from hermes_cli.jarvis_prime.forge.distill import distill_winners, winner_trajectories
from hermes_cli.jarvis_prime.forge.tournament import RatingBook, run_tournament
from hermes_cli.jarvis_prime.guardrail_evidence import GuardrailLedger
from hermes_cli.jarvis_prime.learning_dataset import CandidateStatus, DatasetStore
from hermes_cli.jarvis_prime.research_fabric.verifier.algorithms import (
    AlgorithmCase,
    AlgorithmTask,
)

TASK = AlgorithmTask(
    task_id="alg_sum",
    entrypoint="solve",
    prompt="Sum a list of integers.",
    public_cases=(AlgorithmCase([[1, 2, 3]], 6),),
    holdout_cases=(AlgorithmCase([[4, 5]], 9), AlgorithmCase([[]], 0)),
)

FAST_CODE = "def solve(xs):\n    return sum(xs)\n"
SLOW_CODE = (
    "def solve(xs):\n"
    "    total = 0\n"
    "    for x in xs:\n"
    "        total += x\n"
    "    return total\n"
)
# Wins nothing, but registered to exercise correct-only filtering.
WRONG_CODE = "def solve(xs):\n    return 0\n"
# Correct code carrying an embedded secret — the poison filter must catch it
# even though the verifier passes it.
POISON_CODE = "KEY = 'sk-abcdefghijklmnopqrstuvwx'\ndef solve(xs):\n    return sum(xs)\n"  # pragma: allowlist secret


def _tournament(tmp_path, codes):
    registry = CandidateRegistry(tmp_path / "candidates.jsonl")
    for code in codes:
        registry.register(
            CandidateRecord.build(code=code, task_id=TASK.task_id, contributor_id="t")
        )
    book = RatingBook(tmp_path / "ratings.json")
    report = run_tournament(
        TASK, registry, rounds=2, rating_book=book, rng=random.Random(3)
    )
    return registry, report


def test_winner_lands_as_pending_dataset_candidate(tmp_path):
    registry, report = _tournament(tmp_path, [FAST_CODE, SLOW_CODE, WRONG_CODE])
    trajectories = winner_trajectories(report, registry, top_k=1)
    assert len(trajectories) == 1

    dataset = DatasetStore(path=tmp_path / "dataset.jsonl")
    ledger = GuardrailLedger(tmp_path / "ledger.jsonl")
    decisions = distill_winners(
        report,
        registry,
        TASK,
        contributor=ContributorRecord("local", band=ContributorBand.B2, accepted=30),
        dataset_store=dataset,
        ledger=ledger,
        top_k=1,
    )
    assert decisions[0].admitted
    pending = dataset.pending()
    assert len(pending) == 1
    assert pending[0].status == CandidateStatus.PENDING
    assert pending[0].provenance.source_uri.startswith("forge://alg_sum/")
    assert ledger.verify_chain().ok


def test_verifier_is_recomputed_not_trusted(tmp_path):
    registry, report = _tournament(tmp_path, [WRONG_CODE, SLOW_CODE])
    # Forge the report to claim the wrong candidate is top-rated.
    wrong_id = next(
        r.candidate_id for r in registry.all() if r.code == WRONG_CODE
    )
    report.ratings_after = {wrong_id: 2400.0}
    dataset = DatasetStore(path=tmp_path / "dataset.jsonl")
    decisions = distill_winners(
        report,
        registry,
        TASK,
        contributor=ContributorRecord("local", band=ContributorBand.B2, accepted=30),
        dataset_store=dataset,
        top_k=1,
    )
    assert not decisions[0].admitted  # re-verification catches the smuggle
    assert dataset.pending() == []


def test_poisoned_winner_rejected_despite_winning(tmp_path):
    registry, report = _tournament(tmp_path, [POISON_CODE, SLOW_CODE])
    dataset = DatasetStore(path=tmp_path / "dataset.jsonl")
    decisions = distill_winners(
        report,
        registry,
        TASK,
        contributor=ContributorRecord("local", band=ContributorBand.B2, accepted=30),
        dataset_store=dataset,
        top_k=2,
    )
    poison_decisions = [
        d for d in decisions if any("secret" in r for r in d.reasons)
    ]
    assert poison_decisions and all(not d.admitted for d in poison_decisions)
    # Only the clean candidate may have landed.
    for candidate in dataset.pending():
        assert "sk-" not in str(candidate.content)


def test_b0_contributor_winner_quarantined(tmp_path):
    registry, report = _tournament(tmp_path, [FAST_CODE, SLOW_CODE])
    dataset = DatasetStore(path=tmp_path / "dataset.jsonl")
    decisions = distill_winners(
        report,
        registry,
        TASK,
        contributor=ContributorRecord("newbie", band=ContributorBand.B0),
        dataset_store=dataset,
        top_k=1,
    )
    assert decisions[0].quarantined and not decisions[0].admitted
    assert dataset.pending() == []
