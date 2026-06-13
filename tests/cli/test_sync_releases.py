"""Tests for ``muse sync`` (hermes_cli/sync_releases.py).

Verifies that:
- ``--dry-run`` resolves the repo and prints the expected ``gh workflow run``
  command without dispatching anything.
- A non-GitHub remote is rejected cleanly (no dispatch).
- The ``gh``-missing fallback prints the manual command and returns non-zero.
- A real (non-dry-run) call dispatches via ``gh workflow run`` with the right
  arguments.
"""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from hermes_cli import sync_releases
from hermes_cli.github_publisher import PublisherError, RepoInfo


def _repo(owner="A-C-I-SOFTWARE-AND-DEVELOPMENT", repo="M.U.S.E"):
    return RepoInfo(
        root=Path("/tmp/repo"),
        owner=owner,
        repo=repo,
        remote_url=f"https://github.com/{owner}/{repo}.git",
    )


def test_dispatch_command_shape():
    cmd = sync_releases._dispatch_command("owner/repo", "all")
    assert cmd[:3] == ["gh", "workflow", "run"]
    assert sync_releases.WORKFLOW_FILE in cmd
    assert "--ref" in cmd and "main" in cmd
    assert "targets=all" in cmd


def test_dry_run_prints_command_without_dispatch(capsys):
    args = SimpleNamespace(targets="all", dry_run=True)
    with patch.object(sync_releases, "get_repo_info", return_value=_repo()), \
         patch("subprocess.run") as run:
        rc = sync_releases.cmd_sync(args)
    assert rc == 0
    run.assert_not_called()
    out = capsys.readouterr().out
    assert "dry-run" in out
    assert sync_releases.WORKFLOW_FILE in out
    assert "A-C-I-SOFTWARE-AND-DEVELOPMENT/M.U.S.E" in out


def test_rejects_unknown_targets(capsys):
    args = SimpleNamespace(targets="nonsense", dry_run=True)
    rc = sync_releases.cmd_sync(args)
    assert rc == 2
    assert "Unknown --targets" in capsys.readouterr().out


def test_rejects_non_github_remote(capsys):
    args = SimpleNamespace(targets="all", dry_run=False)
    non_gh = RepoInfo(root=Path("/tmp/repo"), owner=None, repo=None, remote_url="ssh://x/y")
    with patch.object(sync_releases, "get_repo_info", return_value=non_gh):
        rc = sync_releases.cmd_sync(args)
    assert rc == 1
    assert "not a GitHub remote" in capsys.readouterr().out


def test_repo_resolution_failure(capsys):
    args = SimpleNamespace(targets="all", dry_run=False)
    with patch.object(
        sync_releases, "get_repo_info", side_effect=PublisherError("not a git repository")
    ):
        rc = sync_releases.cmd_sync(args)
    assert rc == 1
    assert "Cannot resolve git repository" in capsys.readouterr().out


def test_gh_missing_fallback(capsys):
    args = SimpleNamespace(targets="android", dry_run=False)
    with patch.object(sync_releases, "get_repo_info", return_value=_repo()), \
         patch("shutil.which", return_value=None), \
         patch("subprocess.run") as run:
        rc = sync_releases.cmd_sync(args)
    assert rc == 1
    run.assert_not_called()
    out = capsys.readouterr().out
    assert "gh` CLI not found" in out
    assert "targets=android" in out


def test_real_dispatch_invokes_gh(capsys):
    args = SimpleNamespace(targets="all", dry_run=False)
    with patch.object(sync_releases, "get_repo_info", return_value=_repo()), \
         patch("shutil.which", return_value="/usr/bin/gh"), \
         patch("subprocess.run") as run:
        rc = sync_releases.cmd_sync(args)
    assert rc == 0
    run.assert_called_once()
    dispatched = run.call_args.args[0]
    assert dispatched[:3] == ["gh", "workflow", "run"]
    assert "targets=all" in dispatched
