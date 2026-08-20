"""Belief ledger — machine-readable claims with evidence states (directive §50).

Every material claim the Foundry relies on is a ledger entry. When evidence
refutes a claim, dependents are reopened automatically.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Optional

STATES = (
    "VERIFIED_LOCAL", "VERIFIED_UPSTREAM", "MEASURED",
    "INFERRED", "UNVERIFIED", "REFUTED",
)
PROMOTION_STATES = {"VERIFIED_LOCAL", "VERIFIED_UPSTREAM", "MEASURED"}


@dataclass
class Belief:
    claim_id: str
    statement: str
    status: str = "UNVERIFIED"
    evidence: list[str] = field(default_factory=list)
    source_revision: str = ""
    measurement: str = ""
    confidence: float = 0.0
    depends_on: list[str] = field(default_factory=list)
    last_checked: float = field(default_factory=time.time)
    invalidates: list[str] = field(default_factory=list)


class BeliefLedger:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._beliefs: dict[str, Belief] = {}
        if self.path.exists():
            for raw in json.loads(self.path.read_text()):
                b = Belief(**raw)
                self._beliefs[b.claim_id] = b

    def save(self) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps([asdict(b) for b in self._beliefs.values()], indent=2))
        tmp.replace(self.path)

    def assert_claim(self, belief: Belief) -> None:
        if belief.status not in STATES:
            raise ValueError(f"bad status {belief.status!r}")
        belief.last_checked = time.time()
        self._beliefs[belief.claim_id] = belief
        self.save()

    def refute(self, claim_id: str, evidence: str) -> list[str]:
        """Mark REFUTED and reopen everything that depended on it (§50)."""
        b = self._beliefs[claim_id]
        b.status = "REFUTED"
        b.evidence.append(evidence)
        b.last_checked = time.time()
        reopened = [c for c, other in self._beliefs.items() if claim_id in other.depends_on]
        for cid in reopened:
            dep = self._beliefs[cid]
            if dep.status in PROMOTION_STATES:
                dep.status = "UNVERIFIED"
                dep.evidence.append(f"reopened: dependency {claim_id} was REFUTED")
                dep.last_checked = time.time()
        self.save()
        return reopened

    def promotable(self, claim_id: str) -> bool:
        b = self._beliefs.get(claim_id)
        return bool(b and b.status in PROMOTION_STATES)
