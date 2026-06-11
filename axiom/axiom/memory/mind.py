"""The Mind facade: one front door to the memory plane (Phase 2).

Wires MemoryStore (FSRS economy) + BeliefBase (AGM revision) +
routed retrieval behind three verbs — observe, recall,
on_verification — all persisted on disk so a process kill loses
nothing. A contradiction against an entrenched belief raises
OwnerRequired *and* leaves a contradiction_report in the ledger:
the machine never decides such conflicts, and never hides them.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from ..core.ledger import Ledger
from .beliefs import BeliefBase, ENTRENCH_DEFAULT, OwnerRequired
from .fsrs_memory import MemoryStore
from .retrieval import retrieve


class Mind:
    """Facade over the three memory stores, ledgered."""

    def __init__(self, data_dir: str | Path, ledger: Ledger):
        data_dir = Path(data_dir)
        data_dir.mkdir(parents=True, exist_ok=True)
        self.memories = MemoryStore(str(data_dir / "memory.db"))
        self.beliefs = BeliefBase(str(data_dir / "beliefs.db"))
        self.ledger = ledger

    # ---------------------------------------------------------------- write
    def observe(
        self,
        content: str,
        source_grade: str = "",
        contradicts: int | None = None,
        entrenchment: float = ENTRENCH_DEFAULT,
    ) -> int:
        """Record an observation as a working-tier memory.

        If *contradicts* names an existing belief, the belief base is
        revised. When that belief is entrenched, OwnerRequired is
        raised — but only after a contradiction_report is ledgered:
        conflicts are surfaced, never swallowed.
        """
        if contradicts is not None:
            try:
                self.beliefs.revise(content, contradicts, entrenchment)
            except OwnerRequired:
                self.ledger.append(
                    "contradiction_report",
                    {"belief_id": contradicts,
                     "belief": self.beliefs.get(contradicts)["statement"],
                     "observation": content,
                     "source_grade": source_grade},
                )
                raise
        memory_id = self.memories.observe(content, source_grade)
        return memory_id

    def believe(
        self, statement: str, entrenchment: float = ENTRENCH_DEFAULT
    ) -> int:
        return self.beliefs.assert_belief(statement, entrenchment)

    # ----------------------------------------------------------------- read
    def recall(self, query: str, k: int = 5) -> list[dict]:
        return retrieve(query, self.memories.all(), k=k)

    # ------------------------------------------------------------- feedback
    def on_verification(
        self,
        memory_ids: list[int],
        passed: bool,
        review_datetime: datetime | None = None,
    ) -> dict[int, str]:
        """Grade memories by verifier outcome; returns id -> new tier."""
        return {
            mid: self.memories.on_verification(
                mid, passed, review_datetime=review_datetime
            )
            for mid in memory_ids
        }
