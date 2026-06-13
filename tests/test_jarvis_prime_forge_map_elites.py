"""Tests for the MAP-Elites diversity grid."""

import random

import pytest

from hermes_cli.jarvis_prime.forge import KIND_FORGE_ELITE
from hermes_cli.jarvis_prime.forge.map_elites import (
    BehaviorDescriptor,
    ElitesGrid,
    bin_descriptor,
)
from hermes_cli.jarvis_prime.guardrail_evidence import GuardrailLedger

BOUNDS = ((0.0, 100.0), (0.0, 1000.0))


def test_binning_clamps_and_is_deterministic():
    assert bin_descriptor(
        BehaviorDescriptor((0.0, 0.0)), bins_per_dim=4, bounds=BOUNDS
    ) == (0, 0)
    # Values beyond bounds clamp to the last bin.
    assert bin_descriptor(
        BehaviorDescriptor((1e9, -5.0)), bins_per_dim=4, bounds=BOUNDS
    ) == (3, 0)
    assert bin_descriptor(
        BehaviorDescriptor((50.0, 500.0)), bins_per_dim=4, bounds=BOUNDS
    ) == (2, 2)
    with pytest.raises(ValueError):
        bin_descriptor(BehaviorDescriptor((1.0,)), bins_per_dim=4, bounds=BOUNDS)


def test_consider_keeps_argmax_per_cell(tmp_path):
    ledger = GuardrailLedger(tmp_path / "ledger.jsonl")
    grid = ElitesGrid(bins_per_dim=4, bounds=BOUNDS, path=tmp_path / "elites.json", ledger=ledger)
    descriptor = BehaviorDescriptor((10.0, 100.0))
    assert grid.consider("cand_a", descriptor, fitness=0.5) is True
    assert grid.consider("cand_b", descriptor, fitness=0.3) is False  # weaker
    assert grid.consider("cand_c", descriptor, fitness=0.9) is True  # replaces
    cells = grid.cells()
    assert len(cells) == 1 and cells[0].candidate_id == "cand_c"
    events = [r for r in ledger.read_all() if r.kind == KIND_FORGE_ELITE]
    assert len(events) == 2
    assert events[1].payload["replaced"] == "cand_a"


def test_coverage_and_qd_score(tmp_path):
    grid = ElitesGrid(bins_per_dim=2, bounds=BOUNDS, path=tmp_path / "elites.json")
    assert grid.coverage() == 0.0
    grid.consider("a", BehaviorDescriptor((10.0, 100.0)), 0.4)
    grid.consider("b", BehaviorDescriptor((90.0, 900.0)), 0.6)
    assert grid.coverage() == 2 / 4
    assert grid.qd_score() == pytest.approx(1.0)


def test_sample_elite_seeded_and_persistence(tmp_path):
    path = tmp_path / "elites.json"
    grid = ElitesGrid(bins_per_dim=2, bounds=BOUNDS, path=path)
    assert grid.sample_elite() is None
    grid.consider("a", BehaviorDescriptor((10.0, 100.0)), 0.4)
    grid.consider("b", BehaviorDescriptor((90.0, 900.0)), 0.6)
    sampled = grid.sample_elite(rng=random.Random(7))
    assert sampled is not None and sampled.candidate_id in {"a", "b"}
    resampled = grid.sample_elite(rng=random.Random(7))
    assert resampled is not None and resampled.candidate_id == sampled.candidate_id
    reloaded = ElitesGrid(bins_per_dim=2, bounds=BOUNDS, path=path)
    assert {c.candidate_id for c in reloaded.cells()} == {"a", "b"}
