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


def builtin_worker_classes() -> list:
    """The built-in worker adapter classes (importing them self-registers each).

    All accept an optional ``repo_root`` first arg, so the orchestrator can
    bind them to a job's repo at dispatch.
    """
    from hermes_cli.workers.aider_handoff import AiderExecuteWorker, AiderHandoffWorker
    from hermes_cli.workers.autoresearch import AutoresearchWorker
    from hermes_cli.workers.claude_handoff import ClaudeExecuteWorker, ClaudeHandoffWorker
    from hermes_cli.workers.codex_handoff import CodexExecuteWorker, CodexHandoffWorker
    from hermes_cli.workers.goose_handoff import GooseExecuteWorker, GooseHandoffWorker
    from hermes_cli.workers.llm_jepa import LlmJepaWorker
    from hermes_cli.workers.local_planner import LocalPlannerWorker
    from hermes_cli.workers.sia import SiaWorker

    return [
        LocalPlannerWorker,
        AiderHandoffWorker,
        GooseHandoffWorker,
        CodexHandoffWorker,
        ClaudeHandoffWorker,
        AiderExecuteWorker,
        GooseExecuteWorker,
        CodexExecuteWorker,
        ClaudeExecuteWorker,
        SiaWorker,
        AutoresearchWorker,
        LlmJepaWorker,
    ]


def load_builtins() -> None:
    """Import the built-in worker adapters so they self-register.

    Idempotent (module imports cache; adapters register with replace=True).
    Call before resolving a worker by id from the registry.
    """
    builtin_worker_classes()


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
