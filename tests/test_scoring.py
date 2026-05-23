"""Unit tests for the scoring engine (`hermes_cli.scoring`).

These tests deliberately exercise the layered behaviour:

  * artifact loading is forgiving of missing files
  * each scoring category responds to its dominant signal
  * weighted_total and rank() do the right thing under ties

No filesystem state escapes ``tmp_path``; no LLM calls; no subprocess.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hermes_cli.scoring import (
    SCORE_CATEGORIES,
    Scorecard,
    WorkerArtifact,
    discover_workers,
    load_artifact,
    rank,
    score_artifact,
    score_workers,
)


# ── Test fixtures ─────────────────────────────────────────────────────


def _write_worker(
    root: Path,
    worker_id: str,
    *,
    output_md: str = "Worker did a thing.\n\nIt went fine.\n",
    patch_diff: str | None = "diff --git a/foo.py b/foo.py\n@@ -1 +1 @@\n-old\n+new\n",
    changed_files: list[str] | None = ("foo.py",),
    test_output: str = "1 passed in 0.01s\n",
    status: dict | None = None,
) -> Path:
    """Create a worker directory with the standard 5 artifacts."""
    d = root / worker_id
    d.mkdir(parents=True, exist_ok=True)
    (d / "output.md").write_text(output_md, encoding="utf-8")
    if patch_diff is not None:
        (d / "patch.diff").write_text(patch_diff, encoding="utf-8")
    if changed_files is not None:
        (d / "changed-files.txt").write_text(
            "\n".join(changed_files) + "\n", encoding="utf-8"
        )
    (d / "test-output.txt").write_text(test_output, encoding="utf-8")
    if status is None:
        status = {"success": True, "profile": "test-runner"}
    (d / "status.json").write_text(json.dumps(status), encoding="utf-8")
    return d


# ── load_artifact ─────────────────────────────────────────────────────


def test_load_artifact_reads_all_five_files(tmp_path):
    d = _write_worker(tmp_path, "alpha")
    art = load_artifact(d)
    assert art.worker_id == "alpha"
    assert art.output_md.startswith("Worker did a thing")
    assert "diff --git" in art.patch_diff
    assert art.changed_files == ("foo.py",)
    assert "passed" in art.test_output
    assert art.status["success"] is True
    assert art.missing == ()


def test_load_artifact_tracks_missing_files(tmp_path):
    d = tmp_path / "beta"
    d.mkdir()
    (d / "output.md").write_text("just a note", encoding="utf-8")
    art = load_artifact(d)
    assert "patch.diff" in art.missing
    assert "changed-files.txt" in art.missing
    assert "test-output.txt" in art.missing
    assert "status.json" in art.missing
    assert art.patch_diff == ""
    assert art.status == {}


def test_load_artifact_handles_unparseable_status(tmp_path):
    d = _write_worker(tmp_path, "gamma")
    (d / "status.json").write_text("{not json", encoding="utf-8")
    art = load_artifact(d)
    assert art.status.get("_parse_error") is True


def test_load_artifact_strips_comments_from_changed_files(tmp_path):
    d = _write_worker(
        tmp_path,
        "delta",
        changed_files=["foo.py", "# this is a comment", "bar/baz.py", "  ", "qux.md"],
    )
    art = load_artifact(d)
    assert art.changed_files == ("foo.py", "bar/baz.py", "qux.md")


def test_load_artifact_rejects_nonexistent_dir(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_artifact(tmp_path / "does-not-exist")


def test_discover_workers_returns_sorted_subdirs(tmp_path):
    # Use a dedicated subdir — the shared tmp_path may have been seeded
    # by conftest fixtures (e.g. HERMES_HOME initialization).
    root = tmp_path / "workers"
    root.mkdir()
    (root / "z").mkdir()
    (root / "a").mkdir()
    (root / "m").mkdir()
    (root / "not-a-dir").write_text("x", encoding="utf-8")
    found = discover_workers(root)
    assert [p.name for p in found] == ["a", "m", "z"]


def test_discover_workers_empty_when_missing(tmp_path):
    assert discover_workers(tmp_path / "nope") == []


# ── WorkerArtifact properties ─────────────────────────────────────────


def test_worker_artifact_diff_line_count_ignores_headers():
    art = WorkerArtifact(
        worker_id="x",
        path=Path("/tmp"),
        output_md="",
        patch_diff=(
            "diff --git a/foo b/foo\n"
            "--- a/foo\n"
            "+++ b/foo\n"
            "@@ -1,3 +1,3 @@\n"
            "-removed\n"
            "+added\n"
            " context\n"
        ),
        changed_files=("foo",),
        test_output="",
        status={},
    )
    # Two real changes; the +++/--- headers must not be counted.
    assert art.diff_line_count == 2


def test_touches_high_risk_detects_auth_and_billing_paths():
    art = WorkerArtifact(
        worker_id="x",
        path=Path("/tmp"),
        output_md="",
        patch_diff="",
        changed_files=("hermes_cli/auth.py", "src/billing/charge.py"),
        test_output="",
        status={},
    )
    assert art.touches_high_risk is True


def test_touches_high_risk_false_for_normal_paths():
    art = WorkerArtifact(
        worker_id="x",
        path=Path("/tmp"),
        output_md="",
        patch_diff="",
        changed_files=("hermes_cli/scoring.py", "tests/test_scoring.py"),
        test_output="",
        status={},
    )
    assert art.touches_high_risk is False


def test_adds_tests_detects_pytest_layouts():
    art = WorkerArtifact(
        worker_id="x",
        path=Path("/tmp"),
        output_md="",
        patch_diff="",
        changed_files=("tests/test_foo.py", "src/foo.py"),
        test_output="",
        status={},
    )
    assert art.adds_tests is True


def test_adds_tests_detects_nested_test_dirs():
    art = WorkerArtifact(
        worker_id="x",
        path=Path("/tmp"),
        output_md="",
        patch_diff="",
        changed_files=("hermes_cli/foo.py", "hermes_cli/tests/test_foo.py"),
        test_output="",
        status={},
    )
    assert art.adds_tests is True


# ── score_artifact: per-category behaviour ────────────────────────────


def test_score_card_has_all_twelve_categories(tmp_path):
    d = _write_worker(tmp_path, "alpha")
    card = score_artifact(load_artifact(d))
    assert set(card.scores.keys()) == set(SCORE_CATEGORIES)
    assert all(0.0 <= v <= 1.0 for v in card.scores.values())


def test_passing_tests_lift_correctness(tmp_path):
    d = _write_worker(tmp_path, "winner", test_output="5 passed in 0.10s")
    card = score_artifact(load_artifact(d))
    assert card.tests_passed is True
    assert card.scores["correctness"] >= 0.9


def test_failing_tests_crater_correctness(tmp_path):
    d = _write_worker(
        tmp_path,
        "loser",
        test_output="FAILED tests/test_x.py::test_y - AssertionError: nope",
    )
    card = score_artifact(load_artifact(d))
    assert card.tests_passed is False
    assert card.scores["correctness"] <= 0.2
    assert "tests reported failures" in card.flags


def test_empty_patch_flags_completeness_and_correctness(tmp_path):
    d = _write_worker(
        tmp_path,
        "empty",
        patch_diff="",
        changed_files=[],
        test_output="",
        status={"success": False, "profile": "stub"},
    )
    card = score_artifact(load_artifact(d))
    assert card.scores["correctness"] <= 0.2
    assert card.scores["completeness"] <= 0.25
    assert any("empty patch" in f or "no files changed" in f for f in card.flags)


def test_high_risk_without_tests_craters_risk_control_and_testability(tmp_path):
    d = _write_worker(
        tmp_path,
        "risky",
        changed_files=["hermes_cli/auth.py"],
        test_output="",  # ambiguous - no test evidence
    )
    card = score_artifact(load_artifact(d))
    assert card.touches_high_risk is True
    assert card.adds_tests is False
    assert card.scores["risk_control"] <= 0.2
    assert card.scores["testability"] <= 0.25
    assert any("high-risk" in f for f in card.flags)


def test_high_risk_with_tests_recovers_risk_control(tmp_path):
    d = _write_worker(
        tmp_path,
        "careful",
        changed_files=["hermes_cli/auth.py", "tests/test_auth.py"],
        test_output="2 passed in 0.05s",
    )
    card = score_artifact(load_artifact(d))
    assert card.touches_high_risk is True
    assert card.adds_tests is True
    assert card.scores["risk_control"] >= 0.7
    assert card.scores["testability"] >= 0.9


def test_large_diff_penalises_maintainability(tmp_path):
    big_diff = ["diff --git a/x b/x", "--- a/x", "+++ b/x"]
    big_diff += [f"+line {i}" for i in range(700)]
    d = _write_worker(
        tmp_path,
        "sprawling",
        patch_diff="\n".join(big_diff) + "\n",
        changed_files=["x"],
    )
    card = score_artifact(load_artifact(d))
    assert card.scores["maintainability"] <= 0.4
    assert any("very large diff" in f for f in card.flags)


def test_small_focused_diff_scores_high_maintainability(tmp_path):
    d = _write_worker(tmp_path, "tight")
    card = score_artifact(load_artifact(d))
    assert card.scores["maintainability"] >= 0.85


def test_self_scores_in_status_are_honoured(tmp_path):
    d = _write_worker(
        tmp_path,
        "self-aware",
        status={
            "success": True,
            "profile": "claude",
            "self_scores": {
                "architecture_fit": 0.92,
                "ux_quality": 0.88,
                "jeremiah_fit": 0.4,
            },
        },
    )
    card = score_artifact(load_artifact(d))
    assert card.scores["architecture_fit"] == pytest.approx(0.92)
    assert card.scores["ux_quality"] == pytest.approx(0.88)
    assert card.scores["jeremiah_fit"] == pytest.approx(0.4)


def test_self_scores_are_clamped_to_unit_interval(tmp_path):
    d = _write_worker(
        tmp_path,
        "boastful",
        status={
            "success": True,
            "self_scores": {"ux_quality": 9.0, "speed": -3.0},
        },
    )
    card = score_artifact(load_artifact(d))
    assert card.scores["ux_quality"] == 1.0
    assert card.scores["speed"] == 0.0


def test_flat_category_scores_supported(tmp_path):
    d = _write_worker(
        tmp_path,
        "flat",
        status={"success": True, "speed_score": 0.3, "cost_efficiency_score": 0.9},
    )
    card = score_artifact(load_artifact(d))
    assert card.scores["speed"] == pytest.approx(0.3)
    assert card.scores["cost_efficiency"] == pytest.approx(0.9)


def test_elapsed_seconds_drives_speed_when_not_self_reported(tmp_path):
    fast = _write_worker(
        tmp_path,
        "fast",
        status={"success": True, "elapsed_seconds": 30},
    )
    slow = _write_worker(
        tmp_path,
        "slow",
        status={"success": True, "elapsed_seconds": 800},
    )
    fast_card = score_artifact(load_artifact(fast))
    slow_card = score_artifact(load_artifact(slow))
    assert fast_card.scores["speed"] > slow_card.scores["speed"]


def test_token_count_drives_cost_efficiency_when_not_self_reported(tmp_path):
    cheap = _write_worker(
        tmp_path,
        "cheap",
        status={"success": True, "tokens": 1_000},
    )
    pricey = _write_worker(
        tmp_path,
        "pricey",
        status={"success": True, "tokens": 80_000},
    )
    cheap_card = score_artifact(load_artifact(cheap))
    pricey_card = score_artifact(load_artifact(pricey))
    assert cheap_card.scores["cost_efficiency"] > pricey_card.scores["cost_efficiency"]


def test_local_first_penalises_external_network_calls(tmp_path):
    local = _write_worker(tmp_path, "local")
    networked = _write_worker(
        tmp_path,
        "networked",
        patch_diff=(
            "diff --git a/x b/x\n"
            "+import requests\n"
            "+requests.get('https://example.com/a')\n"
            "+requests.get('https://example.com/b')\n"
            "+requests.get('https://example.com/c')\n"
            "+requests.get('https://example.com/d')\n"
        ),
    )
    local_card = score_artifact(load_artifact(local))
    net_card = score_artifact(load_artifact(networked))
    assert local_card.scores["local_first_fit"] > net_card.scores["local_first_fit"]


# ── weighted_total + rank ─────────────────────────────────────────────


def test_weighted_total_emphasises_correctness():
    """Two cards with identical mean but flipped correctness/ux must rank by correctness."""
    base = {cat: 0.5 for cat in SCORE_CATEGORIES}
    high_correct = Scorecard(worker_id="a", profile="x", scores={**base, "correctness": 0.9, "ux_quality": 0.1})
    high_ux = Scorecard(worker_id="b", profile="y", scores={**base, "correctness": 0.1, "ux_quality": 0.9})
    # Same unweighted mean.
    assert high_correct.total == pytest.approx(high_ux.total)
    # But correctness is weighted 3x more than ux_quality, so:
    assert high_correct.weighted_total > high_ux.weighted_total


def test_rank_breaks_ties_by_correctness_then_diff_size():
    base = {cat: 0.7 for cat in SCORE_CATEGORIES}
    a = Scorecard(worker_id="a", profile="p", scores=dict(base), diff_line_count=50)
    b = Scorecard(worker_id="b", profile="p", scores=dict(base), diff_line_count=10)
    c = Scorecard(worker_id="c", profile="p", scores={**base, "correctness": 0.95}, diff_line_count=300)
    ordering = [s.worker_id for s in rank([a, b, c])]
    # c wins (highest correctness via weighted_total).
    assert ordering[0] == "c"
    # Among a, b: same weighted total → tiebreaker is smaller diff → b before a.
    assert ordering[1:] == ["b", "a"]


def test_rank_is_deterministic_on_full_tie():
    base = {cat: 0.5 for cat in SCORE_CATEGORIES}
    cards = [
        Scorecard(worker_id="z", profile="p", scores=dict(base), diff_line_count=10),
        Scorecard(worker_id="a", profile="p", scores=dict(base), diff_line_count=10),
        Scorecard(worker_id="m", profile="p", scores=dict(base), diff_line_count=10),
    ]
    assert [c.worker_id for c in rank(cards)] == ["a", "m", "z"]


def test_score_workers_returns_one_card_per_worker(tmp_path):
    workers_root = tmp_path / "workers"
    workers_root.mkdir()
    _write_worker(workers_root, "a")
    _write_worker(workers_root, "b")
    arts = [load_artifact(p) for p in discover_workers(workers_root)]
    cards = score_workers(arts)
    assert len(cards) == 2
    assert {c.worker_id for c in cards} == {"a", "b"}


def test_scorecard_as_dict_is_json_serialisable(tmp_path):
    d = _write_worker(tmp_path, "alpha")
    card = score_artifact(load_artifact(d))
    payload = card.as_dict()
    # Round-trip through JSON — fails loudly if any non-serialisable value sneaks in.
    encoded = json.dumps(payload)
    assert "alpha" in encoded
    decoded = json.loads(encoded)
    assert decoded["worker_id"] == "alpha"
    assert set(decoded["scores"].keys()) == set(SCORE_CATEGORIES)
