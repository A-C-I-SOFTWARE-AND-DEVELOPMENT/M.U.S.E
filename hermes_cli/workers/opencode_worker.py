"""OpenCode-style worker — focuses on test-first changes."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from hermes_cli.workers.base import Worker, WorkerResult

if TYPE_CHECKING:  # pragma: no cover
    from hermes_cli.orchestrator import Task


class OpenCodeWorker(Worker):
    name = "opencode"
    role = "test-first"

    def _execute(self, task: "Task", worktree: Path) -> WorkerResult:
        files = self._scan_repo(worktree, limit=200)
        test_count = sum(1 for p in files if "test" in p.name and p.suffix == ".py")
        body = (
            f"Write failing tests first for: {task.title}, then make them pass. "
            f"Existing test files in worktree: {test_count}. "
            "Avoid changes that ship without a corresponding test."
        )
        return self._proposal_template(task, body, score_hint=0.70)
