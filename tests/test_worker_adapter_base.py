"""Tests for the shared :class:`WorkerAdapter` contract.

Every concrete worker inherits this contract. We assert it here with a
synthetic adapter so the test never depends on a real binary being
installed.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from hermes_cli.orchestrator.job_controller import JobController
from hermes_cli.workers.base import (
    JobContext,
    WorkerAdapter,
    WorkerResult,
    WorkerStatus,
    _files_changed_in_diff,
)


class _SyntheticWorker(WorkerAdapter):
    name = "synthetic"
    binary = "true"
    description = "test-only adapter"

    def __init__(self, cmd: list[str] | None = None) -> None:
        self._cmd = cmd or ["true"]

    def build_command(self, job: JobContext) -> list[str]:
        return list(self._cmd)


class _BundledStub(WorkerAdapter):
    name = "bundled_stub"
    binary = ""
    bundled = True

    def build_command(self, job: JobContext) -> list[str]:
        return ["echo", "hi"]


@pytest.fixture
def job_ctx(tmp_path: Path) -> JobContext:
    controller = JobController(tmp_path / "jobs")
    return controller.create("test prompt", title="t")


# ── detect contract ───────────────────────────────────────────────────


def test_detect_false_when_binary_missing() -> None:
    class Missing(WorkerAdapter):
        name = "missing"
        binary = "definitely-not-on-path-9b3c1f"

        def build_command(self, job: JobContext) -> list[str]:
            return []

    assert Missing.detect() is False


def test_detect_true_when_bundled() -> None:
    assert _BundledStub.detect() is True


def test_detect_true_when_binary_present() -> None:
    # Use a binary every POSIX/Linux test runner has.
    class Real(WorkerAdapter):
        name = "real"
        binary = "sh"

        def build_command(self, job: JobContext) -> list[str]:
            return [self.binary]

    assert Real.detect() is True


# ── run() injects runner & captures diff ──────────────────────────────


def test_run_uses_injected_runner_and_records_metadata(
    job_ctx: JobContext,
) -> None:
    calls: list[tuple[list[str], Path]] = []

    def fake_runner(cmd, cwd, env):
        calls.append((cmd, cwd))
        if cmd[:2] == ["git", "diff"]:
            return 0, "--- a/x\n+++ b/x\n@@ -1,1 +1,1 @@\n-old\n+new\n"
        return 0, "synthetic ran OK\n"

    adapter = _SyntheticWorker(["mytool", "--go"])
    result = adapter.run(job_ctx, runner=fake_runner)

    assert result.worker == "synthetic"
    assert result.success is True
    assert result.exit_code == 0
    assert "synthetic ran OK" in result.log
    assert result.diff.startswith("--- a/x")
    assert result.files_changed == 1
    # Both the worker command and the git diff capture must be called.
    cmds = [c[0] for c in calls]
    assert ["mytool", "--go"] in cmds
    assert any(c[:2] == ["git", "diff"] for c in cmds)


def test_run_dry_run_does_not_invoke_runner(job_ctx: JobContext) -> None:
    def boom(*a, **kw):
        raise AssertionError("runner must not be called in dry-run")

    adapter = _SyntheticWorker(["mytool"])
    result = adapter.run(job_ctx, runner=boom, dry_run=True)
    assert result.success is True
    assert "DRY-RUN" in result.log
    assert "mytool" in result.log
    assert result.files_changed == 0


def test_run_propagates_nonzero_exit(job_ctx: JobContext) -> None:
    def fake_runner(cmd, cwd, env):
        if cmd[:2] == ["git", "diff"]:
            return 0, ""
        return 5, "synthetic failed\n"

    adapter = _SyntheticWorker()
    result = adapter.run(job_ctx, runner=fake_runner)
    assert result.success is False
    assert result.exit_code == 5


def test_files_changed_helper_counts_added_paths() -> None:
    diff = (
        "--- a/x\n+++ b/x\n@@ -1,1 +1,1 @@\n-old\n+new\n"
        "--- a/y\n+++ b/y\n@@ -1,1 +1,1 @@\n-q\n+w\n"
        "--- /dev/null\n+++ b/z\n@@ -0,0 +1,1 @@\n+brand new\n"
    )
    # Empty diff
    assert _files_changed_in_diff("") == 0
    # Three files
    assert _files_changed_in_diff(diff) == 3


# ── write_outputs honors the contract ────────────────────────────────


def test_write_outputs_writes_all_four_files(
    job_ctx: JobContext, tmp_path: Path
) -> None:
    adapter = _SyntheticWorker()
    result = WorkerResult(
        worker="synthetic",
        success=True,
        exit_code=0,
        diff="some diff",
        log="some log",
        files_changed=2,
        message="ok",
        started_at="2026-01-01T00:00:00Z",
        finished_at="2026-01-01T00:00:01Z",
    )
    wdir = adapter.write_outputs(job_ctx, result)
    assert (wdir / "status.json").exists()
    assert (wdir / "result.json").exists()
    assert (wdir / "output.diff").read_text() == "some diff"
    assert (wdir / "log.txt").read_text() == "some log"
    status = json.loads((wdir / "status.json").read_text())
    assert status["status"] == WorkerStatus.DONE
    assert status["exit_code"] == 0
    res = json.loads((wdir / "result.json").read_text())
    assert res["files_changed"] == 2


def test_write_outputs_records_failure_status(job_ctx: JobContext) -> None:
    adapter = _SyntheticWorker()
    failure = WorkerResult(worker="synthetic", success=False, exit_code=3)
    wdir = adapter.write_outputs(job_ctx, failure)
    status = json.loads((wdir / "status.json").read_text())
    assert status["status"] == WorkerStatus.FAILED


# ── parse_log default is a no-op ─────────────────────────────────────


def test_default_parse_log_returns_empty() -> None:
    assert _SyntheticWorker().parse_log("anything") == {}
