"""The Swarm Blackboard — stigmergic, indirect coordination for grains.

Per the research, agents that message each other directly scale poorly (adding
an agent forces edits to every other) and the proven pattern is a **blackboard**:
a shared, append-only space agents read from and write to, coordinating
*indirectly* via the traces they leave — never by talking to each other. This
matches Anthropic's "subagents don't coordinate mid-task" finding.

The blackboard is a thin view over the JARVIS Memory Tree: each swarm job owns
the namespace ``swarm/<job-id>``. Grains ``post`` dated notes (a decision, a
discovered interface, a blocker); the coordinator and the Grainler ``read`` them
to re-plan. It is durable, provenance-tagged, and audit-friendly by
construction, and the existing GraphRAG memory indexer already turns these notes
into queryable graph nodes — no new indexer required.

When no memory store is supplied the blackboard degrades to an in-process list,
so it is always safe to call (and unit-testable without HERMES_HOME).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional
import threading

from hermes_cli.swarm.grain import now_iso

__all__ = ["BlackboardEntry", "SwarmBlackboard"]


@dataclass
class BlackboardEntry:
    grain_id: str
    note: str
    kind: str = "note"  # note | decision | interface | blocker
    created_at: str = field(default_factory=now_iso)

    def to_dict(self) -> dict[str, Any]:
        return {
            "grain_id": self.grain_id,
            "note": self.note,
            "kind": self.kind,
            "created_at": self.created_at,
        }


class SwarmBlackboard:
    """Append-only coordination space for one swarm job."""

    def __init__(self, job_id: str, *, memory_store: Optional[Any] = None) -> None:
        self.job_id = job_id
        self.namespace = f"swarm/{job_id}"
        self._memory = memory_store
        self._local: list[BlackboardEntry] = []
        self._lock = threading.Lock()

    def post(self, grain_id: str, note: str, *, kind: str = "note") -> BlackboardEntry:
        """Leave a dated trace. Thread-safe (grains post concurrently)."""

        entry = BlackboardEntry(grain_id=grain_id, note=note, kind=kind)
        with self._lock:
            self._local.append(entry)
        if self._memory is not None:
            try:
                self._memory.write(
                    f"[{kind}] grain {grain_id}: {note}",
                    namespace=self.namespace,
                    title=f"{self.job_id}:{grain_id}:{kind}",
                    source_uri=f"swarm://{self.job_id}/{grain_id}",
                    tags=("swarm", kind),
                )
            except Exception:
                pass
        return entry

    def read(self) -> list[BlackboardEntry]:
        """Return every trace posted in this process for the job (chronological)."""

        with self._lock:
            return list(self._local)

    def query(self, query: str, *, limit: int = 20) -> list[dict[str, Any]]:
        """Search the durable blackboard namespace (memory-backed) for ``query``.

        Falls back to a substring scan of the in-process entries when no memory
        store is attached.
        """

        if self._memory is not None:
            try:
                hits = self._memory.search(
                    query, namespaces=[self.namespace], limit=limit
                )
                out: list[dict[str, Any]] = []
                for hit in hits:
                    node = getattr(hit, "node", hit)
                    out.append(
                        {
                            "title": getattr(node, "title", ""),
                            "text": getattr(node, "text", "") or getattr(node, "summary", ""),
                        }
                    )
                return out
            except Exception:
                pass
        q = query.lower()
        return [e.to_dict() for e in self.read() if q in e.note.lower()]
