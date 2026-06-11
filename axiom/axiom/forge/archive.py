"""MAP-Elites diversity archive, implemented from Mouret & Clune 2015
("Illuminating search spaces by mapping elites", arXiv:1504.04909).

A grid over behavior descriptors keeps exactly one elite — the
best-fitness candidate — per niche. Coverage is the fraction of
niches filled. Diversity is preserved structurally, not by luck.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Elite:
    candidate_id: str
    fitness: float
    descriptor: tuple[float, ...]
    payload: dict = field(default_factory=dict)


class MapElites:
    """Fixed-grid MAP-Elites archive."""

    def __init__(self, bins_per_dim: int, dims: int, lo: float = 0.0, hi: float = 1.0):
        self.bins_per_dim = bins_per_dim
        self.dims = dims
        self.lo = lo
        self.hi = hi
        self._grid: dict[tuple[int, ...], Elite] = {}

    def _niche(self, descriptor: tuple[float, ...]) -> tuple[int, ...]:
        if len(descriptor) != self.dims:
            raise ValueError(f"descriptor must have {self.dims} dims")
        span = self.hi - self.lo
        niche = []
        for d in descriptor:
            frac = (min(max(d, self.lo), self.hi) - self.lo) / span
            niche.append(min(self.bins_per_dim - 1, int(frac * self.bins_per_dim)))
        return tuple(niche)

    def add(
        self,
        candidate_id: str,
        fitness: float,
        descriptor: tuple[float, ...],
        payload: dict | None = None,
    ) -> bool:
        """Insert if the niche is empty or *fitness* beats the incumbent.
        Returns True iff the candidate was kept."""
        niche = self._niche(descriptor)
        incumbent = self._grid.get(niche)
        if incumbent is None or fitness > incumbent.fitness:
            self._grid[niche] = Elite(candidate_id, fitness, descriptor,
                                      payload or {})
            return True
        return False

    def elite_at(self, descriptor: tuple[float, ...]) -> Elite | None:
        return self._grid.get(self._niche(descriptor))

    def elites(self) -> list[Elite]:
        return list(self._grid.values())

    @property
    def coverage(self) -> float:
        return len(self._grid) / (self.bins_per_dim ** self.dims)
