"""Tests for :class:`CodexWorker`. Never invokes a real Codex subscription."""

from __future__ import annotations

import shutil
from pathlib import Path
from unittest.mock import patch

from hermes_cli.orchestrator.job_controller import JobController
from hermes_cli.workers.codex import CodexWorker


def test_detect_false_when_codex_not_on_path() -> None:
    with patch.object(shutil, "which", return_value=None):
        assert CodexWorker.detect() is False


def test_detect_true_when_codex_on_path() -> None:
    with patch.object(shutil, "which", return_value="/usr/local/bin/codex"):
        assert CodexWorker.detect() is True


def test_build_command_shape(tmp_path: Path) -> None:
    controller = JobController(tmp_path / "jobs")
    ctx = controller.create("Refactor function X")

    cmd = CodexWorker().build_command(ctx)
    assert cmd[0] == "codex"
    assert "exec" in cmd
    assert "--cd" in cmd
    assert str(ctx.repo_dir) in cmd
    assert "--file" in cmd
    idx = cmd.index("--file")
    assert cmd[idx + 1].endswith("prompt.md")


def test_parse_log_counts_patches() -> None:
    log = "codex: thinking...\ncodex: applied 4 patches\n"
    meta = CodexWorker().parse_log(log)
    assert meta["files_changed"] == 4
    assert "codex" in meta["message"]


def test_parse_log_single_patch() -> None:
    log = "codex: applied 1 patch\n"
    meta = CodexWorker().parse_log(log)
    assert meta["files_changed"] == 1


def test_parse_log_no_match_returns_empty() -> None:
    assert CodexWorker().parse_log("nothing useful") == {}


def test_run_uses_fake_runner_only(tmp_path: Path) -> None:
    """No subprocess.run, no `codex` lookup, no network."""
    controller = JobController(tmp_path / "jobs")
    ctx = controller.create("Hello")

    captured: list[list[str]] = []

    def fake(cmd, cwd, env):
        captured.append(cmd)
        if cmd[:2] == ["git", "diff"]:
            return 0, ""
        return 0, "codex: applied 2 patches\n"

    result = CodexWorker().run(ctx, runner=fake)
    assert result.success is True
    assert captured[0][0] == "codex"
    # parse_log saw the 2-patches sentinel
    assert result.files_changed == 2
