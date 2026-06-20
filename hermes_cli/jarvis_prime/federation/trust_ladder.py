"""Contributor trust ladder — earned trust, instrumented (Vol VI Part 3).

The human analog of muse's graduated autonomy bands: new contributors are
**B0 (propose-only)**; a verifiable track record earns B1/B2; **B3
(maintainer) is never automatic** — it requires an explicit owner or quorum
grant, mirroring how the vLLM committer ladder ends in a human vote. Any
fatal violation floors the band to B0 (the constitution's "fatal floors
trust" severity model, applied to people).

Every band change is appended to the hash-chained ledger so the ladder is an
auditable instrument, not a vibe.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Mapping, Optional, Union

from hermes_cli.jarvis_prime.guardrail_evidence import GuardrailLedger
from hermes_cli.jarvis_prime.owner_auth import OwnerAuthorizationGrant

from . import KIND_BAND_CHANGE, FederationError, federation_dir
from .quorum_auth import QuorumGrant


class ContributorBand(str, Enum):
    B0 = "B0"  # propose-only
    B1 = "B1"
    B2 = "B2"
    B3 = "B3"  # maintainer — grant-only

    @property
    def rank(self) -> int:
        return {"B0": 0, "B1": 1, "B2": 2, "B3": 3}[self.value]


# Promotion thresholds, in the spirit of capability_wall.DEFAULT_THRESHOLDS.
BAND_REQUIREMENTS: dict[ContributorBand, dict[str, float]] = {
    ContributorBand.B1: {"accepted": 5, "fatal_max": 0},
    ContributorBand.B2: {"accepted": 25, "acceptance_rate": 0.8, "fatal_max": 0},
    # B3 has no automatic requirements — see promote_to_maintainer().
}

# What a contributor's submissions may do, per band.
BAND_MAX_RISK_CLASS: dict[ContributorBand, str] = {
    ContributorBand.B0: "propose_only",
    ContributorBand.B1: "RC1",
    ContributorBand.B2: "RC2",
    ContributorBand.B3: "RC2",
}


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ContributorRecord:
    contributor_id: str
    band: ContributorBand = ContributorBand.B0
    accepted: int = 0
    rejected: int = 0
    fatal_violations: int = 0
    joined_at: str = ""
    last_change_at: str = ""

    @property
    def acceptance_rate(self) -> float:
        total = self.accepted + self.rejected
        return self.accepted / total if total else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "contributor_id": self.contributor_id,
            "band": self.band.value,
            "accepted": self.accepted,
            "rejected": self.rejected,
            "fatal_violations": self.fatal_violations,
            "joined_at": self.joined_at,
            "last_change_at": self.last_change_at,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ContributorRecord":
        return cls(
            contributor_id=str(data["contributor_id"]),
            band=ContributorBand(str(data.get("band", ContributorBand.B0.value))),
            accepted=int(data.get("accepted", 0)),
            rejected=int(data.get("rejected", 0)),
            fatal_violations=int(data.get("fatal_violations", 0)),
            joined_at=str(data.get("joined_at", "")),
            last_change_at=str(data.get("last_change_at", "")),
        )


def evaluate_band(record: ContributorRecord) -> ContributorBand:
    """Pure band evaluation from the track record.

    A fatal violation floors to B0 — including a granted B3. Earned bands cap
    at B2; B3 only ever comes from :func:`promote_to_maintainer`. A granted B3
    with a clean record is preserved.
    """

    if record.fatal_violations > 0:
        return ContributorBand.B0
    if record.band == ContributorBand.B3:
        return ContributorBand.B3
    if (
        record.accepted >= BAND_REQUIREMENTS[ContributorBand.B2]["accepted"]
        and record.acceptance_rate >= BAND_REQUIREMENTS[ContributorBand.B2]["acceptance_rate"]
    ):
        return ContributorBand.B2
    if record.accepted >= BAND_REQUIREMENTS[ContributorBand.B1]["accepted"]:
        return ContributorBand.B1
    return ContributorBand.B0


def max_risk_class(band: ContributorBand) -> str:
    return BAND_MAX_RISK_CLASS[band]


class ContributorStore:
    """JSON-file store of contributor records (``contributors.json``)."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self.path = Path(path) if path is not None else self.default_path()
        self._records: dict[str, ContributorRecord] = {}
        self._load()

    @staticmethod
    def default_path() -> Path:
        return federation_dir() / "contributors.json"

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        for entry in data.get("contributors", []):
            try:
                record = ContributorRecord.from_dict(entry)
            except (KeyError, TypeError, ValueError):
                continue
            self._records[record.contributor_id] = record

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        body = {"contributors": [r.to_dict() for r in self._records.values()]}
        self.path.write_text(
            json.dumps(body, sort_keys=True, indent=2) + "\n", encoding="utf-8"
        )
        try:
            os.chmod(self.path, 0o600)
        except OSError:  # pragma: no cover
            pass

    def all(self) -> list[ContributorRecord]:
        return list(self._records.values())

    def get(self, contributor_id: str) -> ContributorRecord:
        record = self._records.get(contributor_id)
        if record is None:
            now = _utc_iso()
            record = ContributorRecord(
                contributor_id=contributor_id, joined_at=now, last_change_at=now
            )
            self._records[contributor_id] = record
            self._save()
        return record

    def upsert(self, record: ContributorRecord) -> ContributorRecord:
        self._records[record.contributor_id] = record
        self._save()
        return record

    def record_outcome(
        self,
        contributor_id: str,
        *,
        accepted: bool,
        fatal: bool = False,
        ledger: Optional[GuardrailLedger] = None,
    ) -> ContributorRecord:
        """Record one submission outcome and re-evaluate the band."""

        record = self.get(contributor_id)
        if accepted:
            record.accepted += 1
        else:
            record.rejected += 1
        if fatal:
            record.fatal_violations += 1
        new_band = evaluate_band(record)
        if new_band != record.band:
            old_band = record.band
            record.band = new_band
            record.last_change_at = _utc_iso()
            if ledger is not None:
                ledger.append(
                    KIND_BAND_CHANGE,
                    contributor_id,
                    {
                        "from": old_band.value,
                        "to": new_band.value,
                        "accepted": record.accepted,
                        "rejected": record.rejected,
                        "fatal_violations": record.fatal_violations,
                        "cause": "fatal_violation" if fatal else "track_record",
                    },
                )
        self._save()
        return record


def promote_to_maintainer(
    record: ContributorRecord,
    grant: Union[QuorumGrant, OwnerAuthorizationGrant],
    *,
    store: Optional[ContributorStore] = None,
    ledger: Optional[GuardrailLedger] = None,
) -> ContributorRecord:
    """Promote to B3. Requires a real grant object — never automatic."""

    if not isinstance(grant, (QuorumGrant, OwnerAuthorizationGrant)):
        raise FederationError(
            "B3 promotion requires a QuorumGrant or OwnerAuthorizationGrant"
        )
    if record.fatal_violations > 0:
        raise FederationError(
            "B3 promotion refused: contributor has fatal violations on record"
        )
    old_band = record.band
    record.band = ContributorBand.B3
    record.last_change_at = _utc_iso()
    if ledger is not None:
        ledger.append(
            KIND_BAND_CHANGE,
            record.contributor_id,
            {
                "from": old_band.value,
                "to": ContributorBand.B3.value,
                "cause": "maintainer_grant",
                "grant": grant.to_dict(),
            },
        )
    if store is not None:
        store.upsert(record)
    return record


__all__ = [
    "ContributorBand",
    "BAND_REQUIREMENTS",
    "BAND_MAX_RISK_CLASS",
    "ContributorRecord",
    "ContributorStore",
    "evaluate_band",
    "max_risk_class",
    "promote_to_maintainer",
]
