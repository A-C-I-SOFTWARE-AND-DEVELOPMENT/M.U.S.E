"""Aider handoff worker: turn a job into a ready-to-run Aider invocation.

The second concrete :class:`~hermes_cli.workers.base.WorkerAdapter`, and the
template for wrapping any external coding CLI. It runs Aider in **handoff
mode** (``aider.run(..., execute=False)``): it writes a worker-tuned
``prompt.md`` and returns a copy-pasteable ``aider`` command — it **never
spawns Aider or edits the repo**. So it is safe to run ungated
(``requires_approval = False``) and is fully verifiable without the ``aider``
binary present (it still produces the command + prompt).

Candidate files come from the deterministic HyperAgent navigator, so the
handoff is scoped to the files most likely to need editing. Actually
*executing* Aider (``execute=True``) is a separate, owner-gated capability —
this adapter deliberately does not do it.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Optional

from hermes_cli.workers import aider
from hermes_cli.workers.base import (
    WorkerAdapter,
    WorkerArtifacts,
    WorkerDetection,
    WorkerPrompt,
    WorkerRunResult,
    WorkerScore,
    WorkerTask,
)
from hermes_cli.workers.registry import register


def _hermes_home() -> Path:
    import os

    base = os.environ.get("HERMES_HOME") or os.path.expanduser("~/.hermes")
    return Path(base)


class AiderHandoffWorker(WorkerAdapter):
    """Prepare an Aider handoff (prompt + command) — non-executing."""

    id = "aider-handoff"
    display_name = "Aider (handoff)"
    # Handoff only — writes a prompt + returns a command, never runs Aider or
    # edits the repo. Safe to run without the owner 'execute' gate.
    requires_approval = False

    def __init__(self, repo_root: Optional[str] = None) -> None:
        self._repo_root = repo_root
        self._cache: dict[str, WorkerTask] = {}

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
        objective = self._objective(job)
        if objective in self._cache:
            return self._cache[objective]
        files: list[str] = []
        criteria: list[str] = []
        try:
            from hermes_cli.jarvis_prime.navigation import Navigator

            packet = Navigator.for_repo(self._root()).navigate(objective, limit=5).worker_packet()
            files = list(packet.get("candidate_files") or [])
            criteria = list(packet.get("verify_with") or [])
        except Exception:
            pass
        task = WorkerTask(
            title=(objective[:80] or "Untitled task"),
            instructions=objective or "(no instructions provided)",
            files=files,
            acceptance_criteria=criteria,
            metadata={"source": "orchestrator"},
        )
        self._cache[objective] = task
        return task

    def _workspace(self, job: Any) -> Path:
        ws = _hermes_home() / "jarvis_prime" / "handoff" / self._job_id(job) / "aider"
        ws.mkdir(parents=True, exist_ok=True)
        return ws

    # -- WorkerAdapter five-step contract -------------------------------
    def detect(self) -> WorkerDetection:
        # Handoff is always available — it doesn't need the binary to prepare
        # the command. We still report whether `aider` is on PATH.
        present = aider.detect_command(aider.AiderConfig().command)
        return WorkerDetection(
            available=True,
            version="handoff",
            reason=(
                "aider on PATH — handoff command is runnable"
                if present
                else "aider not installed — handoff command prepared for when it is"
            ),
            details={"binary_present": present},
        )

    def prepare_prompt(self, job: Any) -> WorkerPrompt:
        return WorkerPrompt(text=aider.render_prompt(self._task(job)), role="aider")

    def run(self, job: Any) -> WorkerRunResult:
        objective = self._objective(job)
        if not objective:
            return WorkerRunResult(ok=False, error="empty objective")
        t0 = time.monotonic()
        task = self._task(job)
        # execute=False → handoff only: writes prompt.md + status.json, returns
        # the command. Never spawns Aider, never edits the repo.
        result = aider.run(task, self._workspace(job), execute=False, repo_root=self._root())
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

    def collect(self, job: Any) -> WorkerArtifacts:
        task = self._task(job)
        return WorkerArtifacts(
            files=tuple(task.files),
            workspace_path=str(self._workspace(job)),
            notes="handoff prepared — review prompt.md and run the command to execute",
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


register(AiderHandoffWorker(), replace=True)
