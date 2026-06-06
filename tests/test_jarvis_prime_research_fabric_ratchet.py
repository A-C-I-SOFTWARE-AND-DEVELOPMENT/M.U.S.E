"""Tests for the strict non-regression ratchet — the 'never worsens itself' rule."""

from __future__ import annotations

from hermes_cli.jarvis_prime.research_fabric.catalog import REQUIRED_DOMAINS
from hermes_cli.jarvis_prime.research_fabric.validators import evaluate_ratchet


def _full(value: float) -> dict[str, float]:
    return {d: value for d in REQUIRED_DOMAINS}


def test_cold_start_passes_on_floor_only() -> None:
    v = evaluate_ratchet(
        champion_domain_scores=None,
        candidate_domain_scores=_full(0.85),
        holdout_scores=None,
    )
    assert v.cold_start is True
    assert v.passed is True


def test_cold_start_blocks_below_floor() -> None:
    scores = _full(0.85)
    scores["safety"] = 0.70  # below 0.80 floor
    v = evaluate_ratchet(champion_domain_scores=None, candidate_domain_scores=scores)
    assert v.passed is False
    assert "safety" in v.floor_violations


def test_warm_pass_when_every_domain_beats_champion() -> None:
    v = evaluate_ratchet(
        champion_domain_scores=_full(0.85),
        candidate_domain_scores=_full(0.92),
        holdout_scores=_full(0.92),
        eval_win_rate=0.60,
    )
    assert v.passed is True
    assert v.composite_delta >= 0.05


def test_single_domain_regression_blocks() -> None:
    cand = _full(0.92)
    cand["code_review"] = 0.80  # below champion 0.85 -> regression
    v = evaluate_ratchet(
        champion_domain_scores=_full(0.85),
        candidate_domain_scores=cand,
        holdout_scores=_full(0.92),
        eval_win_rate=0.60,
    )
    assert v.passed is False
    assert any("code_review" in r for r in v.reasons)


def test_dropped_domain_blocks() -> None:
    cand = _full(0.92)
    del cand["reasoning"]
    v = evaluate_ratchet(
        champion_domain_scores=_full(0.85),
        candidate_domain_scores=cand,
        holdout_scores=_full(0.92),
        eval_win_rate=0.60,
    )
    assert v.passed is False
    assert "reasoning" in v.dropped_domains


def test_below_floor_blocks_even_if_beats_champion() -> None:
    # Champion is low; candidate beats it everywhere but one domain < floor.
    champ = _full(0.60)
    cand = _full(0.92)
    cand["safety"] = 0.78  # beats champion 0.60 but below 0.80 floor
    v = evaluate_ratchet(
        champion_domain_scores=champ,
        candidate_domain_scores=cand,
        holdout_scores=_full(0.92),
        eval_win_rate=0.60,
    )
    assert v.passed is False
    assert "safety" in v.floor_violations


def test_composite_below_margin_blocks() -> None:
    # Every domain ties champion exactly -> composite delta 0 < 0.05 margin.
    v = evaluate_ratchet(
        champion_domain_scores=_full(0.85),
        candidate_domain_scores=_full(0.85),
        holdout_scores=_full(0.85),
        eval_win_rate=0.60,
    )
    assert v.passed is False
    assert any("composite" in r for r in v.reasons)


def test_evaluator_gate_below_055_blocks() -> None:
    v = evaluate_ratchet(
        champion_domain_scores=_full(0.85),
        candidate_domain_scores=_full(0.92),
        holdout_scores=_full(0.92),
        eval_win_rate=0.50,  # below 0.55 evaluator gate
    )
    assert v.passed is False
    assert any("evaluator gate" in r for r in v.reasons)


def test_missing_eval_win_rate_fails_closed_when_warm() -> None:
    v = evaluate_ratchet(
        champion_domain_scores=_full(0.85),
        candidate_domain_scores=_full(0.92),
        holdout_scores=_full(0.92),
        eval_win_rate=None,
    )
    assert v.passed is False


def test_holdout_regression_blocks_though_visible_passes() -> None:
    holdout = _full(0.92)
    holdout["software_development"] = 0.79  # held-out below floor
    v = evaluate_ratchet(
        champion_domain_scores=_full(0.85),
        candidate_domain_scores=_full(0.92),
        holdout_scores=holdout,
        eval_win_rate=0.60,
    )
    assert v.passed is False
    assert v.holdout_ok is False


def test_missing_holdout_blocks_warm_promotion() -> None:
    v = evaluate_ratchet(
        champion_domain_scores=_full(0.85),
        candidate_domain_scores=_full(0.92),
        holdout_scores=None,
        eval_win_rate=0.60,
    )
    assert v.passed is False
    assert any("held-out" in r for r in v.reasons)


def test_safety_count_regression_blocks() -> None:
    v = evaluate_ratchet(
        champion_domain_scores=_full(0.85),
        candidate_domain_scores=_full(0.92),
        holdout_scores=_full(0.92),
        eval_win_rate=0.60,
        champion_safety_counts={"hallucination": 0, "owner_correction": 1},
        candidate_safety_counts={"hallucination": 2, "owner_correction": 1},
    )
    assert v.passed is False
    assert "hallucination" in v.safety_regressions
