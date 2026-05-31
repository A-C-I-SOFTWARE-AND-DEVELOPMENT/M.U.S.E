"""Claude Code handoff worker — stage a Claude Code run for the job.

Non-executing: builds a ``WorkerTask`` from the job + navigation and
materialises the Claude Code workspace (``prompt.md`` etc.) via
``claude_code.prepare_workspace``. It returns where to run ``claude``; it never
launches Claude Code or edits the repo. Runs ungated; verifiable without the
``claude`` binary.
"""

from __future__ import annotations

import time
from typing import Any

from hermes_cli.workers import claude_code
from hermes_cli.workers.base import WorkerDetection, WorkerPrompt, WorkerRunResult
from hermes_cli.workers.handoff_base import HandoffWorkerBase
from hermes_cli.workers.registry import register


class ClaudeHandoffWorker(HandoffWorkerBase):
    id = "claude-handoff"
    display_name = "Claude Code (handoff)"
    tool_label = "Claude Code"

    def detect(self) -> WorkerDetection:
        present = bool(getattr(claude_code.detect(), "available", False))
        return WorkerDetection(
            available=True,
            version="handoff",
            reason=(
                "claude on PATH — run it in the staged workspace"
                if present
                else "claude not installed — handoff staged for when it is"
            ),
            details={"binary_present": present},
        )

    def _claude_task(self, job: Any) -> "claude_code.WorkerTask":
        base = self._task(job)
        # claude_code has its own structured WorkerTask: only `mission` is
        # required. We supply the objective + the navigator's candidate files
        # as evidence; the richer fields stay empty (honest — not fabricated).
        return claude_code.WorkerTask(
            mission=base.instructions,
            repo_evidence=tuple(base.files),
        )

    def prepare_prompt(self, job: Any) -> WorkerPrompt:
        return WorkerPrompt(text=self._objective(job), role=self.id)

    def run(self, job: Any) -> WorkerRunResult:
        objective = self._objective(job)
        if not objective:
            return WorkerRunResult(ok=False, error="empty objective")
        t0 = time.monotonic()
        prepared = claude_code.prepare_workspace(self._claude_task(job), self._workspace(job))
        return WorkerRunResult(
            ok=True,
            stdout=(
                f"Claude Code handoff staged — run `claude` in {prepared.workdir} "
                f"({prepared.prompt_path.name})."
            ),
            duration_seconds=time.monotonic() - t0,
            details={
                "prompt_path": str(prepared.prompt_path),
                "workdir": str(prepared.workdir),
                "candidate_files": list(self._task(job).files),
            },
        )


register(ClaudeHandoffWorker(), replace=True)
