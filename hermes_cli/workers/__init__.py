"""Hermes orchestration workers.

Each worker takes a :class:`hermes_cli.orchestrator.Task` and a sandboxed
worktree path, and returns a :class:`WorkerResult` describing the proposal
it would submit. Workers MUST be hermetic — they never reach out to a paid
API, never read user secrets, and never modify state outside their
worktree.
"""

from __future__ import annotations

from hermes_cli.workers.base import Worker, WorkerResult
from hermes_cli.workers.claude_worker import ClaudeWorker
from hermes_cli.workers.codex_worker import CodexWorker
from hermes_cli.workers.council_worker import CouncilWorker
from hermes_cli.workers.hermes_worker import HermesWorker
from hermes_cli.workers.kanban_worker import KanbanWorker
from hermes_cli.workers.opencode_worker import OpenCodeWorker

ALL_WORKERS: tuple[Worker, ...] = (
    CodexWorker(),
    ClaudeWorker(),
    OpenCodeWorker(),
    KanbanWorker(),
    CouncilWorker(),
    HermesWorker(),
)

__all__ = [
    "ALL_WORKERS",
    "ClaudeWorker",
    "CodexWorker",
    "CouncilWorker",
    "HermesWorker",
    "KanbanWorker",
    "OpenCodeWorker",
    "Worker",
    "WorkerResult",
]
