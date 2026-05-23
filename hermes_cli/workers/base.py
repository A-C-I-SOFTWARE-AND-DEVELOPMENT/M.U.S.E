"""Worker adapter contract — the five-step interface every tool follows.

A worker is anything Hermes can hand a job to: a local CLI like Codex
or Claude Code, a desktop tool like Aider or Goose, a manual handoff
to ChatGPT, a publisher like GitHub Publisher, or the in-process
Hermes Local runtime. The orchestrator drives them all through the
same shape so swapping or stacking workers stays a configuration
question rather than a code change.

The contract has five steps, each returning a small immutable record:

1. ``detect()``      → :class:`WorkerDetection` — is this worker usable
   on the current machine right now? Returns a verdict the orchestrator
   can act on (skip, prompt for install, fall back to another worker)
   without raising.
2. ``prepare_prompt(job)`` → :class:`WorkerPrompt` — turn an abstract
   job into the exact text / metadata the worker expects. Pure;
   the orchestrator may inspect or log it before running anything.
3. ``run(job)``      → :class:`WorkerRunResult` — execute the worker
   and report success / failure together with stdout, stderr, and
   timing. May spawn subprocesses or call external APIs.
4. ``collect(job)``  → :class:`WorkerArtifacts` — gather whatever the
   worker produced (patches, files, logs, links) into a uniform record
   the rest of Hermes can ingest.
5. ``score(artifacts)`` → :class:`WorkerScore` — heuristic / model-based
   judgement of how well the artifacts satisfy the job. Used by the
   council and the kanban router to decide whether to ship or rework.

The ``job`` parameter is intentionally typed as ``Any``. Different
workers care about different fields and the surrounding orchestrator
chooses what shape it passes. Adapters that need stricter typing can
narrow it themselves in their own implementation.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, ClassVar, Mapping


# ── Result records ──────────────────────────────────────────────────────


@dataclass(frozen=True)
class WorkerDetection:
    """Result of ``WorkerAdapter.detect()``.

    Attributes:
        available: True if the worker can be invoked on this machine
            right now. The orchestrator treats False as "skip silently"
            unless the user explicitly requested this worker.
        version: Best-effort version string of the underlying tool,
            empty when the worker can't report one (or wasn't found).
        reason: Human-readable explanation. For available workers this
            is usually the path / binary that was discovered; for
            unavailable workers it's why detection failed ("codex CLI
            not on PATH", "no API key for chatgpt-handoff").
        details: Optional structured payload — install hints, candidate
            install paths, capability flags. Adapters are free to add
            keys; consumers should treat unknown keys as informational.
    """

    available: bool
    version: str = ""
    reason: str = ""
    details: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class WorkerPrompt:
    """Result of ``WorkerAdapter.prepare_prompt(job)``.

    Attributes:
        text: The actual prompt body to deliver to the worker. For
            manual-handoff workers (ChatGPT, Claude) this is what gets
            copied to the clipboard; for CLI workers it's what gets
            piped on stdin or written to the workspace.
        role: A short tag describing how the prompt frames the worker
            ("builder", "planner", "reviewer", "architect", "publisher",
            ...). The orchestrator uses it to pair prompts with the
            right artifact-collection strategy.
        metadata: Optional extra context — model hints, allowed tools,
            temperature, workspace path. Adapters add what they need;
            unknown keys are fine.
    """

    text: str
    role: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class WorkerRunResult:
    """Result of ``WorkerAdapter.run(job)``.

    Attributes:
        ok: True if the worker finished without an unrecoverable error.
            A worker that completed but reported no useful output is
            still ``ok``; that nuance lives in :class:`WorkerScore`.
        exit_code: Numeric exit code where it makes sense (CLI tools).
            Zero by convention for non-process workers that succeeded.
        stdout: Captured standard output. Empty string when the worker
            doesn't have one (manual handoff, API publishers).
        stderr: Captured standard error.
        duration_seconds: Wall-clock duration of the ``run`` call.
            Zero for synchronous handoff-only flows.
        error: Short error tag for programmatic dispatch ("timeout",
            "not_found", "auth_failed", "no_changes"); empty on success.
        details: Adapter-specific extras — process id, log file path,
            opened deep-link URL, etc.
    """

    ok: bool
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""
    duration_seconds: float = 0.0
    error: str = ""
    details: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class WorkerArtifacts:
    """Result of ``WorkerAdapter.collect(job)``.

    Attributes:
        files: Paths the worker wrote or changed inside the workspace,
            relative to ``workspace_path`` when set. Empty list is
            valid and common for review-only workers.
        patches: Unified-diff strings the worker produced. Patches are
            kept separate from ``files`` because some workers emit
            advisory diffs without applying them.
        logs: Paths to per-step log files the worker dropped on disk.
        links: External URLs the worker created (PR links, gists,
            shared chats). Useful for publisher-style workers.
        workspace_path: Root the file paths are relative to. Empty
            when the worker doesn't operate on a workspace at all.
        notes: Free-form text the adapter wants downstream consumers
            (the judge, the kanban router, the user) to see — e.g.
            a one-line summary of what the worker did.
        details: Adapter-specific extras.
    """

    files: tuple[str, ...] = ()
    patches: tuple[str, ...] = ()
    logs: tuple[str, ...] = ()
    links: tuple[str, ...] = ()
    workspace_path: str = ""
    notes: str = ""
    details: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class WorkerScore:
    """Result of ``WorkerAdapter.score(artifacts)``.

    Attributes:
        value: Normalised quality score in [0.0, 1.0]. The base class
            validates the range on construction so downstream code
            (the council, the kanban router) can compare scores from
            different workers without rescaling.
        confidence: How confident the adapter is in its own scoring,
            also in [0.0, 1.0]. A heuristic scorer reports low
            confidence; a model-graded scorer reports higher.
        rationale: Short explanation the judge / user can read.
        components: Per-axis breakdown ("compiles": 1.0, "tests": 0.0,
            ...) when the adapter wants to surface why the score is
            what it is. All values must be in [0.0, 1.0] but the keys
            are free-form.
    """

    value: float
    confidence: float = 0.0
    rationale: str = ""
    components: Mapping[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not 0.0 <= self.value <= 1.0:
            raise ValueError(
                f"WorkerScore.value must be in [0.0, 1.0], got {self.value!r}"
            )
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(
                f"WorkerScore.confidence must be in [0.0, 1.0], got {self.confidence!r}"
            )
        for key, val in self.components.items():
            if not 0.0 <= val <= 1.0:
                raise ValueError(
                    f"WorkerScore.components[{key!r}] must be in [0.0, 1.0], "
                    f"got {val!r}"
                )


# ── Adapter contract ────────────────────────────────────────────────────


class WorkerAdapter(ABC):
    """Five-step contract every worker implements.

    Concrete subclasses set the class attributes :attr:`id` and
    :attr:`display_name` and implement the five abstract methods.
    ``__init_subclass__`` enforces both class attributes so a misconfigured
    adapter fails at import time instead of at dispatch time.

    Subclasses are expected to be cheap to construct — detection that
    spawns subprocesses or hits the network belongs in :meth:`detect`,
    not ``__init__`` — so the registry can hold long-lived instances.

    The ``job`` argument is typed as ``Any`` deliberately: different
    workers want different fields on it (a workspace path, a model
    name, a clipboard target). Concrete adapters narrow this in their
    own signatures when they want help from a type checker.
    """

    id: ClassVar[str] = ""
    display_name: ClassVar[str] = ""

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if getattr(cls, "__abstractmethods__", None):
            # Still abstract — let the next subclass fill in the gaps.
            return
        if not cls.id or not isinstance(cls.id, str):
            raise TypeError(f"{cls.__name__} must set a non-empty class attribute `id`")
        if not cls.display_name or not isinstance(cls.display_name, str):
            raise TypeError(
                f"{cls.__name__} must set a non-empty class attribute `display_name`"
            )

    @abstractmethod
    def detect(self) -> WorkerDetection:
        """Return whether this worker is usable on the current machine."""

    @abstractmethod
    def prepare_prompt(self, job: Any) -> WorkerPrompt:
        """Turn ``job`` into the exact prompt this worker expects."""

    @abstractmethod
    def run(self, job: Any) -> WorkerRunResult:
        """Execute the worker against ``job`` and report what happened."""

    @abstractmethod
    def collect(self, job: Any) -> WorkerArtifacts:
        """Gather whatever the worker produced into a uniform record."""

    @abstractmethod
    def score(self, artifacts: WorkerArtifacts) -> WorkerScore:
        """Judge how well ``artifacts`` satisfy the original job."""


__all__ = [
    "WorkerAdapter",
    "WorkerArtifacts",
    "WorkerDetection",
    "WorkerPrompt",
    "WorkerRunResult",
    "WorkerScore",
]
