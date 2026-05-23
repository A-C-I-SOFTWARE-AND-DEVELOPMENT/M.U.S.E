"""Hermes orchestrator.

Coordinates a fan-out of N workers (default 6) against a single task. Each
worker runs in a sandboxed git worktree so its changes cannot collide with
the user's working tree or with siblings. Proposals are collected, scored,
merged, validated, and optionally published as a GitHub artifact.

The orchestrator is stdlib-only on purpose: it must run on a $5 VPS with
nothing pre-installed beyond Python and git.
"""

from __future__ import annotations

import concurrent.futures
import dataclasses
import json
import os
import shutil
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Iterable, Sequence

from hermes_cli.workers import ALL_WORKERS, Worker, WorkerResult


@dataclasses.dataclass(frozen=True)
class Task:
    """A unit of work fanned out across workers."""

    task_id: str
    title: str
    prompt: str
    repo_root: Path
    metadata: dict[str, Any] = dataclasses.field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "title": self.title,
            "prompt": self.prompt,
            "repo_root": str(self.repo_root),
            "metadata": self.metadata,
        }


@dataclasses.dataclass
class OrchestrationResult:
    task: Task
    proposals: list[WorkerResult]
    elapsed_seconds: float
    worktree_root: Path

    def to_dict(self) -> dict[str, Any]:
        return {
            "task": self.task.to_dict(),
            "proposals": [p.to_dict() for p in self.proposals],
            "elapsed_seconds": self.elapsed_seconds,
            "worktree_root": str(self.worktree_root),
        }


class WorktreeManager:
    """Create and tear down sandboxed git worktrees."""

    def __init__(self, repo_root: Path, base_dir: Path | None = None) -> None:
        self.repo_root = Path(repo_root).resolve()
        self.base_dir = (base_dir or self.repo_root / ".hermes" / "worktrees").resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._created: list[Path] = []

    def _git(self, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            cwd=str(cwd or self.repo_root),
            check=True,
            capture_output=True,
            text=True,
        )

    def create(self, worker_name: str, task_id: str) -> Path:
        """Create a worktree for ``worker_name`` on ``task_id``.

        Falls back to a regular directory copy if git is unavailable or the
        repo is not a git checkout — this keeps the orchestrator usable in
        unit tests and in sandboxed CI shards.
        """
        path = self.base_dir / f"{worker_name}-{task_id}"
        if path.exists():
            shutil.rmtree(path)
        try:
            branch = f"hermes/worker/{worker_name}/{task_id}"
            self._git(
                "worktree", "add", "--detach", str(path), "HEAD",
            )
            self._created.append(path)
            # Tag a deterministic branch ref for traceability; ignore if it
            # already exists from a previous run.
            try:
                self._git("branch", "-f", branch, "HEAD", cwd=path)
            except subprocess.CalledProcessError:
                pass
            return path
        except (FileNotFoundError, subprocess.CalledProcessError):
            # Pure directory copy fallback. Used in tests where the source
            # is not a git repo.
            shutil.copytree(self.repo_root, path, dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns(".git", ".hermes"))
            self._created.append(path)
            return path

    def remove(self, path: Path) -> None:
        path = Path(path)
        if not path.exists():
            return
        try:
            self._git("worktree", "remove", "--force", str(path))
        except (FileNotFoundError, subprocess.CalledProcessError):
            shutil.rmtree(path, ignore_errors=True)

    def cleanup_all(self) -> None:
        for path in list(self._created):
            self.remove(path)
        self._created.clear()


class Orchestrator:
    """Fan-out N workers across sandboxed worktrees and collect proposals."""

    def __init__(
        self,
        repo_root: Path,
        workers: Sequence[Worker] | None = None,
        max_parallel: int | None = None,
    ) -> None:
        self.repo_root = Path(repo_root).resolve()
        self.workers: list[Worker] = list(workers) if workers is not None else list(ALL_WORKERS)
        if not self.workers:
            raise ValueError("orchestrator requires at least one worker")
        self.max_parallel = max_parallel or len(self.workers)
        self.worktree_manager = WorktreeManager(self.repo_root)

    def run(self, task: Task, timeout_seconds: float = 60.0) -> OrchestrationResult:
        started = time.monotonic()
        proposals: list[WorkerResult] = []

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=self.max_parallel,
        ) as pool:
            future_to_worker: dict[concurrent.futures.Future[WorkerResult], Worker] = {}
            for worker in self.workers:
                worktree = self.worktree_manager.create(worker.name, task.task_id)
                future = pool.submit(self._run_worker, worker, task, worktree)
                future_to_worker[future] = worker

            for future in concurrent.futures.as_completed(future_to_worker, timeout=timeout_seconds * 2):
                worker = future_to_worker[future]
                try:
                    result = future.result(timeout=timeout_seconds)
                except Exception as exc:  # pragma: no cover - defensive
                    result = WorkerResult(
                        worker_name=worker.name,
                        task_id=task.task_id,
                        success=False,
                        proposal="",
                        score_hint=0.0,
                        files_touched=[],
                        log=f"worker crashed: {exc!r}",
                    )
                proposals.append(result)

        proposals.sort(key=lambda r: r.worker_name)
        elapsed = time.monotonic() - started
        return OrchestrationResult(
            task=task,
            proposals=proposals,
            elapsed_seconds=elapsed,
            worktree_root=self.worktree_manager.base_dir,
        )

    def _run_worker(self, worker: Worker, task: Task, worktree: Path) -> WorkerResult:
        return worker.execute(task, worktree)

    def cleanup(self) -> None:
        self.worktree_manager.cleanup_all()


def make_task(prompt: str, title: str | None = None, repo_root: Path | None = None) -> Task:
    """Convenience factory used by the bash entry point and tests."""
    repo = (repo_root or Path.cwd()).resolve()
    task_id = uuid.uuid4().hex[:12]
    return Task(
        task_id=task_id,
        title=title or prompt.splitlines()[0][:80],
        prompt=prompt,
        repo_root=repo,
    )


def write_result(result: OrchestrationResult, out_path: Path) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result.to_dict(), indent=2, sort_keys=True))
    return out_path
