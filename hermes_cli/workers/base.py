"""Worker base class for Hermes orchestration."""

from __future__ import annotations

import abc
import dataclasses
import hashlib
import os
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - import cycle avoidance
    from hermes_cli.orchestrator import Task


@dataclasses.dataclass
class WorkerResult:
    """A worker's proposal artifact.

    The orchestrator never executes ``proposal`` directly — the merge engine
    and validation gates do. Workers may attach a ``score_hint`` between 0
    and 1 but the authoritative score comes from
    :mod:`hermes_cli.scoring`.
    """

    worker_name: str
    task_id: str
    success: bool
    proposal: str
    score_hint: float = 0.0
    files_touched: list[str] = dataclasses.field(default_factory=list)
    log: str = ""
    metadata: dict[str, Any] = dataclasses.field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "worker_name": self.worker_name,
            "task_id": self.task_id,
            "success": self.success,
            "proposal": self.proposal,
            "score_hint": self.score_hint,
            "files_touched": self.files_touched,
            "log": self.log,
            "metadata": self.metadata,
        }


class Worker(abc.ABC):
    """Abstract worker. Subclasses MUST override :meth:`execute`."""

    #: Stable identifier — must be filesystem-safe (used in worktree names).
    name: str = "worker"
    #: Human-friendly role label.
    role: str = "generalist"

    def execute(self, task: "Task", worktree: Path) -> WorkerResult:
        """Run the worker against ``task`` inside ``worktree``."""
        if not worktree.exists():
            return WorkerResult(
                worker_name=self.name,
                task_id=task.task_id,
                success=False,
                proposal="",
                log=f"worktree {worktree} missing",
            )
        try:
            return self._execute(task, worktree)
        except Exception as exc:  # pragma: no cover - defensive
            return WorkerResult(
                worker_name=self.name,
                task_id=task.task_id,
                success=False,
                proposal="",
                log=f"worker raised: {exc!r}",
            )

    @abc.abstractmethod
    def _execute(self, task: "Task", worktree: Path) -> WorkerResult:
        ...

    # ── Shared helpers ────────────────────────────────────────────────

    @staticmethod
    def _scan_repo(worktree: Path, *, limit: int = 200) -> list[Path]:
        """Return a deterministic, bounded snapshot of repo files."""
        files: list[Path] = []
        skip_dirs = {".git", ".hermes", "node_modules", "__pycache__", ".venv"}
        for root, dirs, names in os.walk(worktree):
            dirs[:] = [d for d in dirs if d not in skip_dirs]
            for name in names:
                files.append(Path(root) / name)
                if len(files) >= limit:
                    return files
        files.sort()
        return files

    @staticmethod
    def _fingerprint(prompt: str) -> str:
        digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        return digest[:12]

    @staticmethod
    def _signature(role: str, fingerprint: str) -> str:
        return f"[{role}:{fingerprint}]"

    def _proposal_template(self, task: "Task", body: str, *, score_hint: float) -> WorkerResult:
        fingerprint = self._fingerprint(task.prompt)
        signature = self._signature(self.role, fingerprint)
        proposal = "\n".join([
            f"# Hermes proposal {signature}",
            "",
            f"**Worker:** {self.name}",
            f"**Role:** {self.role}",
            f"**Task:** {task.title}",
            "",
            "## Summary",
            "",
            body.strip(),
            "",
        ])
        return WorkerResult(
            worker_name=self.name,
            task_id=task.task_id,
            success=True,
            proposal=proposal,
            score_hint=score_hint,
            metadata={"fingerprint": fingerprint, "role": self.role},
        )

    @staticmethod
    def _safe_grep(worktree: Path, pattern: str) -> int:
        """Count files containing ``pattern`` (escaped) — bounded and pure-Python."""
        count = 0
        try:
            rx = re.compile(re.escape(pattern))
        except re.error:
            return 0
        for path in Worker._scan_repo(worktree, limit=500):
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except (OSError, UnicodeDecodeError):
                continue
            if rx.search(text):
                count += 1
        return count
