"""Canonical orchestrator decision ledger.

The orchestrator audit trail lives at::

    ~/.hermes/jobs/<job-id>/ledger.jsonl

This is the contract advertised by ``docs/orchestration/README.md`` and
the path that :mod:`muse_cli.jarvis_prime.awareness` reads when it
populates the active-jobs panel.  Until this module existed the path
had a reader but no writer, so awareness/job-listing surfaces were
silently empty.

Format
------
Line-delimited JSON.  Each line is a self-contained object::

    {"ts": "<ISO-8601 UTC>", "kind": "<event>", ...}

``ts`` is added automatically when missing.  All other fields are
caller-defined; the orchestrator emits ``kind`` values such as
``submit``, ``resume``, ``publish``, ``cancel``, ``approve``,
``validation``, ``publish-plan``, ``self-improve``.

Concurrency
-----------
One ``open(..., "a")`` + ``write()`` per entry.  POSIX guarantees an
``O_APPEND`` write up to ``PIPE_BUF`` (4 KiB on Linux) is atomic, and
our entries are well under that bound.  Multiple appenders therefore
serialize without locking.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


_JOBS_DIRNAME = "jobs"
_LEDGER_FILENAME = "ledger.jsonl"


def _hermes_home() -> Path:
    """Resolve the active Hermes home directory.

    Mirrors :func:`muse_cli.orchestrator._hermes_home` so both modules
    agree about where state lives — and so tests that set ``HERMES_HOME``
    work for both.
    """
    try:
        from hermes_constants import get_hermes_home
        return get_hermes_home()
    except Exception:
        return Path(os.environ.get("HERMES_HOME") or os.path.expanduser("~/.hermes"))


def job_dir(job_id: str) -> Path:
    return _hermes_home() / _JOBS_DIRNAME / job_id


def ledger_path(job_id: str) -> Path:
    return job_dir(job_id) / _LEDGER_FILENAME


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def append(job_id: str, entry: dict[str, Any]) -> None:
    """Append ``entry`` to the canonical ledger for ``job_id``.

    Adds ``ts`` if absent.  Creates the job directory on first write.
    """
    path = ledger_path(job_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {"ts": _now_iso(), **entry}
    line = json.dumps(payload, separators=(",", ":"), ensure_ascii=False) + "\n"
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line)


def read(job_id: str) -> list[dict[str, Any]]:
    """Return every entry for ``job_id`` in append order.

    Empty list for a non-existent or unreadable ledger.  Malformed
    individual lines are skipped (best-effort recovery — hand-edited
    files shouldn't crash the reader).
    """
    path = ledger_path(job_id)
    if not path.is_file():
        return []
    entries: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as fh:
            for raw in fh:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    obj = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if isinstance(obj, dict):
                    entries.append(obj)
    except OSError:
        return []
    return entries


def all_ledgers() -> dict[str, list[dict[str, Any]]]:
    """Return ``{job_id: entries}`` for every job that has a ledger on disk."""
    root = _hermes_home() / _JOBS_DIRNAME
    if not root.is_dir():
        return {}
    out: dict[str, list[dict[str, Any]]] = {}
    try:
        for child in root.iterdir():
            if not child.is_dir():
                continue
            if not (child / _LEDGER_FILENAME).is_file():
                continue
            out[child.name] = read(child.name)
    except OSError:
        return out
    return out


def bulk_append(job_id: str, entries: Iterable[dict[str, Any]]) -> None:
    """Append several entries in one ``open``.

    Used by the legacy-format migration helper.  Each entry still gets
    its own line; ``ts`` is preserved when present, added when not.
    """
    path = ledger_path(job_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for entry in entries:
            payload: dict[str, Any] = {"ts": _now_iso(), **entry}
            fh.write(json.dumps(payload, separators=(",", ":"), ensure_ascii=False))
            fh.write("\n")
