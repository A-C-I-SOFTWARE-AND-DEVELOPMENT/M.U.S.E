"""Tests for :class:`GooseWorker`."""

from __future__ import annotations

import shutil
from pathlib import Path
from unittest.mock import patch

from hermes_cli.orchestrator.job_controller import JobController
from hermes_cli.workers.goose import GooseWorker


def test_detect_false_without_goose() -> None:
    with patch.object(shutil, "which", return_value=None):
        assert GooseWorker.detect() is False


def test_detect_true_with_goose() -> None:
    with patch.object(shutil, "which", return_value="/usr/local/bin/goose"):
        assert GooseWorker.detect() is True


def test_build_command_uses_instructions(tmp_path: Path) -> None:
    controller = JobController(tmp_path / "jobs")
    ctx = controller.create("Goose, do the thing")

    cmd = GooseWorker().build_command(ctx)
    assert cmd[0] == "goose"
    assert "run" in cmd
    assert "--instructions" in cmd
    assert "--quiet" in cmd
    idx = cmd.index("--instructions")
    assert cmd[idx + 1].endswith("prompt.md")


def test_parse_log_extracts_files_modified() -> None:
    meta = GooseWorker().parse_log("doing things\nfiles modified: 5\ndone\n")
    assert meta["files_changed"] == 5


def test_parse_log_unrecognized() -> None:
    assert GooseWorker().parse_log("nothing useful") == {}


def test_run_with_fake_runner(tmp_path: Path) -> None:
    controller = JobController(tmp_path / "jobs")
    ctx = controller.create("Hi")

    def fake(cmd, cwd, env):
        if cmd[:2] == ["git", "diff"]:
            return 0, ""
        return 0, "files modified: 2\n"

    result = GooseWorker().run(ctx, runner=fake)
    assert result.success is True
    assert result.files_changed == 2
