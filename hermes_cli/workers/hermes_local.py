"""Hermes' own local agent as a worker adapter (Phase 7 skeleton).

This adapter drives Hermes' built-in one-shot pipeline (``hermes -z``)
as if it were any other external coding agent. That gives the Job
Controller a sensible default worker that always works on a machine
where Hermes itself works, with no extra installation.

Status: skeleton. All methods raise :class:`NotImplementedError`. The
controller treats this adapter as unavailable until they are filled in.

See ``docs/orchestration/worker-adapter-interface.md`` §2 for the
contract this file implements.
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


class HermesLocalAdapter(WorkerAdapter):
    """Drive Hermes' local one-shot pipeline as a worker."""

    name = "hermes_local"
    description = "Hermes' own oneshot pipeline (`hermes -z`)."
    capabilities = frozenset({"code", "plan", "chat", "local"})

    def available(self) -> AvailabilityReport:
        # TODO(phase-7): probe whether the parent Hermes install is
        # importable from here without triggering its heavy module
        # graph. For now, advertise as unavailable.
        return AvailabilityReport(
            ok=False,
            reason="hermes_local adapter is a Phase 7 skeleton",
        )

    def prepare(self, job: Job) -> PreparedRun:
        # TODO(phase-7): build the exact ``hermes -z`` invocation. The
        # cwd should be the job's cwd; the prompt is piped via stdin so
        # we do not need to worry about shell quoting.
        raise NotImplementedError("hermes_local.prepare is a Phase 7 skeleton")

    def run(self, prepared: PreparedRun) -> WorkerRun:
        # TODO(phase-7): spawn ``hermes -z`` via subprocess, stream
        # stdout/stderr to the controller-supplied log paths, and
        # surface its exit code. Failures must be returned as data,
        # never raised.
        raise NotImplementedError("hermes_local.run is a Phase 7 skeleton")

    def collect_artifacts(self, run: WorkerRun) -> ArtifactBundle:
        # TODO(phase-7): inspect the working tree for an unstaged diff
        # produced by the one-shot run and bundle it.
        raise NotImplementedError(
            "hermes_local.collect_artifacts is a Phase 7 skeleton",
        )


def adapter() -> WorkerAdapter:
    """Factory consumed by ``hermes_cli.workers.load_adapter``."""
    return HermesLocalAdapter()


__all__ = ["HermesLocalAdapter", "adapter"]
