"""Tests for verifier-judged Forge tournaments."""

import random

from hermes_cli.jarvis_prime.forge import KIND_FORGE_DUEL, KIND_FORGE_RATING
from hermes_cli.jarvis_prime.forge.glicko2 import GlickoRating
from hermes_cli.jarvis_prime.forge.map_elites import ElitesGrid
from hermes_cli.jarvis_prime.forge.registry import CandidateRecord, CandidateRegistry
from hermes_cli.jarvis_prime.forge.tournament import (
    RatingBook,
    judge_duel,
    match_pairs,
    run_tournament,
)
from hermes_cli.jarvis_prime.guardrail_evidence import GuardrailLedger
from hermes_cli.jarvis_prime.research_fabric.archive.store import ArchiveStore
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
WRONG_CODE = "def solve(xs):\n    return 0\n"


def _registry(tmp_path, codes):
    registry = CandidateRegistry(tmp_path / "candidates.jsonl")
    return registry, [
        registry.register(
            CandidateRecord.build(code=code, task_id=TASK.task_id, contributor_id="t")
        ).candidate_id
        for code in codes
    ]


def test_judge_correct_beats_incorrect(tmp_path):
    registry, (fast, wrong) = _registry(tmp_path, [FAST_CODE, WRONG_CODE])
    duel = judge_duel(TASK, registry.resolve(fast), registry.resolve(wrong))
    assert duel.score_a == 1.0
    assert duel.a_correct and not duel.b_correct


def test_judge_lower_opcount_wins_among_correct(tmp_path):
    registry, (fast, slow) = _registry(tmp_path, [FAST_CODE, SLOW_CODE])
    duel = judge_duel(TASK, registry.resolve(fast), registry.resolve(slow))
    assert duel.a_correct and duel.b_correct
    assert duel.a_opcount < duel.b_opcount
    assert duel.score_a == 1.0
    assert "op-count" in duel.reason


def test_judge_identical_candidates_draw(tmp_path):
    registry, (fast,) = _registry(tmp_path, [FAST_CODE])
    record = registry.resolve(fast)
    duel = judge_duel(TASK, record, record)
    assert duel.score_a == 0.5


def test_match_pairs_adjacent_by_rating(tmp_path):
    book = RatingBook(tmp_path / "ratings.json")
    book.put("hi", GlickoRating(rating=1800.0))
    book.put("mid", GlickoRating(rating=1600.0))
    book.put("lo", GlickoRating(rating=1400.0))
    book.put("floor", GlickoRating(rating=1200.0))
    pairs = match_pairs(book, ["lo", "hi", "floor", "mid"], rng=random.Random(1))
    assert pairs == [("hi", "mid"), ("lo", "floor")]
    # Odd participant sits out.
    assert len(match_pairs(book, ["hi", "mid", "lo"], rng=random.Random(1))) == 1


def test_run_tournament_end_to_end(tmp_path):
    registry, (fast, slow, wrong) = _registry(tmp_path, [FAST_CODE, SLOW_CODE, WRONG_CODE])
    book = RatingBook(tmp_path / "ratings.json")
    ledger = GuardrailLedger(tmp_path / "ledger.jsonl")
    elites = ElitesGrid(path=tmp_path / "elites.json", ledger=ledger)
    archive = ArchiveStore(tmp_path / "archive.jsonl")

    report = run_tournament(
        TASK,
        registry,
        rounds=2,
        rating_book=book,
        elites=elites,
        ledger=ledger,
        archive=archive,
        rng=random.Random(42),
    )

    assert len(report.duels) == 2  # 3 candidates -> 1 pair/round, odd one out
    # The correct, lowest-opcount candidate never loses; ratings move sensibly.
    assert report.ratings_after[fast] >= report.ratings_before[fast]
    kinds = [r.kind for r in ledger.read_all()]
    assert kinds.count(KIND_FORGE_DUEL) == 2
    assert kinds.count(KIND_FORGE_RATING) == 2
    assert ledger.verify_chain().ok
    # Correct candidates joined the elites grid and the diversity archive.
    elite_ids = {c.candidate_id for c in elites.cells()}
    assert fast in elite_ids and wrong not in elite_ids
    assert report.elites_updated >= 1
    archived = {m.config.get("candidate_id") for m in archive.members()}
    assert fast in archived and slow in archived and wrong not in archived


def test_tournament_with_fewer_than_two_candidates(tmp_path):
    registry, _ = _registry(tmp_path, [FAST_CODE])
    report = run_tournament(TASK, registry, rating_book=RatingBook(tmp_path / "r.json"))
    assert report.duels == []
    assert report.ratings_after == report.ratings_before
