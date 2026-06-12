"""End-to-end integration test for the local orchestrator pipeline.

Drives a job from creation through worker prompt + artifact emission,
scorecard rendering, decision ledger capture, and GitHub bundle
preparation — all against an isolated ``tmp_path`` root.

The test deliberately uses only the in-process surfaces; no real
subprocess, no network, no Termux. Phase 25's contract is that a CI
runner with no API keys can still run the full pipeline against
filesystem fixtures.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hermes_cli.job_controller import (
    DECISION_LEDGER_FILE,
    GITHUB_DIRNAME,
    SCORECARD_FILE,
    JobController,
)
from hermes_cli.orchestrator_models import (
    JobMode,
    JobState,
    WorkerRole,
    WorkerSpec,
)


@pytest.fixture
def controller(tmp_path: Path) -> JobController:
    return JobController(root=tmp_path / ".hermes-orchestrator")


def test_full_orchestration_pipeline_audited_on_disk(
    controller: JobController, tmp_path: Path
) -> None:
    # 1. CREATE
    job = controller.create_job(
        prompt="Refactor the auth flow to drop legacy cookies",
        mode=JobMode.REFACTOR,
        repo_root=str(tmp_path),
        trusted_local=True,
    )
    assert job.state == JobState.CREATED
    assert job.workers, "REFACTOR mode should default to ≥1 worker"

    # 2. PLAN
    controller.update_status(job.job_id, JobState.PLANNING)

    # 3. ASSIGN
    controller.create_worker_folders(job.job_id)
    for spec in job.workers:
        controller.write_worker_prompt(
            job.job_id,
            spec.worker_id,
            f"Role-specific prompt for {spec.role}",
        )
    controller.update_status(job.job_id, JobState.WORKERS_ASSIGNED)

    # 4. RUN — simulate one artifact per worker landing on disk.
    controller.update_status(job.job_id, JobState.WORKERS_RUNNING)
    for spec in job.workers:
        wdir = controller._worker_dir(job.job_id, spec.worker_id)
        (wdir / "artifacts" / "out.md").write_text(
            f"output from {spec.role}\n", encoding="utf-8"
        )

    controller.update_status(job.job_id, JobState.WORKERS_COMPLETE)

    # 5. SCORE
    controller.write_decision_ledger(
        job.job_id,
        "## Decisions\n\n- Drop legacy cookies\n- Add migration shim",
    )
    controller.write_scorecard(
        job.job_id,
        payload={
            "summary": "all green",
            "scores": {
                job.workers[0].worker_id: {"tests": "pass", "lint": "pass"},
            },
        },
    )
    controller.update_status(job.job_id, JobState.SCORED)

    # 6. PUBLISH-READY
    gdir = controller.prepare_github_artifacts(job.job_id)
    controller.update_status(job.job_id, JobState.GITHUB_READY)

    # ── Invariants ──────────────────────────────────────────────────
    final = controller.load_job(job.job_id)
    assert final.state == JobState.GITHUB_READY
    assert all(w.prompt_written for w in final.workers)
    assert all(w.artifact_count == 1 for w in final.workers)

    # The github/ bundle was assembled in full.
    assert gdir.name == GITHUB_DIRNAME
    assert (gdir / "pr_body.md").is_file()
    assert (gdir / DECISION_LEDGER_FILE).is_file()
    assert (gdir / SCORECARD_FILE).is_file()

    manifest = json.loads((gdir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["job_id"] == job.job_id
    assert manifest["mode"] == JobMode.REFACTOR
    assert sorted(manifest["files"]) == sorted(
        ["pr_body.md", DECISION_LEDGER_FILE, SCORECARD_FILE, "manifest.json"]
    )

    # Decision ledger content survives the copy.
    ledger_text = (gdir / DECISION_LEDGER_FILE).read_text(encoding="utf-8")
    assert "Drop legacy cookies" in ledger_text


def test_pipeline_is_resumable_from_disk(
    controller: JobController, tmp_path: Path
) -> None:
    # Drive a partial pipeline …
    job = controller.create_job(
        prompt="Build /healthz endpoint",
        mode=JobMode.BUILD,
        repo_root=str(tmp_path),
        trusted_local=True,
    )
    controller.update_status(job.job_id, JobState.PLANNING)
    controller.create_worker_folders(job.job_id)
    wid = job.workers[0].worker_id
    controller.write_worker_prompt(job.job_id, wid, "Build the endpoint")
    controller.update_status(job.job_id, JobState.WORKERS_RUNNING)

    # … then drop the in-memory state and rebuild from disk.
    fresh = JobController(root=controller.root)
    reloaded = fresh.load_job(job.job_id)
    assert reloaded.state == JobState.WORKERS_RUNNING
    assert reloaded.worker(wid).prompt_written is True  # type: ignore[union-attr]  # ty: ignore[unresolved-attribute]  # mock/duck-typed test fixture
    # New controller can drive the next transition.
    fresh.update_status(job.job_id, JobState.WORKERS_COMPLETE)
    assert fresh.load_job(job.job_id).state == JobState.WORKERS_COMPLETE


def test_explicit_worker_assignment_is_honored(
    controller: JobController, tmp_path: Path
) -> None:
    workers = [
        WorkerSpec(worker_id="planner-1", role=WorkerRole.PLANNER, target_tool="chatgpt"),
        WorkerSpec(worker_id="builder-1", role=WorkerRole.BUILDER, target_tool="codex"),
        WorkerSpec(worker_id="reviewer-1", role=WorkerRole.REVIEWER, target_tool="claude_code"),
    ]
    job = controller.create_job(
        prompt="Full team build",
        mode=JobMode.BUILD,
        repo_root=str(tmp_path),
        trusted_local=True,
        workers=workers,
    )
    assert [w.worker_id for w in job.workers] == [
        "planner-1",
        "builder-1",
        "reviewer-1",
    ]
    # Each worker gets its own folder + prompt slot.
    controller.create_worker_folders(job.job_id)
    for spec in workers:
        path = controller.write_worker_prompt(job.job_id, spec.worker_id, "go")
        assert path.exists()
    # And the GitHub bundle's PR body lists every worker.
    gdir = controller.prepare_github_artifacts(job.job_id)
    body = (gdir / "pr_body.md").read_text(encoding="utf-8")
    for spec in workers:
        assert spec.worker_id in body
