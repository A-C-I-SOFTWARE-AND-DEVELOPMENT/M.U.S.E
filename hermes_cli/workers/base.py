"""Worker base — adapter contract + shared primitives.

This module hosts two complementary layers used by every Hermes worker:

1. **Adapter contract** — :class:`WorkerAdapter` plus its five result
   records (:class:`WorkerDetection`, :class:`WorkerPrompt`,
   :class:`WorkerRunResult`, :class:`WorkerArtifacts`, :class:`WorkerScore`).
   The orchestrator drives every adapter through the same five-step
   shape (``detect → prepare_prompt → run → collect → score``) so swapping
   tools is a configuration question rather than a code change.

2. **Shared primitives** — :class:`WorkerStatus`, :class:`WorkerError`,
   :class:`WorkerTask`, :class:`WorkerResult` and the small set of
   workspace I/O helpers (``ensure_workspace``, ``write_prompt``,
   ``write_status``, ``collect_git_artifacts``, render helpers).
   Concrete workers (``aider.py``, ``goose.py``, …) use these helpers so
   each adapter stays small and easy to test.

The two layers are deliberately independent: an adapter may implement
the full ABC while building its on-disk artifacts with the primitives,
or it may stay procedural and only use the primitives. Both styles are
first-class.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, ClassVar, Mapping, Optional


# ── Adapter result records ─────────────────────────────────────────────


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
            unavailable workers it's why detection failed.
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
    """Result of ``WorkerAdapter.prepare_prompt(job)``."""

    text: str
    role: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class WorkerRunResult:
    """Result of ``WorkerAdapter.run(job)``."""

    ok: bool
    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""
    duration_seconds: float = 0.0
    error: str = ""
    details: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class WorkerArtifacts:
    """Result of ``WorkerAdapter.collect(job)``."""

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

    ``value`` and ``confidence`` must be in [0.0, 1.0]; ``components``
    values too. The dataclass validates the range on construction so
    downstream code can compare scores without rescaling.
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


# ── Adapter contract ───────────────────────────────────────────────────


class WorkerAdapter(ABC):
    """Five-step contract every worker implements.

    Concrete subclasses set the class attributes :attr:`id` and
    :attr:`display_name` and implement the five abstract methods.
    ``__init_subclass__`` enforces both class attributes so a misconfigured
    adapter fails at import time instead of at dispatch time.
    """

    id: ClassVar[str] = ""
    display_name: ClassVar[str] = ""

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if getattr(cls, "__abstractmethods__", None):
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


# ── Shared primitives (used by procedural workers) ─────────────────────


class WorkerStatus(str, Enum):
    """Terminal state of a worker invocation."""

    HANDOFF_REQUIRED = "handoff_required"
    EXECUTED = "executed"
    COMMAND_NOT_FOUND = "command_not_found"
    FAILED = "failed"


class WorkerError(Exception):
    """Raised when a worker cannot prepare or run a task."""


@dataclass
class WorkerTask:
    """A description of work to hand to a local CLI agent."""

    title: str
    instructions: str
    files: list[str] = field(default_factory=list)
    context: Optional[str] = None
    acceptance_criteria: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkerResult:
    """Everything a caller needs to surface a worker run to the user."""

    worker: str
    status: WorkerStatus
    workspace: Path
    prompt_path: Path
    status_path: Path
    command_available: bool
    handoff_command: Optional[str] = None
    output_path: Optional[Path] = None
    patch_path: Optional[Path] = None
    changed_files_path: Optional[Path] = None
    exit_code: Optional[int] = None
    error: Optional[str] = None

    def to_status_dict(self) -> dict[str, Any]:
        return {
            "worker": self.worker,
            "status": self.status.value,
            "workspace": str(self.workspace),
            "prompt_path": str(self.prompt_path),
            "command_available": self.command_available,
            "handoff_command": self.handoff_command,
            "exit_code": self.exit_code,
            "error": self.error,
            "output_path": str(self.output_path) if self.output_path else None,
            "patch_path": str(self.patch_path) if self.patch_path else None,
            "changed_files_path": (
                str(self.changed_files_path) if self.changed_files_path else None
            ),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


def detect_command(command: str) -> bool:
    """Return True if ``command`` is callable from ``$PATH``."""
    return shutil.which(command) is not None


def ensure_workspace(workspace: Path) -> Path:
    """Create ``workspace`` (and parents) and return its resolved path."""
    workspace.mkdir(parents=True, exist_ok=True)
    return workspace.resolve()


def write_prompt(workspace: Path, prompt: str) -> Path:
    """Write ``prompt.md`` to ``workspace`` and return its path."""
    prompt_path = workspace / "prompt.md"
    prompt_path.write_text(prompt, encoding="utf-8")
    return prompt_path


def write_status(workspace: Path, result: WorkerResult) -> Path:
    """Persist ``result`` as ``status.json`` and return its path."""
    status_path = workspace / "status.json"
    status_path.write_text(
        json.dumps(result.to_status_dict(), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return status_path


def collect_git_artifacts(
    workspace: Path,
    repo_root: Path,
) -> tuple[Optional[Path], Optional[Path]]:
    """Capture ``git diff`` + changed-files list into ``workspace``."""
    if not (repo_root / ".git").exists():
        return (None, None)
    if shutil.which("git") is None:
        return (None, None)

    patch_path: Optional[Path] = None
    changed_files_path: Optional[Path] = None
    try:
        diff = subprocess.run(
            ["git", "diff", "--no-color"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
        )
        if diff.returncode == 0:
            patch_path = workspace / "patch.diff"
            patch_path.write_text(diff.stdout, encoding="utf-8")
    except OSError:
        patch_path = None

    try:
        names = subprocess.run(
            ["git", "diff", "--name-only"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
        )
        if names.returncode == 0:
            changed_files_path = workspace / "changed-files.txt"
            changed_files_path.write_text(names.stdout, encoding="utf-8")
    except OSError:
        changed_files_path = None

    return (patch_path, changed_files_path)


def render_files_block(files: list[str]) -> str:
    if not files:
        return ""
    bullets = "\n".join(f"- `{path}`" for path in files)
    return f"\n## Files in scope\n{bullets}\n"


def render_acceptance_block(criteria: list[str]) -> str:
    if not criteria:
        return ""
    bullets = "\n".join(f"- {item}" for item in criteria)
    return f"\n## Acceptance criteria\n{bullets}\n"


def render_context_block(context: Optional[str]) -> str:
    if not context:
        return ""
    return f"\n## Context\n{context.strip()}\n"


def result_as_dict(result: WorkerResult) -> dict[str, Any]:
    """``asdict`` shim that stringifies Path values."""
    data = asdict(result)
    for key, value in list(data.items()):
        if isinstance(value, Path):
            data[key] = str(value)
        elif isinstance(value, WorkerStatus):
            data[key] = value.value
    return data


__all__ = [
    "WorkerAdapter",
    "WorkerArtifacts",
    "WorkerDetection",
    "WorkerError",
    "WorkerPrompt",
    "WorkerResult",
    "WorkerRunResult",
    "WorkerScore",
    "WorkerStatus",
    "WorkerTask",
    "collect_git_artifacts",
    "detect_command",
    "ensure_workspace",
    "render_acceptance_block",
    "render_context_block",
    "render_files_block",
    "result_as_dict",
    "write_prompt",
    "write_status",
]
