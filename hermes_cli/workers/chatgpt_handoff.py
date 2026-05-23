"""ChatGPT manual-handoff worker adapter (Phase 7 skeleton).

ChatGPT does not expose a usable headless CLI on the user's own paid
subscription. This adapter therefore does not execute anything itself:
its job is to *prepare* a structured prompt and surface it to the user
so they can paste it into their existing ChatGPT session (web or
mobile app), exactly like the Android local orchestrator does today
(see ``docs/hermes-local-orchestrator.md``).

This matches the ``handoff`` capability described in
``docs/orchestration/worker-adapter-interface.md`` §3: the adapter
advertises itself, the controller routes to it, but the loop is closed
by the user, not by Hermes.

Status: skeleton. All methods raise :class:`NotImplementedError`.
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


class ChatGPTHandoffAdapter(WorkerAdapter):
    """Build a structured prompt for manual ChatGPT handoff."""

    name = "chatgpt_handoff"
    description = "Manual ChatGPT handoff: builds a prompt for the user to paste."
    capabilities = frozenset({"chat", "plan", "review", "handoff"})

    def available(self) -> AvailabilityReport:
        # The handoff adapter is *always* available — it has no
        # external dependencies. But Phase 7 still ships it as
        # unavailable so the controller does not surface it before
        # the controller itself is wired up.
        # TODO(phase-7): flip ``ok=True`` once the controller lands.
        return AvailabilityReport(
            ok=False,
            reason="chatgpt_handoff adapter is a Phase 7 skeleton",
        )

    def prepare(self, job: Job) -> PreparedRun:
        # TODO(phase-7): borrow the prompt-builder logic used by the
        # Android orchestrator's ``PromptBuilder``. Output is a single
        # text payload destined for the user's clipboard — argv stays
        # empty because no process is launched.
        raise NotImplementedError(
            "chatgpt_handoff.prepare is a Phase 7 skeleton",
        )

    def run(self, prepared: PreparedRun) -> WorkerRun:
        # TODO(phase-7): "run" for this adapter means: copy the
        # prepared prompt to the clipboard (best effort), record the
        # handoff in the ledger, and return ``status="succeeded"``
        # with an empty exit code. The actual work happens in the
        # user's browser / app, outside Hermes.
        raise NotImplementedError("chatgpt_handoff.run is a Phase 7 skeleton")

    def collect_artifacts(self, run: WorkerRun) -> ArtifactBundle:
        # Handoff adapters have no artifact to collect — the user is
        # the one with the result. Return an empty bundle once
        # implemented.
        raise NotImplementedError(
            "chatgpt_handoff.collect_artifacts is a Phase 7 skeleton",
        )


def adapter() -> WorkerAdapter:
    """Factory consumed by ``hermes_cli.workers.load_adapter``."""
    return ChatGPTHandoffAdapter()


__all__ = ["ChatGPTHandoffAdapter", "adapter"]
