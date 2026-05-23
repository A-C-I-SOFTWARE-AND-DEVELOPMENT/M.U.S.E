"""Tests for :class:`HermesLocalWorker`."""

from __future__ import annotations

from pathlib import Path

from hermes_cli.orchestrator.job_controller import JobController
from hermes_cli.workers.hermes_local import HermesLocalWorker


def test_hermes_local_is_always_detected() -> None:
    """The local worker is bundled — detect() must not depend on PATH."""
    assert HermesLocalWorker.detect() is True
    assert HermesLocalWorker.bundled is True


def test_build_command_references_prompt_and_workdir(tmp_path: Path) -> None:
    controller = JobController(tmp_path / "jobs")
    ctx = controller.create("Fix readme typo")

    cmd = HermesLocalWorker().build_command(ctx)
    assert cmd[0] == "hermes"
    assert "oneshot" in cmd
    assert "--prompt-file" in cmd
    # Prompt path is the one we just wrote
    idx = cmd.index("--prompt-file")
    assert Path(cmd[idx + 1]).name == "prompt.md"
    # Workdir is the job's repo_dir
    idx = cmd.index("--workdir")
    assert Path(cmd[idx + 1]) == ctx.repo_dir


def test_parse_log_extracts_done_sentinel() -> None:
    log = (
        "running...\n"
        "HERMES_DONE: applied 3 patches\n"
        "trailing noise\n"
    )
    meta = HermesLocalWorker().parse_log(log)
    assert meta["message"] == "applied 3 patches"


def test_parse_log_handles_log_without_sentinel() -> None:
    assert HermesLocalWorker().parse_log("nothing special") == {}


def test_run_with_fake_runner_records_diff(tmp_path: Path) -> None:
    controller = JobController(tmp_path / "jobs")
    ctx = controller.create("Fix readme typo")

    def fake(cmd, cwd, env):
        if cmd[:2] == ["git", "diff"]:
            return 0, "--- a/README.md\n+++ b/README.md\n@@ -1 +1 @@\n-old\n+new\n"
        return 0, "HERMES_DONE: nice\n"

    result = HermesLocalWorker().run(ctx, runner=fake)
    assert result.success is True
    assert "README.md" in result.diff
    assert result.message == "nice"
