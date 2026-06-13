"""Merkle-anchored attested Forge leaderboard + the lookup surface.

Standings are derived from the rating book; the canonical standings list is
Merkle-rooted (stdlib SHA-256) and emitted as a content-addressed evidence
artifact, so organizations can compare leaderboards **without trusting each
other's self-reports** — a peer re-derives the root from the published
standings and cross-attests the artifact hash through the federation layer.

``lookup_standing`` resolves through the candidate registry (resolve-or-fail)
so a leaderboard entry can always be traced to exact, content-addressed code.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional, Sequence

from hermes_cli.jarvis_prime.guardrail_evidence import (
    EvidenceArtifact,
    GuardrailLedger,
    canonical_json,
    sha256_hex,
)

from . import ARTIFACT_LEADERBOARD, KIND_FORGE_ANCHOR
from .registry import CandidateRegistry
from .tournament import RatingBook


@dataclass(frozen=True)
class Standing:
    rank: int
    candidate_id: str
    rating: float
    rd: float
    games: int
    payload_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "rank": self.rank,
            "candidate_id": self.candidate_id,
            "rating": round(self.rating, 4),
            "rd": round(self.rd, 4),
            "games": self.games,
            "payload_sha256": self.payload_sha256,
        }


def standings(rating_book: RatingBook, registry: CandidateRegistry) -> list[Standing]:
    """Rated candidates sorted by rating desc (lower RD breaks ties)."""

    rows = sorted(
        rating_book.all().items(),
        key=lambda item: (-item[1].rating, item[1].rd, item[0]),
    )
    result: list[Standing] = []
    for rank, (candidate_id, rating) in enumerate(rows, start=1):
        record = registry.resolve(candidate_id)
        result.append(
            Standing(
                rank=rank,
                candidate_id=candidate_id,
                rating=rating.rating,
                rd=rating.rd,
                games=rating_book.games(candidate_id),
                payload_sha256=record.payload_sha256,
            )
        )
    return result


def merkle_root(leaves: Sequence[str]) -> str:
    """Pairwise-SHA-256 Merkle root; odd leaf promoted; empty -> hash of ""."""

    if not leaves:
        return sha256_hex("")
    level = list(leaves)
    while len(level) > 1:
        nxt: list[str] = []
        for i in range(0, len(level) - 1, 2):
            nxt.append(sha256_hex(level[i] + level[i + 1]))
        if len(level) % 2 == 1:
            nxt.append(level[-1])
        level = nxt
    return level[0]


def _standings_root(rows: Sequence[dict[str, Any]]) -> str:
    return merkle_root([sha256_hex(canonical_json(row)) for row in rows])


def anchor_leaderboard(
    rating_book: RatingBook,
    registry: CandidateRegistry,
    *,
    node_id: str = "",
    ledger: Optional[GuardrailLedger] = None,
) -> EvidenceArtifact:
    """Emit a content-addressed, Merkle-rooted leaderboard attestation."""

    rows = [s.to_dict() for s in standings(rating_book, registry)]
    root = _standings_root(rows)
    artifact = EvidenceArtifact.make(
        ARTIFACT_LEADERBOARD,
        producer="forge_leaderboard",
        subject=root,
        payload={"standings": rows, "merkle_root": root, "node_id": node_id},
    )
    if ledger is not None:
        ledger.append(
            KIND_FORGE_ANCHOR,
            root,
            {"entries": len(rows), "artifact_id": artifact.artifact_id, "node_id": node_id},
        )
    return artifact


def verify_anchor(artifact: EvidenceArtifact) -> bool:
    """Re-derive the Merkle root and content hash from the published payload."""

    if not artifact.verify_payload():
        return False
    rows = list(artifact.payload.get("standings", []))
    claimed = str(artifact.payload.get("merkle_root", ""))
    return claimed == _standings_root(rows)


def lookup_standing(
    candidate_id: str,
    rating_book: RatingBook,
    registry: CandidateRegistry,
) -> dict[str, Any]:
    """The Forge lookup: standing + provenance, resolve-or-fail."""

    record = registry.resolve(candidate_id)  # raises ForgeError on a miss
    for standing in standings(rating_book, registry):
        if standing.candidate_id == candidate_id:
            return {**standing.to_dict(), "task_id": record.task_id, "kind": record.kind,
                    "contributor_id": record.contributor_id}
    rating = rating_book.get(candidate_id)
    return {
        "rank": None,
        "candidate_id": candidate_id,
        "rating": round(rating.rating, 4),
        "rd": round(rating.rd, 4),
        "games": rating_book.games(candidate_id),
        "payload_sha256": record.payload_sha256,
        "task_id": record.task_id,
        "kind": record.kind,
        "contributor_id": record.contributor_id,
    }


__all__ = [
    "Standing",
    "standings",
    "merkle_root",
    "anchor_leaderboard",
    "verify_anchor",
    "lookup_standing",
]
