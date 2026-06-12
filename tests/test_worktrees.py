"""Tests for ``muse_cli.worktrees``.

Each test runs against an isolated ephemeral git repository created in
``tmp_path`` so we never touch the host's working copy.
"""

from __future__ import annotations

from pathlib import Path
import json
import subprocess

import pytest

from muse_cli import worktrees as wt


# ─── helpers ──────────────────────────────────────────────────────────


def _run(cmd: list[str], cwd: Path) -> str:
    proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, check=True)
    return proc.stdout


def _init_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    _run(["git", "init", "-q", "-b", "main"], path)
    _run(["git", "config", "user.email", "test@example.com"], path)
    _run(["git", "config", "user.name", "Test"], path)
    _run(["git", "config", "commit.gpgsign", "false"], path)
    (path / "README.md").write_text("hello\n", encoding="utf-8")
    _run(["git", "add", "README.md"], path)
    _run(["git", "commit", "-q", "-m", "init"], path)
    return path


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    return _init_repo(tmp_path / "repo")


# ─── sanitization ─────────────────────────────────────────────────────


def test_sanitize_segment_strips_unsafe_chars():
    assert wt.sanitize_segment("job/1 alpha", field_name="job_id") == "job-1-alpha"


def test_sanitize_segment_rejects_empty():
    with pytest.raises(wt.WorktreeError):
        wt.sanitize_segment("", field_name="job_id")


def test_sanitize_segment_rejects_pure_separators():
    with pytest.raises(wt.WorktreeError):
        wt.sanitize_segment("///...", field_name="job_id")


def test_branch_name_uses_hermes_prefix_and_sanitization():
    assert wt.branch_name("Job 1", "worker/A") == "hermes/Job-1/worker-A"


def test_worktree_path_layout(repo: Path):
    expected = (
        repo / ".hermes-orchestrator" / "worktrees" / "job1" / "worker1"
    )
    assert wt.worktree_path(repo, "job1", "worker1") == expected


# ─── repo state checks ───────────────────────────────────────────────


def test_is_dirty_false_on_clean_repo(repo: Path):
    assert wt.is_dirty(repo) is False


def test_is_dirty_true_when_file_modified(repo: Path):
    (repo / "README.md").write_text("changed\n", encoding="utf-8")
    assert wt.is_dirty(repo) is True


def test_create_worktree_refuses_dirty(repo: Path):
    (repo / "dirty.txt").write_text("x", encoding="utf-8")
    with pytest.raises(wt.WorktreeError, match="uncommitted changes"):
        wt.create_worktree(repo, job_id="j1", worker_id="w1")


def test_create_worktree_refuses_non_git_dir(tmp_path: Path):
    (tmp_path / "plain").mkdir()
    with pytest.raises(wt.WorktreeError, match="not a git repository"):
        wt.create_worktree(tmp_path / "plain", job_id="j1", worker_id="w1")


# ─── happy path ──────────────────────────────────────────────────────


def test_create_worktree_writes_metadata_and_branch(repo: Path):
    info = wt.create_worktree(
        repo,
        job_id="job-1",
        worker_id="worker-A",
        extra_metadata={"profile": "researcher"},
    )

    assert info.branch == "hermes/job-1/worker-A"
    assert info.path.exists()
    assert (info.path / "README.md").exists()
    # metadata file written next to the worktree (NOT inside it, so it
    # doesn't show up as an untracked file in the new branch).
    meta_path = wt.metadata_path_for(repo, "job-1", "worker-A")
    assert meta_path.exists()
    assert not (info.path / wt.METADATA_SUFFIX).exists()  # not inside the working tree
    payload = json.loads(meta_path.read_text(encoding="utf-8"))
    assert payload["branch"] == "hermes/job-1/worker-A"
    assert payload["metadata"]["profile"] == "researcher"
    # The brand-new worktree is clean (no stray metadata leaking inside)
    status_out = _run(["git", "status", "--porcelain"], info.path).strip()
    assert status_out == ""
    # branch is actually checked out in the worktree
    head = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], info.path).strip()
    assert head == "hermes/job-1/worker-A"


def test_create_worktree_refuses_to_reuse_branch(repo: Path):
    info = wt.create_worktree(repo, job_id="job-1", worker_id="w1")
    # Remove the on-disk path but leave the branch so we can prove the
    # branch-collision check fires.
    import shutil as _shutil
    _shutil.rmtree(info.path)
    _run(["git", "worktree", "prune"], repo)
    with pytest.raises(wt.WorktreeError, match="branch"):
        wt.create_worktree(repo, job_id="job-1", worker_id="w1")


def test_create_worktree_refuses_existing_path(repo: Path):
    # Pre-populate the destination
    target = wt.worktree_path(repo, "job-2", "w1")
    target.mkdir(parents=True, exist_ok=True)
    with pytest.raises(wt.WorktreeError, match="path already exists"):
        wt.create_worktree(repo, job_id="job-2", worker_id="w1")


def test_create_worktree_allow_dirty(repo: Path):
    (repo / "scratch.txt").write_text("x", encoding="utf-8")
    info = wt.create_worktree(
        repo, job_id="job-3", worker_id="w1", allow_dirty=True
    )
    assert info.path.exists()


def test_create_worktree_with_base_ref(repo: Path):
    # Create a second commit so HEAD != base ref
    (repo / "second.txt").write_text("two\n", encoding="utf-8")
    _run(["git", "add", "second.txt"], repo)
    _run(["git", "commit", "-q", "-m", "two"], repo)
    first = _run(["git", "rev-parse", "HEAD~1"], repo).strip()
    info = wt.create_worktree(
        repo, job_id="job-4", worker_id="w1", base_ref=first
    )
    # The worktree should be checked out at the first commit
    head_sha = _run(["git", "rev-parse", "HEAD"], info.path).strip()
    assert head_sha == first


def test_create_worktree_rejects_unknown_base_ref(repo: Path):
    with pytest.raises(wt.WorktreeError, match="not found"):
        wt.create_worktree(repo, job_id="job-5", worker_id="w1", base_ref="no-such-ref")


# ─── metadata / listing ──────────────────────────────────────────────


def test_list_worktrees_finds_each_created_one(repo: Path):
    wt.create_worktree(repo, job_id="job-a", worker_id="w1")
    wt.create_worktree(repo, job_id="job-a", worker_id="w2")
    wt.create_worktree(repo, job_id="job-b", worker_id="w1")

    infos = wt.list_worktrees(repo)
    keys = {(i.job_id, i.worker_id) for i in infos}
    assert keys == {("job-a", "w1"), ("job-a", "w2"), ("job-b", "w1")}


def test_iter_worktrees_for_job_filters(repo: Path):
    wt.create_worktree(repo, job_id="job-a", worker_id="w1")
    wt.create_worktree(repo, job_id="job-b", worker_id="w1")
    only_a = list(wt.iter_worktrees_for_job(repo, "job-a"))
    assert [i.worker_id for i in only_a] == ["w1"]
    assert only_a[0].job_id == "job-a"


def test_read_metadata_round_trips(repo: Path):
    info = wt.create_worktree(
        repo, job_id="job-x", worker_id="w1", extra_metadata={"k": "v"}
    )
    loaded = wt.read_metadata(repo, "job-x", "w1")
    assert loaded.branch == info.branch
    assert loaded.metadata == {"k": "v"}


def test_read_metadata_missing_raises(repo: Path):
    with pytest.raises(wt.WorktreeError, match="no worktree metadata"):
        wt.read_metadata(repo, "absent", "absent")


# ─── cleanup safety ──────────────────────────────────────────────────


def test_cleanup_worktree_no_confirm_is_noop(repo: Path):
    info = wt.create_worktree(repo, job_id="job-9", worker_id="w1")
    # Default: no confirm → returns False and leaves everything in place.
    assert wt.cleanup_worktree(repo, job_id="job-9", worker_id="w1") is False
    assert info.path.exists()
    # Branch is still there.
    out = _run(["git", "branch", "--list", info.branch], repo)
    assert info.branch in out


def test_cleanup_worktree_with_confirm_removes_path(repo: Path):
    info = wt.create_worktree(repo, job_id="job-10", worker_id="w1")
    assert wt.cleanup_worktree(
        repo,
        job_id="job-10",
        worker_id="w1",
        confirm=True,
    ) is True
    assert not info.path.exists()
    # Branch survives by default — we only remove it when delete_branch=True.
    out = _run(["git", "branch", "--list", info.branch], repo)
    assert info.branch in out


def test_cleanup_worktree_delete_branch_opt_in(repo: Path):
    info = wt.create_worktree(repo, job_id="job-11", worker_id="w1")
    wt.cleanup_worktree(
        repo,
        job_id="job-11",
        worker_id="w1",
        confirm=True,
        delete_branch=True,
    )
    out = _run(["git", "branch", "--list", info.branch], repo)
    assert out.strip() == ""


def test_run_git_blocks_destructive(repo: Path):
    with pytest.raises(wt.WorktreeError, match="not allowed"):
        wt._run_git(repo, "push")
    with pytest.raises(wt.WorktreeError, match="not allowed"):
        wt._run_git(repo, "reset", "--hard")
