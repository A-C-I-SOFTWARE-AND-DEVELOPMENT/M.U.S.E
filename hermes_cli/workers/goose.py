"""Goose CLI worker adapter (Phase 7 skeleton).

Wraps Block's ``goose`` CLI. Goose is a developer-focused agent that
ships with its own session model and toolset. The controller drives it
in headless ``goose run`` mode so the output is pipe-friendly.

Status: skeleton. All methods raise :class:`NotImplementedError`.

See ``docs/orchestration/worker-adapter-interface.md`` for the contract.
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


class GooseAdapter(WorkerAdapter):
    """Drive Goose (``goose run``) as a worker."""

    name = "goose"
    description = "Block Goose CLI (`goose run`)."
    capabilities = frozenset({"code", "plan", "long-task"})

    def available(self) -> AvailabilityReport:
        # TODO(phase-7): ``shutil.which("goose")`` plus a check that
        # the user has a Goose profile configured under ``~/.config/goose``.
        return AvailabilityReport(
            ok=False,
            reason="goose adapter is a Phase 7 skeleton",
        )

    def prepare(self, job: Job) -> PreparedRun:
        # TODO(phase-7): build the headless command:
        #   ``goose run --text <prompt> --no-session``
        # and decide which extensions to enable. Default to whatever
        # the user has in their Goose profile.
        raise NotImplementedError("goose.prepare is a Phase 7 skeleton")

    def run(self, prepared: PreparedRun) -> WorkerRun:
        # TODO(phase-7): exec the prepared argv, stream stdout/stderr,
        # set status from exit code.
        raise NotImplementedError("goose.run is a Phase 7 skeleton")

    def collect_artifacts(self, run: WorkerRun) -> ArtifactBundle:
        # TODO(phase-7): grab Goose's session transcript (when not
        # ``--no-session``) and any working-tree diff it produced.
        raise NotImplementedError("goose.collect_artifacts is a Phase 7 skeleton")


def adapter() -> WorkerAdapter:
    """Factory consumed by ``hermes_cli.workers.load_adapter``."""
    return GooseAdapter()


__all__ = ["GooseAdapter", "adapter"]
