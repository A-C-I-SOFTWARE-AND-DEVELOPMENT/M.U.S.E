"""Codex handoff worker — stage a Codex run scoped to the navigator's files.

Non-executing: builds a ``CodexTask`` from the job + navigation and writes
``prompt.md`` + ``status.json`` into a per-job workspace via
``codex.write_prompt_and_status``. It returns where to open Codex; it never
launches Codex or edits the repo. Runs ungated; verifiable without the
``codex`` binary.
"""

from __future__ import annotations

import time
from typing import Any

from hermes_cli.workers import codex
from hermes_cli.workers.base import WorkerDetection, WorkerPrompt, WorkerRunResult
from hermes_cli.workers.handoff_base import HandoffWorkerBase
from hermes_cli.workers.registry import register


class CodexHandoffWorker(HandoffWorkerBase):
    id = "codex-handoff"
    display_name = "Codex (handoff)"
    tool_label = "Codex"

    def _codex_task(self, job: Any) -> "codex.CodexTask":
        t = self._task(job)
        return codex.CodexTask(
            mission=t.instructions,
            task=t.instructions,
            files_likely_to_edit=list(t.files),
            acceptance_criteria=list(t.acceptance_criteria),
            validation_commands=list(t.acceptance_criteria),
        )

    def detect(self) -> WorkerDetection:
        present = bool(getattr(codex.detect_codex(), "available", False))
        return WorkerDetection(
            available=True,
            version="handoff",
            reason=(
                "codex on PATH — open it in the staged workspace"
                if present
                else "codex not installed — handoff staged for when it is"
            ),
            details={"binary_present": present},
        )

    def prepare_prompt(self, job: Any) -> WorkerPrompt:
        return WorkerPrompt(text=codex.build_prompt(self._codex_task(job)), role=self.id)

    def run(self, job: Any) -> WorkerRunResult:
        objective = self._objective(job)
        if not objective:
            return WorkerRunResult(ok=False, error="empty objective")
        t0 = time.monotonic()
        ws = self._workspace(job)
        prompt_path, status_path = codex.write_prompt_and_status(self._codex_task(job), ws)
        return WorkerRunResult(
            ok=True,
            stdout=f"Codex handoff staged — open Codex in {ws} and run {prompt_path.name}.",
            duration_seconds=time.monotonic() - t0,
            details={
                "prompt_path": str(prompt_path),
                "status_path": str(status_path),
                "candidate_files": list(self._task(job).files),
            },
        )


register(CodexHandoffWorker(), replace=True)
