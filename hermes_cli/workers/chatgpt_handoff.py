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

Status: skeleton. ``detect()`` returns ``available=False`` so the
controller will skip the adapter until the rest of the handoff flow is
wired up; every other method raises :class:`NotImplementedError`. The
module imports cleanly without any optional CLI installed.
"""

from __future__ import annotations

from typing import Any

from hermes_cli.workers.base import (
    WorkerAdapter,
    WorkerArtifacts,
    WorkerDetection,
    WorkerPrompt,
    WorkerRunResult,
    WorkerScore,
)


class ChatGPTHandoffAdapter(WorkerAdapter):
    """Build a structured prompt for manual ChatGPT handoff."""

    id = "chatgpt-handoff"
    display_name = "ChatGPT (manual handoff)"

    def detect(self) -> WorkerDetection:
        # The handoff adapter has no external dependency, but Phase 7
        # still ships it as unavailable so the controller does not
        # surface it before the rest of the handoff flow is wired up.
        # TODO(phase-7): flip ``available=True`` once the controller's
        # clipboard / handoff plumbing lands.
        return WorkerDetection(
            available=False,
            reason="chatgpt-handoff adapter is a Phase 7 skeleton",
            details={"capabilities": ("chat", "plan", "review", "handoff")},
        )

    def prepare_prompt(self, job: Any) -> WorkerPrompt:
        # TODO(phase-7): borrow the prompt-builder logic used by the
        # Android orchestrator's ``PromptBuilder``. The text payload is
        # destined for the user's clipboard — no argv, no subprocess.
        raise NotImplementedError(
            "chatgpt-handoff.prepare_prompt is a Phase 7 skeleton",
        )

    def run(self, job: Any) -> WorkerRunResult:
        # TODO(phase-7): "run" for this adapter means copy the prepared
        # prompt to the clipboard (best effort), record the handoff in
        # the ledger, and return ``ok=True`` with an empty exit code.
        # The actual work happens in the user's browser / app, outside
        # Hermes.
        raise NotImplementedError(
            "chatgpt-handoff.run is a Phase 7 skeleton",
        )

    def collect(self, job: Any) -> WorkerArtifacts:
        # Handoff adapters have no artifact to collect — the user is
        # the one with the result. Return an empty bundle once
        # implemented.
        raise NotImplementedError(
            "chatgpt-handoff.collect is a Phase 7 skeleton",
        )

    def score(self, artifacts: WorkerArtifacts) -> WorkerScore:
        # Handoff outcomes aren't observable from Hermes; scoring is
        # something the user supplies out-of-band via the decision
        # ledger. The Phase 7 skeleton refuses to invent a number.
        raise NotImplementedError(
            "chatgpt-handoff.score is a Phase 7 skeleton",
        )


def adapter() -> WorkerAdapter:
    """Factory consumed by ``hermes_cli.workers.load_adapter``."""
    return ChatGPTHandoffAdapter()


__all__ = ["ChatGPTHandoffAdapter", "adapter"]
