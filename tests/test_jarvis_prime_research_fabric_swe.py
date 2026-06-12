"""Tests for the SWE-style local repo verifier (real subprocess + temp repo)."""

from __future__ import annotations

import sys

from muse_cli.jarvis_prime.research_fabric.verifier.swe import (
    SweTask,
    baseline_fails,
    score_swe_patch,
)

# A test command that imports the candidate module and asserts behavior.
_TEST_CMD = [sys.executable, "-c", "import mod; assert mod.f(3) == 9; print('ok')"]


def _make_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    # Buggy: f should square, but returns the input.
    (repo / "mod.py").write_text("def f(x):\n    return x\n", encoding="utf-8")
    return repo


def _task(repo):
    return SweTask(
        task_id="square",
        repo_path=str(repo),
        target_path="mod.py",
        test_command=_TEST_CMD,
    )


def test_baseline_fails_on_bug(tmp_path) -> None:
    repo = _make_repo(tmp_path)
    assert baseline_fails(_task(repo)) is True


def test_correct_patch_passes(tmp_path) -> None:
    repo = _make_repo(tmp_path)
    score = score_swe_patch(_task(repo), "def f(x):\n    return x * x\n")
    assert score.accepted is True
    assert score.correctness == 1.0
    # The source working copy is never mutated.
    assert (repo / "mod.py").read_text(encoding="utf-8") == "def f(x):\n    return x\n"


def test_still_buggy_patch_fails(tmp_path) -> None:
    repo = _make_repo(tmp_path)
    score = score_swe_patch(_task(repo), "def f(x):\n    return x + 1\n")
    assert score.accepted is False
    assert score.correctness == 0.0


def test_missing_repo_is_handled(tmp_path) -> None:
    task = SweTask(
        task_id="x", repo_path=str(tmp_path / "nope"), target_path="mod.py", test_command=_TEST_CMD
    )
    score = score_swe_patch(task, "def f(x):\n    return x\n")
    assert score.accepted is False
    assert score.ran is False
