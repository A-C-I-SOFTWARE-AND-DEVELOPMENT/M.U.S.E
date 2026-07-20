"""Aider-Polyglot verifier — reads a runner-written ``results.jsonl`` and scores it.

Aider's Polyglot benchmark (https://aider.chat/docs/leaderboards/) is a
multi-language code-editing suite; the runner in
``benchmarks.polyglot_runner.PolyglotRunner.run_batch`` executes each task's
test command after the agent's edit and writes a per-task row with a
``passed`` boolean (== ``test_command`` exit 0), a ``score`` (0/1, same
information), a ``language``, and the test output.

The verifier here is the post-run rollup: it loads ``results.jsonl`` from
``run_dir`` and reduces it to a single :class:`DomainScore` in ``[0, 1]`` that
the strict non-regression ratchet (see ``research_fabric.validators``) can
consume. It is *the* trusted judge for the Aider-Polyglot lane — nothing else.

Mapped domain: ``code_editing`` (Polyglot is explicitly an edit-loop,
multi-language signal; matches the SWE/Aider-Polyglot domain tag in
``catalog.BENCHMARK_CANDIDATES``).
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
    """Return (accuracy, passed, total, language_breakdown) from Polyglot rows.

    The runner uses a ``passed`` boolean per row (True iff ``test_command``
    exited 0); we accept either ``passed`` (preferred) or the redundant
    ``score`` (0/1). Each row carries a ``language`` (``python``, ``go``,
    ``javascript``, ...); we aggregate overall accuracy and per-language pass
    counts — both are surfaced in ``raw`` for the per-benchmark report.
    """

    total = len(rows)
    if total == 0:
        return 0.0, 0, 0, {}

    passed = 0
    lang_total: dict[str, int] = {}
    lang_passed: dict[str, int] = {}
    for row in rows:
        # Prefer ``passed`` (bool); fall back to ``score`` (0/1).
        if "passed" in row:
            is_correct = bool(row.get("passed"))
        else:
            is_correct = bool(row.get("score", 0))
        if is_correct:
            passed += 1
        language = row.get("language")
        if language is not None:
            lang = str(language).lower()
            lang_total[lang] = lang_total.get(lang, 0) + 1
            if is_correct:
                lang_passed[lang] = lang_passed.get(lang, 0) + 1

    language_breakdown: dict[str, int] = {}
    for lang in sorted(lang_total):
        language_breakdown[f"lang_{lang}_total"] = lang_total[lang]
        language_breakdown[f"lang_{lang}_passed"] = lang_passed.get(lang, 0)

    return passed / total, passed, total, language_breakdown


def verify(run_dir: Path, *, results_name: str = _DEFAULT_RESULTS_NAME) -> DomainScore:
    """Score an Aider-Polyglot runner batch from ``run_dir/results.jsonl``.

    Args:
        run_dir: Directory the
            :class:`benchmarks.polyglot_runner.PolyglotRunner` wrote its
            per-task results to. Must contain ``results.jsonl``.
        results_name: Filename inside ``run_dir`` (default ``results.jsonl``).
            Exposed for tests that write to a different name.

    Returns:
        A :class:`DomainScore` whose ``correctness`` is the fraction of
        tasks with ``passed == True``, in ``[0, 1]``, and ``accepted`` is
        True iff at least one task ran *and* the runner reached a non-empty
        set of rows (so the ratchet's missing-score branch is never silently
        masked).

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

    accuracy, passed, total, language_breakdown = _accuracy_from_rows(rows)
    # Clamp to [0, 1] defensively in case a future runner ships a non-bool
    # ``passed``/``score`` that rounds outside the unit interval.
    accuracy = max(0.0, min(1.0, float(accuracy)))

    return DomainScore(
        accepted=True,
        correctness=accuracy,
        ran=True,
        detail=(
            f"polyglot: {passed}/{total} tests passed "
            f"({accuracy:.4f}) across {len(language_breakdown) // 2 or 0} language(s)"
        ),
        raw={
            "run_dir": str(run_dir),
            "results_path": str(results_path),
            "total": total,
            "passed": passed,
            "per_language": language_breakdown,
        },
    )


__all__ = ["DomainScore", "verify"]
