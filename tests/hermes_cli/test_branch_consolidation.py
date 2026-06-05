"""Tests for hermes_cli.branch_consolidation.

These exercise the real git plumbing in throwaway repositories so the merge,
conflict-resolution, review-gate, and safe-stop paths are covered end to end.
Network access is avoided by injecting ``complete_fn`` / ``is_model_configured``.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from hermes_cli.branch_consolidation import (
    INTEGRATION_BRANCH,
    STATUS_DECLINED,
    STATUS_MERGED,
    STATUS_SAFE_STOP,
    STATUS_SKIPPED,
    consolidate_into_main,
)

GIT = ["git"]


def _run(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=True
    )


def _init_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    _run(path, "init", "-q", "-b", "main")
    _run(path, "config", "user.email", "t@example.com")
    _run(path, "config", "user.name", "Test")


def _write_commit(repo: Path, name: str, content: str, msg: str) -> None:
    (repo / name).write_text(content, encoding="utf-8")
    _run(repo, "add", "-A")
    _run(repo, "commit", "-q", "-m", msg)


def _current_branch(repo: Path) -> str:
    return _run(repo, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()


def _branch_exists(repo: Path, name: str) -> bool:
    return (
        subprocess.run(
            ["git", "rev-parse", "--verify", "--quiet", name], cwd=repo
        ).returncode
        == 0
    )


def _file_on_main(repo: Path, name: str) -> str | None:
    res = subprocess.run(
        ["git", "show", f"main:{name}"], cwd=repo, capture_output=True, text=True
    )
    return res.stdout if res.returncode == 0 else None


def _main_sha(repo: Path) -> str:
    return _run(repo, "rev-parse", "main").stdout.strip()


@pytest.fixture
def fork_setup(tmp_path: Path):
    """Build upstream → origin (fork) → working clone on a feature branch.

    Returns (work_repo, helpers) so each test can tailor upstream/feature
    content before calling ``consolidate_into_main``.
    """

    upstream = tmp_path / "upstream"
    _init_repo(upstream)
    _write_commit(upstream, "base.txt", "base\n", "initial")

    # Origin is bare so the working clone can push main back to it (mirrors a
    # remote like GitHub).
    origin = tmp_path / "origin.git"
    _run(tmp_path, "clone", "-q", "--bare", str(upstream), str(origin))

    work = tmp_path / "work"
    _run(tmp_path, "clone", "-q", str(origin), str(work))
    _run(work, "config", "user.email", "t@example.com")
    _run(work, "config", "user.name", "Test")
    _run(work, "remote", "add", "upstream", str(upstream))
    _run(work, "fetch", "-q", "upstream")

    return {"upstream": upstream, "origin": origin, "work": work}


def _make_feature_branch(work: Path, name: str, content: str) -> None:
    _run(work, "checkout", "-q", "-b", "feature")
    _write_commit(work, name, content, "feature work")


def _add_upstream_commit(upstream: Path, work: Path, name: str, content: str) -> None:
    _write_commit(upstream, name, content, "upstream work")
    _run(work, "fetch", "-q", "upstream")


def test_clean_three_way_merge_merges_into_main(fork_setup):
    work = fork_setup["work"]
    origin = fork_setup["origin"]
    _make_feature_branch(work, "feature.txt", "feature\n")
    _add_upstream_commit(fork_setup["upstream"], work, "upstream.txt", "upstream\n")

    # Autonomous by default: no input_fn, no interactive — it just merges.
    result = consolidate_into_main(
        GIT,
        work,
        current_branch="feature",
        is_model_configured=lambda: False,  # not needed; no conflicts
    )

    assert result.status == STATUS_MERGED
    assert _current_branch(work) == "main"
    # Both sources landed on main.
    assert _file_on_main(work, "feature.txt") == "feature\n"
    assert _file_on_main(work, "upstream.txt") == "upstream\n"
    # Integration branch cleaned up; feature branch preserved.
    assert not _branch_exists(work, INTEGRATION_BRANCH)
    assert _branch_exists(work, "feature")
    # Auto-pushed to origin: the bare origin's main matches local main.
    assert result.pushed is True
    assert _main_sha(origin) == _main_sha(work)


def test_no_push_keeps_origin_unchanged(fork_setup):
    work = fork_setup["work"]
    origin = fork_setup["origin"]
    origin_before = _main_sha(origin)
    _make_feature_branch(work, "feature.txt", "feature\n")
    _add_upstream_commit(fork_setup["upstream"], work, "upstream.txt", "upstream\n")

    result = consolidate_into_main(
        GIT,
        work,
        current_branch="feature",
        push=False,
        is_model_configured=lambda: False,
    )

    assert result.status == STATUS_MERGED
    assert result.pushed is False
    # Local main advanced, origin did not.
    assert _file_on_main(work, "feature.txt") == "feature\n"
    assert _main_sha(origin) == origin_before


def test_push_failure_keeps_local_main(fork_setup, monkeypatch):
    """A rejected push (e.g. origin advanced — the non-ff race) must still
    return MERGED with pushed=False and leave the consolidated local main
    intact, so the caller does not discard the integrated commits."""
    import hermes_cli.branch_consolidation as bc

    work = fork_setup["work"]
    _make_feature_branch(work, "feature.txt", "feature\n")
    _add_upstream_commit(fork_setup["upstream"], work, "upstream.txt", "upstream\n")

    monkeypatch.setattr(
        bc, "_push_main", lambda git_cmd, repo: (False, "  ℹ push rejected (non-ff)")
    )

    result = consolidate_into_main(
        GIT,
        work,
        current_branch="feature",
        is_model_configured=lambda: False,
    )

    assert result.status == STATUS_MERGED
    assert result.pushed is False
    # The integrated commits survive on local main despite the push failure.
    assert _file_on_main(work, "feature.txt") == "feature\n"
    assert _file_on_main(work, "upstream.txt") == "upstream\n"
    assert not _branch_exists(work, INTEGRATION_BRANCH)


def test_conflict_without_model_safe_stops(fork_setup):
    work = fork_setup["work"]
    # Feature and upstream both edit base.txt → conflict.
    _make_feature_branch(work, "base.txt", "feature edit\n")
    _add_upstream_commit(fork_setup["upstream"], work, "base.txt", "upstream edit\n")

    result = consolidate_into_main(
        GIT,
        work,
        current_branch="feature",
        assume_yes=True,
        is_model_configured=lambda: False,
    )

    assert result.status == STATUS_SAFE_STOP
    assert "base.txt" in result.conflict_files
    # main untouched (still the original base content), no integration branch,
    # back on the feature branch, working tree clean.
    assert _file_on_main(work, "base.txt") == "base\n"
    assert not _branch_exists(work, INTEGRATION_BRANCH)
    assert _current_branch(work) == "feature"
    status = _run(work, "status", "--porcelain").stdout.strip()
    assert status == ""


def test_conflict_with_model_resolution_merges(fork_setup):
    work = fork_setup["work"]
    _make_feature_branch(work, "base.txt", "feature edit\n")
    _add_upstream_commit(fork_setup["upstream"], work, "base.txt", "upstream edit\n")

    resolved = "merged: feature + upstream\n"
    result = consolidate_into_main(
        GIT,
        work,
        current_branch="feature",
        assume_yes=True,
        is_model_configured=lambda: True,
        complete_fn=lambda prompt: resolved,
    )

    assert result.status == STATUS_MERGED
    assert "base.txt" in result.resolved_files
    assert _file_on_main(work, "base.txt") == resolved


def test_model_returns_unresolved_markers_safe_stops(fork_setup):
    work = fork_setup["work"]
    _make_feature_branch(work, "base.txt", "feature edit\n")
    _add_upstream_commit(fork_setup["upstream"], work, "base.txt", "upstream edit\n")

    bad = "<<<<<<< HEAD\nfeature\n=======\nupstream\n>>>>>>> x\n"
    result = consolidate_into_main(
        GIT,
        work,
        current_branch="feature",
        assume_yes=True,
        is_model_configured=lambda: True,
        complete_fn=lambda prompt: bad,
    )

    assert result.status == STATUS_SAFE_STOP
    assert _file_on_main(work, "base.txt") == "base\n"
    assert not _branch_exists(work, INTEGRATION_BRANCH)


def test_interactive_review_declined_leaves_main_untouched(fork_setup):
    work = fork_setup["work"]
    origin = fork_setup["origin"]
    origin_before = _main_sha(origin)
    _make_feature_branch(work, "feature.txt", "feature\n")
    _add_upstream_commit(fork_setup["upstream"], work, "upstream.txt", "upstream\n")

    # With interactive=True the review gate applies; declining touches nothing.
    result = consolidate_into_main(
        GIT,
        work,
        current_branch="feature",
        interactive=True,
        input_fn=lambda q, d: "n",
        is_model_configured=lambda: False,
    )

    assert result.status == STATUS_DECLINED
    assert _file_on_main(work, "feature.txt") is None
    assert _file_on_main(work, "upstream.txt") is None
    assert not _branch_exists(work, INTEGRATION_BRANCH)
    assert _current_branch(work) == "feature"
    assert _main_sha(origin) == origin_before


def test_no_upstream_remote_skips(tmp_path: Path):
    # A plain repo with no 'upstream' remote → consolidation is not applicable.
    repo = tmp_path / "repo"
    _init_repo(repo)
    _write_commit(repo, "base.txt", "base\n", "initial")

    result = consolidate_into_main(
        GIT,
        repo,
        current_branch="main",
        assume_yes=True,
        is_model_configured=lambda: False,
    )

    assert result.status == STATUS_SKIPPED


def test_syntax_guard_failure_safe_stops(fork_setup):
    work = fork_setup["work"]
    _make_feature_branch(work, "feature.txt", "feature\n")
    _add_upstream_commit(fork_setup["upstream"], work, "upstream.txt", "upstream\n")

    result = consolidate_into_main(
        GIT,
        work,
        current_branch="feature",
        assume_yes=True,
        is_model_configured=lambda: False,
        validate_syntax=lambda repo: (False, "feature.txt", "boom"),
    )

    assert result.status == STATUS_SAFE_STOP
    # Nothing landed on main.
    assert _file_on_main(work, "feature.txt") is None
    assert not _branch_exists(work, INTEGRATION_BRANCH)
    assert _current_branch(work) == "feature"
