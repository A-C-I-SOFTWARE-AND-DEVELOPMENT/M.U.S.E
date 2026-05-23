"""Tests for :class:`ClaudeCodeWorker`. Never invokes a real Claude session."""

from __future__ import annotations

import shutil
from pathlib import Path
from unittest.mock import patch

from hermes_cli.orchestrator.job_controller import JobController
from hermes_cli.workers.claude_code import ClaudeCodeWorker


def test_detect_false_when_claude_missing() -> None:
    with patch.object(shutil, "which", return_value=None):
        assert ClaudeCodeWorker.detect() is False


def test_detect_true_when_claude_on_path() -> None:
    with patch.object(shutil, "which", return_value="/opt/claude/bin/claude"):
        assert ClaudeCodeWorker.detect() is True


def test_build_command_shape(tmp_path: Path) -> None:
    controller = JobController(tmp_path / "jobs")
    ctx = controller.create("Add docs")

    cmd = ClaudeCodeWorker().build_command(ctx)
    assert cmd[0] == "claude"
    assert "--print" in cmd
    assert "--cwd" in cmd
    idx = cmd.index("--cwd")
    assert Path(cmd[idx + 1]) == ctx.repo_dir
    assert "--file" in cmd


def test_parse_log_modified_count() -> None:
    meta = ClaudeCodeWorker().parse_log("Doing work...\nModified 7 files\n")
    assert meta["files_changed"] == 7
    assert meta["message"] == "claude run"


def test_parse_log_no_changes_sentinel() -> None:
    meta = ClaudeCodeWorker().parse_log("Nothing to do.\nNo changes\n")
    assert meta["files_changed"] == 0
    assert meta["message"] == "no changes"


def test_parse_log_no_match() -> None:
    assert ClaudeCodeWorker().parse_log("Some other output") == {}


def test_run_no_real_subprocess(tmp_path: Path) -> None:
    controller = JobController(tmp_path / "jobs")
    ctx = controller.create("Hi")

    def fake(cmd, cwd, env):
        if cmd[:2] == ["git", "diff"]:
            return 0, "--- a/x\n+++ b/x\n@@ -1 +1 @@\n-1\n+2\n"
        return 0, "Modified 1 files\n"

    result = ClaudeCodeWorker().run(ctx, runner=fake)
    assert result.success is True
    assert result.files_changed == 1
    assert result.diff.startswith("--- a/x")
