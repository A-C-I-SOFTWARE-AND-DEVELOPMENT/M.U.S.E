"""Persistent diversity archive (Plane 3).

A Darwin-Gödel-style archive of accepted improvements with full lineage. Stored
as append-only JSONL under ``hermes_home()/jarvis_prime/archive.jsonl``. Parents
are sampled by score AND editability (stepping stones, not greedy hill-climbing)
so the search keeps a diverse frontier rather than collapsing onto one peak.

This complements the champion lineage already captured as ``champion_freeze``
ledger snapshots: the archive holds *every* accepted candidate (not only the
reigning champion), which is what an evolutionary search needs to branch from.
"""

from __future__ import annotations

import json
import os
import random
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from hermes_cli.jarvis_prime.guardrail_evidence import hermes_home

from . import Archive, ArchiveMember


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_member(
    *,
    parent_id: Optional[str],
    config: dict[str, Any],
    composite: float,
    domain_scores: dict[str, float],
    rollback_handle: str = "",
    note: str = "",
) -> ArchiveMember:
    return ArchiveMember(
        member_id=f"mem_{uuid.uuid4().hex[:16]}",
        parent_id=parent_id,
        config=dict(config),
        composite=round(float(composite), 4),
        domain_scores=dict(domain_scores),
        rollback_handle=rollback_handle,
        created_at=_utc_iso(),
        note=note,
    )


class ArchiveStore:
    """JSONL-backed persistence for the diversity archive."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = Path(path) if path is not None else self.default_path()
        self.archive = Archive()
        self._load()

    @staticmethod
    def default_path() -> Path:
        return hermes_home() / "jarvis_prime" / "archive.jsonl"

    def _load(self) -> None:
        if not self.path.exists():
            return
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            self.archive.add(
                ArchiveMember(
                    member_id=str(data["member_id"]),
                    parent_id=data.get("parent_id"),
                    config=dict(data.get("config", {})),
                    composite=float(data.get("composite", 0.0)),
                    domain_scores={
                        k: float(v) for k, v in dict(data.get("domain_scores", {})).items()
                    },
                    rollback_handle=str(data.get("rollback_handle", "")),
                    created_at=str(data.get("created_at", "")),
                    note=str(data.get("note", "")),
                )
            )

    def add(self, member: ArchiveMember) -> ArchiveMember:
        self.archive.add(member)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(member.to_dict(), sort_keys=True) + "\n")
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass
        return member

    def members(self) -> list[ArchiveMember]:
        return list(self.archive.members)

    def sample_parent(self, *, rng: Optional[random.Random] = None) -> Optional[ArchiveMember]:
        return self.archive.sample_parent(rng=rng)


__all__ = ["ArchiveStore", "new_member"]
