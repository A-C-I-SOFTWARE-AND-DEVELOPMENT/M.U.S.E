"""Model scorecards — pick models by measured outcomes, not hype.

A scorecard accumulates the metrics that actually matter for an autonomous
coding partner and lets the router rank models by a composite score:

- coding_success_rate
- test_pass_rate
- repair_success_rate
- hallucination_correction_rate
- latency_seconds (lower is better)
- cost_per_task (lower is better)
- owner_interruption_count (lower is better)

Scorecards are append-only samples persisted as JSONL; the aggregate is
recomputed from samples so history is auditable and never silently rewritten.
This is scoped to *local/open-weight model selection* (Phase 6) and is distinct
from any worker-output scorecard elsewhere in the tree.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

# Weights for the composite. Quality signals are rewarded; latency/cost/
# interruptions are penalised. Tunable, but constant so ranking is reproducible.
COMPOSITE_WEIGHTS = {
    "coding_success_rate": 0.30,
    "test_pass_rate": 0.25,
    "repair_success_rate": 0.20,
    "hallucination_correction_rate": 0.15,
    # Penalties (subtracted after normalization):
    "latency_penalty": 0.05,
    "cost_penalty": 0.03,
    "interruption_penalty": 0.02,
}


@dataclass(frozen=True)
class ScorecardSample:
    model: str
    coding_success: bool
    tests_passed: bool
    repair_succeeded: Optional[bool]  # None when no repair was attempted
    hallucination_corrected: Optional[bool]
    latency_seconds: float
    cost: float
    owner_interruptions: int
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, object]:
        return {
            "model": self.model,
            "coding_success": self.coding_success,
            "tests_passed": self.tests_passed,
            "repair_succeeded": self.repair_succeeded,
            "hallucination_corrected": self.hallucination_corrected,
            "latency_seconds": self.latency_seconds,
            "cost": self.cost,
            "owner_interruptions": self.owner_interruptions,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, object]) -> "ScorecardSample":
        return cls(
            model=str(d["model"]),
            coding_success=bool(d.get("coding_success")),
            tests_passed=bool(d.get("tests_passed")),
            repair_succeeded=_opt_bool(d.get("repair_succeeded")),
            hallucination_corrected=_opt_bool(d.get("hallucination_corrected")),
            latency_seconds=float(d.get("latency_seconds", 0.0)),
            cost=float(d.get("cost", 0.0)),
            owner_interruptions=int(d.get("owner_interruptions", 0)),
            created_at=str(d.get("created_at", "")),
        )


@dataclass(frozen=True)
class Scorecard:
    model: str
    samples: int
    coding_success_rate: float
    test_pass_rate: float
    repair_success_rate: float
    hallucination_correction_rate: float
    avg_latency_seconds: float
    avg_cost: float
    avg_owner_interruptions: float

    def composite(self, *, latency_ref: float = 30.0, cost_ref: float = 1.0) -> float:
        """A single 0..1-ish score. Higher is better.

        Penalties are normalised against reference values so a slow/expensive
        model is dragged down without dominating the quality signals.
        """

        w = COMPOSITE_WEIGHTS
        score = (
            w["coding_success_rate"] * self.coding_success_rate
            + w["test_pass_rate"] * self.test_pass_rate
            + w["repair_success_rate"] * self.repair_success_rate
            + w["hallucination_correction_rate"] * self.hallucination_correction_rate
        )
        latency_norm = (
            min(1.0, self.avg_latency_seconds / latency_ref) if latency_ref else 0.0
        )
        cost_norm = min(1.0, self.avg_cost / cost_ref) if cost_ref else 0.0
        interruption_norm = min(1.0, self.avg_owner_interruptions / 3.0)
        score -= w["latency_penalty"] * latency_norm
        score -= w["cost_penalty"] * cost_norm
        score -= w["interruption_penalty"] * interruption_norm
        return round(score, 6)

    def to_dict(self) -> dict[str, object]:
        d = {
            "model": self.model,
            "samples": self.samples,
            "coding_success_rate": round(self.coding_success_rate, 4),
            "test_pass_rate": round(self.test_pass_rate, 4),
            "repair_success_rate": round(self.repair_success_rate, 4),
            "hallucination_correction_rate": round(
                self.hallucination_correction_rate, 4
            ),
            "avg_latency_seconds": round(self.avg_latency_seconds, 4),
            "avg_cost": round(self.avg_cost, 6),
            "avg_owner_interruptions": round(self.avg_owner_interruptions, 4),
        }
        d["composite"] = self.composite()
        return d


@dataclass
class ScorecardStore:
    """Append-only JSONL store of scorecard samples."""

    path: Path

    @classmethod
    def default(cls) -> "ScorecardStore":
        home = Path.home() / ".hermes" / "model_scorecards.jsonl"
        return cls(path=home)

    def record(self, sample: ScorecardSample) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(sample.to_dict(), sort_keys=True) + "\n")

    def samples(self) -> list[ScorecardSample]:
        if not self.path.exists():
            return []
        out: list[ScorecardSample] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                out.append(ScorecardSample.from_dict(json.loads(line)))
            except (json.JSONDecodeError, KeyError, ValueError):
                continue  # tolerate a corrupt line; never crash the router
        return out

    def scorecard(self, model: str) -> Optional[Scorecard]:
        rows = [s for s in self.samples() if s.model == model]
        return aggregate(model, rows)

    def all_scorecards(self) -> list[Scorecard]:
        by_model: dict[str, list[ScorecardSample]] = {}
        for s in self.samples():
            by_model.setdefault(s.model, []).append(s)
        cards = [aggregate(m, rows) for m, rows in by_model.items()]
        return [c for c in cards if c is not None]


def aggregate(model: str, rows: list[ScorecardSample]) -> Optional[Scorecard]:
    if not rows:
        return None
    n = len(rows)

    def rate(pred) -> float:
        considered = [pred(r) for r in rows if pred(r) is not None]
        if not considered:
            return 0.0
        return sum(1 for v in considered if v) / len(considered)

    return Scorecard(
        model=model,
        samples=n,
        coding_success_rate=rate(lambda r: r.coding_success),
        test_pass_rate=rate(lambda r: r.tests_passed),
        repair_success_rate=rate(lambda r: r.repair_succeeded),
        hallucination_correction_rate=rate(lambda r: r.hallucination_corrected),
        avg_latency_seconds=sum(r.latency_seconds for r in rows) / n,
        avg_cost=sum(r.cost for r in rows) / n,
        avg_owner_interruptions=sum(r.owner_interruptions for r in rows) / n,
    )


def select_model(
    candidates: Iterable[str],
    store: ScorecardStore,
    *,
    min_samples: int = 1,
) -> Optional[str]:
    """Pick the best candidate by composite scorecard.

    Candidates with fewer than ``min_samples`` are ranked last (we don't trust
    a model we've never measured over one we have). Ties break alphabetically
    for determinism. Returns ``None`` only if ``candidates`` is empty.
    """

    cand = list(candidates)
    if not cand:
        return None
    scored: list[tuple[float, int, str]] = []
    for name in cand:
        card = store.scorecard(name)
        if card and card.samples >= min_samples:
            scored.append((card.composite(), card.samples, name))
        else:
            scored.append((-1.0, 0, name))
    scored.sort(key=lambda t: (-t[0], -t[1], t[2]))
    return scored[0][2]


def _opt_bool(value: object) -> Optional[bool]:
    if value is None:
        return None
    return bool(value)
