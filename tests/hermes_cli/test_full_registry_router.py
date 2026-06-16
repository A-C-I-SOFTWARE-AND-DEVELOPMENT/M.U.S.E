"""Tests for the opt-in full-registry model ranker.

Confirms it enumerates the ENTIRE catalog (not a tier-gated subset) and that
measured scorecard evidence floats any model to the top — the "MUSE picks the
best model from the whole registry" capability.
"""

from __future__ import annotations

from hermes_cli.jarvis_prime.full_registry_router import (
    RankedModel,
    best_model,
    explain,
    rank_full_registry,
)
from hermes_cli.oss_model_brain import load_oss_catalog


class _StubBook:
    """Minimal scorecard book: returns canned (model, score, samples) rows."""

    def __init__(self, rows):
        self._rows = rows

    def recommend(self, task, *, task_class=None):  # noqa: ARG002 - signature parity
        return list(self._rows)


def test_ranks_the_entire_catalog_not_a_subset():
    catalog = load_oss_catalog()
    ranked = rank_full_registry("coding", catalog=catalog, book=_StubBook([]))
    # Every family is ranked — no tier gating drops candidates.
    assert {r.model for r in ranked} == set(catalog.ids())
    assert all(isinstance(r, RankedModel) for r in ranked)


def test_measured_evidence_floats_a_model_to_the_top():
    catalog = load_oss_catalog()
    ids = catalog.ids()
    assert ids, "catalog should not be empty"
    target = ids[-1]  # any model — even a normally low-ranked one
    book = _StubBook([(target, 0.99, 7)])
    top = best_model("coding", catalog=catalog, book=book)
    assert top is not None
    assert top.model == target
    assert top.measured and top.measured_score == 0.99 and top.samples == 7


def test_unmeasured_ranks_by_catalog_signals():
    catalog = load_oss_catalog()
    ranked = rank_full_registry("coding", catalog=catalog, book=_StubBook([]))
    # With no evidence, nothing is "measured"; ordering is by task fit/quality.
    assert all(not r.measured for r in ranked)
    # sort_key is monotonically non-increasing down the list.
    keys = [r.sort_key for r in ranked]
    assert keys == sorted(keys, reverse=True)


def test_unknown_task_still_returns_all_families():
    catalog = load_oss_catalog()
    ranked = rank_full_registry("no_such_task_xyz", catalog=catalog, book=_StubBook([]))
    assert {r.model for r in ranked} == set(catalog.ids())


def test_explain_is_human_readable():
    catalog = load_oss_catalog()
    text = explain(rank_full_registry("coding", catalog=catalog, book=_StubBook([])))
    assert text and "\n" in text or text  # non-empty summary
