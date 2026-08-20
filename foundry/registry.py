"""Foundry artifact registry — content-addressed lineage for specialist models.

Separate from AXIOM's native Registry (directive §41): AXIOM does not natively
model ML checkpoints/training lineage, so the Foundry keeps its own registry and
attaches AXIOM attestations by hash reference.

Storage: a single JSON file (append-safe, human-auditable). Content-addressed
identity via sha256 of every artifact in the chain.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Optional

LIFECYCLE = (
    "CANDIDATE", "DATA_PREP", "TRAINING", "EVALUATING", "FAILED", "SHADOW",
    "CANARY", "ACTIVE", "DEGRADED", "QUARANTINED", "RETIRED",
)


def sha256_file(path: os.PathLike | str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass
class SpecialistRecord:
    specialist_id: str
    niche_id: str
    specialist_version: str
    status: str = "CANDIDATE"
    base_model_id: str = "Cactus-Compute/needle2"
    base_revision: str = ""
    base_hash: str = ""
    engine_hash: str = ""
    tokenizer_hash: str = ""
    schema_hash: str = ""
    dataset_hash: str = ""
    adapter_hash: str = ""
    final_model_hash: str = ""
    eval_report_hash: str = ""
    training_config_hash: str = ""
    metrics: dict[str, Any] = field(default_factory=dict)
    thresholds: dict[str, float] = field(default_factory=dict)
    provider_lineage: list[str] = field(default_factory=list)
    axiom_attestation: str = ""
    created_at: float = field(default_factory=time.time)
    promoted_at: Optional[float] = None
    history: list[dict[str, Any]] = field(default_factory=list)

    def transition(self, new_status: str, reason: str) -> None:
        if new_status not in LIFECYCLE:
            raise ValueError(f"unknown lifecycle state {new_status!r}")
        self.history.append(
            {"from": self.status, "to": new_status, "reason": reason, "at": time.time()}
        )
        self.status = new_status
        if new_status == "ACTIVE":
            self.promoted_at = time.time()

    @property
    def content_id(self) -> str:
        """Content-addressed identity over the lineage-critical hashes."""
        h = hashlib.sha256()
        for part in (
            self.specialist_id, self.specialist_version, self.base_hash,
            self.schema_hash, self.dataset_hash, self.adapter_hash,
            self.final_model_hash,
        ):
            h.update(part.encode())
        return h.hexdigest()


class FoundryRegistry:
    def __init__(self, path: os.PathLike | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._records: dict[str, SpecialistRecord] = {}
        if self.path.exists():
            for raw in json.loads(self.path.read_text()):
                rec = SpecialistRecord(**raw)
                self._records[rec.content_id] = rec

    def save(self) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps([asdict(r) for r in self._records.values()], indent=2))
        tmp.replace(self.path)

    def register(self, rec: SpecialistRecord) -> str:
        cid = rec.content_id
        self._records[cid] = rec
        self.save()
        return cid

    def get(self, content_id: str) -> Optional[SpecialistRecord]:
        return self._records.get(content_id)

    def active(self, specialist_id: str) -> Optional[SpecialistRecord]:
        for r in self._records.values():
            if r.specialist_id == specialist_id and r.status == "ACTIVE":
                return r
        return None

    def known_good(self, specialist_id: str) -> Optional[SpecialistRecord]:
        """Previous known-good for rollback (§44)."""
        cands = [
            r for r in self._records.values()
            if r.specialist_id == specialist_id and r.status in ("ACTIVE", "DEGRADED")
        ]
        return max(cands, key=lambda r: r.promoted_at or 0) if cands else None
