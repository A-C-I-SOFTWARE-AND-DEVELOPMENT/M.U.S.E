"""Tests for the scoring rubric and worker selection logic."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hermes_cli.orchestrator.scoring import (
    DIFF_SIZE_CAP,
    FILES_CHANGED_CAP,
    WEIGHT_FILES_CHANGED,
    WEIGHT_SUCCESS,
    ScoreBreakdown,
    score_worker,
    select_best,
)


def _materialize_worker(
    job_dir: Path,
    name: str,
    *,
    success: bool,
    files_changed: int,
    diff: str = "",
    log: str = "",
) -> Path:
    wdir = job_dir / "workers" / name
    wdir.mkdir(parents=True, exist_ok=True)
    status = "done" if success else "failed"
    (wdir / "status.json").write_text(
        json.dumps({"worker": name, "status": status, "exit_code": 0})
    )
    (wdir / "result.json").write_text(
        json.dumps(
            {
                "worker": name,
                "success": success,
                "message": "test",
                "files_changed": files_changed,
                "exit_code": 0 if success else 2,
            }
        )
    )
    (wdir / "output.diff").write_text(diff)
    (wdir / "log.txt").write_text(log)
    return wdir


# ── score_worker ──────────────────────────────────────────────────────


def test_score_failed_worker_gets_zero_success(tmp_path: Path) -> None:
    wdir = _materialize_worker(
        tmp_path, "bad", success=False, files_changed=0,
    )
    s = score_worker(wdir)
    assert s.success == 0.0
    assert s.total >= 0.0


def test_score_successful_worker_rewards_success(tmp_path: Path) -> None:
    wdir = _materialize_worker(
        tmp_path,
        "good",
        success=True,
        files_changed=3,
        diff="--- a/x\n+++ b/x\n@@ -1 +1 @@\n-a\n+b\n",
        log="Applied edit to x\nDONE\n",
    )
    s = score_worker(wdir)
    assert s.success == WEIGHT_SUCCESS
    assert s.files_changed == WEIGHT_FILES_CHANGED * 3
    assert s.total > WEIGHT_SUCCESS


def test_score_caps_files_changed(tmp_path: Path) -> None:
    wdir = _materialize_worker(
        tmp_path,
        "spammy",
        success=True,
        files_changed=FILES_CHANGED_CAP + 50,
        diff="--- a/x\n+++ b/x\n@@ -1 +1 @@\n-a\n+b\n",
    )
    s = score_worker(wdir)
    assert s.files_changed == WEIGHT_FILES_CHANGED * FILES_CHANGED_CAP


def test_score_caps_diff_size(tmp_path: Path) -> None:
    huge = "\n".join(
        ["--- a/x", "+++ b/x", "@@ -1,1 +1,1 @@", *(["-" + str(i) for i in range(5000)])]
    )
    wdir = _materialize_worker(
        tmp_path, "huge", success=True, files_changed=1, diff=huge,
    )
    s = score_worker(wdir)
    # Diff component is capped at DIFF_SIZE_CAP * weight = 2000 * 0.01 = 20
    assert s.diff_size <= 20.0 + 1e-6


def test_score_penalizes_empty_success(tmp_path: Path) -> None:
    wdir = _materialize_worker(
        tmp_path, "lazy", success=True, files_changed=0, diff="", log="DONE",
    )
    s = score_worker(wdir)
    # The success weight is halved when no change was actually produced.
    assert s.success == WEIGHT_SUCCESS / 2


def test_score_log_quality_penalizes_traceback(tmp_path: Path) -> None:
    wdir = _materialize_worker(
        tmp_path,
        "crashy",
        success=False,
        files_changed=0,
        log="Traceback (most recent call last):\n  ...\nError\n",
    )
    s = score_worker(wdir)
    assert s.log_quality < 1.0


# ── select_best ──────────────────────────────────────────────────────


def test_select_best_picks_successful_over_failed(tmp_path: Path) -> None:
    _materialize_worker(tmp_path, "a_bad", success=False, files_changed=0)
    _materialize_worker(
        tmp_path,
        "b_good",
        success=True,
        files_changed=2,
        diff="--- a/x\n+++ b/x\n@@ -1 +1 @@\n-a\n+b\n",
    )
    winner, score = select_best(tmp_path)
    assert winner == "b_good"
    assert score is not None and score.worker == "b_good"


def test_select_best_breaks_ties_alphabetically(tmp_path: Path) -> None:
    # Two workers with identical signals — pick the alphabetically first.
    for name in ("zeta", "alpha"):
        _materialize_worker(
            tmp_path,
            name,
            success=True,
            files_changed=1,
            diff="--- a/x\n+++ b/x\n@@ -1 +1 @@\n-a\n+b\n",
            log="Applied edit to x\nDONE\n",
        )
    winner, _ = select_best(tmp_path)
    assert winner == "alpha"


def test_select_best_returns_none_when_no_workers(tmp_path: Path) -> None:
    (tmp_path / "workers").mkdir()
    winner, score = select_best(tmp_path)
    assert winner is None
    assert score is None


def test_select_best_returns_none_when_all_failed(tmp_path: Path) -> None:
    _materialize_worker(tmp_path, "x", success=False, files_changed=0)
    _materialize_worker(tmp_path, "y", success=False, files_changed=0)
    winner, score = select_best(tmp_path)
    assert winner is None
    assert score is not None  # the best (zero) breakdown is still returned


def test_score_breakdown_serializes() -> None:
    s = ScoreBreakdown(
        worker="x", success=1.0, diff_size=0.5, files_changed=0.2,
        log_quality=0.1, total=1.8,
    )
    d = s.to_dict()
    assert d["worker"] == "x"
    assert d["total"] == 1.8
