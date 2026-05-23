"""Aider worker adapter (Phase 7 skeleton).

Wraps the ``aider`` binary. Aider is a CLI pair-programmer that edits
files in place inside a git repository. The controller drives it in
``--yes`` mode with an explicit file scope to keep changes auditable.

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


class AiderAdapter(WorkerAdapter):
    """Drive Aider (``aider``) as a worker."""

    name = "aider"
    description = "Aider pair-programmer (`aider --yes`)."
    capabilities = frozenset({"code", "review"})

    def available(self) -> AvailabilityReport:
        # TODO(phase-7): ``shutil.which("aider")`` plus a check for a
        # provider API key the user has chosen for Aider. Aider
        # supports several backends; we should not hardcode one.
        return AvailabilityReport(
            ok=False,
            reason="aider adapter is a Phase 7 skeleton",
        )

    def prepare(self, job: Job) -> PreparedRun:
        # TODO(phase-7): pick the file scope. For the first cut the
        # scope is the union of files mentioned in the prompt plus
        # any file the user added to the job's metadata. Default to
        # the empty set rather than the whole repo.
        raise NotImplementedError("aider.prepare is a Phase 7 skeleton")

    def run(self, prepared: PreparedRun) -> WorkerRun:
        # TODO(phase-7): exec ``aider --yes --message <prompt> <files>``,
        # stream output. Aider exits 0 on success even when it made no
        # changes; treat "no diff" as a soft failure for routing
        # purposes, with status "succeeded" but an empty artifact
        # bundle.
        raise NotImplementedError("aider.run is a Phase 7 skeleton")

    def collect_artifacts(self, run: WorkerRun) -> ArtifactBundle:
        # TODO(phase-7): snapshot ``git diff`` and (optionally) the
        # last commit Aider produced.
        raise NotImplementedError("aider.collect_artifacts is a Phase 7 skeleton")


def adapter() -> WorkerAdapter:
    """Factory consumed by ``hermes_cli.workers.load_adapter``."""
    return AiderAdapter()


__all__ = ["AiderAdapter", "adapter"]
