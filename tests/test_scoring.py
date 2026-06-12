"""Unit tests for the scoring engine (`muse_cli.scoring`).

Phase 14: the scoring engine now produces sixteen categories per
worker. These tests deliberately exercise the layered behaviour:

  * artifact loading is forgiving of missing files
  * each scoring category responds to its dominant signal
  * weighted_total and rank() do the right thing under ties
  * user_profile and decision_ledger inputs bias scoring without
    breaking deterministic ranking

No filesystem state escapes ``tmp_path``; no LLM calls; no subprocess.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

import pytest

from muse_cli.scoring import (
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
    changed_files: Sequence[str] | None = ("foo.py",),
    validation_output: str = "1 passed in 0.01s\n",
    status: dict | None = None,
    validation_filename: str = "validation-output.txt",
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
    (d / validation_filename).write_text(validation_output, encoding="utf-8")
    if status is None:
        status = {"success": True, "profile": "test-runner"}
    (d / "status.json").write_text(json.dumps(status), encoding="utf-8")
    return d


def _artifact(
    *,
    worker_id: str = "x",
    output_md: str = "",
    patch_diff: str = "",
    changed_files: Sequence[str] = (),
    validation_output: str = "",
    status: dict | None = None,
) -> WorkerArtifact:
    """Build a WorkerArtifact in-memory for property-level tests."""
    return WorkerArtifact(
        worker_id=worker_id,
        path=Path("/tmp"),
        output_md=output_md,
        patch_diff=patch_diff,
        changed_files=tuple(changed_files),
        validation_output=validation_output,
        status=status or {},
    )


# ── load_artifact ─────────────────────────────────────────────────────


def test_load_artifact_reads_all_five_files(tmp_path):
    d = _write_worker(tmp_path, "alpha")
    art = load_artifact(d)
    assert art.worker_id == "alpha"
    assert art.output_md.startswith("Worker did a thing")
    assert "diff --git" in art.patch_diff
    assert art.changed_files == ("foo.py",)
    assert "passed" in art.validation_output
    # Legacy alias still works.
    assert art.test_output == art.validation_output
    assert art.status["success"] is True
    assert art.missing == ()


def test_load_artifact_accepts_legacy_test_output_filename(tmp_path):
    d = _write_worker(
        tmp_path,
        "legacy",
        validation_filename="test-output.txt",
    )
    art = load_artifact(d)
    assert "passed" in art.validation_output
    assert art.missing == ()


def test_load_artifact_tracks_missing_files(tmp_path):
    d = tmp_path / "beta"
    d.mkdir()
    (d / "output.md").write_text("just a note", encoding="utf-8")
    art = load_artifact(d)
    assert "patch.diff" in art.missing
    assert "changed-files.txt" in art.missing
    assert "validation-output.txt" in art.missing
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
    art = _artifact(
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
    )
    # Two real changes; the +++/--- headers must not be counted.
    assert art.diff_line_count == 2


def test_touches_high_risk_detects_auth_and_billing_paths():
    art = _artifact(changed_files=("muse_cli/auth.py", "src/billing/charge.py"))
    assert art.touches_high_risk is True


def test_touches_high_risk_false_for_normal_paths():
    art = _artifact(changed_files=("muse_cli/scoring.py", "tests/test_scoring.py"))
    assert art.touches_high_risk is False


def test_touches_mobile_detects_android_and_termux_paths():
    art = _artifact(changed_files=("apps/android/MainActivity.kt", "scripts/termux-setup.sh"))
    assert art.touches_mobile is True


def test_touches_voice_detects_tts_and_speech_paths():
    art = _artifact(changed_files=("gateway/voice/tts.py",))
    assert art.touches_voice is True


def test_adds_tests_detects_pytest_layouts():
    art = _artifact(changed_files=("tests/test_foo.py", "src/foo.py"))
    assert art.adds_tests is True


def test_adds_tests_detects_nested_test_dirs():
    art = _artifact(changed_files=("muse_cli/foo.py", "muse_cli/tests/test_foo.py"))
    assert art.adds_tests is True


def test_adds_docs_detects_docs_and_readme():
    art = _artifact(changed_files=("docs/orchestration/foo.md", "src/foo.py"))
    assert art.adds_docs is True


# ── score_artifact: per-category behaviour ────────────────────────────


def test_score_card_has_all_sixteen_categories(tmp_path):
    d = _write_worker(tmp_path, "alpha")
    card = score_artifact(load_artifact(d))
    assert set(card.scores.keys()) == set(SCORE_CATEGORIES)
    assert len(SCORE_CATEGORIES) == 16
    assert all(0.0 <= v <= 1.0 for v in card.scores.values())


def test_passing_validation_lifts_correctness(tmp_path):
    d = _write_worker(tmp_path, "winner", validation_output="5 passed in 0.10s")
    card = score_artifact(load_artifact(d))
    assert card.tests_passed is True
    assert card.scores["correctness"] >= 0.9


def test_failing_validation_craters_correctness(tmp_path):
    d = _write_worker(
        tmp_path,
        "loser",
        validation_output="FAILED tests/test_x.py::test_y - AssertionError: nope",
    )
    card = score_artifact(load_artifact(d))
    assert card.tests_passed is False
    assert card.scores["correctness"] <= 0.2
    assert any("validation reported failures" in f for f in card.flags)


def test_empty_patch_flags_completeness_and_correctness(tmp_path):
    d = _write_worker(
        tmp_path,
        "empty",
        patch_diff="",
        changed_files=[],
        validation_output="",
        status={"success": False, "profile": "stub"},
    )
    card = score_artifact(load_artifact(d))
    assert card.scores["correctness"] <= 0.2
    assert card.scores["completeness"] <= 0.25
    assert any("empty patch" in f or "no files changed" in f for f in card.flags)


def test_high_risk_without_tests_craters_security_and_testability(tmp_path):
    d = _write_worker(
        tmp_path,
        "risky",
        changed_files=["muse_cli/auth.py"],
        validation_output="",  # ambiguous - no validation evidence
    )
    card = score_artifact(load_artifact(d))
    assert card.touches_high_risk is True
    assert card.adds_tests is False
    assert card.scores["security"] <= 0.2
    assert card.scores["testability"] <= 0.25
    assert any("high-risk" in f for f in card.flags)


def test_high_risk_with_tests_recovers_security(tmp_path):
    d = _write_worker(
        tmp_path,
        "careful",
        changed_files=["muse_cli/auth.py", "tests/test_auth.py"],
        validation_output="2 passed in 0.05s",
    )
    card = score_artifact(load_artifact(d))
    assert card.touches_high_risk is True
    assert card.adds_tests is True
    assert card.scores["security"] >= 0.7
    assert card.scores["testability"] >= 0.9


def test_secrets_in_diff_zero_secrets_safety(tmp_path):
    leaky = _write_worker(
        tmp_path,
        "leaky",
        patch_diff=(
            "diff --git a/cfg.py b/cfg.py\n"
            "@@ -1 +1,2 @@\n"
            "+AWS_KEY = 'AKIAIOSFODNN7EXAMPLE'\n"
            "+OPENAI = 'sk-abcdefghijklmnopqrstuv'\n"
        ),
    )
    card = score_artifact(load_artifact(leaky))
    assert card.scores["secrets_safety"] == 0.0
    assert any("secret" in f.lower() for f in card.flags)


def test_clean_diff_keeps_secrets_safety_high(tmp_path):
    d = _write_worker(tmp_path, "clean")
    card = score_artifact(load_artifact(d))
    assert card.scores["secrets_safety"] >= 0.5


def test_remote_unfriendly_patterns_lower_remote_execution_fit(tmp_path):
    friendly = _write_worker(tmp_path, "friendly")
    unfriendly = _write_worker(
        tmp_path,
        "unfriendly",
        patch_diff=(
            "diff --git a/a b/a\n"
            "+import os\n"
            "+if os.isatty(0):\n"
            "+    pass\n"
            "+conn = ('127.0.0.1', 8000)\n"
            "+open('/home/jeremiah/.ssh/id_rsa')\n"
        ),
    )
    fcard = score_artifact(load_artifact(friendly))
    ucard = score_artifact(load_artifact(unfriendly))
    assert fcard.scores["remote_execution_fit"] > ucard.scores["remote_execution_fit"]


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
                "ui_ux": 0.88,
                "jeremiah_fit": 0.4,
            },
        },
    )
    card = score_artifact(load_artifact(d))
    assert card.scores["architecture_fit"] == pytest.approx(0.92)
    assert card.scores["ui_ux"] == pytest.approx(0.88)
    assert card.scores["jeremiah_fit"] == pytest.approx(0.4)


def test_legacy_ux_quality_self_score_falls_back_to_ui_ux(tmp_path):
    d = _write_worker(
        tmp_path,
        "legacy",
        status={
            "success": True,
            "self_scores": {"ux_quality": 0.77},
        },
    )
    card = score_artifact(load_artifact(d))
    assert card.scores["ui_ux"] == pytest.approx(0.77)


def test_self_scores_are_clamped_to_unit_interval(tmp_path):
    d = _write_worker(
        tmp_path,
        "boastful",
        status={
            "success": True,
            "self_scores": {"ui_ux": 9.0, "speed": -3.0},
        },
    )
    card = score_artifact(load_artifact(d))
    assert card.scores["ui_ux"] == 1.0
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


def test_mobile_paths_lift_mobile_fit_when_validated(tmp_path):
    d = _write_worker(
        tmp_path,
        "mobile-aware",
        changed_files=["apps/android/MainActivity.kt", "tests/test_mobile.py"],
        validation_output="3 passed in 0.04s",
    )
    card = score_artifact(load_artifact(d))
    assert card.scores["mobile_fit"] >= 0.8


def test_voice_paths_lift_voice_fit_when_validated(tmp_path):
    d = _write_worker(
        tmp_path,
        "voice-aware",
        changed_files=["gateway/voice/tts.py", "tests/test_voice.py"],
        validation_output="ok",
    )
    card = score_artifact(load_artifact(d))
    assert card.scores["voice_fit"] >= 0.8


def test_docs_changes_lift_developer_experience(tmp_path):
    plain = _write_worker(tmp_path, "code-only")
    docsy = _write_worker(
        tmp_path,
        "docsy",
        changed_files=["docs/orchestration/foo.md", "README.md"],
        output_md="A " * 100,
    )
    plain_card = score_artifact(load_artifact(plain))
    docs_card = score_artifact(load_artifact(docsy))
    assert docs_card.scores["developer_experience"] >= plain_card.scores["developer_experience"]


def test_user_profile_can_override_category(tmp_path):
    d = _write_worker(tmp_path, "alpha")
    profile = {
        "category_preferences": {
            "ui_ux": 0.99,
            "jeremiah_fit": 0.99,
        }
    }
    card = score_artifact(load_artifact(d), user_profile=profile)
    assert card.scores["ui_ux"] == pytest.approx(0.99)
    assert card.scores["jeremiah_fit"] == pytest.approx(0.99)


def test_decision_ledger_adds_note_for_prior_rejection(tmp_path):
    d = _write_worker(tmp_path, "repeat")
    ledger = [
        {"worker_id": "repeat", "outcome": "rejected", "reason": "high-risk no tests"},
        {"worker_id": "other", "outcome": "accepted"},
    ]
    card = score_artifact(load_artifact(d), decision_ledger=ledger)
    assert any("prior rejection" in n for n in card.notes)


# ── weighted_total + rank ─────────────────────────────────────────────


def test_weighted_total_emphasises_correctness_and_secrets_safety():
    """Correctness and secrets_safety must dominate the weighted total."""
    base = {cat: 0.5 for cat in SCORE_CATEGORIES}
    high_correct = Scorecard(
        worker_id="a",
        profile="x",
        scores={**base, "correctness": 0.9, "ui_ux": 0.1},
    )
    high_ux = Scorecard(
        worker_id="b",
        profile="y",
        scores={**base, "correctness": 0.1, "ui_ux": 0.9},
    )
    # Same unweighted mean.
    assert high_correct.total == pytest.approx(high_ux.total)
    # Correctness is weighted 3x more than ui_ux, so:
    assert high_correct.weighted_total > high_ux.weighted_total


def test_rank_breaks_ties_by_correctness_then_diff_size():
    base = {cat: 0.7 for cat in SCORE_CATEGORIES}
    a = Scorecard(worker_id="a", profile="p", scores=dict(base), diff_line_count=50)
    b = Scorecard(worker_id="b", profile="p", scores=dict(base), diff_line_count=10)
    c = Scorecard(
        worker_id="c",
        profile="p",
        scores={**base, "correctness": 0.95},
        diff_line_count=300,
    )
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
