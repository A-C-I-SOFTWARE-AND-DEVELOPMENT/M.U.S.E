"""Tests for the template-fast-path corpus builder (Phase 0)."""

from __future__ import annotations

from collections import Counter

import pytest

from hermes_cli.jarvis_prime.bench.baseline import measure_runner
from hermes_cli.jarvis_prime.bench.corpus import (
    FIXTURE_SUITE,
    build_corpus,
    corpus_hash,
    split_heldout,
)


@pytest.fixture(scope="module")
def small_corpus() -> list:
    # max_per_domain bounds the verifier subprocess count so the module stays
    # fast; verdicts are still earned by real execution.
    return build_corpus(max_per_domain=2)


def test_fixture_suite_exists() -> None:
    assert FIXTURE_SUITE.exists()
    assert FIXTURE_SUITE.read_text(encoding="utf-8").count("\n") >= 30


def test_corpus_is_deterministic(small_corpus: list) -> None:
    again = build_corpus(max_per_domain=2)
    assert [r.to_dict() for r in again] == [r.to_dict() for r in small_corpus]
    assert corpus_hash(again) == corpus_hash(small_corpus)


def test_verdicts_are_earned_not_asserted(small_corpus: list) -> None:
    good = [r for r in small_corpus if r.task_id.endswith("#c0")]
    bad = [r for r in small_corpus if r.task_id.endswith("#c1")]
    assert good and bad
    assert all(r.verifier_passed for r in good)
    assert not any(r.verifier_passed for r in bad)


def test_corpus_covers_required_domains(small_corpus: list) -> None:
    domains = {r.domain for r in small_corpus}
    assert domains == {
        "code_generation",
        "code_editing",
        "code_review",
        "software_development",
        "reasoning",
        "safety",
    }


def test_split_is_disjoint_stratified_and_stable(small_corpus: list) -> None:
    train, held = split_heldout(small_corpus, ratio=0.2, seed=0)
    train2, held2 = split_heldout(small_corpus, ratio=0.2, seed=0)
    assert [r.task_id for r in train] == [r.task_id for r in train2]
    assert [r.task_id for r in held] == [r.task_id for r in held2]
    assert not {r.task_id for r in train} & {r.task_id for r in held}
    assert len(train) + len(held) == len(small_corpus)
    # Stratified: every domain keeps a held-out wall.
    assert set(Counter(r.domain for r in held)) == {r.domain for r in small_corpus}


def test_split_keeps_candidate_siblings_together(small_corpus: list) -> None:
    _, held = split_heldout(small_corpus, ratio=0.2, seed=0)
    held_bases = {r.task_id.split("#", 1)[0] for r in held}
    for rec in small_corpus:
        base = rec.task_id.split("#", 1)[0]
        assert (base in held_bases) == (rec in held)


def test_different_seed_changes_split(small_corpus: list) -> None:
    _, held0 = split_heldout(small_corpus, ratio=0.2, seed=0)
    _, held7 = split_heldout(small_corpus, ratio=0.2, seed=7)
    # Same sizes (stratified), but at least some membership difference.
    assert len(held0) == len(held7)
    assert {r.task_id for r in held0} != {r.task_id for r in held7}


def test_measure_runner_records_hashes_and_latency() -> None:
    ticks = iter(float(i) for i in range(100))
    report = measure_runner(
        lambda p: p.upper(),
        ["alpha", "beta"],
        label="stub",
        clock=lambda: next(ticks),
    )
    assert len(report.measurements) == 2
    assert all(m.latency_s == 1.0 for m in report.measurements)
    assert report.output_hashes() == measure_runner(
        lambda p: p.upper(), ["alpha", "beta"], label="again"
    ).output_hashes()
    assert "| stub | 2 |" in report.to_markdown_row()
