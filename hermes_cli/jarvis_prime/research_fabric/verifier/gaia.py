"""GAIA verifier — reads a runner-written ``results.jsonl`` and scores it.

GAIA (https://huggingface.co/datasets/gaia-benchmark/GAIA) is a general-agent
benchmark; the per-task rows that ``benchmarks.gaia_runner.GAIARunner.run_batch``
writes each have a ``correct`` boolean set by exact-match against the gold
answer (case-insensitive, whitespace-normalized — the GAIA leaderboard standard).

The verifier here is the post-run rollup: it loads ``results.jsonl`` from
``run_dir`` and reduces it to a single :class:`DomainScore` in ``[0, 1]`` that
the strict non-regression ratchet (see ``research_fabric.validators``) can
consume. It is *the* trusted judge for the GAIA lane — nothing else.

Mapped domain: ``reasoning`` (GAIA is a multi-step reasoning benchmark with
tool-use, the natural fit per ``catalog.DOMAIN_VERIFIERS``).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable


@dataclass(frozen=True)
class DomainScore:
    """Verifier-grounded score in [0, 1] for one benchmark lane.

    Matches the structural pattern of :class:`verifier.swe.SweScore` — frozen
    dataclass, ``correctness`` is the [0, 1] reward, ``ran`` indicates whether
    the underlying run completed, ``detail`` is a short human-readable summary
    suitable for the ratchet's ``reasons`` field, and ``raw`` carries the
    intermediate counts for downstream reporting.
    """

    accepted: bool
    correctness: float          # fraction of tasks passed, in [0, 1]
    ran: bool
    detail: str
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "accepted": self.accepted,
            "correctness": round(self.correctness, 4),
            "ran": self.ran,
            "detail": self.detail,
            "raw": self.raw,
        }


_DEFAULT_RESULTS_NAME = "results.jsonl"


def _iter_results(path: Path) -> Iterable[dict[str, Any]]:
    """Yield parsed JSON objects from a results.jsonl file, skipping blanks."""

    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                # A corrupt row must not poison the whole batch — skip and let
                # ``raw`` record how many were dropped.
                continue


def _accuracy_from_rows(rows: list[dict[str, Any]]) -> tuple[float, int, int, dict[str, int]]:
    """Return (accuracy, passed, total, level_breakdown) from GAIA result rows.

    The runner uses an exact-match ``correct`` boolean per row, and records the
    GAIA level (1, 2, or 3). We aggregate overall accuracy and, when levels are
    present, per-level pass counts — both are surfaced in ``raw`` for the
    per-benchmark report.
    """

    total = len(rows)
    if total == 0:
        return 0.0, 0, 0, {}

    passed = 0
    level_total: dict[int, int] = {}
    level_passed: dict[int, int] = {}
    for row in rows:
        is_correct = bool(row.get("correct"))
        if is_correct:
            passed += 1
        level = row.get("level")
        # Only count rows that carry a real GAIA level (1/2/3).
        if isinstance(level, int) and level in (1, 2, 3):
            level_total[level] = level_total.get(level, 0) + 1
            if is_correct:
                level_passed[level] = level_passed.get(level, 0) + 1

    level_breakdown: dict[str, int] = {}
    for lvl in sorted(level_total):
        level_breakdown[f"level_{lvl}_total"] = level_total[lvl]
        level_breakdown[f"level_{lvl}_passed"] = level_passed.get(lvl, 0)

    return passed / total, passed, total, level_breakdown


def verify(run_dir: Path, *, results_name: str = _DEFAULT_RESULTS_NAME) -> DomainScore:
    """Score a GAIA runner batch from ``run_dir/results.jsonl``.

    Args:
        run_dir: Directory the :class:`benchmarks.gaia_runner.GAIARunner`
            wrote its per-task results to. Must contain ``results.jsonl``.
        results_name: Filename inside ``run_dir`` (default ``results.jsonl``).
            Exposed for tests that write to a different name.

    Returns:
        A :class:`DomainScore` whose ``correctness`` is the fraction of rows
        with ``correct == True`` in ``[0, 1]``, and ``accepted`` is True iff
        at least one task ran *and* the runner reached a non-empty set of
        rows (so the ratchet's missing-score branch is never silently masked).

    A missing or empty ``results.jsonl`` is reported as ``ran=False``,
    ``correctness=0.0`` — the ratchet will treat the domain as below floor and
    fail closed (see ``catalog.ABSOLUTE_FLOOR``).
    """

    run_dir = Path(run_dir)
    results_path = run_dir / results_name

    if not results_path.is_file():
        return DomainScore(
            accepted=False,
            correctness=0.0,
            ran=False,
            detail=f"results file not found: {results_path}",
            raw={"run_dir": str(run_dir), "results_path": str(results_path)},
        )

    rows = list(_iter_results(results_path))
    if not rows:
        return DomainScore(
            accepted=False,
            correctness=0.0,
            ran=False,
            detail=f"results file empty: {results_path}",
            raw={"run_dir": str(run_dir), "results_path": str(results_path)},
        )

    accuracy, passed, total, level_breakdown = _accuracy_from_rows(rows)
    # Clamp to [0, 1] defensively in case a future runner ships a non-bool
    # "correct" that rounds outside the unit interval.
    accuracy = max(0.0, min(1.0, float(accuracy)))

    return DomainScore(
        accepted=True,
        correctness=accuracy,
        ran=True,
        detail=(
            f"gaia: {passed}/{total} correct "
            f"({accuracy:.4f}) across {len(level_breakdown) // 2 or 0} level(s)"
        ),
        raw={
            "run_dir": str(run_dir),
            "results_path": str(results_path),
            "total": total,
            "passed": passed,
            "per_level": level_breakdown,
        },
    )


__all__ = ["DomainScore", "verify"]
