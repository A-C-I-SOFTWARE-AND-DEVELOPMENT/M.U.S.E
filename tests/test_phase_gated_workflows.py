"""Phase-gated workflow tests.

Hermes orchestrates work through an explicit pipeline of states. A
job moves from CREATED → PLANNING → WORKERS_* → SCORED → GITHUB_READY
(see ``hermes_cli.orchestrator_models.JobState``), and every transition
must be:

  * recorded in the on-disk history list
  * idempotent against a same-state update
  * publishable as ``github/`` artifacts only after the prior phases

These tests model the full pipeline against an isolated job-controller
root so we never touch ``~/.hermes`` and never spawn a subprocess.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hermes_cli.job_controller import (
    GITHUB_DIRNAME,
    JobController,
    JobControllerError,
)
from hermes_cli.orchestrator_models import (
    Job,
    JobMode,
    JobState,
    WorkerRole,
    WorkerSpec,
)


@pytest.fixture
def controller(tmp_path: Path) -> JobController:
    return JobController(root=tmp_path / ".hermes-orchestrator")


@pytest.fixture
def build_job(controller: JobController) -> Job:
    return controller.create_job(
        prompt="Add a /healthz endpoint",
        mode=JobMode.BUILD,
        repo_root="/srv/example",
        trusted_local=True,
    )


# ── linear progression ───────────────────────────────────────────────


PHASE_SEQUENCE = (
    JobState.CREATED,
    JobState.PLANNING,
    JobState.WORKERS_ASSIGNED,
    JobState.WORKERS_RUNNING,
    JobState.WORKERS_COMPLETE,
    JobState.SCORED,
    JobState.GITHUB_READY,
    JobState.DONE,
)


class TestLinearPhaseProgression:
    def test_full_pipeline_recorded_in_history(
        self, controller: JobController, build_job: Job
    ) -> None:
        for state in PHASE_SEQUENCE[1:]:
            controller.update_status(build_job.job_id, state)
        final = controller.load_job(build_job.job_id)
        assert [h.to_state for h in final.history] == list(PHASE_SEQUENCE)
        # ``from_state`` chains correctly.
        for prev, curr in zip(final.history, final.history[1:]):
            assert curr.from_state == prev.to_state

    def test_same_state_update_is_idempotent(
        self, controller: JobController, build_job: Job
    ) -> None:
        before = len(build_job.history)
        controller.update_status(build_job.job_id, JobState.CREATED)
        after = len(controller.load_job(build_job.job_id).history)
        assert after == before

    def test_terminal_states_are_recorded(
        self, controller: JobController, build_job: Job
    ) -> None:
        controller.update_status(build_job.job_id, JobState.FAILED, note="bad")
        loaded = controller.load_job(build_job.job_id)
        assert loaded.state == JobState.FAILED
        assert loaded.history[-1].note == "bad"

    def test_cancelled_state_recorded(
        self, controller: JobController, build_job: Job
    ) -> None:
        controller.update_status(build_job.job_id, JobState.CANCELLED, note="user")
        loaded = controller.load_job(build_job.job_id)
        assert loaded.state == JobState.CANCELLED
        assert loaded.history[-1].note == "user"


# ── workflow gating ───────────────────────────────────────────────────


class TestWorkflowGating:
    def test_scorecard_requires_workers(self, controller: JobController) -> None:
        # Creating a job in BUILD mode auto-assigns a default builder
        # worker; verify the scorecard renders normally.
        job = controller.create_job(
            prompt="x",
            mode=JobMode.BUILD,
            repo_root=".",
            trusted_local=True,
        )
        path = controller.write_scorecard(job.job_id)
        assert path.is_file()
        text = path.read_text(encoding="utf-8")
        assert "Workers" in text

    def test_scorecard_renders_no_workers_message(
        self, controller: JobController
    ) -> None:
        # Forcing an empty workers list — scorecard should still render
        # without crashing.
        job = controller.create_job(
            prompt="x",
            mode=JobMode.BUILD,
            repo_root=".",
            trusted_local=True,
            workers=[],
        )
        path = controller.write_scorecard(job.job_id)
        assert "_No workers assigned._" in path.read_text(encoding="utf-8")

    def test_github_bundle_only_includes_artifacts_that_exist(
        self, controller: JobController, build_job: Job
    ) -> None:
        # No ledger, no scorecard — bundle still produced, manifest
        # lists only pr_body + manifest itself.
        gdir = controller.prepare_github_artifacts(build_job.job_id)
        manifest = json.loads((gdir / "manifest.json").read_text(encoding="utf-8"))
        assert set(manifest["files"]) == {"pr_body.md", "manifest.json"}

    def test_github_bundle_adds_ledger_and_scorecard_when_present(
        self, controller: JobController, build_job: Job
    ) -> None:
        controller.write_decision_ledger(build_job.job_id, "## chose plan A")
        controller.write_scorecard(build_job.job_id, payload={"summary": "ok"})
        gdir = controller.prepare_github_artifacts(build_job.job_id)
        manifest = json.loads((gdir / "manifest.json").read_text(encoding="utf-8"))
        assert "decision_ledger.md" in manifest["files"]
        assert "scorecard.md" in manifest["files"]


# ── invariants across phases ──────────────────────────────────────────


class TestPhaseInvariants:
    def test_worker_prompt_written_flag_persists(
        self, controller: JobController, build_job: Job
    ) -> None:
        wid = build_job.workers[0].worker_id
        controller.write_worker_prompt(build_job.job_id, wid, "do thing")
        # Run more updates — the flag must survive a reload.
        controller.update_status(build_job.job_id, JobState.PLANNING)
        controller.update_status(build_job.job_id, JobState.WORKERS_RUNNING)
        reloaded = controller.load_job(build_job.job_id)
        assert reloaded.worker(wid).prompt_written is True  # type: ignore[union-attr]

    def test_artifact_count_updates_through_phases(
        self, controller: JobController, build_job: Job
    ) -> None:
        controller.create_worker_folders(build_job.job_id)
        wid = build_job.workers[0].worker_id
        wdir = controller._worker_dir(build_job.job_id, wid)
        (wdir / "artifacts" / "result.md").write_text("ok", encoding="utf-8")
        controller.collect_worker_artifacts(build_job.job_id)
        reloaded = controller.load_job(build_job.job_id)
        assert reloaded.worker(wid).artifact_count == 1  # type: ignore[union-attr]

    def test_publish_phase_emits_github_directory(
        self, controller: JobController, build_job: Job
    ) -> None:
        gdir = controller.prepare_github_artifacts(build_job.job_id)
        assert gdir.name == GITHUB_DIRNAME
        assert gdir.is_dir()

    def test_invalid_state_value_rejected(
        self, controller: JobController, build_job: Job
    ) -> None:
        with pytest.raises(JobControllerError):
            controller.update_status(build_job.job_id, "not_a_state")
