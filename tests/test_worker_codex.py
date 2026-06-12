"""Tests for the Codex worker adapter (muse_cli/workers/codex.py).

The adapter must:

1. Detect cleanly when `codex` is absent — no exception, just
   `available=False`.
2. Materialize a structured prompt + status.json on disk for every run.
3. Default to handoff mode unless the operator explicitly opts into
   execution AND the CLI is detected.
4. Downgrade to handoff (with an error recorded) when execution was
   requested but the binary is missing.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from muse_cli.workers import codex as codex_worker
from muse_cli.workers.codex import (
    MODE_EXECUTED,
    MODE_HANDOFF,
    CodexTask,
    build_prompt,
    collect_artifacts,
    detect_codex,
    run_worker,
    write_prompt_and_status,
)


@pytest.fixture
def sample_task() -> CodexTask:
    return CodexTask(
        mission="Add a Codex worker adapter.",
        task="Implement muse_cli/workers/codex.py with handoff support.",
        repo_evidence="Phase 09 plan in the orchestrator brief.",
        files_to_inspect=["muse_cli/workers/codex.py"],
        files_likely_to_edit=["muse_cli/workers/codex.py"],
        acceptance_criteria=[
            "Default mode is handoff-required.",
            "Execution requires explicit opt-in.",
        ],
        validation_commands=[
            "python -m py_compile muse_cli/workers/codex.py",
            "python -m pytest tests/test_worker_codex.py -q",
        ],
        do_not_change=["Hermes core orchestrator APIs."],
        task_id="phase-09",
    )


# ── detection ──────────────────────────────────────────────────────────────


def test_detect_codex_returns_unavailable_when_command_absent():
    with patch("muse_cli.workers.codex.shutil.which", return_value=None):
        detection = detect_codex()
    assert detection.available is False
    assert detection.path is None
    assert detection.version is None
    assert detection.error and "not found" in detection.error


def test_detect_codex_does_not_raise_on_version_probe_failure(tmp_path):
    fake_codex = tmp_path / "codex"
    fake_codex.write_text("#!/bin/sh\nexit 0\n")
    fake_codex.chmod(0o755)

    def boom(*args, **kwargs):
        raise OSError("simulated failure")

    with patch("muse_cli.workers.codex.shutil.which", return_value=str(fake_codex)):
        with patch("muse_cli.workers.codex.subprocess.run", side_effect=boom):
            detection = detect_codex()

    assert detection.available is True
    assert detection.path == str(fake_codex)
    assert detection.version is None
    assert detection.error and "version probe failed" in detection.error


def test_detect_codex_captures_version_string(tmp_path):
    fake_codex = tmp_path / "codex"
    fake_codex.write_text("#!/bin/sh\necho 'codex 1.2.3'\n")
    fake_codex.chmod(0o755)

    class _Proc:
        returncode = 0
        stdout = "codex 1.2.3\n"
        stderr = ""

    with patch("muse_cli.workers.codex.shutil.which", return_value=str(fake_codex)):
        with patch("muse_cli.workers.codex.subprocess.run", return_value=_Proc()):
            detection = detect_codex()

    assert detection.available is True
    assert detection.version == "codex 1.2.3"
    assert detection.error is None


# ── prompt construction ───────────────────────────────────────────────────


def test_build_prompt_contains_all_required_sections(sample_task):
    prompt = build_prompt(sample_task)
    for heading in (
        "## Mission",
        "## Repository evidence",
        "## Files to inspect",
        "## Files likely to edit",
        "## Exact implementation task",
        "## Acceptance criteria",
        "## Validation commands",
        "## What NOT to change",
        "## Output contract",
    ):
        assert heading in prompt, f"missing section: {heading}"

    for artifact in ("output.md", "patch.diff", "changed-files.txt", "status.json"):
        assert artifact in prompt


def test_build_prompt_handles_empty_lists():
    task = CodexTask(mission="m", task="t")
    prompt = build_prompt(task)
    # Empty bullet sections fall back to "(none provided)" rather than blank.
    assert "_(none provided)_" in prompt


# ── prompt + status materialization ───────────────────────────────────────


def test_write_prompt_and_status_creates_files(tmp_path, sample_task):
    with patch(
        "muse_cli.workers.codex.detect_codex",
        return_value=codex_worker.CodexDetection(available=False, error="missing"),
    ):
        prompt_path, status_path = write_prompt_and_status(sample_task, tmp_path)

    assert prompt_path.is_file()
    assert status_path.is_file()
    assert prompt_path.parent == (tmp_path / "workers" / "codex").resolve()

    prompt_text = prompt_path.read_text(encoding="utf-8")
    assert "## Mission" in prompt_text
    assert sample_task.task in prompt_text

    status = json.loads(status_path.read_text(encoding="utf-8"))
    assert status["worker"] == "codex"
    assert status["mode"] == MODE_HANDOFF
    assert status["status"] == "pending"
    assert status["detection"]["available"] is False
    assert status["task_id"] == "phase-09"


# ── handoff / execution control ───────────────────────────────────────────


def test_run_worker_defaults_to_handoff_when_codex_missing(tmp_path, sample_task):
    with patch(
        "muse_cli.workers.codex.detect_codex",
        return_value=codex_worker.CodexDetection(available=False, error="missing"),
    ):
        result = run_worker(sample_task, tmp_path)

    assert result.mode == MODE_HANDOFF
    assert result.detection.available is False
    assert result.prompt_path.is_file()
    assert result.status_path.is_file()

    status = json.loads(result.status_path.read_text(encoding="utf-8"))
    assert status["mode"] == MODE_HANDOFF
    assert status["status"] == "pending"

    artifacts = collect_artifacts(result.workdir)
    # Only the status file exists at this point — output.md, patch.diff,
    # changed-files.txt, test-output.txt are produced by the worker.
    assert "status.json" in artifacts
    assert "output.md" not in artifacts


def test_run_worker_handoff_when_execute_requested_but_codex_missing(
    tmp_path, sample_task
):
    with patch(
        "muse_cli.workers.codex.detect_codex",
        return_value=codex_worker.CodexDetection(available=False, error="missing"),
    ):
        result = run_worker(sample_task, tmp_path, execute=True)

    assert result.mode == MODE_HANDOFF
    assert result.error and "not found" in result.error

    status = json.loads(result.status_path.read_text(encoding="utf-8"))
    assert status["mode"] == MODE_HANDOFF
    assert status["error"] and "not found" in status["error"]


def test_run_worker_does_not_execute_without_opt_in(tmp_path, sample_task):
    detection = codex_worker.CodexDetection(
        available=True, path="/usr/local/bin/codex", version="codex 1.2.3"
    )
    with patch("muse_cli.workers.codex.detect_codex", return_value=detection):
        with patch("muse_cli.workers.codex.subprocess.run") as run_mock:
            result = run_worker(sample_task, tmp_path, execute=False)

    # Even though codex is available, we never shell out without opt-in.
    run_mock.assert_not_called()
    assert result.mode == MODE_HANDOFF
    status = json.loads(result.status_path.read_text(encoding="utf-8"))
    assert status["mode"] == MODE_HANDOFF


def test_run_worker_env_var_enables_execution(tmp_path, sample_task, monkeypatch):
    detection = codex_worker.CodexDetection(
        available=True, path="/usr/local/bin/codex", version="codex 1.2.3"
    )

    class _Proc:
        returncode = 0
        stdout = "ok\n"
        stderr = ""

    monkeypatch.setenv(codex_worker.EXECUTE_ENV_VAR, "1")
    with patch("muse_cli.workers.codex.detect_codex", return_value=detection):
        with patch(
            "muse_cli.workers.codex.subprocess.run", return_value=_Proc()
        ) as run_mock:
            result = run_worker(sample_task, tmp_path)

    run_mock.assert_called_once()
    args, kwargs = run_mock.call_args
    assert args[0][0] == "/usr/local/bin/codex"
    assert kwargs.get("cwd") == str(tmp_path)

    assert result.mode == MODE_EXECUTED
    assert result.returncode == 0
    status = json.loads(result.status_path.read_text(encoding="utf-8"))
    assert status["status"] == "success"
    assert status["mode"] == MODE_EXECUTED
