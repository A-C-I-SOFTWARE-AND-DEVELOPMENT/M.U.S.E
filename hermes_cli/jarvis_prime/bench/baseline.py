"""Latency/output baseline measurement for runners (Phase 0 / Phase 3 bench).

``measure_runner`` wraps any ``(prompt) -> completion`` runner (the Ollama
Gemma runner, the template fast path, a stub) and records per-prompt wall
latency plus a sha256 of each output — the byte-identity anchor used by the
Phase-3 flag-off regression check.
"""

from __future__ import annotations

import hashlib
import statistics
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Sequence


@dataclass(frozen=True)
class PromptMeasurement:
    prompt_sha256: str
    output_sha256: str
    output_chars: int
    latency_s: float


@dataclass(frozen=True)
class BaselineReport:
    label: str
    measurements: tuple[PromptMeasurement, ...] = field(default_factory=tuple)

    @property
    def mean_latency_s(self) -> float:
        if not self.measurements:
            return 0.0
        return statistics.fmean(m.latency_s for m in self.measurements)

    @property
    def p95_latency_s(self) -> float:
        if not self.measurements:
            return 0.0
        ordered = sorted(m.latency_s for m in self.measurements)
        idx = min(len(ordered) - 1, max(0, round(0.95 * (len(ordered) - 1))))
        return ordered[idx]

    def output_hashes(self) -> tuple[str, ...]:
        return tuple(m.output_sha256 for m in self.measurements)

    def to_markdown_row(self) -> str:
        return (
            f"| {self.label} | {len(self.measurements)} "
            f"| {self.mean_latency_s * 1000:.1f} ms | {self.p95_latency_s * 1000:.1f} ms |"
        )


def measure_runner(
    runner: Callable[[str], str],
    prompts: Sequence[str],
    *,
    label: str = "runner",
    clock: Callable[[], float] = time.perf_counter,
) -> BaselineReport:
    """Run every prompt through ``runner``; record latency + output hashes."""

    measurements: list[PromptMeasurement] = []
    for prompt in prompts:
        start = clock()
        output = runner(prompt)
        elapsed = clock() - start
        measurements.append(
            PromptMeasurement(
                prompt_sha256=hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
                output_sha256=hashlib.sha256(output.encode("utf-8")).hexdigest(),
                output_chars=len(output),
                latency_s=elapsed,
            )
        )
    return BaselineReport(label=label, measurements=tuple(measurements))


def write_report_section(path: Path, title: str, body: str) -> None:
    """Append a titled section to a markdown report (creates the file if absent)."""

    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    separator = "" if not existing or existing.endswith("\n\n") else "\n"
    path.write_text(f"{existing}{separator}## {title}\n\n{body.rstrip()}\n\n", encoding="utf-8")


__all__ = [
    "PromptMeasurement",
    "BaselineReport",
    "measure_runner",
    "write_report_section",
]
