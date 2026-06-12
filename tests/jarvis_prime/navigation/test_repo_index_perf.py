"""Performance-pruning tests for the repo navigator's tree walk.

These guard the fix for the ~306s "root-at-checkout" walk found by the
FU-15 E2E: at a full hermes checkout, ``.claude/worktrees`` holds many full
sibling repo checkouts (six figures of files), and the navigator used to
descend into every one of them. The fix prunes heavy/irrelevant directories
*in place* during ``os.walk`` so they are never descended into.

The tests are deterministic, fast, and stdlib-only (no network): they build
a synthetic tmp tree with a large ignored subtree plus a handful of real
files and assert (a) the ignored directories are never *descended* — proven
by monkeypatching ``os.walk`` to record the directories it actually visits —
and (b) the genuinely-relevant files are still indexed unchanged.
"""

from __future__ import annotations

import os
from pathlib import Path

import muse_cli.jarvis_prime.navigation.repo_index as repo_index_mod
from muse_cli.jarvis_prime.navigation.repo_index import (
    DEFAULT_IGNORE_DIRS,
    RepoIndex,
)


def _make_tree(root: Path) -> dict[str, list[str]]:
    """Create a synthetic repo with real files + large ignored subtrees.

    Returns a map of {category: [relative_posix_paths]} for the *real* files
    so the test can assert they survive indexing.
    """

    real_source = root / "pkg"
    real_source.mkdir()
    (real_source / "__init__.py").write_text("", encoding="utf-8")
    (real_source / "core.py").write_text("def go():\n    return 1\n", encoding="utf-8")
    (real_source / "util.py").write_text("def helper():\n    return 2\n", encoding="utf-8")

    tests_dir = root / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_core.py").write_text(
        "def test_go():\n    assert True\n", encoding="utf-8"
    )

    (root / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    (root / "README.md").write_text("# synthetic\n", encoding="utf-8")

    # --- Heavy ignored subtrees: a fake node_modules and a fake
    # .claude/worktrees, each with many files. If pruning regresses these
    # would be walked (and indexed), which is exactly the bug we fix. ---
    node_modules = root / "node_modules"
    node_modules.mkdir()
    for i in range(200):
        pkg = node_modules / f"dep_{i}"
        pkg.mkdir()
        (pkg / "index.js").write_text(f"module.exports = {i}\n", encoding="utf-8")

    worktrees = root / ".claude" / "worktrees"
    worktrees.mkdir(parents=True)
    for i in range(5):
        wt = worktrees / f"agent-{i}"
        (wt / "pkg").mkdir(parents=True)
        # Files that look exactly like real source — only their location
        # (inside an ignored subtree) should keep them out of the index.
        (wt / "pkg" / "core.py").write_text("def go():\n    return 99\n", encoding="utf-8")
        (wt / "README.md").write_text("# clone\n", encoding="utf-8")

    # A couple more ignored dirs that the walk must also skip.
    (root / "__pycache__").mkdir()
    (root / "__pycache__" / "core.cpython-313.pyc").write_bytes(b"\x00\x01")
    (root / ".venv").mkdir()
    (root / ".venv" / "marker.py").write_text("x = 1\n", encoding="utf-8")

    return {
        "source": ["pkg/__init__.py", "pkg/core.py", "pkg/util.py"],
        "test": ["tests/test_core.py"],
        "config": ["pyproject.toml"],
        "doc": ["README.md"],
    }


def test_default_ignore_covers_heavy_dirs() -> None:
    """The dirs the FU-15 fix calls out must be in the default ignore set."""

    required = {
        ".git",
        "node_modules",
        ".venv",
        "venv",
        ".claude",
        "__pycache__",
        "dist",
        "build",
        ".mypy_cache",
        ".ruff_cache",
        ".pytest_cache",
        "site-packages",
    }
    missing = required - set(DEFAULT_IGNORE_DIRS)
    assert not missing, f"DEFAULT_IGNORE_DIRS is missing {sorted(missing)}"


def test_ignored_dirs_are_never_descended(tmp_path: Path, monkeypatch) -> None:
    """Prove pruning happens *during* the walk, not after.

    We wrap ``os.walk`` to record every directory it yields. If pruning works,
    ``os.walk`` is never iterated into the ignored subtrees, so none of their
    paths show up in the visited set. This is a true descent check, not just
    an output filter.
    """

    _make_tree(tmp_path)

    visited: list[str] = []
    real_walk = os.walk

    def counting_walk(top, *args, **kwargs):
        for dirpath, dirnames, filenames in real_walk(top, *args, **kwargs):
            visited.append(str(dirpath))
            yield dirpath, dirnames, filenames

    monkeypatch.setattr(repo_index_mod.os, "walk", counting_walk)

    index = RepoIndex.build(tmp_path)

    # Not one directory inside any ignored subtree may have been visited.
    ignored_roots = ["node_modules", ".claude", "__pycache__", ".venv"]
    offenders = [
        v
        for v in visited
        if any(
            seg in ignored_roots
            for seg in Path(v).relative_to(tmp_path).parts
        )
    ]
    assert not offenders, f"os.walk descended into pruned dirs: {offenders[:5]}"

    # The fake node_modules alone has 200 nested package dirs; if any had been
    # descended, the visited count would balloon. Keep a tight upper bound.
    assert len(visited) < 20, f"walked too many dirs ({len(visited)}): {visited}"

    # And nothing from an ignored subtree leaked into the index.
    paths = {f.path for f in index.files}
    assert not any(
        p.startswith(("node_modules/", ".claude/", "__pycache__/", ".venv/"))
        for p in paths
    ), f"index contains pruned paths: {sorted(paths)}"


def test_real_files_still_indexed(tmp_path: Path) -> None:
    """Pruning the heavy dirs must not drop any genuinely-relevant file."""

    expected = _make_tree(tmp_path)
    index = RepoIndex.build(tmp_path)
    paths = {f.path for f in index.files}

    for category, rels in expected.items():
        for rel in rels:
            assert rel in paths, f"expected {category} file {rel!r} missing from index"

    # Roles are unchanged by the perf fix.
    assert {f.path for f in index.source_files} >= {"pkg/core.py", "pkg/util.py"}
    assert [f.path for f in index.test_files] == ["tests/test_core.py"]
    assert "pyproject.toml" in {f.path for f in index.config_files}
    assert "README.md" in {f.path for f in index.doc_files}

    # Exactly the real files survive (the fake node_modules core.py / clone
    # README must not double the counts).
    assert len(paths) == sum(len(v) for v in expected.values())


def test_max_files_cap_is_opt_in(tmp_path: Path) -> None:
    """``max_files`` is a backstop: default ``None`` indexes everything."""

    _make_tree(tmp_path)

    full = RepoIndex.build(tmp_path)
    assert len(full.files) > 1  # sanity: the synthetic tree has several files

    capped = RepoIndex.build(tmp_path, max_files=1)
    assert len(capped.files) == 1

    # An absurdly high cap is identical to the default (no cap).
    uncapped = RepoIndex.build(tmp_path, max_files=10_000)
    assert {f.path for f in uncapped.files} == {f.path for f in full.files}


def test_build_never_raises_on_missing_root(tmp_path: Path) -> None:
    """The walk is best-effort: a non-existent root yields an empty index."""

    missing = tmp_path / "does-not-exist"
    index = RepoIndex.build(missing)
    assert index.files == []
