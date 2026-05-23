"""Deterministic scoring rubric for worker outputs.

We score each worker's directory on a small set of signals and pick the
highest total. Weights are chosen so that a *failed* worker with a huge
diff loses to a *successful* worker with a small one, and ties break by
worker name so the choice is reproducible.

The rubric is intentionally simple and inspection-friendly — it's the
kind of thing a human reviewer would do at a glance before merging.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any


@dataclass
class ScoreBreakdown:
    worker: str
    success: float
    diff_size: float
    files_changed: float
    log_quality: float
    total: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


WEIGHT_SUCCESS = 100.0
WEIGHT_FILES_CHANGED = 10.0
WEIGHT_DIFF_SIZE = 0.01
WEIGHT_LOG_QUALITY = 5.0

# A diff that touches more than this many lines is treated as
# diminishing-returns (we don't keep rewarding mega-diffs forever).
DIFF_SIZE_CAP = 2000
# Same for files-changed: spreading edits over a few files is good, but
# blasting every file in the repo isn't.
FILES_CHANGED_CAP = 10


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _count_diff_lines(diff: str) -> int:
    n = 0
    for line in diff.splitlines():
        if not line:
            continue
        c = line[0]
        if c in ("+", "-") and not line.startswith(("+++", "---")):
            n += 1
    return n


def _log_quality(log: str) -> float:
    """Cheap, deterministic heuristic in [0,1]: rewards non-empty,
    structured-looking logs without crash markers."""
    if not log.strip():
        return 0.0
    score = 0.5
    bad = ("Traceback (most recent call last)", "panicked at", "fatal error")
    if any(m in log for m in bad):
        score -= 0.4
    if "DONE" in log or "Applied" in log or "Modified" in log:
        score += 0.3
    return max(0.0, min(1.0, score))


def score_worker(worker_dir: Path) -> ScoreBreakdown:
    """Score a single ``<job>/workers/<name>/`` directory."""

    worker_dir = Path(worker_dir)
    name = worker_dir.name
    result = _read_json(worker_dir / "result.json")
    status = _read_json(worker_dir / "status.json")
    diff_path = worker_dir / "output.diff"
    log_path = worker_dir / "log.txt"

    diff_text = diff_path.read_text(encoding="utf-8") if diff_path.exists() else ""
    log_text = log_path.read_text(encoding="utf-8") if log_path.exists() else ""

    success = bool(result.get("success")) and status.get("status") == "done"
    files_changed = int(result.get("files_changed") or 0)
    diff_lines = _count_diff_lines(diff_text)
    lq = _log_quality(log_text)

    success_score = WEIGHT_SUCCESS if success else 0.0
    files_score = WEIGHT_FILES_CHANGED * min(files_changed, FILES_CHANGED_CAP)
    diff_score = WEIGHT_DIFF_SIZE * min(diff_lines, DIFF_SIZE_CAP)
    log_score = WEIGHT_LOG_QUALITY * lq

    # Penalize zero-effect "successful" runs — if the worker said "OK"
    # but produced no diff, that's worth less than one that actually
    # changed code.
    if success and files_changed == 0 and diff_lines == 0:
        success_score *= 0.5

    total = success_score + files_score + diff_score + log_score
    return ScoreBreakdown(
        worker=name,
        success=success_score,
        diff_size=diff_score,
        files_changed=files_score,
        log_quality=log_score,
        total=round(total, 6),
    )


def select_best(job_dir: Path) -> tuple[str | None, ScoreBreakdown | None]:
    """Inspect ``<job>/workers/*`` and return the highest-scoring worker.

    Ties break alphabetically by name so the selection is reproducible.
    """
    job_dir = Path(job_dir)
    workers_dir = job_dir / "workers"
    if not workers_dir.is_dir():
        return None, None
    scored = [score_worker(d) for d in sorted(workers_dir.iterdir()) if d.is_dir()]
    if not scored:
        return None, None
    scored.sort(key=lambda s: (-s.total, s.worker))
    best = scored[0]
    if best.total <= 0:
        return None, best
    return best.worker, best


__all__ = ["ScoreBreakdown", "score_worker", "select_best"]
