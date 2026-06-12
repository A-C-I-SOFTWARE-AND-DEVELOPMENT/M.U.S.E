"""Tests for model scorecards + scorecard-driven selection."""

from __future__ import annotations

from pathlib import Path

from muse_cli.local_models.scorecards import (
    ScorecardSample,
    ScorecardStore,
    select_model,
)


def _sample(
    model: str,
    *,
    coding=True,
    tests=True,
    repair=None,
    latency=10.0,
    cost=0.0,
    interrupts=0,
):
    return ScorecardSample(
        model=model,
        coding_success=coding,
        tests_passed=tests,
        repair_succeeded=repair,
        hallucination_corrected=None,
        latency_seconds=latency,
        cost=cost,
        owner_interruptions=interrupts,
    )


def test_record_and_aggregate(tmp_path: Path):
    store = ScorecardStore(path=tmp_path / "sc.jsonl")
    store.record(_sample("qwen", coding=True, tests=True))
    store.record(_sample("qwen", coding=False, tests=True))
    card = store.scorecard("qwen")
    assert card is not None
    assert card.samples == 2
    assert card.coding_success_rate == 0.5
    assert card.test_pass_rate == 1.0
    assert 0.0 <= card.composite() <= 1.0


def test_repair_rate_ignores_none(tmp_path: Path):
    store = ScorecardStore(path=tmp_path / "sc.jsonl")
    store.record(_sample("m", repair=None))  # no repair attempted
    store.record(_sample("m", repair=True))
    store.record(_sample("m", repair=False))
    card = store.scorecard("m")
    # Only the two non-None repair attempts count -> 0.5
    assert card.repair_success_rate == 0.5  # ty: ignore[unresolved-attribute]  # mock/duck-typed test fixture


def test_select_prefers_higher_composite(tmp_path: Path):
    store = ScorecardStore(path=tmp_path / "sc.jsonl")
    # "good" wins on quality; "slow" identical quality but high latency/cost.
    for _ in range(3):
        store.record(
            _sample("good", coding=True, tests=True, repair=True, latency=5.0, cost=0.0)
        )
        store.record(
            _sample(
                "slow",
                coding=True,
                tests=True,
                repair=True,
                latency=120.0,
                cost=5.0,
                interrupts=3,
            )
        )
    chosen = select_model(["good", "slow"], store)
    assert chosen == "good"


def test_select_ranks_measured_over_unknown(tmp_path: Path):
    store = ScorecardStore(path=tmp_path / "sc.jsonl")
    store.record(_sample("measured", coding=True, tests=True))
    chosen = select_model(["measured", "never-seen"], store, min_samples=1)
    assert chosen == "measured"


def test_select_empty_returns_none(tmp_path: Path):
    store = ScorecardStore(path=tmp_path / "sc.jsonl")
    assert select_model([], store) is None


def test_store_tolerates_corrupt_line(tmp_path: Path):
    p = tmp_path / "sc.jsonl"
    p.write_text(
        '{"model":"x","coding_success":true,"tests_passed":true,"latency_seconds":1,"cost":0,"owner_interruptions":0}\n{ broken json\n'
    )
    store = ScorecardStore(path=p)
    samples = store.samples()
    assert len(samples) == 1
