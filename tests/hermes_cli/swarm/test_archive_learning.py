"""Tests for the evolutionary variant archive and the learning/apply hooks."""

from __future__ import annotations

from pathlib import Path

import pytest

from hermes_cli.swarm.archive import (
    GrainVariant,
    VariantArchive,
    benchmark_gated_promotion,
)
from hermes_cli.swarm.grain import FileDomain, Grain, SwarmPlan
from hermes_cli.swarm.coordinator import SwarmGrainResult
from hermes_cli.swarm.learning import (
    applied_updates_log_path,
    capture_swarm_trace,
    record_applied_update,
)


# ── archive ─────────────────────────────────────────────────────────────────


def test_archive_roundtrip(tmp_path: Path):
    arc = VariantArchive(path=tmp_path / "arc.jsonl")
    v = GrainVariant(variant_id="v1", grain_kind="api", model_lane="claude",
                     benchmark_score=0.8, benchmark_ran=True)
    arc.add(v)
    loaded = arc.all()
    assert len(loaded) == 1
    assert loaded[0].variant_id == "v1"
    assert loaded[0].benchmark_score == 0.8


def test_benchmark_gated_promotion_passes_when_better(tmp_path: Path):
    arc = VariantArchive(path=tmp_path / "arc.jsonl")
    v = GrainVariant(variant_id="v2", grain_kind="api", benchmark_task="custom",
                     benchmark_score=0.9, benchmark_ran=True)
    rec = benchmark_gated_promotion(0.5, v, archive=arc)
    assert rec["outcome"] == "pass"
    assert rec["promoted"] is True
    assert arc.all()[0].promoted is True


def test_benchmark_gated_promotion_fails_when_not_better(tmp_path: Path):
    arc = VariantArchive(path=tmp_path / "arc.jsonl")
    v = GrainVariant(variant_id="v3", grain_kind="api", benchmark_score=0.5,
                     benchmark_ran=True)
    rec = benchmark_gated_promotion(0.9, v, archive=arc)
    assert rec["outcome"] == "fail"
    assert rec["promoted"] is False
    # Loser is still archived (lineage preserved).
    assert len(arc.all()) == 1


def test_best_for_picks_highest_score(tmp_path: Path):
    arc = VariantArchive(path=tmp_path / "arc.jsonl")
    arc.add(GrainVariant(variant_id="a", grain_kind="api", benchmark_score=0.6, benchmark_ran=True))
    arc.add(GrainVariant(variant_id="b", grain_kind="api", benchmark_score=0.8, benchmark_ran=True))
    arc.add(GrainVariant(variant_id="c", grain_kind="web", benchmark_score=0.95, benchmark_ran=True))
    assert arc is not None
    assert arc.best_for("api").variant_id == "b"  # ty: ignore[unresolved-attribute]  # mock/duck-typed test fixture


# ── learning + apply hook ────────────────────────────────────────────────────


@pytest.fixture
def hermes_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "home"))
    return tmp_path / "home"


def _plan():
    return SwarmPlan(
        job_id="job-x",
        goal="do stuff",
        grains=(
            Grain(grain_id="g1", intent="api", domain=FileDomain(globs=("src/api/**",))),
        ),
    )


def test_capture_swarm_trace_writes_record(hermes_home):
    plan = _plan()
    results = [SwarmGrainResult(grain_id="g1", state="completed")]
    path = capture_swarm_trace(plan, results, convergence={"mode": "cooperative"})
    assert path.exists()
    import json

    line = json.loads(path.read_text().splitlines()[-1])
    assert line["job_id"] == "job-x"
    assert line["grains"][0]["grain_id"] == "g1"


def test_record_applied_update_is_reversible(hermes_home):
    class P:
        kind = "routing_miss"
        target = "lane:codex"
        summary = "nudge"
        reversible = True
        extra = {"previous_value": "codex", "nudge_delta": 1}

    rec = record_applied_update(P())
    assert rec["previous_value"] == "codex"
    assert "Restore" in rec["rollback"]
    assert applied_updates_log_path().exists()
