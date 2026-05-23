"""Tests for individual worker implementations."""

from __future__ import annotations

from pathlib import Path

import pytest

from hermes_cli.orchestrator import make_task
from hermes_cli.workers import (
    ALL_WORKERS,
    ClaudeWorker,
    CodexWorker,
    CouncilWorker,
    HermesWorker,
    KanbanWorker,
    OpenCodeWorker,
)


@pytest.fixture
def worktree(tmp_path: Path) -> Path:
    root = tmp_path / "wt"
    root.mkdir()
    (root / "main.py").write_text("print('hi')\n")
    (root / "test_main.py").write_text("def test_main(): pass\n")
    (root / "README.md").write_text("# demo\n")
    (root / "SECURITY.md").write_text("Security policy\n")
    skills = root / "skills" / "demo"
    skills.mkdir(parents=True)
    (skills / "SKILL.md").write_text("---\nname: demo\n---\n")
    return root


def test_all_workers_have_unique_names() -> None:
    names = [w.name for w in ALL_WORKERS]
    assert len(names) == len(set(names))


def test_all_workers_have_six_members() -> None:
    assert len(ALL_WORKERS) == 6


@pytest.mark.parametrize("worker_cls", [
    CodexWorker, ClaudeWorker, OpenCodeWorker, KanbanWorker, CouncilWorker, HermesWorker,
])
def test_worker_produces_valid_proposal(worker_cls, worktree: Path) -> None:
    task = make_task("Improve testing.", repo_root=worktree)
    result = worker_cls().execute(task, worktree)
    assert result.success
    assert result.worker_name == worker_cls.name
    assert result.task_id == task.task_id
    assert 0.0 <= result.score_hint <= 1.0
    assert "## Summary" in result.proposal
    assert worker_cls.role in result.proposal


def test_worker_handles_missing_worktree(tmp_path: Path) -> None:
    task = make_task("x", repo_root=tmp_path)
    result = CodexWorker().execute(task, tmp_path / "does-not-exist")
    assert not result.success
    assert "missing" in result.log


def test_workers_produce_distinct_proposals(worktree: Path) -> None:
    task = make_task("Improve testing.", repo_root=worktree)
    bodies = {w.execute(task, worktree).proposal for w in ALL_WORKERS}
    # Each worker has a distinct role line, so proposals must differ.
    assert len(bodies) == len(ALL_WORKERS)
