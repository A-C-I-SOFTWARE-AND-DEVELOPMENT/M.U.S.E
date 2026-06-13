"""Tests for the Merkle-anchored attested leaderboard + lookup."""

import pytest

from hermes_cli.jarvis_prime.forge import KIND_FORGE_ANCHOR, ForgeError
from hermes_cli.jarvis_prime.forge.glicko2 import GlickoRating
from hermes_cli.jarvis_prime.forge.leaderboard import (
    anchor_leaderboard,
    lookup_standing,
    merkle_root,
    standings,
    verify_anchor,
)
from hermes_cli.jarvis_prime.forge.registry import CandidateRecord, CandidateRegistry
from hermes_cli.jarvis_prime.forge.tournament import RatingBook
from hermes_cli.jarvis_prime.guardrail_evidence import EvidenceArtifact, GuardrailLedger


def _setup(tmp_path):
    registry = CandidateRegistry(tmp_path / "candidates.jsonl")
    book = RatingBook(tmp_path / "ratings.json")
    ids = []
    for i, rating in enumerate((1700.0, 1500.0, 1300.0)):
        record = registry.register(
            CandidateRecord.build(
                code=f"def solve(xs):\n    return sum(xs) + {i} - {i}\n",
                task_id="alg_sum",
                contributor_id="t",
            )
        )
        book.put(record.candidate_id, GlickoRating(rating=rating), games_delta=i + 1)
        ids.append(record.candidate_id)
    return registry, book, ids


def test_standings_sorted_by_rating(tmp_path):
    registry, book, ids = _setup(tmp_path)
    rows = standings(book, registry)
    assert [s.candidate_id for s in rows] == ids
    assert [s.rank for s in rows] == [1, 2, 3]
    assert all(s.payload_sha256 for s in rows)


def test_merkle_root_properties():
    assert merkle_root([]) == merkle_root([])
    single = merkle_root(["a" * 64])
    assert single == "a" * 64  # lone leaf promotes
    pair = merkle_root(["a" * 64, "b" * 64])
    assert pair != single
    # Order matters; any leaf change changes the root.
    assert merkle_root(["b" * 64, "a" * 64]) != pair
    assert merkle_root(["a" * 64, "c" * 64]) != pair
    odd = merkle_root(["a" * 64, "b" * 64, "c" * 64])
    assert odd not in (pair, single)


def test_anchor_and_verify_round_trip(tmp_path):
    registry, book, _ = _setup(tmp_path)
    ledger = GuardrailLedger(tmp_path / "ledger.jsonl")
    artifact = anchor_leaderboard(book, registry, node_id="node_x", ledger=ledger)
    assert verify_anchor(artifact)
    records = ledger.read_all()
    assert records[-1].kind == KIND_FORGE_ANCHOR
    assert records[-1].subject == artifact.payload["merkle_root"]

    # Tampering with a standing breaks verification.
    tampered_payload = dict(artifact.payload)
    rows = [dict(r) for r in tampered_payload["standings"]]
    rows[0]["rating"] = 9999.0
    tampered_payload["standings"] = rows
    tampered = EvidenceArtifact.make(
        artifact.artifact_type,
        producer=artifact.producer,
        subject=artifact.subject,
        payload=tampered_payload,
    )
    assert not verify_anchor(tampered)


def test_lookup_standing_resolves_or_fails(tmp_path):
    registry, book, ids = _setup(tmp_path)
    top = lookup_standing(ids[0], book, registry)
    assert top["rank"] == 1
    assert top["task_id"] == "alg_sum"
    with pytest.raises(ForgeError, match="unresolved"):
        lookup_standing("cand_missing0000", book, registry)
