"""Append-only decision ledger for orchestration jobs.

The decision ledger is the audit trail for everything the orchestrator
does on behalf of a job: phase transitions, approval requests, model
routing decisions, worker spawns, validation outcomes, publish steps.

The on-disk format is **JSONL** under
``$HERMES_HOME/orchestrator/jobs/<job-id>/ledger.jsonl``.  One entry
per line, each line a JSON object with at least:

    {"ts": <unix-microseconds>, "kind": "<event-kind>", ...}

JSONL is chosen over JSON-array so the file can be appended to without
re-reading; that keeps writes O(1) even on long jobs.

The ledger is intentionally write-once-per-event: do not rewrite or
delete entries in place.  If a later event supersedes an earlier one,
record the supersession as a new entry.

TODO:
    * Add a ``verify_ledger`` hash chain for tamper detection.
    * Provide a streaming reader for the live-status TUI.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Iterator


_LEDGER_FILENAME = "ledger.jsonl"


def _now_us() -> int:
    """Return a monotonically-increasing unix timestamp in microseconds."""
    # Same monotonic-tie guard the orchestrator uses for created_at.
    global _LAST_TS
    candidate = time.time_ns() // 1_000
    if candidate <= _LAST_TS:
        candidate = _LAST_TS + 1
    _LAST_TS = candidate
    return candidate


_LAST_TS = 0


@dataclass
class LedgerEntry:
    """One audit-trail event."""

    kind: str
    payload: dict[str, Any] = field(default_factory=dict)
    ts: int = 0

    def to_dict(self) -> dict[str, Any]:
        out = {"ts": self.ts or _now_us(), "kind": self.kind}
        out.update(self.payload)
        return out


class DecisionLedger:
    """Append-only JSONL ledger for one job."""

    def __init__(self, job_dir: str | os.PathLike[str]) -> None:
        self.job_dir = Path(job_dir)
        self.path = self.job_dir / _LEDGER_FILENAME

    # ── write ─────────────────────────────────────────────────────────────

    def append(self, kind: str, **payload: Any) -> LedgerEntry:
        """Append a new entry of ``kind`` with arbitrary keyword payload."""
        entry = LedgerEntry(kind=kind, payload=dict(payload), ts=_now_us())
        self._write_line(entry.to_dict())
        return entry

    def extend(self, entries: Iterable[LedgerEntry]) -> None:
        for entry in entries:
            self._write_line(entry.to_dict())

    def _write_line(self, obj: dict[str, Any]) -> None:
        self.job_dir.mkdir(parents=True, exist_ok=True)
        line = json.dumps(obj, ensure_ascii=False, sort_keys=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")

    # ── read ──────────────────────────────────────────────────────────────

    def entries(self) -> list[dict[str, Any]]:
        """Return every entry as a list of dicts.  Skips malformed lines."""
        if not self.path.exists():
            return []
        out: list[dict[str, Any]] = []
        with self.path.open("r", encoding="utf-8") as f:
            for raw in f:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    out.append(json.loads(raw))
                except json.JSONDecodeError:
                    continue
        return out

    def iter_entries(self) -> Iterator[dict[str, Any]]:
        if not self.path.exists():
            return iter(())
        def _gen() -> Iterator[dict[str, Any]]:
            with self.path.open("r", encoding="utf-8") as f:
                for raw in f:
                    raw = raw.strip()
                    if not raw:
                        continue
                    try:
                        yield json.loads(raw)
                    except json.JSONDecodeError:
                        continue
        return _gen()

    def entries_of_kind(self, kind: str) -> list[dict[str, Any]]:
        return [e for e in self.entries() if e.get("kind") == kind]

    def last_of_kind(self, kind: str) -> dict[str, Any] | None:
        last: dict[str, Any] | None = None
        for e in self.entries():
            if e.get("kind") == kind:
                last = e
        return last


def open_ledger(job_dir: str | os.PathLike[str]) -> DecisionLedger:
    """Convenience factory matching the controller's import style."""
    return DecisionLedger(job_dir)


__all__ = [
    "LedgerEntry",
    "DecisionLedger",
    "open_ledger",
]
