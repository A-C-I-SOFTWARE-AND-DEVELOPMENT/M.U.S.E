"""Tests for the ambition layer — additive, can only raise the bar."""

from __future__ import annotations

from muse_cli.jarvis_prime.research_fabric.ambition import (
    AmbitionProfile,
    apply_ambition,
)
from muse_cli.jarvis_prime.research_fabric.validators import RatchetVerdict


def _passing_verdict() -> RatchetVerdict:
    return RatchetVerdict(
        passed=True,
        per_domain={},
        composite_champion=0.85,
        composite_candidate=0.92,
        composite_delta=0.07,
        eval_win_rate=0.6,
        floor_violations=(),
        dropped_domains=(),
        safety_regressions=(),
        holdout_ok=True,
        cold_start=False,
        reasons=("ratchet passed",),
    )


def _failing_verdict() -> RatchetVerdict:
    return RatchetVerdict(
        passed=False,
        per_domain={},
        composite_champion=0.85,
        composite_candidate=0.80,
        composite_delta=-0.05,
        eval_win_rate=0.6,
        floor_violations=("safety",),
        dropped_domains=(),
        safety_regressions=(),
        holdout_ok=True,
        cold_start=False,
        reasons=("composite below margin",),
    )


def test_ambition_can_flip_pass_to_fail() -> None:
    profile = AmbitionProfile(required_minimums={"human_compassion": 0.9})
    out = apply_ambition(_passing_verdict(), {"human_compassion": 0.5}, profile)
    assert out.passed is False
    assert any("human_compassion" in r for r in out.reasons)


def test_ambition_never_flips_fail_to_pass() -> None:
    # Even with perfect ambition scores, a failing verdict stays failing.
    profile = AmbitionProfile(required_minimums={"human_compassion": 0.0})
    out = apply_ambition(_failing_verdict(), {"human_compassion": 1.0}, profile)
    assert out.passed is False


def test_ambition_never_mutates_safety_fields() -> None:
    profile = AmbitionProfile(required_minimums={"frontier_seeking": 0.99})
    v = _passing_verdict()
    out = apply_ambition(v, {"frontier_seeking": 0.1}, profile)
    assert out.floor_violations == v.floor_violations
    assert out.safety_regressions == v.safety_regressions
    assert out.dropped_domains == v.dropped_domains


def test_ambition_passes_when_minimums_met() -> None:
    profile = AmbitionProfile(required_minimums={"creativity": 0.5})
    out = apply_ambition(_passing_verdict(), {"creativity": 0.9}, profile)
    assert out.passed is True
