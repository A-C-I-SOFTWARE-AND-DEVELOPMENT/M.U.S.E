"""Shared scaffolding for non-executing **handoff** worker adapters.

A handoff worker turns a job into a ready-to-run invocation of an external
coding CLI (Aider / Goose / Codex / Claude Code): it writes a worker-tuned
``prompt.md`` scoped to the navigator's candidate files and returns the command
(or workspace) for the owner to run. It **never spawns the tool or edits the
repo**, so ``requires_approval = False`` and it is fully verifiable even when
the tool's binary is absent. Actually executing the tool is a separate,
owner-gated capability.

``ProceduralHandoffWorker`` covers the Aider/Goose family (same module shape:
``render_prompt`` / ``run(task, ws, execute=False)`` / a ``*Config`` /
``detect_command``). Codex and Claude Code use bespoke staging and subclass
the lighter :class:`HandoffWorkerBase`.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, Optional

from hermes_cli.workers.base import (
    WorkerAdapter,
    WorkerArtifacts,
    WorkerDetection,
    WorkerPrompt,
    WorkerRunResult,
    WorkerScore,
    WorkerStatus,
    WorkerTask,
)


def hermes_home() -> Path:
    base = os.environ.get("HERMES_HOME") or os.path.expanduser("~/.hermes")
    return Path(base)


def build_worker_task(
    objective: str, repo_root: Path, *, source: str = "orchestrator"
) -> WorkerTask:
    """Build a scoped :class:`WorkerTask` from an objective using the navigator."""
    files: list[str] = []
    criteria: list[str] = []
    try:
        from hermes_cli.jarvis_prime.navigation import Navigator

        packet = Navigator.for_repo(repo_root).navigate(objective, limit=5).worker_packet()
        files = list(packet.get("candidate_files") or [])
        criteria = list(packet.get("verify_with") or [])
    except Exception:
        pass
    return WorkerTask(
        title=(objective[:80] or "Untitled task"),
        instructions=objective or "(no instructions provided)",
        files=files,
        acceptance_criteria=criteria,
        metadata={"source": source},
    )


class HandoffWorkerBase(WorkerAdapter):
    """Common helpers for handoff adapters. Subclasses implement detect/run.

    Note: ``WorkerAdapter.__init_subclass__`` enforces a non-empty ``id`` on
    every subclass (``__abstractmethods__`` isn't populated yet when it runs),
    so intermediate bases carry a placeholder id. These bases are never
    registered or dispatched — only concrete subclasses (which override
    ``id``/``display_name``) are.
    """

    id = "_handoff_base"
    display_name = "Handoff (base)"
    requires_approval = False
    tool_label = ""

    def __init__(self, repo_root: Optional[str] = None) -> None:
        self._repo_root = repo_root
        self._task_cache: dict[str, WorkerTask] = {}

    def _root(self) -> Path:
        return Path(self._repo_root) if self._repo_root else Path.cwd()

    @staticmethod
    def _objective(job: Any) -> str:
        return str(
            getattr(job, "prompt", "") or getattr(job, "objective", "") or ""
        ).strip()

    def _job_id(self, job: Any) -> str:
        return str(getattr(job, "id", "") or "adhoc")

    def _task(self, job: Any) -> WorkerTask:
        obj = self._objective(job)
        if obj not in self._task_cache:
            self._task_cache[obj] = build_worker_task(obj, self._root())
        return self._task_cache[obj]

    def _workspace(self, job: Any) -> Path:
        ws = hermes_home() / "jarvis_prime" / "handoff" / self._job_id(job) / self.id
        ws.mkdir(parents=True, exist_ok=True)
        return ws

    def collect(self, job: Any) -> WorkerArtifacts:
        task = self._task(job)
        return WorkerArtifacts(
            files=tuple(task.files),
            workspace_path=str(self._workspace(job)),
            notes=(
                f"{self.tool_label} handoff prepared — review prompt.md and run "
                "the command to execute"
            ),
        )

    def score(self, artifacts: WorkerArtifacts) -> WorkerScore:
        n = len(artifacts.files)
        value = 0.7 if n else 0.3
        return WorkerScore(
            value=value,
            confidence=0.5 if n else 0.3,
            rationale=f"handoff scoped to {n} candidate file(s)",
            components={"scoping": value},
        )


class ProceduralHandoffWorker(HandoffWorkerBase):
    """Handoff adapter for the Aider/Goose-family modules.

    Subclasses set ``id``, ``display_name``, ``tool_label``, ``worker_module``
    (the module), and ``config_cls`` (its ``*Config``).
    """

    # Placeholder identity so WorkerAdapter.__init_subclass__ (which enforces a
    # non-empty `id` on every concrete subclass) accepts this fully-implemented
    # intermediate base. It is never registered or dispatched — only concrete
    # subclasses (which override id/display_name) are.
    id = "_procedural_handoff_base"
    display_name = "Procedural handoff (base)"

    worker_module: Any = None
    config_cls: Any = None

    def detect(self) -> WorkerDetection:
        present = self.worker_module.detect_command(self.config_cls().command)
        return WorkerDetection(
            available=True,
            version="handoff",
            reason=(
                f"{self.tool_label} on PATH — handoff command is runnable"
                if present
                else f"{self.tool_label} not installed — handoff prepared for when it is"
            ),
            details={"binary_present": present},
        )

    def prepare_prompt(self, job: Any) -> WorkerPrompt:
        return WorkerPrompt(text=self.worker_module.render_prompt(self._task(job)), role=self.id)

    def run(self, job: Any) -> WorkerRunResult:
        objective = self._objective(job)
        if not objective:
            return WorkerRunResult(ok=False, error="empty objective")
        t0 = time.monotonic()
        task = self._task(job)
        # execute=False → handoff only: writes prompt.md + status.json and
        # returns the command. Never spawns the tool, never edits the repo.
        result = self.worker_module.run(
            task, self._workspace(job), execute=False, repo_root=self._root()
        )
        return WorkerRunResult(
            ok=True,
            stdout=(result.handoff_command or ""),
            duration_seconds=time.monotonic() - t0,
            details={
                "status": result.status.value,
                "prompt_path": str(result.prompt_path),
                "command_available": result.command_available,
                "handoff_command": result.handoff_command,
                "candidate_files": list(task.files),
            },
        )


class ProceduralExecuteWorker(ProceduralHandoffWorker):
    """Execute-mode adapter for the Aider/Goose family.

    Unlike the handoff variant, this **actually runs the tool**
    (``module.run(..., execute=True)``) — so it is owner-gated
    (``requires_approval = True``) and ``detect()`` reports the *real* binary
    availability, so dispatch blocks honestly when the CLI is absent rather
    than pretending. Subclasses set the same class attrs as the handoff family.
    """

    # Placeholder identity (see HandoffWorkerBase note); concrete subclasses
    # override. Never registered.
    id = "_procedural_execute_base"
    display_name = "Procedural execute (base)"
    requires_approval = True

    def detect(self) -> WorkerDetection:
        present = self.worker_module.detect_command(self.config_cls().command)
        return WorkerDetection(
            available=present,
            version="execute",
            reason=(
                f"{self.tool_label} ready to execute"
                if present
                else f"{self.tool_label} not installed — cannot execute"
            ),
            details={"binary_present": present},
        )

    def run(self, job: Any) -> WorkerRunResult:
        objective = self._objective(job)
        if not objective:
            return WorkerRunResult(ok=False, error="empty objective")
        t0 = time.monotonic()
        task = self._task(job)
        result = self.worker_module.run(
            task, self._workspace(job), execute=True, repo_root=self._root()
        )
        ok = result.status == WorkerStatus.EXECUTED
        return WorkerRunResult(
            ok=ok,
            exit_code=int(result.exit_code or 0),
            stdout=(result.handoff_command or ""),
            error=(result.error or ""),
            duration_seconds=time.monotonic() - t0,
            details={
                "status": result.status.value,
                "output_path": str(result.output_path) if result.output_path else None,
                "patch_path": str(result.patch_path) if result.patch_path else None,
                "command_available": result.command_available,
                "candidate_files": list(task.files),
            },
        )

    def score(self, artifacts: WorkerArtifacts) -> WorkerScore:
        # An execute worker's value is the change it produced, not just scoping.
        n = len(artifacts.files)
        value = 0.6 if n else 0.3
        return WorkerScore(
            value=value,
            confidence=0.4 if n else 0.2,
            rationale=f"executed against {n} candidate file(s)",
            components={"execution": value},
        )
