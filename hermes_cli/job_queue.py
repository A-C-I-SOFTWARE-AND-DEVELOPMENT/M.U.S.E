"""In-memory + on-disk queue of orchestration jobs.

The job queue tracks which jobs are *waiting* for the controller to
pick them up next.  It is intentionally small: the authoritative job
state lives in each job's ``job.json`` (managed by the controller).
The queue is just an ordered list of job ids the controller pops from
in FIFO order when running batched phase transitions.

The queue is persisted under
``$HERMES_HOME/orchestrator/queue.json`` so that a controller restart
picks up where it left off.

TODO:
    * Add priority lanes (e.g. ``urgent``, ``background``).
    * Add a ``in_progress`` set so multiple controllers can cooperate
      (file-locked).
"""

from __future__ import annotations

import json
import os
from collections import deque
from pathlib import Path
from threading import Lock
from typing import Iterable


_QUEUE_FILENAME = "queue.json"


class JobQueue:
    """FIFO queue of job ids with filesystem persistence."""

    def __init__(self, root: str | os.PathLike[str]) -> None:
        self.root = Path(root)
        self.path = self.root / _QUEUE_FILENAME
        self._lock = Lock()
        self._items: deque[str] = deque(self._load())

    # ── persistence ───────────────────────────────────────────────────────

    def _load(self) -> list[str]:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return []
        if not isinstance(data, list):
            return []
        return [str(x) for x in data if isinstance(x, (str, int))]

    def _persist(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(
            json.dumps(list(self._items), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(tmp, self.path)

    # ── queue ops ─────────────────────────────────────────────────────────

    def enqueue(self, job_id: str) -> None:
        with self._lock:
            if job_id in self._items:
                return  # idempotent
            self._items.append(job_id)
            self._persist()

    def dequeue(self) -> str | None:
        with self._lock:
            if not self._items:
                return None
            out = self._items.popleft()
            self._persist()
            return out

    def remove(self, job_id: str) -> bool:
        with self._lock:
            try:
                self._items.remove(job_id)
            except ValueError:
                return False
            self._persist()
            return True

    def peek(self) -> str | None:
        with self._lock:
            return self._items[0] if self._items else None

    def snapshot(self) -> list[str]:
        with self._lock:
            return list(self._items)

    def extend(self, ids: Iterable[str]) -> None:
        with self._lock:
            for jid in ids:
                if jid not in self._items:
                    self._items.append(jid)
            self._persist()

    def __len__(self) -> int:
        with self._lock:
            return len(self._items)

    def __contains__(self, item: object) -> bool:
        if not isinstance(item, str):
            return False
        with self._lock:
            return item in self._items


__all__ = ["JobQueue"]
