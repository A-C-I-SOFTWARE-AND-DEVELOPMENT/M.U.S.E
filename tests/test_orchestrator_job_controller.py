"""Tests for the job folder contract and lifecycle controller.

These tests verify the on-disk shape promised by
``hermes_cli.orchestrator.job_controller``. The contract is what every
worker and downstream phase relies on, so it must be enforced rigidly.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hermes_cli.orchestrator.job_controller import (
    JOB_FOLDER_VERSION,
    JobController,
    JobNotFoundError,
)
from hermes_cli.workers.base import WorkerStatus, WorkerResult
from hermes_cli.workers.hermes_local import HermesLocalWorker


@pytest.fixture
def controller(tmp_path: Path) -> JobController:
    return JobController(tmp_path / "jobs")


# ── creation contract ──────────────────────────────────────────────


def test_create_writes_required_files(controller: JobController) -> None:
    ctx = controller.create("Fix the readme typo", title="readme-typo")
    assert ctx.job_dir.is_dir()
    # Required files
    assert (ctx.job_dir / "job.json").exists()
    assert (ctx.job_dir / "prompt.md").exists()
    assert (ctx.job_dir / "workers").is_dir()
    # job.json schema
    meta = json.loads((ctx.job_dir / "job.json").read_text())
    assert meta["version"] == JOB_FOLDER_VERSION
    assert meta["id"] == ctx.job_id
    assert meta["status"] == WorkerStatus.PENDING
    assert meta["title"] == "readme-typo"
    assert meta["base_branch"] == "main"
    assert "created_at" in meta and meta["created_at"].endswith("Z")
    # Prompt content roundtrips
    assert (ctx.job_dir / "prompt.md").read_text() == "Fix the readme typo"


def test_create_rejects_empty_prompt(controller: JobController) -> None:
    with pytest.raises(ValueError):
        controller.create("   \n   ")


def test_create_rejects_duplicate_id(controller: JobController) -> None:
    ctx = controller.create("Hello", job_id="my-job-1")
    with pytest.raises(FileExistsError):
        controller.create("Hello again", job_id="my-job-1")


def test_create_rejects_bad_job_id(controller: JobController) -> None:
    with pytest.raises(ValueError):
        controller.create("Hi", job_id="bad id with spaces")
    with pytest.raises(ValueError):
        controller.create("Hi", job_id="UPPERCASE")


def test_create_auto_slug_safe(controller: JobController) -> None:
    ctx = controller.create("Fix CVE-2026-xyz!! emergency $$$ fix")
    # The slug must satisfy the same charset rule as explicit ids.
    import re
    assert re.match(r"^[a-z0-9][a-z0-9_-]{0,63}$", ctx.job_id), ctx.job_id


# ── load / list ────────────────────────────────────────────────────


def test_load_roundtrips(controller: JobController) -> None:
    ctx = controller.create("Build a thing", title="t")
    loaded = controller.load(ctx.job_id)
    assert loaded.job_id == ctx.job_id
    assert loaded.prompt == "Build a thing"
    assert loaded.title == "t"


def test_load_missing_raises(controller: JobController) -> None:
    with pytest.raises(JobNotFoundError):
        controller.load("does-not-exist")


def test_list_sorted_and_skips_garbage(controller: JobController) -> None:
    a = controller.create("a", job_id="job-a")
    b = controller.create("b", job_id="job-b")
    # Drop a stray directory without job.json — must be skipped.
    (controller.jobs_root / "not-a-job").mkdir()
    out = controller.list()
    assert out == ["job-a", "job-b"]


# ── mutators ───────────────────────────────────────────────────────


def test_set_status_validates(controller: JobController) -> None:
    ctx = controller.create("hi")
    controller.set_status(ctx, WorkerStatus.RUNNING)
    info = controller.status(ctx.job_id)
    assert info["status"] == WorkerStatus.RUNNING
    assert "updated_at" in info
    with pytest.raises(ValueError):
        controller.set_status(ctx, "wat")


def test_write_worker_result_materializes_contract(
    controller: JobController,
) -> None:
    ctx = controller.create("hi")
    adapter = HermesLocalWorker()
    result = WorkerResult(
        worker="hermes_local",
        success=True,
        exit_code=0,
        diff="--- a/x\n+++ b/x\n@@ -1,1 +1,1 @@\n-old\n+new\n",
        log="all done",
        files_changed=1,
        message="ok",
        started_at="2026-01-01T00:00:00Z",
        finished_at="2026-01-01T00:00:01Z",
    )
    wdir = controller.write_worker_result(ctx, adapter, result)
    assert (wdir / "status.json").exists()
    assert (wdir / "result.json").exists()
    assert (wdir / "output.diff").exists()
    assert (wdir / "log.txt").exists()
    # status.json contract
    status = json.loads((wdir / "status.json").read_text())
    assert status["worker"] == "hermes_local"
    assert status["status"] == WorkerStatus.DONE
    assert status["exit_code"] == 0
    # result.json contract
    res = json.loads((wdir / "result.json").read_text())
    assert res["success"] is True
    assert res["files_changed"] == 1


def test_mark_selected_writes_selected_json(controller: JobController) -> None:
    ctx = controller.create("hi")
    path = controller.mark_selected(ctx, "hermes_local", 42.0)
    payload = json.loads(path.read_text())
    assert payload["worker"] == "hermes_local"
    assert payload["score"] == 42.0
    assert "selected_at" in payload


def test_status_aggregates_workers(controller: JobController) -> None:
    ctx = controller.create("hi")
    adapter = HermesLocalWorker()
    controller.write_worker_result(
        ctx,
        adapter,
        WorkerResult(worker="hermes_local", success=True, exit_code=0),
    )
    info = controller.status(ctx.job_id)
    assert "hermes_local" in info["workers"]
    assert info["workers"]["hermes_local"]["status"] == WorkerStatus.DONE
    assert info["has_selected"] is False
    assert info["has_validation"] is False
    assert info["has_publish"] is False


def test_write_validation_and_publish_paths(controller: JobController) -> None:
    ctx = controller.create("hi")
    controller.write_validation(ctx, {"gates": {}, "overall": True})
    controller.write_publish(ctx, {"dry_run": True, "branch": "x", "base": "main"})
    info = controller.status(ctx.job_id)
    assert info["has_validation"] is True
    assert info["has_publish"] is True


def test_failed_worker_status_recorded(controller: JobController) -> None:
    ctx = controller.create("hi")
    adapter = HermesLocalWorker()
    controller.write_worker_result(
        ctx,
        adapter,
        WorkerResult(worker="hermes_local", success=False, exit_code=2),
    )
    info = controller.status(ctx.job_id)
    assert info["workers"]["hermes_local"]["status"] == WorkerStatus.FAILED
