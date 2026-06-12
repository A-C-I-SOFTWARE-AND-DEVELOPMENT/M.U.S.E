"""Tests for the Goose worker adapter (``hermes_cli/workers/goose.py``)."""

from __future__ import annotations

import json
import subprocess
from typing import Any
from unittest import mock

from hermes_cli.workers import WorkerStatus, WorkerTask
from hermes_cli.workers import goose as goose_worker


def _task(**overrides: Any) -> WorkerTask:
    defaults: dict[str, Any] = {
        "title": "Summarize today's logs",
        "instructions": (
            "Use the file extension to read ``./logs/today.txt`` and"
            " produce a 5-bullet executive summary in ``summary.md``."
        ),
        "files": ["logs/today.txt"],
        "context": "Goose can use the developer / files extensions only.",
        "acceptance_criteria": [
            "summary.md exists",
            "Five bullets, no more",
        ],
    }
    defaults.update(overrides)
    return WorkerTask(**defaults)


class TestPromptRendering:
    def test_prompt_includes_all_sections(self):
        prompt = goose_worker.render_prompt(_task())
        assert "# Summarize today's logs" in prompt
        assert "## Task" in prompt
        assert "## Files in scope" in prompt
        assert "logs/today.txt" in prompt
        assert "## Acceptance criteria" in prompt
        assert "## Context" in prompt
        assert "Goose" in prompt
        assert "## Guardrails" in prompt
        # Destructive shortcuts MUST be explicitly forbidden.
        assert "git push --force" in prompt
        assert "auto-approve" in prompt.lower()

    def test_prompt_handles_empty_optional_fields(self):
        prompt = goose_worker.render_prompt(
            WorkerTask(title="t", instructions="i")
        )
        assert "# t" in prompt
        assert "## Files in scope" not in prompt
        assert "## Context" not in prompt
        assert "## Acceptance criteria" not in prompt

    def test_prompt_blank_title_does_not_crash(self):
        prompt = goose_worker.render_prompt(
            WorkerTask(title="   ", instructions="   ")
        )
        assert "Untitled task" in prompt
        assert "(no instructions provided)" in prompt


class TestHandoffPath:
    def test_default_run_is_handoff_required(self, tmp_path):
        with mock.patch.object(goose_worker, "detect_command", return_value=True):
            result = goose_worker.run(_task(), tmp_path / "ws")

        assert result.status is WorkerStatus.HANDOFF_REQUIRED
        assert result.worker == "goose"
        assert result.prompt_path.exists()
        assert result.status_path.exists()
        assert result.output_path is None
        assert result.patch_path is None
        assert result.changed_files_path is None
        assert result.exit_code is None

    def test_handoff_command_references_instructions(self, tmp_path):
        with mock.patch.object(goose_worker, "detect_command", return_value=True):
            result = goose_worker.run(_task(), tmp_path / "ws")
        assert "goose run" in result.handoff_command  # ty: ignore[unsupported-operator]  # mock/duck-typed test fixture
        assert "--instructions" in result.handoff_command  # ty: ignore[unsupported-operator]  # mock/duck-typed test fixture
        assert "prompt.md" in result.handoff_command  # ty: ignore[unsupported-operator]  # mock/duck-typed test fixture

    def test_status_json_is_machine_readable(self, tmp_path):
        with mock.patch.object(goose_worker, "detect_command", return_value=True):
            result = goose_worker.run(_task(), tmp_path / "ws")
        data = json.loads(result.status_path.read_text())
        assert data["worker"] == "goose"
        assert data["status"] == "handoff_required"
        assert data["command_available"] is True
        assert "timestamp" in data

    def test_handoff_works_when_binary_missing(self, tmp_path):
        with mock.patch.object(goose_worker, "detect_command", return_value=False):
            result = goose_worker.run(_task(), tmp_path / "ws")
        assert result.status is WorkerStatus.HANDOFF_REQUIRED
        assert result.command_available is False
        assert result.prompt_path.exists()

    def test_recipe_and_extensions_appear_in_handoff(self, tmp_path):
        cfg = goose_worker.GooseConfig(
            recipe="recipes/summarize.yaml",
            extensions=("developer", "files"),
        )
        with mock.patch.object(goose_worker, "detect_command", return_value=True):
            result = goose_worker.run(_task(), tmp_path / "ws", config=cfg)
        assert "--recipe recipes/summarize.yaml" in result.handoff_command  # ty: ignore[unsupported-operator]  # mock/duck-typed test fixture
        assert "--with-extension developer" in result.handoff_command  # ty: ignore[unsupported-operator]  # mock/duck-typed test fixture
        assert "--with-extension files" in result.handoff_command  # ty: ignore[unsupported-operator]  # mock/duck-typed test fixture


class TestExecutionPath:
    def test_missing_binary_yields_command_not_found(self, tmp_path):
        with mock.patch.object(goose_worker, "detect_command", return_value=False):
            result = goose_worker.run(
                _task(), tmp_path / "ws", execute=True
            )
        assert result.status is WorkerStatus.COMMAND_NOT_FOUND
        assert result.command_available is False
        assert result.exit_code is None
        assert result.error and "not found" in result.error
        assert result.status_path.exists()

    def test_successful_execution_captures_output_and_artifacts(self, tmp_path):
        repo = tmp_path / "repo"
        (repo / ".git").mkdir(parents=True)
        ws = tmp_path / "ws"

        completed = subprocess.CompletedProcess(
            args=["goose"], returncode=0,
            stdout="goose: ok\n", stderr="",
        )
        with mock.patch.object(goose_worker, "detect_command", return_value=True), \
             mock.patch.object(subprocess, "run", return_value=completed) as run_mock, \
             mock.patch(
                 "hermes_cli.workers.goose.collect_git_artifacts",
                 return_value=(ws / "patch.diff", ws / "changed-files.txt"),
             ):
            ws.mkdir(parents=True, exist_ok=True)
            (ws / "patch.diff").write_text("diff --git a/x b/x\n")
            (ws / "changed-files.txt").write_text("logs/today.txt\n")
            result = goose_worker.run(
                _task(), ws, execute=True, repo_root=repo
            )

        assert result.status is WorkerStatus.EXECUTED
        assert result.exit_code == 0
        assert result.output_path and result.output_path.exists()
        assert "goose: ok" in result.output_path.read_text()
        assert result.patch_path and result.patch_path.exists()
        # Verify we did NOT pass any auto-approval shortcut.
        argv = run_mock.call_args.args[0]
        assert argv[0:2] == ["goose", "run"]
        assert "--yes" not in argv
        assert "--auto-approve" not in argv

    def test_extensions_propagate_to_subprocess(self, tmp_path):
        completed = subprocess.CompletedProcess(
            args=["goose"], returncode=0, stdout="", stderr="",
        )
        cfg = goose_worker.GooseConfig(extensions=("developer",))
        with mock.patch.object(goose_worker, "detect_command", return_value=True), \
             mock.patch.object(subprocess, "run", return_value=completed) as run_mock, \
             mock.patch(
                 "hermes_cli.workers.goose.collect_git_artifacts",
                 return_value=(None, None),
             ):
            goose_worker.run(_task(), tmp_path / "ws", execute=True, config=cfg)
        argv = run_mock.call_args.args[0]
        assert "--with-extension" in argv
        assert "developer" in argv

    def test_timeout_marks_failure(self, tmp_path):
        with mock.patch.object(goose_worker, "detect_command", return_value=True), \
             mock.patch.object(
                 subprocess, "run",
                 side_effect=subprocess.TimeoutExpired(cmd="goose", timeout=1),
             ), \
             mock.patch(
                 "hermes_cli.workers.goose.collect_git_artifacts",
                 return_value=(None, None),
             ):
            result = goose_worker.run(
                _task(), tmp_path / "ws",
                execute=True,
                config=goose_worker.GooseConfig(timeout_seconds=1),
            )
        assert result.status is WorkerStatus.FAILED
        assert result.error and "timed out" in result.error

    def test_launch_oserror_marks_failure(self, tmp_path):
        with mock.patch.object(goose_worker, "detect_command", return_value=True), \
             mock.patch.object(subprocess, "run", side_effect=OSError("no exec")), \
             mock.patch(
                 "hermes_cli.workers.goose.collect_git_artifacts",
                 return_value=(None, None),
             ):
            result = goose_worker.run(
                _task(), tmp_path / "ws", execute=True,
            )
        assert result.status is WorkerStatus.FAILED
        assert result.error and "failed to launch" in result.error


def test_module_is_importable():
    import hermes_cli.workers.goose as _  # noqa: F401
