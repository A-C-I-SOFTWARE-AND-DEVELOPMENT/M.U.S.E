"""Latency benchmark harness.

Times a zero-argument callable across repeated iterations and reports
mean/percentile latency and throughput. Useful for benchmarking the
retrieval orchestrator end-to-end or any individual stage.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Callable, List

logger = logging.getLogger(__name__)

__all__ = ["LatencyResult", "percentile", "LatencyBenchmark"]


def percentile(samples: List[float], pct: float) -> float:
    """Return the ``pct`` percentile (0..100) via linear interpolation."""
    if not samples:
        return 0.0
    if pct <= 0:
        return min(samples)
    if pct >= 100:
        return max(samples)
    ordered = sorted(samples)
    rank = (pct / 100.0) * (len(ordered) - 1)
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    frac = rank - low
    return ordered[low] + (ordered[high] - ordered[low]) * frac


@dataclass(slots=True)
class LatencyResult:
    """Summary statistics for a latency benchmark run (milliseconds)."""

    iterations: int
    mean_ms: float
    p50_ms: float
    p95_ms: float
    p99_ms: float
    min_ms: float
    max_ms: float
    throughput_qps: float

    def as_dict(self) -> dict:
        return {
            "iterations": self.iterations,
            "mean_ms": round(self.mean_ms, 4),
            "p50_ms": round(self.p50_ms, 4),
            "p95_ms": round(self.p95_ms, 4),
            "p99_ms": round(self.p99_ms, 4),
            "min_ms": round(self.min_ms, 4),
            "max_ms": round(self.max_ms, 4),
            "throughput_qps": round(self.throughput_qps, 4),
        }


class LatencyBenchmark:
    """Run a callable repeatedly and summarise its latency distribution."""

    def __init__(self, *, warmup: int = 3) -> None:
        self._warmup = max(0, warmup)

    def run(self, fn: Callable[[], object], *, iterations: int = 50) -> LatencyResult:
        """Benchmark ``fn`` over ``iterations`` timed calls (after warmup)."""
        if iterations <= 0:
            raise ValueError("iterations must be positive")
        for _ in range(self._warmup):
            fn()
        samples_ms: List[float] = []
        for _ in range(iterations):
            start = time.perf_counter()
            fn()
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            samples_ms.append(elapsed_ms)
        total_seconds = sum(samples_ms) / 1000.0
        throughput = iterations / total_seconds if total_seconds > 0 else 0.0
        result = LatencyResult(
            iterations=iterations,
            mean_ms=sum(samples_ms) / len(samples_ms),
            p50_ms=percentile(samples_ms, 50),
            p95_ms=percentile(samples_ms, 95),
            p99_ms=percentile(samples_ms, 99),
            min_ms=min(samples_ms),
            max_ms=max(samples_ms),
            throughput_qps=throughput,
        )
        logger.info("latency benchmark: %s", result.as_dict())
        return result
