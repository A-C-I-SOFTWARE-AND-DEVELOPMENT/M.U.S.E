"""Kanban-style worker — focuses on task decomposition."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from hermes_cli.workers.base import Worker, WorkerResult

if TYPE_CHECKING:  # pragma: no cover
    from hermes_cli.orchestrator import Task


class KanbanWorker(Worker):
    name = "kanban"
    role = "decomposer"

    def _execute(self, task: "Task", worktree: Path) -> WorkerResult:
        sentences = [s.strip() for s in task.prompt.replace("\n", " ").split(".") if s.strip()]
        steps = sentences[:5] or [task.title]
        body = (
            "Decompose the task into ordered, independent steps:\n"
            + "\n".join(f"  {i + 1}. {step}" for i, step in enumerate(steps))
        )
        return self._proposal_template(task, body, score_hint=0.65)
