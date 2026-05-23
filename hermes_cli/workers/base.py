"""Shared worker primitives: task, status, result, workspace I/O.

This module is intentionally framework-free so individual workers
(``aider.py``, ``goose.py``, …) stay small and easy to test.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional


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
    """A description of work to hand to a local CLI agent.

    ``title`` and ``instructions`` are required. Everything else is
    optional metadata the worker may surface in the rendered prompt.
    """

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
        """Serialize for ``status.json``. ``Path`` values become strings."""
        data: dict[str, Any] = {
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
        return data


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
    """Capture ``git diff`` + changed-files list into ``workspace``.

    Returns ``(patch_path, changed_files_path)``. Each entry is ``None``
    when the underlying ``git`` command failed or ``repo_root`` is not a
    git checkout. This function never raises on a missing/broken git;
    workers degrade gracefully when artifacts cannot be collected.
    """
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


# Re-exported so callers can build their own status dicts without
# pulling in ``dataclasses`` directly.
def result_as_dict(result: WorkerResult) -> dict[str, Any]:
    """``asdict`` shim that stringifies Path values."""
    data = asdict(result)
    for key, value in list(data.items()):
        if isinstance(value, Path):
            data[key] = str(value)
        elif isinstance(value, WorkerStatus):
            data[key] = value.value
    return data
