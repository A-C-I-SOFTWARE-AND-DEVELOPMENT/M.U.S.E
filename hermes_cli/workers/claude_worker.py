"""Claude-style worker — focuses on architectural reasoning."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from hermes_cli.workers.base import Worker, WorkerResult

if TYPE_CHECKING:  # pragma: no cover
    from hermes_cli.orchestrator import Task


class ClaudeWorker(Worker):
    name = "claude"
    role = "architect"

    def _execute(self, task: "Task", worktree: Path) -> WorkerResult:
        files = self._scan_repo(worktree, limit=200)
        md_count = sum(1 for p in files if p.suffix == ".md")
        body = (
            f"Reason about the architectural impact of: {task.title}. "
            f"Repo has {md_count} markdown docs to keep in sync with the change. "
            "Surface failure modes, identify risk-bearing boundaries, and "
            "propose explicit invariants before editing code."
        )
        return self._proposal_template(task, body, score_hint=0.78)
