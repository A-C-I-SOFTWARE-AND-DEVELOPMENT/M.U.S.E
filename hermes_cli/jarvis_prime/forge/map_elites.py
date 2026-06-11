"""MAP-Elites diversity grid for the Forge (Vol VI Part 5).

Quality-diversity, minimally: the behavior space is binned into cells; each
cell keeps only its fittest occupant (the elite). The grid preserves diverse
stepping stones a pure leaderboard would discard — elites are the seeds for
diversity-seeded tournaments and ``evolve()`` branch points.

stdlib-only; persisted as one JSON file under the forge directory.
"""

from __future__ import annotations

import json
import os
import random
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional

from hermes_cli.jarvis_prime.guardrail_evidence import GuardrailLedger

from . import KIND_FORGE_ELITE, forge_dir

# v1 behavior space for the algorithms lane: (opcount, code length), both
# normalized into [0, 1) by these soft upper bounds before binning.
DEFAULT_BOUNDS: tuple[tuple[float, float], ...] = ((0.0, 500.0), (0.0, 4000.0))
DEFAULT_BINS_PER_DIM = 8


@dataclass(frozen=True)
class BehaviorDescriptor:
    features: tuple[float, ...]


def bin_descriptor(
    descriptor: BehaviorDescriptor,
    *,
    bins_per_dim: int,
    bounds: tuple[tuple[float, float], ...],
) -> tuple[int, ...]:
    """Clamp each feature into its bounds and bin it. Deterministic."""

    if len(descriptor.features) != len(bounds):
        raise ValueError(
            f"descriptor has {len(descriptor.features)} features, bounds cover {len(bounds)}"
        )
    cell: list[int] = []
    for value, (low, high) in zip(descriptor.features, bounds):
        span = high - low
        if span <= 0:
            raise ValueError("bounds must have positive span")
        normalized = (min(max(value, low), high) - low) / span
        cell.append(min(int(normalized * bins_per_dim), bins_per_dim - 1))
    return tuple(cell)


@dataclass
class EliteCell:
    cell: tuple[int, ...]
    candidate_id: str
    fitness: float
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "cell": list(self.cell),
            "candidate_id": self.candidate_id,
            "fitness": self.fitness,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "EliteCell":
        return cls(
            cell=tuple(int(c) for c in data.get("cell", [])),
            candidate_id=str(data.get("candidate_id", "")),
            fitness=float(data.get("fitness", 0.0)),
            updated_at=str(data.get("updated_at", "")),
        )


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ElitesGrid:
    """One MAP-Elites grid (argmax fitness per cell), JSON-persisted."""

    def __init__(
        self,
        *,
        bins_per_dim: int = DEFAULT_BINS_PER_DIM,
        bounds: tuple[tuple[float, float], ...] = DEFAULT_BOUNDS,
        path: Optional[Path] = None,
        ledger: Optional[GuardrailLedger] = None,
    ) -> None:
        self.bins_per_dim = bins_per_dim
        self.bounds = bounds
        self.path = Path(path) if path is not None else self.default_path()
        self.ledger = ledger
        self._cells: dict[tuple[int, ...], EliteCell] = {}
        self._load()

    @staticmethod
    def default_path() -> Path:
        return forge_dir() / "elites.json"

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        for entry in data.get("cells", []):
            try:
                elite = EliteCell.from_dict(entry)
            except (TypeError, ValueError):
                continue
            self._cells[elite.cell] = elite

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        body = {
            "bins_per_dim": self.bins_per_dim,
            "bounds": [list(b) for b in self.bounds],
            "cells": [c.to_dict() for c in self._cells.values()],
        }
        self.path.write_text(
            json.dumps(body, sort_keys=True, indent=2) + "\n", encoding="utf-8"
        )
        try:
            os.chmod(self.path, 0o600)
        except OSError:  # pragma: no cover
            pass

    def consider(
        self,
        candidate_id: str,
        descriptor: BehaviorDescriptor,
        fitness: float,
    ) -> bool:
        """Offer a candidate to its cell; keep the argmax. True if elite changed."""

        cell = bin_descriptor(descriptor, bins_per_dim=self.bins_per_dim, bounds=self.bounds)
        incumbent = self._cells.get(cell)
        if incumbent is not None and incumbent.fitness >= fitness:
            return False
        self._cells[cell] = EliteCell(
            cell=cell, candidate_id=candidate_id, fitness=fitness, updated_at=_utc_iso()
        )
        self._save()
        if self.ledger is not None:
            self.ledger.append(
                KIND_FORGE_ELITE,
                candidate_id,
                {
                    "cell": list(cell),
                    "fitness": fitness,
                    "replaced": incumbent.candidate_id if incumbent else None,
                },
            )
        return True

    def cells(self) -> list[EliteCell]:
        return sorted(self._cells.values(), key=lambda c: c.cell)

    def coverage(self) -> float:
        total = self.bins_per_dim ** len(self.bounds)
        return len(self._cells) / total if total else 0.0

    def qd_score(self) -> float:
        """Quality-diversity score: total fitness held across the grid."""

        return sum(c.fitness for c in self._cells.values())

    def sample_elite(self, rng: Optional[random.Random] = None) -> Optional[EliteCell]:
        if not self._cells:
            return None
        chooser = rng or random
        return chooser.choice(self.cells())


__all__ = [
    "DEFAULT_BOUNDS",
    "DEFAULT_BINS_PER_DIM",
    "BehaviorDescriptor",
    "bin_descriptor",
    "EliteCell",
    "ElitesGrid",
]
