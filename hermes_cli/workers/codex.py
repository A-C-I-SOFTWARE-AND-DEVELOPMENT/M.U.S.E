"""OpenAI Codex CLI worker adapter (Phase 7 skeleton).

Wraps the ``codex`` binary installed via ``npm install -g @openai/codex``.
Authenticates through either ``OPENAI_API_KEY`` or the Codex OAuth
credentials stored under ``~/.codex/auth.json``. Codex insists on
running inside a git repository.

Status: skeleton. All methods raise :class:`NotImplementedError`.

See ``skills/autonomous-ai-agents/codex/SKILL.md`` for the existing
hand-driven workflow this adapter will eventually automate, and
``docs/orchestration/worker-adapter-interface.md`` for the contract.
"""

from __future__ import annotations

from hermes_cli.workers.base import (
    ArtifactBundle,
    AvailabilityReport,
    Job,
    PreparedRun,
    WorkerAdapter,
    WorkerRun,
)


class CodexAdapter(WorkerAdapter):
    """Drive OpenAI Codex (``codex exec``) as a worker."""

    name = "codex"
    description = "OpenAI Codex CLI (`codex exec`)."
    capabilities = frozenset({"code", "review", "interactive", "long-task"})

    def available(self) -> AvailabilityReport:
        # TODO(phase-7): use ``shutil.which("codex")`` plus a check
        # that either ``OPENAI_API_KEY`` is set or
        # ``~/.codex/auth.json`` exists. Also confirm the cwd is a git
        # repo before declaring available for a given job — that check
        # belongs in ``prepare``.
        return AvailabilityReport(
            ok=False,
            reason="codex adapter is a Phase 7 skeleton",
        )

    def prepare(self, job: Job) -> PreparedRun:
        # TODO(phase-7): build ``codex exec <prompt>`` with the job's
        # cwd. Codex needs a PTY, so the controller must allocate one
        # when calling ``run``.
        raise NotImplementedError("codex.prepare is a Phase 7 skeleton")

    def run(self, prepared: PreparedRun) -> WorkerRun:
        # TODO(phase-7): allocate a PTY, exec ``codex``, copy
        # stdout/stderr to log files. Treat exit code 0 as success
        # and anything else as failure.
        raise NotImplementedError("codex.run is a Phase 7 skeleton")

    def collect_artifacts(self, run: WorkerRun) -> ArtifactBundle:
        # TODO(phase-7): Codex writes changes directly into the
        # working tree, so the bundle is a ``git diff`` snapshot
        # captured right after the run finished.
        raise NotImplementedError("codex.collect_artifacts is a Phase 7 skeleton")


def adapter() -> WorkerAdapter:
    """Factory consumed by ``hermes_cli.workers.load_adapter``."""
    return CodexAdapter()


__all__ = ["CodexAdapter", "adapter"]
