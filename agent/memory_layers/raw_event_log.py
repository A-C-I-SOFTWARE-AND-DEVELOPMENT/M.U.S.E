"""Append-only raw memory-event log (MEM-1).

Local-first, gitignored JSONL at ``$HERMES_HOME/memory-raw/<scope>.jsonl``. This
is the bottom layer of the memory architecture: every candidate memory is
recorded here with full provenance BEFORE any promotion decision, so the
pipeline is auditable and reconstructible. It is **never auto-read into the
prompt** — retrieval goes through the existing MemoryProvider + the selective
filter in ``retrieval.py``.

Writes fail open: a logging failure never breaks the caller.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Iterable, Optional

from .provenance import MemoryEvent

logger = logging.getLogger(__name__)


def _base_dir() -> Path:
    home = os.environ.get("HERMES_HOME") or os.path.join(os.path.expanduser("~"), ".hermes")
    return Path(home) / "memory-raw"


def _safe(scope: str) -> str:
    return "".join(c if (c.isalnum() or c in "-_.") else "_" for c in (scope or "global"))[:120]


def record(event: MemoryEvent, scope: str = "global") -> Optional[str]:
    """Append one event. Returns the log path, or None on failure."""
    try:
        directory = _base_dir()
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{_safe(scope)}.jsonl"
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")
        return str(path)
    except Exception as err:  # fail open
        logger.debug("[memory] raw_event_log.record failed: %s", err)
        return None


def read_all(scope: str = "global") -> list[MemoryEvent]:
    """Read back all events for a scope (debug / curator use)."""
    path = _base_dir() / f"{_safe(scope)}.jsonl"
    out: list[MemoryEvent] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            d = json.loads(line)
            out.append(
                MemoryEvent(
                    content=d.get("content", ""),
                    source=d.get("source", "unknown"),
                    trust_level=d.get("trust_level", "untrusted"),
                    originating_tool=d.get("originating_tool"),
                    permissions=tuple(d.get("permissions") or ()),
                    user_approval_state=d.get("user_approval_state", "unreviewed"),
                    timestamp=float(d.get("timestamp", 0.0)),
                    metadata=tuple((d.get("metadata") or {}).items()),
                )
            )
    except OSError:
        return out
    except ValueError:
        return out
    return out
