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


def _record_passes(
    rec: Any,
    since: Optional[str],
    levels: Optional[set],
    sources: Optional[set],
    job_id: Optional[str],
) -> bool:
    """The shared filter for :func:`read` — one record, one verdict."""
    if not isinstance(rec, dict):
        return False
    if since and str(rec.get("ts", "")) < since:
        return False
    if levels is not None and rec.get("level") not in levels:
        return False
    if sources is not None and rec.get("source") not in sources:
        return False
    if job_id and rec.get("job_id") != job_id:
        return False
    return True


# Block size for the backwards tail-read below. 256 KiB comfortably holds
# hundreds of records per read() syscall while staying cache-friendly.
_TAIL_BLOCK = 256 * 1024


def _read_tail(
    path: Path,
    since: Optional[str],
    levels: Optional[set],
    sources: Optional[set],
    job_id: Optional[str],
    limit: int,
) -> list[dict[str, Any]]:
    """Last ``limit`` matching records via a backwards block scan.

    Equivalent to full-scanning and keeping ``out[-limit:]`` — "the last N
    matching" is exactly what collecting N matches while walking backwards
    yields — but reads only the tail blocks it needs, so a request for the
    recent window stays fast no matter how large the (append-only, never yet
    rotated) log has grown.
    """
    out_rev: list[dict[str, Any]] = []
    try:
        with path.open("rb") as fh:
            fh.seek(0, os.SEEK_END)
            pos = fh.tell()
            carry = b""
            while pos > 0 and len(out_rev) < limit:
                step = min(_TAIL_BLOCK, pos)
                pos -= step
                fh.seek(pos)
                data = fh.read(step) + carry
                if pos > 0:
                    # First line fragment may continue in the previous block —
                    # carry it backwards instead of parsing a partial record.
                    nl = data.find(b"\n")
                    if nl == -1:
                        carry = data
                        continue
                    carry = data[:nl]
                    chunk = data[nl + 1 :]
                else:
                    carry = b""
                    chunk = data
                for raw in reversed(chunk.split(b"\n")):
                    if len(out_rev) >= limit:
                        break
                    line = raw.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line.decode("utf-8", errors="ignore"))
                    except ValueError:
                        continue
                    if _record_passes(rec, since, levels, sources, job_id):
                        out_rev.append(rec)
    except OSError:  # pragma: no cover - defensive
        return []
    out_rev.reverse()
    return out_rev


def read(
    *,
    since: Optional[str] = None,
    level: Optional[str] = None,
    source: Optional[str] = None,
    job_id: Optional[str] = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Recent events (filtered), oldest→newest, capped at ``limit``.

    ``level`` / ``source`` are comma-separated allow-lists; ``since`` is an
    inclusive ISO-timestamp lower bound. Returns the last ``limit`` matching
    records. Honest-empty when absent.

    For ``limit > 0`` this tail-reads the file backwards in blocks and stops
    as soon as ``limit`` matches are collected — the log is append-only and
    unrotated, so a full scan was costing hundreds of ms once the file grew
    to tens of MB. ``limit=0`` (all matching records) still full-scans.
    """
    path = _path()
    if not path.is_file():
        return []
    levels = {v.strip() for v in (level or "").split(",") if v.strip()} or None
    sources = {v.strip() for v in (source or "").split(",") if v.strip()} or None
    if limit and limit > 0:
        return _read_tail(path, since, levels, sources, job_id, limit)
    out: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as fh:
            for raw in fh:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    rec = json.loads(raw)
                except ValueError:
                    continue
                if _record_passes(rec, since, levels, sources, job_id):
                    out.append(rec)
    except OSError:  # pragma: no cover - defensive
        return []
    return out


__all__ = [
    "emit", "current_offset", "read_since_offset", "read", "LEVELS", "SOURCES",
]
