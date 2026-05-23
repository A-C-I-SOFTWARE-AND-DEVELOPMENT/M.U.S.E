"""Unit tests for the merge engine (`hermes_cli.merge_engine`).

Coverage:

  * policy gates: high-risk-no-tests rejection, score floor
  * ranking and winner selection
  * conflict detection across surviving candidates
  * manual-review gate triggers
  * output artifact contents (scorecard.json, council-review.md,
    conflict-report.md, final-plan.md, final-patch.diff)

Tests run entirely against ``tmp_path``; no LLM calls; no subprocess.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hermes_cli.merge_engine import (
    HIGH_RISK_TEST_REQUIRED,
    MANUAL_REVIEW_FLOOR,
    SCORE_FLOOR,
    FileConflict,
    RejectedWorker,
    run_merge,
    select_winner,
)
from hermes_cli.scoring import (
    SCORE_CATEGORIES,
    Scorecard,
    WorkerArtifact,
    load_artifact,
    score_artifact,
)


# ── Helpers ───────────────────────────────────────────────────────────


def _write_worker(
    root: Path,
    worker_id: str,
    *,
    output_md: str = "Made the change. Tests pass.\n",
    patch_diff: str = "diff --git a/foo.py b/foo.py\n@@ -1 +1 @@\n-old\n+new\n",
    changed_files=("foo.py",),
    test_output: str = "1 passed in 0.01s\n",
    status: dict | None = None,
) -> Path:
    d = root / worker_id
    d.mkdir(parents=True, exist_ok=True)
    (d / "output.md").write_text(output_md, encoding="utf-8")
    (d / "patch.diff").write_text(patch_diff, encoding="utf-8")
    (d / "changed-files.txt").write_text(
        "\n".join(changed_files) + "\n", encoding="utf-8"
    )
    (d / "test-output.txt").write_text(test_output, encoding="utf-8")
    if status is None:
        status = {"success": True, "profile": "test-runner"}
    (d / "status.json").write_text(json.dumps(status), encoding="utf-8")
    return d


def _load_pair(worker_dirs: list[Path]):
    arts = [load_artifact(d) for d in worker_dirs]
    cards = [score_artifact(a) for a in arts]
    return arts, cards


# ── Policy gates ──────────────────────────────────────────────────────


def test_high_risk_worker_without_tests_is_rejected(tmp_path):
    assert HIGH_RISK_TEST_REQUIRED is True
    risky = _write_worker(
        tmp_path,
        "risky",
        changed_files=["hermes_cli/auth.py"],
        test_output="",
        status={"success": True},
    )
    safe = _write_worker(
        tmp_path,
        "safe",
        changed_files=["hermes_cli/scoring.py"],
        test_output="1 passed in 0.01s",
    )
    arts, cards = _load_pair([risky, safe])
    result = select_winner(arts, cards)
    assert result.winner is not None
    assert result.winner.worker_id == "safe"
    rejected_ids = [r.worker_id for r in result.rejected]
    assert "risky" in rejected_ids
    risky_reason = next(r.reason for r in result.rejected if r.worker_id == "risky")
    assert "high-risk" in risky_reason


def test_high_risk_with_tests_is_eligible(tmp_path):
    careful = _write_worker(
        tmp_path,
        "careful",
        changed_files=["hermes_cli/auth.py", "tests/test_auth.py"],
        test_output="2 passed in 0.05s",
    )
    arts, cards = _load_pair([careful])
    result = select_winner(arts, cards)
    assert result.winner is not None
    assert result.winner.worker_id == "careful"
    assert "winning worker touches high-risk paths" in " ".join(result.review_reasons)


def test_worker_below_score_floor_is_rejected(tmp_path):
    # An empty patch + missing artifacts → score well below the floor.
    bad_dir = tmp_path / "bad"
    bad_dir.mkdir()
    (bad_dir / "output.md").write_text("nope", encoding="utf-8")

    good = _write_worker(tmp_path, "good")
    arts, cards = _load_pair([bad_dir, good])
    result = select_winner(arts, cards)
    assert result.winner is not None
    assert result.winner.worker_id == "good"
    rejected_ids = [r.worker_id for r in result.rejected]
    assert "bad" in rejected_ids
    bad_reason = next(r.reason for r in result.rejected if r.worker_id == "bad")
    assert "floor" in bad_reason


def test_no_survivors_triggers_manual_review_with_no_winner(tmp_path):
    bad_dir = tmp_path / "bad"
    bad_dir.mkdir()
    (bad_dir / "output.md").write_text("", encoding="utf-8")
    arts, cards = _load_pair([bad_dir])
    result = select_winner(arts, cards)
    assert result.winner is None
    assert result.manual_review_required is True
    assert any("no worker survived" in r for r in result.review_reasons)


# ── Ranking / winner selection ────────────────────────────────────────


def test_winner_is_the_highest_weighted_total(tmp_path):
    # Worker A: small focused diff, tests pass.
    a = _write_worker(tmp_path, "a")
    # Worker B: huge sprawling diff, tests pass.
    big_diff = ["diff --git a/x b/x", "--- a/x", "+++ b/x"]
    big_diff += [f"+line {i}" for i in range(700)]
    b = _write_worker(
        tmp_path,
        "b",
        patch_diff="\n".join(big_diff) + "\n",
        changed_files=["x"],
    )
    arts, cards = _load_pair([a, b])
    result = select_winner(arts, cards)
    assert result.winner is not None
    assert result.winner.worker_id == "a"
    assert result.runners_up[0].worker_id == "b"


def test_winner_below_manual_review_floor_triggers_review(tmp_path):
    """A surviving worker that lands between SCORE_FLOOR and MANUAL_REVIEW_FLOOR
    must still be selected — but the plan must be flagged for manual review.
    Constructed directly because the natural heuristics tend to land above
    the floor; we want to assert the gate itself, not the heuristics.
    """
    artifact = WorkerArtifact(
        worker_id="mid",
        path=tmp_path / "mid",
        output_md="something",
        patch_diff="diff --git a/x b/x\n@@ -1 +1 @@\n-a\n+b\n",
        changed_files=("x",),
        test_output="",
        status={"profile": "p"},
    )
    # Hand-build a score profile that sits in the [floor, review-floor) band.
    target = (SCORE_FLOOR + MANUAL_REVIEW_FLOOR) / 2
    scores = {cat: target for cat in SCORE_CATEGORIES}
    card = Scorecard(
        worker_id="mid",
        profile="p",
        scores=scores,
        changed_file_count=1,
        diff_line_count=2,
    )
    assert SCORE_FLOOR <= card.weighted_total < MANUAL_REVIEW_FLOOR

    result = select_winner([artifact], [card])
    assert result.winner is not None
    assert result.winner.worker_id == "mid"
    assert result.manual_review_required is True
    assert any("manual-review floor" in r for r in result.review_reasons)


def test_failing_tests_on_winner_triggers_manual_review(tmp_path):
    failing = _write_worker(
        tmp_path,
        "failing",
        test_output="FAILED tests/test_x.py::test_y - AssertionError",
    )
    arts, cards = _load_pair([failing])
    # If correctness drops the worker below SCORE_FLOOR they're rejected.
    if cards[0].weighted_total < SCORE_FLOOR:
        pytest.skip("worker fell below score floor — covered by other test")
    result = select_winner(arts, cards)
    if result.winner is not None:
        assert result.manual_review_required is True
        assert any("tests reported failures" in r for r in result.review_reasons)


# ── Conflict detection ────────────────────────────────────────────────


def test_conflicts_detected_across_surviving_candidates(tmp_path):
    a = _write_worker(
        tmp_path, "a", changed_files=["foo.py", "bar.py"]
    )
    b = _write_worker(
        tmp_path, "b", changed_files=["foo.py", "baz.py"]
    )
    c = _write_worker(
        tmp_path, "c", changed_files=["bar.py", "baz.py"]
    )
    arts, cards = _load_pair([a, b, c])
    result = select_winner(arts, cards)
    conflict_paths = {c.path for c in result.conflicts}
    assert conflict_paths == {"foo.py", "bar.py", "baz.py"}
    assert result.manual_review_required is True
    assert any("modified by 2+" in r for r in result.review_reasons)


def test_no_conflicts_when_workers_touch_disjoint_files(tmp_path):
    a = _write_worker(tmp_path, "a", changed_files=["a.py"])
    b = _write_worker(tmp_path, "b", changed_files=["b.py"])
    arts, cards = _load_pair([a, b])
    result = select_winner(arts, cards)
    assert result.conflicts == []


def test_rejected_workers_do_not_create_conflicts(tmp_path):
    # Rejected (high-risk no tests) touches foo.py.
    rejected = _write_worker(
        tmp_path,
        "rejected",
        changed_files=["hermes_cli/auth.py", "foo.py"],
        test_output="",
    )
    survivor = _write_worker(tmp_path, "survivor", changed_files=["foo.py"])
    arts, cards = _load_pair([rejected, survivor])
    result = select_winner(arts, cards)
    # `rejected` should not appear in conflict detection because we
    # only consider surviving candidates.
    assert result.conflicts == []


# ── run_merge: end-to-end output artifacts ────────────────────────────


def test_run_merge_writes_five_canonical_artifacts(tmp_path):
    workers_dir = tmp_path / "workers"
    workers_dir.mkdir()
    _write_worker(workers_dir, "a")
    _write_worker(
        workers_dir,
        "b",
        patch_diff="diff --git a/qux.py b/qux.py\n@@ -1 +1 @@\n-x\n+y\n",
        changed_files=["qux.py"],
    )
    out_dir = tmp_path / "merge"
    result = run_merge(workers_dir, out_dir)

    assert (out_dir / "scorecard.json").exists()
    assert (out_dir / "council-review.md").exists()
    assert (out_dir / "conflict-report.md").exists()
    assert (out_dir / "final-plan.md").exists()
    assert (out_dir / "final-patch.diff").exists()
    assert result.output_dir == out_dir


def test_run_merge_scorecard_json_is_well_formed(tmp_path):
    workers_dir = tmp_path / "workers"
    workers_dir.mkdir()
    _write_worker(workers_dir, "a")
    _write_worker(workers_dir, "b", changed_files=["b.py"])
    out_dir = tmp_path / "merge"
    run_merge(workers_dir, out_dir)

    payload = json.loads((out_dir / "scorecard.json").read_text())
    assert payload["schema"] == "hermes.merge.scorecard.v1"
    assert payload["categories"] == list(SCORE_CATEGORIES)
    assert payload["winner"] in {"a", "b"}
    assert len(payload["scorecards"]) == 2
    for card in payload["scorecards"]:
        assert set(card["scores"].keys()) == set(SCORE_CATEGORIES)


def test_run_merge_final_patch_matches_winner_diff(tmp_path):
    workers_dir = tmp_path / "workers"
    workers_dir.mkdir()
    winning_diff = "diff --git a/win.py b/win.py\n@@ -1 +1 @@\n-old\n+winning\n"
    losing_diff = "diff --git a/lose.py b/lose.py\n" + "@@ -1 +1 @@\n-x\n+y\n" + (
        # Make this one big so it loses on maintainability.
        "\n".join(f"+filler {i}" for i in range(800)) + "\n"
    )
    _write_worker(
        workers_dir,
        "winner",
        patch_diff=winning_diff,
        changed_files=["win.py"],
    )
    _write_worker(
        workers_dir,
        "loser",
        patch_diff=losing_diff,
        changed_files=["lose.py"],
    )
    out_dir = tmp_path / "merge"
    result = run_merge(workers_dir, out_dir)

    assert result.winner is not None
    assert result.winner.worker_id == "winner"
    final = (out_dir / "final-patch.diff").read_text()
    assert final == winning_diff


def test_run_merge_council_review_lists_rejected_and_runners_up(tmp_path):
    workers_dir = tmp_path / "workers"
    workers_dir.mkdir()
    _write_worker(workers_dir, "winner")
    _write_worker(
        workers_dir,
        "runnerup",
        patch_diff="diff --git a/q.py b/q.py\n@@ -1 +1 @@\n-x\n+y\n",
        changed_files=["q.py"],
        output_md="Different approach. Equally focused.\n",
    )
    _write_worker(
        workers_dir,
        "risky",
        changed_files=["hermes_cli/auth.py"],
        test_output="",
    )
    out_dir = tmp_path / "merge"
    run_merge(workers_dir, out_dir)

    review = (out_dir / "council-review.md").read_text()
    assert "Selected:" in review
    assert "## Score breakdown" in review
    assert "## Rejected workers" in review
    assert "risky" in review
    assert "## Runners-up" in review
    assert "runnerup" in review or "winner" in review


def test_run_merge_conflict_report_when_no_conflicts(tmp_path):
    workers_dir = tmp_path / "workers"
    workers_dir.mkdir()
    _write_worker(workers_dir, "a")
    out_dir = tmp_path / "merge"
    run_merge(workers_dir, out_dir)

    report = (out_dir / "conflict-report.md").read_text()
    assert "No conflicts detected" in report


def test_run_merge_conflict_report_lists_each_conflict(tmp_path):
    workers_dir = tmp_path / "workers"
    workers_dir.mkdir()
    _write_worker(workers_dir, "a", changed_files=["shared.py", "a_only.py"])
    _write_worker(workers_dir, "b", changed_files=["shared.py", "b_only.py"])
    out_dir = tmp_path / "merge"
    run_merge(workers_dir, out_dir)

    report = (out_dir / "conflict-report.md").read_text()
    assert "shared.py" in report
    assert "a_only.py" not in report
    assert "b_only.py" not in report


def test_run_merge_final_plan_reflects_manual_review(tmp_path):
    workers_dir = tmp_path / "workers"
    workers_dir.mkdir()
    # Two workers touching the same file → conflict → manual review.
    _write_worker(workers_dir, "a", changed_files=["shared.py"])
    _write_worker(workers_dir, "b", changed_files=["shared.py"])
    out_dir = tmp_path / "merge"
    result = run_merge(workers_dir, out_dir)

    assert result.manual_review_required is True
    plan = (out_dir / "final-plan.md").read_text()
    assert "MANUAL REVIEW REQUIRED" in plan
    assert "## How to apply" in plan


def test_run_merge_no_survivors_writes_empty_final_patch(tmp_path):
    workers_dir = tmp_path / "workers"
    workers_dir.mkdir()
    bad = workers_dir / "bad"
    bad.mkdir()
    (bad / "output.md").write_text("nope", encoding="utf-8")
    out_dir = tmp_path / "merge"
    result = run_merge(workers_dir, out_dir)

    assert result.winner is None
    assert (out_dir / "final-patch.diff").read_text() == ""
    plan = (out_dir / "final-plan.md").read_text()
    assert "REJECTED" in plan


def test_run_merge_handles_empty_workers_dir(tmp_path):
    workers_dir = tmp_path / "workers"
    workers_dir.mkdir()
    out_dir = tmp_path / "merge"
    result = run_merge(workers_dir, out_dir)

    assert result.winner is None
    assert result.manual_review_required is True
    # All five artifacts must still exist so downstream tools don't blow up.
    for name in (
        "scorecard.json",
        "council-review.md",
        "conflict-report.md",
        "final-plan.md",
        "final-patch.diff",
    ):
        assert (out_dir / name).exists(), name


# ── Dataclass-as-dict / typing sanity ─────────────────────────────────


def test_file_conflict_and_rejected_worker_dataclasses():
    fc = FileConflict(path="foo.py", workers=("a", "b"))
    assert fc.as_dict() == {"path": "foo.py", "workers": ["a", "b"]}

    rw = RejectedWorker(worker_id="x", profile="p", reason="r", score=0.1)
    assert rw.as_dict() == {
        "worker_id": "x",
        "profile": "p",
        "reason": "r",
        "score": 0.1,
    }


def test_merge_result_as_dict_is_json_serialisable(tmp_path):
    workers_dir = tmp_path / "workers"
    workers_dir.mkdir()
    _write_worker(workers_dir, "a")
    out_dir = tmp_path / "merge"
    result = run_merge(workers_dir, out_dir)
    encoded = json.dumps(result.as_dict())
    decoded = json.loads(encoded)
    assert decoded["winner"]["worker_id"] == "a"
    assert decoded["output_dir"] == str(out_dir)
