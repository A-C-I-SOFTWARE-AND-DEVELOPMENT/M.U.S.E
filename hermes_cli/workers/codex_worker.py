"""Codex-style worker — focuses on small, surgical edits."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from hermes_cli.workers.base import Worker, WorkerResult

if TYPE_CHECKING:  # pragma: no cover
    from hermes_cli.orchestrator import Task


class CodexWorker(Worker):
    name = "codex"
    role = "surgical-edit"

    def _execute(self, task: "Task", worktree: Path) -> WorkerResult:
        files = self._scan_repo(worktree, limit=100)
        py_count = sum(1 for p in files if p.suffix == ".py")
        body = (
            f"Apply minimal, well-scoped patches to address: {task.title}.\n"
            f"Repo snapshot: {len(files)} files (Python: {py_count}). "
            "Prefer single-file changes; avoid sweeping refactors."
        )
        return self._proposal_template(task, body, score_hint=0.72)
