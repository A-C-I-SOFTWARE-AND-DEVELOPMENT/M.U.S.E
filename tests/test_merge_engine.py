"""Tests for the unified-diff merge engine."""

from __future__ import annotations

from pathlib import Path

import pytest

from hermes_cli.orchestrator.merge_engine import (
    Hunk,
    apply_diff,
    has_conflicts,
    merge_diffs,
    parse_diff,
)


# ── parsing ──────────────────────────────────────────────────────────


def test_parse_empty_diff_returns_empty() -> None:
    assert parse_diff("") == {}
    assert parse_diff("\n") == {}


def test_parse_single_file_diff() -> None:
    diff = (
        "--- a/foo.py\n"
        "+++ b/foo.py\n"
        "@@ -1,3 +1,3 @@\n"
        " ctx1\n"
        "-old\n"
        "+new\n"
        " ctx2\n"
    )
    parsed = parse_diff(diff)
    assert list(parsed.keys()) == ["foo.py"]
    fp = parsed["foo.py"]
    assert fp.old_path == "foo.py"
    assert len(fp.hunks) == 1
    h = fp.hunks[0]
    assert h.new_start == 1
    assert h.new_count == 3
    assert h.body == [" ctx1", "-old", "+new", " ctx2"]


def test_parse_multiple_hunks_in_one_file() -> None:
    diff = (
        "--- a/foo.py\n"
        "+++ b/foo.py\n"
        "@@ -1,1 +1,1 @@\n"
        "-a\n"
        "+b\n"
        "@@ -10,1 +10,1 @@\n"
        "-c\n"
        "+d\n"
    )
    parsed = parse_diff(diff)
    assert len(parsed["foo.py"].hunks) == 2
    assert parsed["foo.py"].hunks[1].new_start == 10


def test_parse_multiple_files() -> None:
    diff = (
        "diff --git a/x b/x\n"
        "--- a/x\n+++ b/x\n@@ -1 +1 @@\n-a\n+b\n"
        "diff --git a/y b/y\n"
        "--- a/y\n+++ b/y\n@@ -1 +1 @@\n-c\n+d\n"
    )
    parsed = parse_diff(diff)
    assert set(parsed.keys()) == {"x", "y"}


# ── overlap / conflict detection ─────────────────────────────────────


def test_hunk_overlap_detection() -> None:
    a = Hunk(1, 1, 5, 5)
    b = Hunk(1, 1, 8, 1)  # 8..8 ⊂ 5..9 → overlap
    c = Hunk(1, 1, 100, 1)  # disjoint
    assert a.overlaps(b)
    assert b.overlaps(a)
    assert not a.overlaps(c)


def test_conflicts_when_same_file_overlapping_hunks() -> None:
    a = (
        "--- a/x\n+++ b/x\n@@ -1,3 +1,3 @@\n"
        " a\n-b\n+B\n c\n"
    )
    b = (
        "--- a/x\n+++ b/x\n@@ -1,3 +1,3 @@\n"
        " a\n-b\n+BB\n c\n"
    )
    assert has_conflicts(a, b)


def test_no_conflicts_when_same_file_disjoint_hunks() -> None:
    a = "--- a/x\n+++ b/x\n@@ -1,1 +1,1 @@\n-a\n+b\n"
    b = "--- a/x\n+++ b/x\n@@ -50,1 +50,1 @@\n-c\n+d\n"
    assert not has_conflicts(a, b)


def test_no_conflicts_when_different_files() -> None:
    a = "--- a/x\n+++ b/x\n@@ -1 +1 @@\n-a\n+b\n"
    b = "--- a/y\n+++ b/y\n@@ -1 +1 @@\n-c\n+d\n"
    assert not has_conflicts(a, b)


def test_no_conflicts_with_empty_input() -> None:
    assert not has_conflicts("", "")
    assert not has_conflicts("--- a/x\n+++ b/x\n@@ -1 +1 @@\n-a\n+b\n", "")


# ── merge ────────────────────────────────────────────────────────────


def test_merge_disjoint_diffs_yields_combined_output() -> None:
    a = "--- a/x\n+++ b/x\n@@ -1 +1 @@\n-a\n+b\n"
    b = "--- a/y\n+++ b/y\n@@ -1 +1 @@\n-c\n+d\n"
    res = merge_diffs([a, b])
    assert res.ok is True
    assert res.merged_files == ["x", "y"]
    assert "x" in res.diff and "y" in res.diff


def test_merge_records_conflicts() -> None:
    a = "--- a/x\n+++ b/x\n@@ -1 +1 @@\n-a\n+b\n"
    b = "--- a/x\n+++ b/x\n@@ -1 +1 @@\n-a\n+B\n"
    res = merge_diffs([a, b])
    assert res.ok is False
    assert res.conflicts == ["x"]
    # Conflicting file must NOT appear in the merged output.
    assert "x" not in res.merged_files


def test_merge_combines_disjoint_hunks_in_same_file() -> None:
    a = "--- a/x\n+++ b/x\n@@ -1 +1 @@\n-a\n+b\n"
    b = "--- a/x\n+++ b/x\n@@ -50 +50 @@\n-c\n+d\n"
    res = merge_diffs([a, b])
    assert res.ok is True
    assert res.merged_files == ["x"]
    # Both hunks present, ordered by new_start
    lines = res.diff.splitlines()
    headers = [l for l in lines if l.startswith("@@")]
    assert len(headers) == 2
    assert "+1,1" in headers[0] or "+1 " in headers[0]


def test_merge_empty_list_returns_empty() -> None:
    res = merge_diffs([])
    assert res.diff == ""
    assert res.ok is True


def test_merge_skips_falsy_diffs() -> None:
    res = merge_diffs(["", None, "--- a/x\n+++ b/x\n@@ -1 +1 @@\n-a\n+b\n"])  # type: ignore[list-item]
    assert res.merged_files == ["x"]


# ── apply_diff via fake runner ───────────────────────────────────────


def test_apply_diff_skips_empty(tmp_path: Path) -> None:
    def boom(*a, **kw):
        raise AssertionError("runner must not be called for empty diff")

    assert apply_diff(tmp_path, "", runner=boom) is True


def test_apply_diff_check_failure_short_circuits(tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def runner(cmd, cwd, env):
        calls.append(cmd)
        return 1, "patch does not apply\n"  # fail at --check

    ok = apply_diff(tmp_path, "--- a/x\n+++ b/x\n@@ -1 +1 @@\n-a\n+b\n", runner=runner)
    assert ok is False
    # Only the --check call happens; no second apply.
    assert len(calls) == 1
    assert "--check" in calls[0]


def test_apply_diff_check_then_apply_succeeds(tmp_path: Path) -> None:
    calls: list[list[str]] = []

    def runner(cmd, cwd, env):
        calls.append(cmd)
        return 0, ""

    ok = apply_diff(tmp_path, "--- a/x\n+++ b/x\n@@ -1 +1 @@\n-a\n+b\n", runner=runner)
    assert ok is True
    assert len(calls) == 2
    assert "--check" in calls[0]
    assert "--check" not in calls[1]
