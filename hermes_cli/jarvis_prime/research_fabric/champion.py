"""Champion / challenger baselines for the research fabric.

The *champion* is the currently-trusted configuration: frozen per-domain scores
plus a ``rollback_handle`` (a git sha or snapshot id) the controller can revert
to instantly. A challenger only becomes the champion by clearing the strict
ratchet (:mod:`research_fabric.validators`) — the AlphaGo-Zero gating pattern.

Every freeze writes BOTH an indexed row (:class:`SnapshotStore`) and a
hash-chained ledger record (:class:`GuardrailLedger`), so the promotion history
is queryable *and* tamper-evident.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping, Optional

from hermes_cli.jarvis_prime.guardrail_evidence import GuardrailLedger

from .store import SnapshotStore


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class Champion:
    champion_id: str
    domain_scores: Mapping[str, float]
    composite: float
    safety_counts: Mapping[str, float]
    rollback_handle: str
    frozen_at: str
    note: str = ""

    @classmethod
    def make(
        cls,
        *,
        domain_scores: Mapping[str, float],
        composite: float,
        rollback_handle: str,
        safety_counts: Optional[Mapping[str, float]] = None,
        note: str = "",
    ) -> "Champion":
        return cls(
            champion_id=f"champ_{uuid.uuid4().hex[:16]}",
            domain_scores=dict(domain_scores),
            composite=round(float(composite), 4),
            safety_counts=dict(safety_counts or {}),
            rollback_handle=rollback_handle,
            frozen_at=_utc_iso(),
            note=note,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "champion_id": self.champion_id,
            "domain_scores": dict(self.domain_scores),
            "composite": self.composite,
            "safety_counts": dict(self.safety_counts),
            "rollback_handle": self.rollback_handle,
            "frozen_at": self.frozen_at,
            "note": self.note,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Champion":
        return cls(
            champion_id=str(data.get("champion_id", f"champ_{uuid.uuid4().hex[:16]}")),
            domain_scores={k: float(v) for k, v in dict(data.get("domain_scores", {})).items()},
            composite=float(data.get("composite", 0.0)),
            safety_counts={k: float(v) for k, v in dict(data.get("safety_counts", {})).items()},
            rollback_handle=str(data.get("rollback_handle", "")),
            frozen_at=str(data.get("frozen_at", "")),
            note=str(data.get("note", "")),
        )


@dataclass
class ChampionStore:
    """Tracks the current champion plus the full promotion lineage."""

    store: SnapshotStore
    ledger: GuardrailLedger
    _current: Optional[Champion] = field(default=None, init=False)

    def __post_init__(self) -> None:
        row = self.store.latest("champion_freeze")
        if row is not None:
            import json

            payload = json.loads(row["payload_json"])
            champ = payload.get("champion")
            if champ:
                self._current = Champion.from_dict(champ)

    def current(self) -> Optional[Champion]:
        return self._current

    def rollback_handle(self) -> Optional[str]:
        return self._current.rollback_handle if self._current else None

    def freeze(self, champion: Champion, *, reason: str = "") -> Champion:
        """Promote ``champion`` to current; record to ledger + index."""

        previous = self._current.to_dict() if self._current else None
        rec = self.ledger.append(
            "champion_freeze",
            champion.champion_id,
            {"champion": champion.to_dict(), "previous": previous, "reason": reason},
        )
        self.store.record_snapshot(
            "champion_freeze",
            champion.champion_id,
            {"champion": champion.to_dict(), "previous": previous, "reason": reason},
            ledger_record_hash=rec.record_hash,
        )
        self._current = champion
        return champion


__all__ = ["Champion", "ChampionStore"]
