"""Tests for ROUTE-2 eval-gating, extending the existing model_router/registry.

Verifies the gate is opt-in (no behavior change by default), excludes
un-evaluated workers for gated categories, keeps eval-passed workers, and that
``eval_passed`` / ``eval_results`` round-trip through the YAML loader.
"""

import pytest

from hermes_cli.model_registry import Registry, WorkerEntry, _worker_from_yaml
from hermes_cli.model_router import RouterContext, route


def _registry() -> Registry:
    workers = (
        WorkerEntry(
            id="verified-impl",
            categories=("implementation",),
            strengths=("implementation",),
            quality="high",
            eval_passed=True,
            eval_results=(("coding", 0.92),),
        ),
        WorkerEntry(
            id="unverified-impl",
            categories=("implementation",),
            strengths=("implementation",),
            quality="high",
            eval_passed=False,
        ),
    )
    return Registry(workers=workers, source="test", path=None)


def test_default_no_gate_keeps_unverified_worker():
    # Empty require_eval_for → existing behavior; unverified worker not excluded
    # by an eval gate (it may appear in selected or fallback, but must NOT be
    # rejected for an eval reason).
    dec = route("do impl", "implementation", context=RouterContext(), registry=_registry())
    assert "eval gate" not in (dec.rejected.get("unverified-impl") or "")


def test_gated_category_excludes_unverified_worker():
    ctx = RouterContext(require_eval_for=frozenset({"implementation"}))
    dec = route("do impl", "implementation", context=ctx, registry=_registry())
    assert "unverified-impl" in dec.rejected
    assert "eval gate" in dec.rejected["unverified-impl"]
    assert "unverified-impl" not in dec.selected_ids()


def test_gated_category_keeps_verified_worker():
    ctx = RouterContext(require_eval_for=frozenset({"implementation"}))
    dec = route("do impl", "implementation", context=ctx, registry=_registry())
    # verified-impl is eval-passed → not rejected for eval reasons.
    assert "eval gate" not in (dec.rejected.get("verified-impl") or "")


def test_gate_does_not_affect_other_categories():
    # Gating "security" must not eval-reject implementation workers.
    ctx = RouterContext(require_eval_for=frozenset({"security"}))
    dec = route("do impl", "implementation", context=ctx, registry=_registry())
    assert "eval gate" not in (dec.rejected.get("unverified-impl") or "")


def test_eval_fields_round_trip_through_yaml():
    raw = {
        "id": "w1",
        "eval_passed": True,
        "eval_results": {"coding": 0.9, "safety": 1.0},
    }
    w = _worker_from_yaml(raw)
    assert w.eval_passed is True
    assert w.eval_results_dict == {"coding": 0.9, "safety": 1.0}


def test_eval_defaults_backward_compatible():
    w = _worker_from_yaml({"id": "legacy"})
    assert w.eval_passed is False
    assert w.eval_results == ()
