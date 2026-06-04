"""Append-only structured event log for the cockpit.

One JSON line per event at ``${HERMES_HOME:-~/.hermes}/cockpit/events.jsonl`` in
the contract's ``CockpitEvent`` shape::

    {ts, level: info|warn|error, source: gateway|worker|hook|cron, job_id,
     message, attributes}

It powers ``GET /v1/cockpit/events/stream`` (tail-and-emit). Writes are
best-effort and **never raise into the caller** — an event-log failure must not
break the action that emitted it. Reads consume only *complete* lines, so a tail
that races a concurrent ``emit`` never sees a half-written record.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

LEVELS = ("info", "warn", "error")
SOURCES = ("gateway", "worker", "hook", "cron")


def _path() -> Path:
    base = os.environ.get("HERMES_HOME") or os.path.expanduser("~/.hermes")
    return Path(base) / "cockpit" / "events.jsonl"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def emit(
    level: str,
    source: str,
    message: str,
    *,
    job_id: Optional[str] = None,
    attributes: Optional[dict[str, Any]] = None,
) -> None:
    """Append one event. Best-effort — swallows every error."""
    record = {
        "ts": _now_iso(),
        "level": level if level in LEVELS else "info",
        "source": source if source in SOURCES else "gateway",
        "job_id": job_id,
        "message": str(message),
        "attributes": dict(attributes or {}),
    }
    try:
        path = _path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, default=str) + "\n")
    except Exception:  # pragma: no cover - logging must never break the caller
        pass


def current_offset() -> int:
    """Byte size of the log now — the point a fresh tail should start from."""
    path = _path()
    try:
        return path.stat().st_size if path.is_file() else 0
    except OSError:  # pragma: no cover - defensive
        return 0


def read_since_offset(offset: int) -> tuple[list[dict[str, Any]], int]:
    """Return ``(new_records, new_offset)`` for complete lines added since ``offset``.

    Only whole lines (up to the last newline) are consumed; a trailing partial
    line is left for the next read. A shrunk file (rotation/truncation) restarts
    from 0.
    """
    path = _path()
    if not path.is_file():
        return [], offset
    try:
        size = path.stat().st_size
        if size < offset:  # rotated/truncated → restart
            offset = 0
        with path.open("rb") as fh:
            fh.seek(offset)
            data = fh.read()
    except OSError:  # pragma: no cover - defensive
        return [], offset
    newline = data.rfind(b"\n")
    if newline == -1:
        return [], offset  # no complete line yet
    consumed = data[: newline + 1]
    new_offset = offset + len(consumed)
    records: list[dict[str, Any]] = []
    for line in consumed.decode("utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if isinstance(rec, dict):
            records.append(rec)
    return records, new_offset


__all__ = ["emit", "current_offset", "read_since_offset", "LEVELS", "SOURCES"]
