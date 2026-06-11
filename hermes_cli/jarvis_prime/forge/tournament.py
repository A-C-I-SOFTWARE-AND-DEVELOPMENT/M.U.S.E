"""Forge tournaments: verifier-judged duels with Glicko-2 matchmaking.

A duel between two registered candidates is decided **only** by the
executable verifier: correctness against held-out cases hard-gates (a correct
candidate always beats an incorrect one), and among correct candidates the
deterministic op-count decides (lower wins). No self-reports, no model judge.

Candidates are referenced exclusively through
:meth:`~hermes_cli.jarvis_prime.forge.registry.CandidateRegistry.resolve`
(resolve-or-fail) and verifier scores are computed locally and cached for the
tournament run — a peer's claimed results are never trusted.
"""

from __future__ import annotations

import json
import os
import random
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional

from hermes_cli.jarvis_prime.guardrail_evidence import GuardrailLedger
from hermes_cli.jarvis_prime.research_fabric.archive.store import ArchiveStore, new_member
from hermes_cli.jarvis_prime.research_fabric.verifier.algorithms import (
    AlgorithmTask,
    measure_opcount,
    score_algorithm_candidate,
)

from . import KIND_FORGE_DUEL, KIND_FORGE_RATING, forge_dir
from .glicko2 import DRAW, LOSS, WIN, GlickoRating, update_rating
from .map_elites import BehaviorDescriptor, ElitesGrid
from .registry import CandidateRecord, CandidateRegistry


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class RatingBook:
    """JSON-persisted candidate_id -> (GlickoRating, games played)."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = Path(path) if path is not None else self.default_path()
        self._ratings: dict[str, GlickoRating] = {}
        self._games: dict[str, int] = {}
        self._load()

    @staticmethod
    def default_path() -> Path:
        return forge_dir() / "ratings.json"

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        for cid, entry in dict(data.get("ratings", {})).items():
            self._ratings[str(cid)] = GlickoRating.from_dict(entry)
            self._games[str(cid)] = int(entry.get("games", 0))

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        body = {
            "ratings": {
                cid: {**rating.to_dict(), "games": self._games.get(cid, 0)}
                for cid, rating in self._ratings.items()
            }
        }
        self.path.write_text(
            json.dumps(body, sort_keys=True, indent=2) + "\n", encoding="utf-8"
        )
        try:
            os.chmod(self.path, 0o600)
        except OSError:  # pragma: no cover
            pass

    def get(self, candidate_id: str) -> GlickoRating:
        return self._ratings.get(candidate_id, GlickoRating())

    def games(self, candidate_id: str) -> int:
        return self._games.get(candidate_id, 0)

    def put(self, candidate_id: str, rating: GlickoRating, *, games_delta: int = 0) -> None:
        self._ratings[candidate_id] = rating
        self._games[candidate_id] = self._games.get(candidate_id, 0) + games_delta
        self._save()

    def all(self) -> dict[str, GlickoRating]:
        return dict(self._ratings)


@dataclass(frozen=True)
class DuelResult:
    duel_id: str
    task_id: str
    a: str  # candidate ids — duels reference, never carry, code
    b: str
    score_a: float  # 1.0 win / 0.5 draw / 0.0 loss, from a's perspective
    a_correct: bool
    b_correct: bool
    a_opcount: Optional[int]
    b_opcount: Optional[int]
    reason: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "duel_id": self.duel_id,
            "task_id": self.task_id,
            "a": self.a,
            "b": self.b,
            "score_a": self.score_a,
            "a_correct": self.a_correct,
            "b_correct": self.b_correct,
            "a_opcount": self.a_opcount,
            "b_opcount": self.b_opcount,
            "reason": self.reason,
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class CandidateEvaluation:
    """One locally computed verifier evaluation, cached per tournament."""

    correct: bool
    opcount: Optional[int]
    correctness: float


def evaluate_candidate(task: AlgorithmTask, record: CandidateRecord) -> CandidateEvaluation:
    score = score_algorithm_candidate(record.code, task)
    opcount = measure_opcount(record.code, task) if score.accepted else None
    return CandidateEvaluation(
        correct=score.accepted, opcount=opcount, correctness=score.correctness
    )


def judge_duel(
    task: AlgorithmTask,
    a: CandidateRecord,
    b: CandidateRecord,
    *,
    eval_a: Optional[CandidateEvaluation] = None,
    eval_b: Optional[CandidateEvaluation] = None,
) -> DuelResult:
    """Verifier as the only judge: correctness hard-gates, op-count decides."""

    ea = eval_a or evaluate_candidate(task, a)
    eb = eval_b or evaluate_candidate(task, b)

    if ea.correct and not eb.correct:
        score_a, reason = WIN, "a correct, b incorrect"
    elif eb.correct and not ea.correct:
        score_a, reason = LOSS, "b correct, a incorrect"
    elif not ea.correct and not eb.correct:
        score_a, reason = DRAW, "both incorrect (draw at zero)"
    elif ea.opcount is not None and eb.opcount is not None and ea.opcount != eb.opcount:
        if ea.opcount < eb.opcount:
            score_a, reason = WIN, f"both correct; a op-count {ea.opcount} < {eb.opcount}"
        else:
            score_a, reason = LOSS, f"both correct; b op-count {eb.opcount} < {ea.opcount}"
    else:
        score_a, reason = DRAW, "both correct; equal op-count"

    return DuelResult(
        duel_id=f"duel_{uuid.uuid4().hex[:16]}",
        task_id=task.task_id,
        a=a.candidate_id,
        b=b.candidate_id,
        score_a=score_a,
        a_correct=ea.correct,
        b_correct=eb.correct,
        a_opcount=ea.opcount,
        b_opcount=eb.opcount,
        reason=reason,
        created_at=_utc_iso(),
    )


def match_pairs(
    rating_book: RatingBook,
    candidate_ids: list[str],
    *,
    rng: Optional[random.Random] = None,
) -> list[tuple[str, str]]:
    """Closest-rating (adjacent) pairing; ties shuffled; odd one sits out."""

    chooser = rng or random.Random()
    shuffled = list(candidate_ids)
    chooser.shuffle(shuffled)  # break exact-rating ties non-positionally
    ordered = sorted(shuffled, key=lambda cid: -rating_book.get(cid).rating)
    return [(ordered[i], ordered[i + 1]) for i in range(0, len(ordered) - 1, 2)]


@dataclass
class TournamentReport:
    task_id: str
    rounds: int
    duels: list[DuelResult] = field(default_factory=list)
    ratings_before: dict[str, float] = field(default_factory=dict)
    ratings_after: dict[str, float] = field(default_factory=dict)
    elites_updated: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "rounds": self.rounds,
            "duels": [d.to_dict() for d in self.duels],
            "ratings_before": {k: round(v, 2) for k, v in self.ratings_before.items()},
            "ratings_after": {k: round(v, 2) for k, v in self.ratings_after.items()},
            "elites_updated": self.elites_updated,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "TournamentReport":
        report = cls(
            task_id=str(data.get("task_id", "")),
            rounds=int(data.get("rounds", 0)),
            ratings_before={k: float(v) for k, v in dict(data.get("ratings_before", {})).items()},
            ratings_after={k: float(v) for k, v in dict(data.get("ratings_after", {})).items()},
            elites_updated=int(data.get("elites_updated", 0)),
        )
        for d in data.get("duels", []):
            report.duels.append(
                DuelResult(
                    duel_id=str(d.get("duel_id", "")),
                    task_id=str(d.get("task_id", "")),
                    a=str(d.get("a", "")),
                    b=str(d.get("b", "")),
                    score_a=float(d.get("score_a", 0.5)),
                    a_correct=bool(d.get("a_correct", False)),
                    b_correct=bool(d.get("b_correct", False)),
                    a_opcount=d.get("a_opcount"),
                    b_opcount=d.get("b_opcount"),
                    reason=str(d.get("reason", "")),
                    created_at=str(d.get("created_at", "")),
                )
            )
        return report


def run_tournament(
    task: AlgorithmTask,
    registry: CandidateRegistry,
    *,
    rounds: int = 1,
    rating_book: Optional[RatingBook] = None,
    elites: Optional[ElitesGrid] = None,
    ledger: Optional[GuardrailLedger] = None,
    archive: Optional[ArchiveStore] = None,
    rng: Optional[random.Random] = None,
) -> TournamentReport:
    """Run ``rounds`` of matched duels over the task's registered candidates."""

    book = rating_book or RatingBook()
    candidate_ids = [r.candidate_id for r in registry.for_task(task.task_id)]
    report = TournamentReport(
        task_id=task.task_id,
        rounds=rounds,
        ratings_before={cid: book.get(cid).rating for cid in candidate_ids},
    )
    if len(candidate_ids) < 2:
        report.ratings_after = dict(report.ratings_before)
        return report

    # Verifier scores are deterministic per (candidate, task): evaluate once.
    evaluations: dict[str, CandidateEvaluation] = {
        cid: evaluate_candidate(task, registry.resolve(cid)) for cid in candidate_ids
    }

    for _round in range(rounds):
        for cid_a, cid_b in match_pairs(book, candidate_ids, rng=rng):
            record_a, record_b = registry.resolve(cid_a), registry.resolve(cid_b)
            duel = judge_duel(
                task,
                record_a,
                record_b,
                eval_a=evaluations[cid_a],
                eval_b=evaluations[cid_b],
            )
            report.duels.append(duel)
            if ledger is not None:
                ledger.append(KIND_FORGE_DUEL, duel.duel_id, duel.to_dict())

            rating_a, rating_b = book.get(cid_a), book.get(cid_b)
            new_a = update_rating(rating_a, [(rating_b, duel.score_a)])
            new_b = update_rating(rating_b, [(rating_a, 1.0 - duel.score_a)])
            book.put(cid_a, new_a, games_delta=1)
            book.put(cid_b, new_b, games_delta=1)
            if ledger is not None:
                ledger.append(
                    KIND_FORGE_RATING,
                    duel.duel_id,
                    {
                        cid_a: new_a.to_dict(),
                        cid_b: new_b.to_dict(),
                        "score_a": duel.score_a,
                    },
                )

    # Feed correct candidates to the diversity grid; archive the frontier.
    for cid, evaluation in evaluations.items():
        if not evaluation.correct or evaluation.opcount is None:
            continue
        record = registry.resolve(cid)
        if elites is not None:
            descriptor = BehaviorDescriptor(
                features=(float(evaluation.opcount), float(len(record.code)))
            )
            # Fitness: fewer ops is fitter; bounded into (0, 1].
            fitness = 1.0 / (1.0 + evaluation.opcount)
            if elites.consider(cid, descriptor, fitness):
                report.elites_updated += 1
        if archive is not None:
            archive.add(
                new_member(
                    parent_id=None,
                    config={
                        "candidate_id": cid,
                        "task_id": task.task_id,
                        "opcount": evaluation.opcount,
                        "role": "forge_winner",
                    },
                    composite=evaluation.correctness,
                    domain_scores={"correctness": evaluation.correctness},
                    note=f"forge tournament candidate (op-count {evaluation.opcount})",
                )
            )

    report.ratings_after = {cid: book.get(cid).rating for cid in candidate_ids}
    return report


__all__ = [
    "RatingBook",
    "DuelResult",
    "CandidateEvaluation",
    "evaluate_candidate",
    "judge_duel",
    "match_pairs",
    "TournamentReport",
    "run_tournament",
]
