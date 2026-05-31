"""Worker adapter framework for Hermes.

A *worker* is any tool Hermes can hand a job off to: Hermes Local,
Codex, Claude Code, Aider, Goose, the ChatGPT manual-handoff flow,
GitHub Publisher, or anything plugged in later. Every worker exposes
the same five-step contract so the orchestrator can drive it
identically regardless of which CLI / SDK / human-handoff sits behind
it:

    detect → prepare_prompt → run → collect → score

This package gives that contract a home. ``base`` defines the
``WorkerAdapter`` abstract base class plus the small set of dataclass
records (``WorkerDetection``, ``WorkerPrompt``, ``WorkerRunResult``,
``WorkerArtifacts``, ``WorkerScore``) the steps exchange. ``registry``
holds the in-process lookup table so the orchestrator can ask for a
worker by id without importing the adapter module directly.

Concrete adapters live outside this package — each ships in its own
module (e.g. ``hermes_cli.workers.codex``) and registers itself via
``registry.register``. Keeping the base small means new tools can be
added without touching this module.
"""

from __future__ import annotations

from hermes_cli.workers.base import (
    WorkerAdapter,
    WorkerArtifacts,
    WorkerDetection,
    WorkerError,
    WorkerPrompt,
    WorkerResult,
    WorkerRunResult,
    WorkerScore,
    WorkerStatus,
    WorkerTask,
)
from hermes_cli.workers.isolation import (
    CollectedRun,
    IsolatedSpawner,
    IsolatedWorkspace,
    IsolationError,
    SpawnResult,
    cleanup_workspace,
    list_workspaces,
    new_instance_id,
    prepare_workspace,
)
from hermes_cli.workers.registry import (
    WorkerRegistry,
    default_registry,
    get,
    known_workers,
    register,
    unregister,
)


def load_builtins() -> None:
    """Import the built-in worker adapters so they self-register.

    Idempotent (module imports cache; adapters register with replace=True).
    Call before resolving a worker by id from the registry.
    """
    from hermes_cli.workers import aider_handoff, local_planner  # noqa: F401


__all__ = [
    "CollectedRun",
    "IsolatedSpawner",
    "IsolatedWorkspace",
    "IsolationError",
    "SpawnResult",
    "WorkerAdapter",
    "WorkerArtifacts",
    "WorkerDetection",
    "WorkerError",
    "WorkerPrompt",
    "WorkerRegistry",
    "WorkerResult",
    "WorkerRunResult",
    "WorkerScore",
    "WorkerStatus",
    "WorkerTask",
    "cleanup_workspace",
    "default_registry",
    "get",
    "known_workers",
    "list_workspaces",
    "new_instance_id",
    "prepare_workspace",
    "register",
    "unregister",
]
