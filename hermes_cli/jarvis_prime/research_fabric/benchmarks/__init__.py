"""Benchmark-harness layer — the "benchmark wall" loop (scale Plane 4).

Loads a benchmark *suite* (a local JSONL of task specs, in the shape real
SWE-bench / SWE-rebench / LiveCodeBench exports reduce to) and grades each task
through the existing executable verifiers (algorithms lane or repo-level SWE
lane), then aggregates **per-domain correctness** — exactly the signal the
:class:`RatchetWall` consumes to gate promotion.

It is deliberately **offline and download-free**: a spec may embed the candidate
solution to grade (deterministic, for fixtures/CI), or a live solver/fixer is
supplied to produce one. Real benchmark data is fetched separately by the
operator and pointed at via ``--suite`` / ``base_dir``; nothing here reaches the
network, and the held-out walls must never be used as a training signal.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from ..verifier.algorithms import (
    AlgorithmCase,
    AlgorithmTask,
    score_algorithm_candidate,
)
from ..verifier.swe import SweScore, SweTask, score_swe_patch

# A live solver produces algorithm code from a task; a fixer produces repo file
# content from (task, current). Both optional — specs may embed the candidate.
AlgorithmSolver = Callable[[AlgorithmTask], str]
SweFixer = Callable[[SweTask, str], str]


@dataclass(frozen=True)
class BenchmarkTaskSpec:
    task_id: str
    domain: str          # a REQUIRED_DOMAINS key, e.g. "code_generation"
    kind: str            # "algorithm" | "swe"
    payload: dict[str, Any]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BenchmarkTaskSpec":
        return cls(
            task_id=str(data["task_id"]),
            domain=str(data["domain"]),
            kind=str(data["kind"]),
            payload=dict(data.get("payload", {})),
        )


@dataclass
class TaskOutcome:
    task_id: str
    domain: str
    correctness: float
    ran: bool
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "domain": self.domain,
            "correctness": round(self.correctness, 4),
            "ran": self.ran,
            "detail": self.detail,
        }


@dataclass
class SuiteResult:
    outcomes: list[TaskOutcome] = field(default_factory=list)

    def per_domain_scores(self) -> dict[str, float]:
        by_domain: dict[str, list[float]] = {}
        for o in self.outcomes:
            by_domain.setdefault(o.domain, []).append(o.correctness)
        return {d: round(sum(v) / len(v), 4) for d, v in by_domain.items() if v}

    @property
    def resolved_rate(self) -> float:
        if not self.outcomes:
            return 0.0
        return round(sum(o.correctness for o in self.outcomes) / len(self.outcomes), 4)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_count": len(self.outcomes),
            "resolved_rate": self.resolved_rate,
            "per_domain_scores": self.per_domain_scores(),
            "outcomes": [o.to_dict() for o in self.outcomes],
        }


def load_suite(path: Path) -> list[BenchmarkTaskSpec]:
    """Load a JSONL suite (one task spec per line)."""

    specs: list[BenchmarkTaskSpec] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        specs.append(BenchmarkTaskSpec.from_dict(json.loads(line)))
    return specs


def _algorithm_task(spec: BenchmarkTaskSpec) -> AlgorithmTask:
    p = spec.payload
    return AlgorithmTask(
        task_id=spec.task_id,
        entrypoint=str(p.get("entrypoint", "solve")),
        prompt=str(p.get("prompt", "")),
        public_cases=tuple(
            AlgorithmCase(args=list(c["args"]), expected=c["expected"])
            for c in p.get("public_cases", [])
        ),
        holdout_cases=tuple(
            AlgorithmCase(args=list(c["args"]), expected=c["expected"])
            for c in p.get("holdout_cases", [])
        ),
    )


def _swe_task(spec: BenchmarkTaskSpec, base_dir: Optional[Path]) -> SweTask:
    p = spec.payload
    repo = p["repo_path"]
    if base_dir is not None and not Path(repo).is_absolute():
        repo = str((base_dir / repo).resolve())
    return SweTask(
        task_id=spec.task_id,
        repo_path=repo,
        target_path=str(p["target_path"]),
        test_command=list(p["test_command"]),
    )


def run_suite(
    specs: list[BenchmarkTaskSpec],
    *,
    solver: Optional[AlgorithmSolver] = None,
    swe_fixer: Optional[SweFixer] = None,
    base_dir: Optional[Path] = None,
) -> SuiteResult:
    """Grade every task through the executable verifiers; aggregate per domain."""

    result = SuiteResult()
    for spec in specs:
        if spec.kind == "algorithm":
            task = _algorithm_task(spec)
            candidate = spec.payload.get("candidate")
            if candidate is None and solver is not None:
                candidate = solver(task)
            if candidate is None:
                result.outcomes.append(
                    TaskOutcome(spec.task_id, spec.domain, 0.0, False, "no candidate/solver")
                )
                continue
            score = score_algorithm_candidate(candidate, task)
            result.outcomes.append(
                TaskOutcome(spec.task_id, spec.domain, score.correctness, score.ran, score.detail)
            )
        elif spec.kind == "swe":
            task = _swe_task(spec, base_dir)
            current = str(spec.payload.get("baseline", ""))
            candidate = spec.payload.get("candidate")
            if candidate is None and swe_fixer is not None:
                candidate = swe_fixer(task, current)
            if candidate is None:
                result.outcomes.append(
                    TaskOutcome(spec.task_id, spec.domain, 0.0, False, "no candidate/fixer")
                )
                continue
            sscore: SweScore = score_swe_patch(task, candidate)
            result.outcomes.append(
                TaskOutcome(spec.task_id, spec.domain, sscore.correctness, sscore.ran, sscore.detail)
            )
        else:
            result.outcomes.append(
                TaskOutcome(spec.task_id, spec.domain, 0.0, False, f"unknown kind {spec.kind!r}")
            )
    return result


__all__ = [
    "BenchmarkTaskSpec",
    "TaskOutcome",
    "SuiteResult",
    "load_suite",
    "run_suite",
    "AlgorithmSolver",
    "SweFixer",
]
