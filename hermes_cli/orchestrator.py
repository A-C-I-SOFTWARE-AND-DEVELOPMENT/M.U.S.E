"""Hermes Job Controller (Phase 7 skeleton).

This module is the future entry point for the slash commands described
in ``docs/orchestration/orchestrator-command-roadmap.md``:

    /orchestrate <prompt>
    /orchestrator status [job-id]
    /orchestrator open <job-id>
    /orchestrator resume <job-id>
    /orchestrator publish <job-id>
    /ai-radar update
    /model-router explain <prompt>
    /decision-ledger show [job-id]
    /best-coding-tool-mission status

Status: **skeleton**. Nothing here is wired into ``hermes_cli/main.py``
yet. The functions below define the public shape the CLI dispatcher
will eventually call; their bodies raise :class:`NotImplementedError`
or return obviously-empty placeholders so the controller is safe to
import.

Design references:
    - ``docs/orchestration/job-controller-roadmap.md``
    - ``docs/orchestration/worker-adapter-interface.md``
    - ``docs/orchestration/orchestrator-command-roadmap.md``
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal


def _utcnow() -> datetime:
    """Return a timezone-aware UTC ``datetime`` for ledger timestamps."""
    return datetime.now(timezone.utc)

JobState = Literal[
    "NEW",
    "PLANNED",
    "DISPATCHED",
    "WAITING",
    "COMPLETED",
    "FAILED",
    "CANCELLED",
]


@dataclass
class JobRecord:
    """Persistent record for one orchestrate job.

    Mirrors the on-disk layout described in
    ``docs/orchestration/job-controller-roadmap.md`` §5. The controller
    serializes this to ``${HERMES_HOME}/orchestrator/jobs/<job_id>/job.json``.
    """

    job_id: str
    prompt: str
    cwd: Path
    state: JobState = "NEW"
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)
    candidate_workers: tuple[str, ...] = ()
    run_ids: tuple[str, ...] = ()


@dataclass
class LedgerEntry:
    """One append-only event in a job's decision ledger.

    Persisted to ``ledger.jsonl`` as one JSON object per line so
    ``/decision-ledger show`` can stream it without loading the whole
    file.
    """

    timestamp: datetime
    actor: str
    event: str
    message: str


# ---------------------------------------------------------------------------
# Slash-command handlers. These are the functions the future CLI
# dispatcher will call. Each one is currently a stub; they share the
# same shape so a later PR can wire them all at once.
# ---------------------------------------------------------------------------


def orchestrate(prompt: str, *, cwd: Path | None = None) -> JobRecord:
    """Handle ``/orchestrate <prompt>``.

    Creates a new :class:`JobRecord`, asks the model router for a
    candidate list, dispatches the first available worker, and returns
    the record. Subsequent inspection happens through
    :func:`status` and :func:`open_job`.

    TODO(phase-7): implement persistence, router call, and dispatch
    loop. For now this raises so callers know the controller is not
    live.
    """
    raise NotImplementedError("orchestrate is a Phase 7 skeleton")


def status(job_id: str | None = None) -> list[JobRecord]:
    """Handle ``/orchestrator status [job-id]``.

    With ``job_id``: return a single-element list with the requested
    record. Without: return the most recent N records (default N = 10).

    TODO(phase-7): implement once persistence lands.
    """
    raise NotImplementedError("status is a Phase 7 skeleton")


def open_job(job_id: str) -> dict[str, object]:
    """Handle ``/orchestrator open <job-id>``.

    Returns a dict describing the job's working directory and the
    prepared handoff for each candidate worker. Read-only.

    TODO(phase-7): implement once :func:`orchestrate` persists jobs.
    """
    raise NotImplementedError("open_job is a Phase 7 skeleton")


def resume(job_id: str) -> JobRecord:
    """Handle ``/orchestrator resume <job-id>``.

    Re-enters a ``WAITING`` or ``FAILED`` job and runs the next
    untried candidate (or retries the last failed one once).

    TODO(phase-7): implement.
    """
    raise NotImplementedError("resume is a Phase 7 skeleton")


def publish(job_id: str, *, run_id: str | None = None) -> dict[str, object]:
    """Handle ``/orchestrator publish <job-id>``.

    Applies a worker's artifact bundle to the user's working tree. If
    more than one run succeeded the caller must pass ``run_id``
    explicitly. Never pushes to a remote.

    TODO(phase-7): implement.
    """
    raise NotImplementedError("publish is a Phase 7 skeleton")


def ai_radar_update() -> dict[str, object]:
    """Handle ``/ai-radar update``.

    Walks every adapter in ``hermes_cli.workers.BUILTIN_ADAPTERS``, calls
    ``available()``, and persists the result to
    ``${HERMES_HOME}/orchestrator/ai_radar.json``.

    TODO(phase-7): implement. The probe itself is already safe (no
    network calls), but persistence needs the orchestrator home
    directory helper, which doesn't exist yet.
    """
    raise NotImplementedError("ai_radar_update is a Phase 7 skeleton")


def model_router_explain(prompt: str) -> list[dict[str, object]]:
    """Handle ``/model-router explain <prompt>``.

    Dry-run the model router. Returns one entry per candidate worker:
    name, score, matched capability tags, and whether the AI Radar
    cache lists it as available. Does not create a job or write to
    the ledger.

    TODO(phase-7): implement once the router exists.
    """
    raise NotImplementedError("model_router_explain is a Phase 7 skeleton")


def decision_ledger_show(job_id: str | None = None) -> list[LedgerEntry]:
    """Handle ``/decision-ledger show [job-id]``.

    Streams the ledger for one job (or the most recent one) into a
    list of :class:`LedgerEntry` objects, in order. Read-only.

    TODO(phase-7): implement once jobs persist their ledgers.
    """
    raise NotImplementedError("decision_ledger_show is a Phase 7 skeleton")


def best_coding_tool_mission_status() -> dict[str, object]:
    """Handle ``/best-coding-tool-mission status``.

    Aggregates per-tool success / failure / publish counts across every
    job's ledger and returns a sorted scoreboard the model router uses
    as a tiebreaker.

    TODO(phase-7): implement once enough jobs have run to make the
    scoreboard meaningful.
    """
    raise NotImplementedError(
        "best_coding_tool_mission_status is a Phase 7 skeleton",
    )


__all__ = [
    "JobRecord",
    "JobState",
    "LedgerEntry",
    "ai_radar_update",
    "best_coding_tool_mission_status",
    "decision_ledger_show",
    "model_router_explain",
    "open_job",
    "orchestrate",
    "publish",
    "resume",
    "status",
]
