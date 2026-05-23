"""Enterprise-council-style worker — focuses on policy and review."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from hermes_cli.workers.base import Worker, WorkerResult

if TYPE_CHECKING:  # pragma: no cover
    from hermes_cli.orchestrator import Task


class CouncilWorker(Worker):
    name = "council"
    role = "reviewer"

    def _execute(self, task: "Task", worktree: Path) -> WorkerResult:
        # Use a cheap, local heuristic: presence of policy artifacts.
        security_hits = self._safe_grep(worktree, "SECURITY")
        body = (
            f"Apply council review heuristics to: {task.title}. "
            f"Found {security_hits} files referencing SECURITY conventions. "
            "Flag any change that crosses a boundary marked by policy, "
            "audit, or judge modules; require explicit dual sign-off."
        )
        return self._proposal_template(task, body, score_hint=0.74)
