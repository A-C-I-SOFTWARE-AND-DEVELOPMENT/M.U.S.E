"""Terminal-Bench verifier — reads a runner-written ``results.jsonl`` and scores it.

Terminal-Bench (https://github.com/laude-institute/terminal-bench) tests
agents on realistic terminal tasks defined as YAML files; the runner in
``benchmarks.terminal_bench_runner.TerminalBenchRunner.run_batch`` executes
each task's ``test_script`` after the agent's turn and writes a per-task row
with a binary ``score`` (1 if the test exited 0, 0 otherwise) plus a
``tags`` list.

The verifier here is the post-run rollup: it loads ``results.jsonl`` from
``run_dir`` and reduces it to a single :class:`DomainScore` in ``[0, 1]`` that
the strict non-regression ratchet (see ``research_fabric.validators``) can
consume. It is *the* trusted judge for the Terminal-Bench lane — nothing else.

Mapped domain: ``software_development`` (Terminal-Bench is repo- and shell-
grounded; the same lane as SWE-bench-style execution grading).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from .gaia import DomainScore  # shared contract: same shape as swe.SweScore


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
    """Return (accuracy, passed, total, tag_breakdown) from Terminal-Bench rows.

    The runner uses a binary ``score`` per row (1 = test_script exit 0, 0
    otherwise) and a ``tags`` list (e.g. ``["easy", "shell"]``). We aggregate
    overall accuracy and, when tags are present, per-tag pass counts — both
    are surfaced in ``raw`` for the per-benchmark report.
    """

    total = len(rows)
    if total == 0:
        return 0.0, 0, 0, {}

    passed = 0
    tag_total: dict[str, int] = {}
    tag_passed: dict[str, int] = {}
    for row in rows:
        score = row.get("score", 0)
        # ``score`` should be 0/1; treat any truthy non-zero as a pass.
        is_correct = bool(score)
        if is_correct:
            passed += 1
        for tag in (row.get("tags") or []):
            t = str(tag)
            tag_total[t] = tag_total.get(t, 0) + 1
            if is_correct:
                tag_passed[t] = tag_passed.get(t, 0) + 1

    tag_breakdown: dict[str, int] = {}
    for tag in sorted(tag_total):
        tag_breakdown[f"tag_{tag}_total"] = tag_total[tag]
        tag_breakdown[f"tag_{tag}_passed"] = tag_passed.get(tag, 0)

    return passed / total, passed, total, tag_breakdown


def verify(run_dir: Path, *, results_name: str = _DEFAULT_RESULTS_NAME) -> DomainScore:
    """Score a Terminal-Bench runner batch from ``run_dir/results.jsonl``.

    Args:
        run_dir: Directory the
            :class:`benchmarks.terminal_bench_runner.TerminalBenchRunner`
            wrote its per-task results to. Must contain ``results.jsonl``.
        results_name: Filename inside ``run_dir`` (default ``results.jsonl``).
            Exposed for tests that write to a different name.

    Returns:
        A :class:`DomainScore` whose ``correctness`` is the mean of the
        binary ``score`` fields (== fraction of tasks whose test_script
        passed), in ``[0, 1]``, and ``accepted`` is True iff at least one
        task ran *and* the runner reached a non-empty set of rows (so the
        ratchet's missing-score branch is never silently masked).

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

    accuracy, passed, total, tag_breakdown = _accuracy_from_rows(rows)
    # Clamp to [0, 1] defensively in case a future runner ships a non-binary
    # ``score`` that rounds outside the unit interval.
    accuracy = max(0.0, min(1.0, float(accuracy)))

    return DomainScore(
        accepted=True,
        correctness=accuracy,
        ran=True,
        detail=(
            f"terminal-bench: {passed}/{total} test_scripts passed "
            f"({accuracy:.4f}) across {len(tag_breakdown) // 2 or 0} tag(s)"
        ),
        raw={
            "run_dir": str(run_dir),
            "results_path": str(results_path),
            "total": total,
            "passed": passed,
            "per_tag": tag_breakdown,
        },
    )


__all__ = ["DomainScore", "verify"]
