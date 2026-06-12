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

from muse_cli.workers import claude_code
from muse_cli.workers.base import WorkerDetection, WorkerPrompt, WorkerRunResult
from muse_cli.workers.handoff_base import HandoffWorkerBase
from muse_cli.workers.registry import register


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


class ClaudeExecuteWorker(ClaudeHandoffWorker):
    """Live: actually runs Claude Code agentically (owner-gated; needs `claude`).

    The Claude Code execute path (``run_claude_cli``) already existed but had no
    registered adapter, so the orchestrator could never dispatch it. This wraps
    it as the ``claude-execute`` lane — double-gated like Codex: the owner must
    approve the ``execute`` phase AND the ``claude`` binary must be present, and
    the workspace is prepared in ``RUN_MODE_EXECUTE`` so ``run_claude_cli``'s own
    second gate also passes only on purpose.
    """

    id = "claude-execute"
    display_name = "Claude Code (execute)"
    requires_approval = True

    def detect(self) -> WorkerDetection:
        present = bool(getattr(claude_code.detect(), "available", False))
        return WorkerDetection(
            available=present,
            version="execute",
            reason=(
                "claude ready to execute"
                if present
                else "claude not installed — cannot execute"
            ),
            details={"binary_present": present},
        )

    def run(self, job: Any) -> WorkerRunResult:
        objective = self._objective(job)
        if not objective:
            return WorkerRunResult(ok=False, error="empty objective")
        t0 = time.monotonic()
        prepared = claude_code.prepare_workspace(
            self._claude_task(job),
            self._workspace(job),
            mode=claude_code.RUN_MODE_EXECUTE,
        )
        result = claude_code.run_claude_cli(prepared, allow_execute=True)
        ok = (
            bool(result.invoked)
            and not result.error
            and (result.returncode in (0, None))
            and not result.timed_out
        )
        return WorkerRunResult(
            ok=ok,
            exit_code=int(result.returncode or 0),
            stdout=(result.stdout or "")[:500],
            error=(result.error or ""),
            duration_seconds=time.monotonic() - t0,
            details={
                "invoked": result.invoked,
                "timed_out": result.timed_out,
                "workdir": str(prepared.workdir),
                "candidate_files": list(self._task(job).files),
            },
        )


register(ClaudeExecuteWorker(), replace=True)
