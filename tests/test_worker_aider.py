"""Tests for the Aider worker adapter (``hermes_cli/workers/aider.py``)."""

from __future__ import annotations

import json
import subprocess
from typing import Any
from unittest import mock

from hermes_cli.workers import WorkerStatus, WorkerTask
from hermes_cli.workers import aider as aider_worker


def _task(**overrides: Any) -> WorkerTask:
    defaults: dict[str, Any] = {
        "title": "Fix the broken auth test",
        "instructions": (
            "The login flow regression test fails after the recent "
            "session-cookie refactor. Track down the breakage and fix it."
        ),
        "files": ["tests/test_login.py", "app/auth.py"],
        "context": "Repro: `pytest tests/test_login.py::test_login_ok`.",
        "acceptance_criteria": [
            "Login test passes",
            "No new fixtures introduced",
        ],
    }
    defaults.update(overrides)
    return WorkerTask(**defaults)


class TestPromptRendering:
    def test_prompt_includes_all_sections(self):
        prompt = aider_worker.render_prompt(_task())
        assert "# Fix the broken auth test" in prompt
        assert "## Task" in prompt
        assert "## Files in scope" in prompt
        assert "tests/test_login.py" in prompt
        assert "## Acceptance criteria" in prompt
        assert "## Context" in prompt
        assert "Aider" in prompt
        assert "## Guardrails" in prompt
        # Destructive shortcuts MUST be explicitly forbidden.
        assert "git reset --hard" in prompt
        assert "auto-commit" in prompt.lower()

    def test_prompt_handles_empty_optional_fields(self):
        prompt = aider_worker.render_prompt(
            WorkerTask(title="t", instructions="i")
        )
        assert "# t" in prompt
        assert "## Files in scope" not in prompt
        assert "## Context" not in prompt
        assert "## Acceptance criteria" not in prompt

    def test_prompt_blank_title_does_not_crash(self):
        prompt = aider_worker.render_prompt(
            WorkerTask(title="   ", instructions="   ")
        )
        assert "Untitled task" in prompt
        assert "(no instructions provided)" in prompt


class TestHandoffPath:
    def test_default_run_is_handoff_required(self, tmp_path):
        with mock.patch.object(aider_worker, "detect_command", return_value=True):
            result = aider_worker.run(_task(), tmp_path / "ws")

        assert result.status is WorkerStatus.HANDOFF_REQUIRED
        assert result.worker == "aider"
        assert result.prompt_path.exists()
        assert result.status_path.exists()
        # No execution artifacts when we did not execute.
        assert result.output_path is None
        assert result.patch_path is None
        assert result.changed_files_path is None
        assert result.exit_code is None

    def test_handoff_command_references_prompt_file(self, tmp_path):
        with mock.patch.object(aider_worker, "detect_command", return_value=True):
            result = aider_worker.run(_task(), tmp_path / "ws")
        assert "--message-file" in result.handoff_command  # ty: ignore[unsupported-operator]  # mock/duck-typed test fixture
        assert "prompt.md" in result.handoff_command  # ty: ignore[unsupported-operator]  # mock/duck-typed test fixture
        # The safe flag set the orchestrator picks must be visible to the
        # user copying the command.
        assert "--no-auto-commits" in result.handoff_command  # ty: ignore[unsupported-operator]  # mock/duck-typed test fixture

    def test_status_json_is_machine_readable(self, tmp_path):
        with mock.patch.object(aider_worker, "detect_command", return_value=True):
            result = aider_worker.run(_task(), tmp_path / "ws")
        data = json.loads(result.status_path.read_text())
        assert data["worker"] == "aider"
        assert data["status"] == "handoff_required"
        assert data["command_available"] is True
        assert "timestamp" in data

    def test_handoff_works_when_binary_missing(self, tmp_path):
        with mock.patch.object(aider_worker, "detect_command", return_value=False):
            result = aider_worker.run(_task(), tmp_path / "ws")
        # The handoff path still produces a prompt and status — the
        # user can install Aider and run the printed command later.
        assert result.status is WorkerStatus.HANDOFF_REQUIRED
        assert result.command_available is False
        assert result.prompt_path.exists()


class TestExecutionPath:
    def test_missing_binary_yields_command_not_found(self, tmp_path):
        with mock.patch.object(aider_worker, "detect_command", return_value=False):
            result = aider_worker.run(
                _task(), tmp_path / "ws", execute=True
            )
        assert result.status is WorkerStatus.COMMAND_NOT_FOUND
        assert result.command_available is False
        assert result.exit_code is None
        assert result.error and "not found" in result.error
        # Even on failure, status.json is written for the dashboard.
        assert result.status_path.exists()

    def test_successful_execution_captures_output_and_artifacts(self, tmp_path):
        repo = tmp_path / "repo"
        (repo / ".git").mkdir(parents=True)
        ws = tmp_path / "ws"

        completed = subprocess.CompletedProcess(
            args=["aider"], returncode=0,
            stdout="aider says: done\n", stderr="",
        )
        with mock.patch.object(aider_worker, "detect_command", return_value=True), \
             mock.patch.object(subprocess, "run", return_value=completed) as run_mock, \
             mock.patch(
                 "hermes_cli.workers.aider.collect_git_artifacts",
                 return_value=(ws / "patch.diff", ws / "changed-files.txt"),
             ):
            (ws).mkdir(parents=True, exist_ok=True)
            (ws / "patch.diff").write_text("diff --git a/x b/x\n")
            (ws / "changed-files.txt").write_text("app/auth.py\n")
            result = aider_worker.run(
                _task(), ws, execute=True, repo_root=repo
            )

        assert result.status is WorkerStatus.EXECUTED
        assert result.exit_code == 0
        assert result.output_path and result.output_path.exists()
        assert "aider says: done" in result.output_path.read_text()
        assert result.patch_path and result.patch_path.exists()
        assert result.changed_files_path and result.changed_files_path.exists()
        # Verify we did NOT pass any destructive shortcut.
        argv = run_mock.call_args.args[0]
        assert "--yes-always" not in argv
        assert "--auto-commits" not in argv
        assert "--no-auto-commits" in argv

    def test_timeout_marks_failure(self, tmp_path):
        with mock.patch.object(aider_worker, "detect_command", return_value=True), \
             mock.patch.object(
                 subprocess, "run",
                 side_effect=subprocess.TimeoutExpired(cmd="aider", timeout=1),
             ), \
             mock.patch(
                 "hermes_cli.workers.aider.collect_git_artifacts",
                 return_value=(None, None),
             ):
            result = aider_worker.run(
                _task(), tmp_path / "ws",
                execute=True,
                config=aider_worker.AiderConfig(timeout_seconds=1),
            )
        assert result.status is WorkerStatus.FAILED
        assert result.error and "timed out" in result.error

    def test_launch_oserror_marks_failure(self, tmp_path):
        with mock.patch.object(aider_worker, "detect_command", return_value=True), \
             mock.patch.object(subprocess, "run", side_effect=OSError("no exec")), \
             mock.patch(
                 "hermes_cli.workers.aider.collect_git_artifacts",
                 return_value=(None, None),
             ):
            result = aider_worker.run(
                _task(), tmp_path / "ws", execute=True,
            )
        assert result.status is WorkerStatus.FAILED
        assert result.error and "failed to launch" in result.error


class TestCommandConstruction:
    def test_safe_flags_in_handoff(self, tmp_path):
        cmd = aider_worker.build_handoff_command(
            aider_worker.AiderConfig(model="sonnet"),
            tmp_path,
            _task(),
        )
        assert cmd.startswith("aider ")
        assert "--no-auto-commits" in cmd
        assert "--model sonnet" in cmd
        # Never auto-yes.
        assert "--yes-always" not in cmd

    def test_extra_args_propagate(self, tmp_path):
        cfg = aider_worker.AiderConfig(extra_args=("--read", "AGENTS.md"))
        cmd = aider_worker.build_handoff_command(cfg, tmp_path, _task())
        assert "--read AGENTS.md" in cmd


def test_module_is_importable():
    import hermes_cli.workers.aider as _  # noqa: F401
