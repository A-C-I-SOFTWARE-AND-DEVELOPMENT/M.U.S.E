"""Behavioral tests for the W5 model-lane reranker.

These exercise the documented contract: scorecard evidence wins, the
function never raises when files are absent, the intent->task-class map
behaves, and identical calls are deterministic. Each test isolates
``HERMES_HOME`` and uses ``tmp_path`` so no real scorecard/catalog is
touched.
"""

from __future__ import annotations

import pytest

from muse_cli.jarvis_prime.model_rerank import (
    LaneRecommendation,
    recommend_model_lane,
    task_class_for,
)
from muse_cli.jarvis_prime.model_scorecard import ModelScorecard, ScorecardBook
from muse_cli.jarvis_prime.natural_language_coder import CodingIntent


@pytest.fixture(autouse=True)
def _isolated_home(monkeypatch, tmp_path):
    """Point HERMES_HOME at a throwaway dir so defaults never hit real files."""
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes_home"))


def _seed_scorecards(path):
    """Seed a tmp ScorecardBook for coding_build, with a clear winner."""
    book = ScorecardBook(path=path)
    # winner: high pass rate + high accepted-diff, several samples.
    for _ in range(4):
        book.record(
            ModelScorecard(
                model="glm-5",
                provider="zai",
                task_type="coding_build",
                risk_class="RC2",
                tests_passed=10,
                tests_failed=0,
                accepted_diff_rate=0.95,
                tool_reliability=0.99,
            ),
            persist=True,
        )
    # weaker contender: mediocre outcomes.
    for _ in range(4):
        book.record(
            ModelScorecard(
                model="devstral-small",
                provider="ollama",
                task_type="coding_build",
                risk_class="RC2",
                tests_passed=5,
                tests_failed=5,
                accepted_diff_rate=0.40,
                tool_reliability=0.50,
            ),
            persist=True,
        )
    return book


def test_no_scorecard_file_does_not_raise_and_skips_scorecard(tmp_path):
    missing = tmp_path / "does_not_exist" / "scorecards.jsonl"
    assert not missing.exists()

    rec = recommend_model_lane("coding_build", "RC2", scorecard_path=missing)

    assert isinstance(rec, LaneRecommendation)
    assert rec.source != "scorecard"
    assert rec.source in {"oss_catalog", "route_hint"}
    assert rec.lane  # non-empty lane string


def test_measured_scorecard_wins_with_best_model(tmp_path):
    sc_path = tmp_path / "scorecards.jsonl"
    _seed_scorecards(sc_path)

    rec = recommend_model_lane("coding_build", "RC2", scorecard_path=sc_path)

    assert rec.source == "scorecard"
    assert rec.lane == "glm-5"
    # the weaker contender should still appear in the considered shortlist.
    assert "devstral-small" in rec.candidates
    assert rec.candidates[0] == "glm-5"


def test_task_class_for_mapping():
    assert task_class_for(CodingIntent.REVIEW) == "coding_review"
    assert task_class_for(CodingIntent.RESEARCH) == "research"
    assert task_class_for(CodingIntent.TEST) == "test_debug"
    assert task_class_for(CodingIntent.IMPLEMENT) == "coding_build"
    # an unmapped intent falls back to the default.
    assert task_class_for(CodingIntent.UNKNOWN) == "coding_build"


def test_determinism_identical_calls(tmp_path):
    sc_path = tmp_path / "scorecards.jsonl"
    _seed_scorecards(sc_path)

    a = recommend_model_lane("coding_build", "RC2", scorecard_path=sc_path)
    b = recommend_model_lane("coding_build", "RC2", scorecard_path=sc_path)

    assert a.to_dict() == b.to_dict()


def test_determinism_route_hint_path(tmp_path):
    missing = tmp_path / "nope.jsonl"
    a = recommend_model_lane("coding_build", "RC2", scorecard_path=missing)
    b = recommend_model_lane("coding_build", "RC2", scorecard_path=missing)
    assert a.to_dict() == b.to_dict()
