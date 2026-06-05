"""Durable, append-only per-job event log for restart-replay (Sprint 14).

The orchestrator's :class:`hermes_cli.orchestrator_api.JobStore` keeps job
state — and the event envelopes that produce it — purely in memory. That copy
is lost when the process dies. This module is the missing durable seam: it tees
each job's event envelopes to disk so a restarted process can fold them back
through :func:`hermes_cli.job_replay.rebuild_snapshot` and resume mid-job.

Layout — one append-only JSONL file per job::

    ${HERMES_HOME:-~/.hermes}/jobs/<job_id>/events.jsonl

Each line is one envelope in the
:func:`hermes_cli.orchestrator_events.make_envelope` shape
(``{event, job_id, ts, data}``).

Design rules, deliberately copied from
:mod:`gateway.cockpit.event_log`:

* **Writes are best-effort and never raise into the caller.** A persistence
  failure must not break the action that emitted the event — the in-memory
  store is still the source of truth for the live process.
* **Reads consume only complete lines.** A truncated trailing line (the
  process died mid-write) is tolerated and skipped, so a replay never chokes on
  a half-written record.
* **A disable switch makes every operation a no-op.** Setting the environment
  variable :data:`PERSIST_ENV` to a falsey value (``0`` / ``false`` / ``no`` /
  ``off``) turns the tee off entirely, restoring pure in-memory behavior.

Stdlib-only; no import of FastAPI or the orchestrator. The module is safe to
import from the hot path.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List

# Environment switch that disables persistence. When set to a falsey value
# (case-insensitive ``0`` / ``false`` / ``no`` / ``off`` / empty), every public
# function below becomes a no-op and the orchestrator stays pure in-memory.
PERSIST_ENV = "HERMES_JOB_PERSIST"

_FALSEY = frozenset({"0", "false", "no", "off", ""})

_EVENTS_FILENAME = "events.jsonl"


def persistence_enabled() -> bool:
    """Return ``True`` unless :data:`PERSIST_ENV` is set to a falsey value.

    Persistence is *opt-out*: the variable being unset (the common case)
    means enabled. Only an explicit ``0`` / ``false`` / ``no`` / ``off``
    (case-insensitive) disables it.
    """
    raw = os.environ.get(PERSIST_ENV)
    if raw is None:
        return True
    return raw.strip().lower() not in _FALSEY


def _jobs_root() -> Path:
    """Resolve the ``jobs/`` root under ``HERMES_HOME`` (matches event_log.py)."""
    base = os.environ.get("HERMES_HOME") or os.path.expanduser("~/.hermes")
    return Path(base) / "jobs"


def _job_dir(job_id: str) -> Path:
    return _jobs_root() / job_id


def _events_path(job_id: str) -> Path:
    return _job_dir(job_id) / _EVENTS_FILENAME


def append(job_id: str, envelope: Dict[str, Any]) -> None:
    """Append one envelope to ``jobs/<job_id>/events.jsonl``. Best-effort.

    Swallows every error — a durability failure must never propagate into the
    orchestrator's event-emission fast path. A no-op when persistence is
    disabled or ``job_id`` is empty.
    """
    if not job_id or not persistence_enabled():
        return
    try:
        path = _events_path(job_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(envelope, default=str) + "\n")
    except Exception:  # pragma: no cover - persistence must never break callers
        pass


def read(job_id: str) -> List[Dict[str, Any]]:
    """Return the persisted envelopes for ``job_id``, oldest→newest.

    Only whole lines are parsed; a truncated trailing line (a crash mid-write)
    is skipped rather than raised on, mirroring
    :func:`gateway.cockpit.event_log.read`. Returns ``[]`` when persistence is
    disabled, the file is absent, or it cannot be read.
    """
    if not job_id or not persistence_enabled():
        return []
    path = _events_path(job_id)
    if not path.is_file():
        return []
    out: List[Dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as fh:
            for raw in fh:
                # A complete record ends in a newline. The final line of a
                # file truncated by a crash will not — drop it rather than
                # feed the reducer a half-written envelope.
                if not raw.endswith("\n"):
                    continue
                line = raw.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if isinstance(rec, dict):
                    out.append(rec)
    except OSError:  # pragma: no cover - defensive
        return []
    return out


def iter_job_ids() -> List[str]:
    """List job ids that have a persisted event log on disk.

    A job id is reported only when its ``events.jsonl`` exists, so a stray
    empty directory does not resurrect a phantom job. Returns ``[]`` when
    persistence is disabled or the root is absent/unreadable.
    """
    if not persistence_enabled():
        return []
    root = _jobs_root()
    if not root.is_dir():
        return []
    job_ids: List[str] = []
    try:
        for child in root.iterdir():
            try:
                if child.is_dir() and (child / _EVENTS_FILENAME).is_file():
                    job_ids.append(child.name)
            except OSError:  # pragma: no cover - defensive per-entry
                continue
    except OSError:  # pragma: no cover - defensive
        return []
    return job_ids


__all__ = [
    "PERSIST_ENV",
    "append",
    "iter_job_ids",
    "persistence_enabled",
    "read",
]
