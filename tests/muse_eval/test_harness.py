"""Tests for the additive ``muse_eval`` behavioral + adversarial harness.

These assert real invariants of the corpus and the harness — not that specific
strings exist in specific files (no change-detector tests):

* every case file parses and passes schema validation;
* ids are unique;
* every ``scoring_dimensions`` key is one of the eight known dimensions;
* the two NEW axes each have >= 2 cases;
* every dimension is exercised by >= 1 core (held-out) case;
* the offline HeuristicJudge self-test separates a compliant target from a
  violating one;
* the CLI exits 0 on the clean corpus and non-zero on a malformed case.
"""

from __future__ import annotations

import json

import pytest

from hermes_cli.jarvis_prime.muse_eval import harness as H
from hermes_cli.jarvis_prime.muse_eval import (
    DIMENSIONS,
    HeuristicJudge,
    load_cases,
    run,
)


@pytest.fixture(scope="module")
def cases():
    return load_cases()


def test_all_cases_load_and_validate():
    # strict load raises on any schema error; reaching here means clean.
    loaded = load_cases()
    assert loaded, "expected a non-empty case corpus"
    assert validate_clean() == []


def validate_clean():
    return H.validate_cases()


def test_expected_case_count(cases):
    # ~20 cases: 10 behavioral + ~10 adversarial. Assert the documented split.
    behavioral = [c for c in cases if c.category == "behavioral"]
    adversarial = [c for c in cases if c.category == "adversarial"]
    assert len(behavioral) == 10
    assert len(adversarial) >= 10
    assert len(cases) >= 20


def test_ids_unique(cases):
    ids = [c.id for c in cases]
    assert len(ids) == len(set(ids)), "case ids must be unique"


def test_required_fields_present(cases):
    for c in cases:
        assert c.id and isinstance(c.id, str)
        assert c.title
        assert c.mode
        assert c.category in ("behavioral", "adversarial")
        assert c.prompt
        assert c.trap
        assert c.expected_behaviors, f"{c.id}: expected_behaviors empty"
        assert c.scoring_dimensions, f"{c.id}: scoring_dimensions empty"
        assert c.pass_criteria
        assert isinstance(c.source_clauses, tuple)
        assert c.pool in ("core", "dev")


def test_scoring_dimensions_are_known(cases):
    for c in cases:
        for dim, weight in c.scoring_dimensions.items():
            assert dim in DIMENSIONS, f"{c.id}: unknown dimension {dim!r}"
            assert weight > 0, f"{c.id}: non-positive weight for {dim!r}"


def test_new_axes_have_at_least_two_cases(cases):
    for axis in ("agent_selection_quality", "verification_honesty"):
        n = sum(1 for c in cases if axis in c.scoring_dimensions)
        assert n >= 2, f"NEW axis {axis!r} needs >= 2 cases, has {n}"


def test_every_dimension_has_a_core_case(cases):
    core_dims = {
        dim
        for c in cases
        if c.pool == "core"
        for dim in c.scoring_dimensions
    }
    missing = set(DIMENSIONS) - core_dims
    assert not missing, f"dimensions with no core case: {sorted(missing)}"


def test_pools_partition(cases):
    # core and dev are disjoint by construction (a case is in exactly one pool).
    for c in cases:
        assert c.pool in ("core", "dev")
    assert any(c.pool == "core" for c in cases)
    assert any(c.pool == "dev" for c in cases)


def test_heuristic_judge_self_test_separates_targets(cases):
    judge = HeuristicJudge()
    report = run(cases, judge)  # compliant reference target
    # Compliant stand-in should pass the large majority of cases.
    assert report.pass_rate >= 0.9, report.to_dict()

    # Violating target (echoes the trap, no safe markers) should pass far fewer.
    violating_passes = sum(
        1 for c in cases if judge.grade(c, H.noncompliant_answer(c)).passed
    )
    assert violating_passes < report.passed


def test_report_is_version_tagged_and_json_serializable(cases):
    report = run(cases, HeuristicJudge())
    assert report.harness_version == H.HARNESS_VERSION
    blob = report.to_json()
    parsed = json.loads(blob)
    assert parsed["harness_version"] == H.HARNESS_VERSION
    assert parsed["total"] == len(cases)
    # every reported dimension is a known one
    for dim in parsed["dimension_scores"]:
        assert dim in DIMENSIONS


def test_weighted_score_bounds(cases):
    judge = HeuristicJudge()
    for c in cases:
        v = judge.grade(c, H.compliant_answer(c))
        assert 0.0 <= v.weighted_score <= 1.0


def test_cli_returns_zero_on_clean_corpus():
    assert H.main([]) == 0


def test_cli_json_mode_returns_zero():
    assert H.main(["--json"]) == 0


def test_cli_returns_nonzero_on_malformed_case(tmp_path):
    good = {
        "id": "TMP-01",
        "title": "t",
        "mode": "companion",
        "category": "behavioral",
        "prompt": "p",
        "trap": "x",
        "expected_behaviors": ["a"],
        "scoring_dimensions": {"scope_discipline": 1.0},
        "pass_criteria": "c",
        "source_clauses": [],
    }
    (tmp_path / "good.json").write_text(json.dumps(good), encoding="utf-8")
    # Unknown dimension -> schema failure.
    bad = dict(good, id="TMP-02", scoring_dimensions={"not_a_dimension": 1.0})
    (tmp_path / "bad.json").write_text(json.dumps(bad), encoding="utf-8")

    assert H.main(["--cases-dir", str(tmp_path)]) != 0


def test_load_cases_nonstrict_skips_bad(tmp_path):
    bad = {"id": "X", "title": "t"}  # missing most keys
    (tmp_path / "bad.json").write_text(json.dumps(bad), encoding="utf-8")
    # non-strict: no raise, just skipped
    assert load_cases(tmp_path, strict=False) == []
    # strict: raises
    with pytest.raises(ValueError):
        load_cases(tmp_path, strict=True)
