"""Hermes-native worker — leans on the local agent's existing skills."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from hermes_cli.workers.base import Worker, WorkerResult

if TYPE_CHECKING:  # pragma: no cover
    from hermes_cli.orchestrator import Task


class HermesWorker(Worker):
    name = "hermes"
    role = "skill-router"

    def _execute(self, task: "Task", worktree: Path) -> WorkerResult:
        skills_root = worktree / "skills"
        skill_count = 0
        if skills_root.is_dir():
            skill_count = sum(1 for p in skills_root.rglob("SKILL.md"))
        body = (
            f"Route to the most relevant Hermes skill for: {task.title}. "
            f"Worktree exposes {skill_count} SKILL.md descriptors. "
            "If no skill matches, propose creating one and capture the "
            "learnings into the curator's memory at session end."
        )
        return self._proposal_template(task, body, score_hint=0.69)
