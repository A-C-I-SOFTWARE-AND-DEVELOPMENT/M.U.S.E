"""Worker adapters for the Hermes orchestration system.

A worker is an external AI coding tool (Codex, Claude Code, Aider, Goose, or
the bundled local Hermes agent) that we can hand a job folder to and that
produces an output diff plus a log we can score and merge.

The orchestrator runs multiple workers in parallel against the same job,
scores their outputs (``hermes_cli.orchestrator.scoring``), optionally merges
them (``hermes_cli.orchestrator.merge_engine``), runs validation gates
(``hermes_cli.orchestrator.validation_gates``) and publishes the winner
(``hermes_cli.orchestrator.github_publisher``).

All workers share a common contract defined in :mod:`hermes_cli.workers.base`.
Workers must never assume network access or a real subscription at test
time — every adapter accepts an injectable ``runner`` callable so tests
can stub the external subprocess invocation without ever calling out.
"""

from hermes_cli.workers.base import (
    JobContext,
    WorkerAdapter,
    WorkerResult,
    WorkerStatus,
)
from hermes_cli.workers.aider import AiderWorker
from hermes_cli.workers.claude_code import ClaudeCodeWorker
from hermes_cli.workers.codex import CodexWorker
from hermes_cli.workers.goose import GooseWorker
from hermes_cli.workers.hermes_local import HermesLocalWorker

ALL_WORKERS: list[type[WorkerAdapter]] = [
    HermesLocalWorker,
    CodexWorker,
    ClaudeCodeWorker,
    AiderWorker,
    GooseWorker,
]


def get_worker(name: str) -> type[WorkerAdapter]:
    """Look up a worker class by its ``name`` field. Raises KeyError."""
    for cls in ALL_WORKERS:
        if cls.name == name:
            return cls
    raise KeyError(f"unknown worker: {name!r}")


def detect_available() -> list[type[WorkerAdapter]]:
    """Return the subset of workers whose external binary is on PATH.

    HermesLocalWorker is always considered available because it is
    bundled with the CLI itself.
    """
    return [cls for cls in ALL_WORKERS if cls.detect()]


__all__ = [
    "ALL_WORKERS",
    "AiderWorker",
    "ClaudeCodeWorker",
    "CodexWorker",
    "GooseWorker",
    "HermesLocalWorker",
    "JobContext",
    "WorkerAdapter",
    "WorkerResult",
    "WorkerStatus",
    "detect_available",
    "get_worker",
]
