"""Tests for hermes_cli.orchestrator."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hermes_cli.orchestrator import Orchestrator, Task, WorktreeManager, make_task, write_result
from hermes_cli.workers import ALL_WORKERS


@pytest.fixture
def fake_repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "README.md").write_text("# fake repo\n")
    (root / "main.py").write_text("print('hi')\n")
    skills = root / "skills" / "demo"
    skills.mkdir(parents=True)
    (skills / "SKILL.md").write_text("---\nname: demo\n---\n")
    return root


def test_make_task_generates_unique_id(fake_repo: Path) -> None:
    a = make_task("do the thing", repo_root=fake_repo)
    b = make_task("do the thing", repo_root=fake_repo)
    assert a.task_id != b.task_id
    assert a.title == "do the thing"


def test_worktree_manager_copy_fallback(tmp_path: Path, fake_repo: Path) -> None:
    mgr = WorktreeManager(fake_repo, base_dir=tmp_path / "wt")
    path = mgr.create("codex", "abc123")
    assert path.exists()
    assert (path / "README.md").is_file()
    mgr.cleanup_all()
    assert not path.exists()


def test_orchestrator_runs_all_workers(fake_repo: Path) -> None:
    orch = Orchestrator(repo_root=fake_repo)
    task = make_task("improve docs", repo_root=fake_repo)
    result = orch.run(task)
    orch.cleanup()

    names = sorted(p.worker_name for p in result.proposals)
    assert names == sorted(w.name for w in ALL_WORKERS)
    assert all(p.success for p in result.proposals)
    assert result.elapsed_seconds >= 0.0


def test_orchestrator_proposals_have_signature(fake_repo: Path) -> None:
    orch = Orchestrator(repo_root=fake_repo)
    task = make_task("refactor README", repo_root=fake_repo)
    result = orch.run(task)
    orch.cleanup()

    for prop in result.proposals:
        assert "**Worker:**" in prop.proposal
        assert "**Role:**" in prop.proposal
        assert "## Summary" in prop.proposal
        assert prop.metadata["fingerprint"]


def test_write_result_round_trip(fake_repo: Path, tmp_path: Path) -> None:
    orch = Orchestrator(repo_root=fake_repo)
    task = make_task("audit", repo_root=fake_repo)
    result = orch.run(task)
    orch.cleanup()

    out = tmp_path / "run.json"
    write_result(result, out)
    payload = json.loads(out.read_text())
    assert payload["task"]["task_id"] == task.task_id
    assert len(payload["proposals"]) == len(ALL_WORKERS)


def test_orchestrator_runs_with_custom_worker_subset(fake_repo: Path) -> None:
    from hermes_cli.workers import ClaudeWorker, CodexWorker

    orch = Orchestrator(repo_root=fake_repo, workers=[CodexWorker(), ClaudeWorker()])
    task = make_task("quick fix", repo_root=fake_repo)
    result = orch.run(task)
    orch.cleanup()
    assert len(result.proposals) == 2


def test_orchestrator_rejects_empty_worker_list(fake_repo: Path) -> None:
    with pytest.raises(ValueError):
        Orchestrator(repo_root=fake_repo, workers=[])
