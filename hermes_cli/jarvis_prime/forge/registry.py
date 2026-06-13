"""Content-addressed Forge candidate registry — the lookup (Vol VI Part 5).

The L1 registry pattern applied to Forge candidates: a candidate's id is
derived from the hash of its content, so two candidates with the same code
share an id, a lookalike substitution (same id, different content) is
detectable, and an unregistered reference **fails to resolve** instead of
being fuzzily matched — resolve-or-fail kills hallucinated references.

Append-only JSONL persistence (the ``ArchiveStore`` pattern), 0o600.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional

from hermes_cli.jarvis_prime.guardrail_evidence import (
    GuardrailLedger,
    canonical_json,
    sha256_hex,
)

from . import KIND_FORGE_REGISTER, ForgeError, forge_dir


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class CandidateRecord:
    """One registered Forge candidate, addressed by its content."""

    candidate_id: str  # "cand_" + sha256(canonical {kind, code})[:16]
    kind: str  # "algorithm" for the v1 lane
    code: str
    task_id: str
    payload_sha256: str  # full content hash — the federation trust anchor
    contributor_id: str
    created_at: str
    note: str = ""

    @staticmethod
    def content_hash(kind: str, code: str) -> str:
        return sha256_hex(canonical_json({"kind": kind, "code": code}))

    @classmethod
    def build(
        cls,
        *,
        kind: str = "algorithm",
        code: str,
        task_id: str,
        contributor_id: str,
        note: str = "",
    ) -> "CandidateRecord":
        digest = cls.content_hash(kind, code)
        return cls(
            candidate_id=f"cand_{digest[:16]}",
            kind=kind,
            code=code,
            task_id=task_id,
            payload_sha256=digest,
            contributor_id=contributor_id,
            created_at=_utc_iso(),
            note=note,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "kind": self.kind,
            "code": self.code,
            "task_id": self.task_id,
            "payload_sha256": self.payload_sha256,
            "contributor_id": self.contributor_id,
            "created_at": self.created_at,
            "note": self.note,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "CandidateRecord":
        return cls(
            candidate_id=str(data["candidate_id"]),
            kind=str(data.get("kind", "algorithm")),
            code=str(data.get("code", "")),
            task_id=str(data.get("task_id", "")),
            payload_sha256=str(data.get("payload_sha256", "")),
            contributor_id=str(data.get("contributor_id", "")),
            created_at=str(data.get("created_at", "")),
            note=str(data.get("note", "")),
        )


class CandidateRegistry:
    """JSONL-backed, content-addressed candidate store with strict resolve."""

    def __init__(
        self,
        path: Optional[Path] = None,
        ledger: Optional[GuardrailLedger] = None,
    ) -> None:
        self.path = Path(path) if path is not None else self.default_path()
        self.ledger = ledger
        self._by_id: dict[str, CandidateRecord] = {}
        self._load()

    @staticmethod
    def default_path() -> Path:
        return forge_dir() / "candidates.jsonl"

    def _load(self) -> None:
        if not self.path.exists():
            return
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                record = CandidateRecord.from_dict(json.loads(line))
            except (json.JSONDecodeError, KeyError, TypeError):
                continue
            self._by_id[record.candidate_id] = record

    def register(self, record: CandidateRecord) -> CandidateRecord:
        """Register a candidate. Idempotent on identical content.

        Raises :class:`ForgeError` on a lookalike — the same ``candidate_id``
        with a different content hash means someone is trying to substitute
        content under a known name.
        """

        expected = CandidateRecord.content_hash(record.kind, record.code)
        if record.payload_sha256 != expected or record.candidate_id != f"cand_{expected[:16]}":
            raise ForgeError(
                f"candidate {record.candidate_id} content hash mismatch — "
                "lookalike substitution detected"
            )
        existing = self._by_id.get(record.candidate_id)
        if existing is not None:
            if existing.payload_sha256 != record.payload_sha256:
                raise ForgeError(
                    f"candidate {record.candidate_id} already registered with "
                    "different content — lookalike substitution detected"
                )
            return existing

        self._by_id[record.candidate_id] = record
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record.to_dict(), sort_keys=True) + "\n")
        try:
            os.chmod(self.path, 0o600)
        except OSError:  # pragma: no cover
            pass
        if self.ledger is not None:
            self.ledger.append(
                KIND_FORGE_REGISTER,
                record.candidate_id,
                {
                    "task_id": record.task_id,
                    "kind": record.kind,
                    "payload_sha256": record.payload_sha256,
                    "contributor_id": record.contributor_id,
                },
            )
        return record

    def resolve(self, candidate_id: str) -> CandidateRecord:
        """Resolve-or-fail: an unknown id raises, never fuzzy-matches."""

        record = self._by_id.get(candidate_id)
        if record is None:
            raise ForgeError(f"unresolved candidate reference {candidate_id!r}")
        return record

    def lookup_by_hash(self, payload_sha256: str) -> Optional[CandidateRecord]:
        for record in self._by_id.values():
            if record.payload_sha256 == payload_sha256:
                return record
        return None

    def all(self) -> list[CandidateRecord]:
        return list(self._by_id.values())

    def for_task(self, task_id: str) -> list[CandidateRecord]:
        return [r for r in self._by_id.values() if r.task_id == task_id]


__all__ = ["CandidateRecord", "CandidateRegistry"]
