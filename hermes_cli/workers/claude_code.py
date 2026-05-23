"""Claude Code CLI worker adapter (Phase 7 skeleton).

Wraps the ``claude`` binary (Anthropic's Claude Code CLI). The CLI is
interactive by default; the controller will drive it in
``claude -p <prompt>`` or ``claude --print`` mode so the run is
pipe-friendly.

Status: skeleton. All methods raise :class:`NotImplementedError`.

See ``skills/autonomous-ai-agents/claude-code/SKILL.md`` for the
hand-driven workflow, and ``docs/orchestration/worker-adapter-interface.md``
for the contract.
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


class ClaudeCodeAdapter(WorkerAdapter):
    """Drive Claude Code (``claude``) as a worker."""

    name = "claude_code"
    description = "Anthropic Claude Code CLI (`claude --print`)."
    capabilities = frozenset({"code", "review", "plan", "long-task"})

    def available(self) -> AvailabilityReport:
        # TODO(phase-7): use ``shutil.which("claude")`` and verify the
        # user has completed ``claude login`` at least once
        # (presence of ``~/.claude/`` or similar). Do not read the
        # token itself.
        return AvailabilityReport(
            ok=False,
            reason="claude_code adapter is a Phase 7 skeleton",
        )

    def prepare(self, job: Job) -> PreparedRun:
        # TODO(phase-7): build the non-interactive invocation:
        #   ``claude --print --output-format json <prompt>``
        # and capture the JSON output so we can pull out the final
        # message cleanly.
        raise NotImplementedError("claude_code.prepare is a Phase 7 skeleton")

    def run(self, prepared: PreparedRun) -> WorkerRun:
        # TODO(phase-7): exec the prepared argv, stream stdout/stderr,
        # set status from exit code. No PTY needed in ``--print`` mode.
        raise NotImplementedError("claude_code.run is a Phase 7 skeleton")

    def collect_artifacts(self, run: WorkerRun) -> ArtifactBundle:
        # TODO(phase-7): parse the JSON output, grab any tool-use
        # results, and snapshot ``git diff`` if the run touched files.
        raise NotImplementedError(
            "claude_code.collect_artifacts is a Phase 7 skeleton",
        )


def adapter() -> WorkerAdapter:
    """Factory consumed by ``hermes_cli.workers.load_adapter``."""
    return ClaudeCodeAdapter()


__all__ = ["ClaudeCodeAdapter", "adapter"]
