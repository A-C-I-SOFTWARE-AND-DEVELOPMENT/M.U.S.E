"""Tests for :class:`AiderWorker`."""

from __future__ import annotations

import shutil
from pathlib import Path
from unittest.mock import patch

from hermes_cli.orchestrator.job_controller import JobController
from hermes_cli.workers.aider import AiderWorker


def test_detect_false_without_aider() -> None:
    with patch.object(shutil, "which", return_value=None):
        assert AiderWorker.detect() is False


def test_detect_true_with_aider() -> None:
    with patch.object(shutil, "which", return_value="/usr/local/bin/aider"):
        assert AiderWorker.detect() is True


def test_build_command_uses_message_file(tmp_path: Path) -> None:
    controller = JobController(tmp_path / "jobs")
    ctx = controller.create("Fix things")

    cmd = AiderWorker().build_command(ctx)
    assert cmd[0] == "aider"
    assert "--yes" in cmd
    assert "--no-stream" in cmd
    assert "--message-file" in cmd
    idx = cmd.index("--message-file")
    assert cmd[idx + 1].endswith("prompt.md")


def test_parse_log_counts_unique_edited_files() -> None:
    log = (
        "Applied edit to src/a.py\n"
        "Applied edit to src/a.py\n"  # duplicate — must dedupe
        "Applied edit to src/b.py\n"
    )
    meta = AiderWorker().parse_log(log)
    assert meta["files_changed"] == 2


def test_parse_log_no_edits_returns_empty() -> None:
    assert AiderWorker().parse_log("nothing happened") == {}


def test_run_with_fake_runner(tmp_path: Path) -> None:
    controller = JobController(tmp_path / "jobs")
    ctx = controller.create("Hi")

    def fake(cmd, cwd, env):
        if cmd[:2] == ["git", "diff"]:
            return 0, "--- a/x\n+++ b/x\n@@ -1 +1 @@\n-a\n+b\n"
        return 0, "Applied edit to x\n"

    result = AiderWorker().run(ctx, runner=fake)
    assert result.success is True
    assert result.files_changed == 1
