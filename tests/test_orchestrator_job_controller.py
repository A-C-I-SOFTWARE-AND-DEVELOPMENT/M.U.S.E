"""Tests for hermes_cli.orchestrator — the local job controller.

The controller owns filesystem state only (no subprocesses, no network),
so every test runs against a tmp_path root.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hermes_cli.job_controller import (
    GITHUB_DIRNAME,
    JOB_FILE,
    JobController,
    JobControllerError,
    JobNotFoundError,
    InvalidStateError,
)
from hermes_cli.orchestrator_models import (
    DEFAULT_WORKERS_BY_MODE,
    Job,
    JobMode,
    JobState,
    WorkerRole,
    WorkerSpec,
)


# ──────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────


@pytest.fixture
def controller(tmp_path: Path) -> JobController:
    return JobController(root=tmp_path / ".hermes-orchestrator")


@pytest.fixture
def job(controller: JobController) -> Job:
    return controller.create_job(
        prompt="Add a /healthz endpoint and a smoke test",
        mode=JobMode.BUILD,
        repo_root="/srv/example",
        trusted_local=True,
    )


# ──────────────────────────────────────────────────────────────────────
# create_job
# ──────────────────────────────────────────────────────────────────────


class TestCreateJob:
    def test_creates_job_dir_and_job_json(self, controller: JobController):
        job = controller.create_job(
            prompt="ship it",
            mode=JobMode.BUILD,
            repo_root="/work/repo",
            trusted_local=False,
        )
        job_dir = controller.job_dir(job.job_id)
        assert job_dir.is_dir()
        job_file = job_dir / JOB_FILE
        assert job_file.is_file()
        data = json.loads(job_file.read_text())
        assert data["job_id"] == job.job_id
        assert data["mode"] == JobMode.BUILD
        assert data["state"] == JobState.CREATED
        assert data["trusted_local"] is False
        assert data["repo_root"] == "/work/repo"

    def test_default_workers_match_mode(self, controller: JobController):
        job = controller.create_job(
            prompt="refactor module",
            mode=JobMode.REFACTOR,
            repo_root=".",
            trusted_local=True,
        )
        roles = [w.role for w in job.workers]
        assert roles == list(DEFAULT_WORKERS_BY_MODE[JobMode.REFACTOR])

    def test_explicit_workers_override_defaults(self, controller: JobController):
        workers = [
            WorkerSpec(worker_id="w1-builder", role=WorkerRole.BUILDER),
            WorkerSpec(worker_id="w2-reviewer", role=WorkerRole.REVIEWER),
        ]
        job = controller.create_job(
            prompt="do thing",
            mode=JobMode.BUILD,
            repo_root=".",
            trusted_local=True,
            workers=workers,
        )
        assert [w.worker_id for w in job.workers] == [
            "w1-builder",
            "w2-reviewer",
        ]

    def test_rejects_empty_prompt(self, controller: JobController):
        with pytest.raises(JobControllerError, match="prompt is required"):
            controller.create_job(
                prompt="   ",
                mode=JobMode.BUILD,
                repo_root=".",
                trusted_local=True,
            )

    def test_rejects_unknown_mode(self, controller: JobController):
        with pytest.raises(JobControllerError, match="mode must be one of"):
            controller.create_job(
                prompt="x",
                mode="bogus",
                repo_root=".",
                trusted_local=True,
            )

    def test_rejects_duplicate_worker_ids(self, controller: JobController):
        workers = [
            WorkerSpec(worker_id="w1", role=WorkerRole.BUILDER),
            WorkerSpec(worker_id="w1", role=WorkerRole.REVIEWER),
        ]
        with pytest.raises(JobControllerError, match="duplicate worker_id"):
            controller.create_job(
                prompt="x",
                mode=JobMode.BUILD,
                repo_root=".",
                trusted_local=True,
                workers=workers,
            )

    def test_records_creation_in_history(self, controller: JobController, job: Job):
        assert len(job.history) == 1
        h = job.history[0]
        assert h.from_state is None
        assert h.to_state == JobState.CREATED
        assert h.timestamp > 0


# ──────────────────────────────────────────────────────────────────────
# load_job / list_jobs
# ──────────────────────────────────────────────────────────────────────


class TestLoadAndList:
    def test_load_job_round_trips(self, controller: JobController, job: Job):
        loaded = controller.load_job(job.job_id)
        assert loaded.job_id == job.job_id
        assert loaded.prompt == job.prompt
        assert loaded.mode == job.mode
        assert loaded.state == job.state
        assert len(loaded.workers) == len(job.workers)

    def test_load_job_missing(self, controller: JobController):
        with pytest.raises(JobNotFoundError):
            controller.load_job("20260101t000000z-deadbe")

    def test_load_job_corrupt(self, controller: JobController, job: Job):
        # Stomp the file with non-JSON content
        (controller.job_dir(job.job_id) / JOB_FILE).write_text("not json")
        with pytest.raises(JobControllerError, match="corrupt"):
            controller.load_job(job.job_id)

    def test_list_jobs_empty(self, controller: JobController):
        assert controller.list_jobs() == []

    def test_list_jobs_sorted_oldest_first(self, controller: JobController):
        ids: list[str] = []
        for i in range(3):
            j = controller.create_job(
                prompt=f"task {i}",
                mode=JobMode.BUILD,
                repo_root=".",
                trusted_local=True,
            )
            ids.append(j.job_id)
        jobs = controller.list_jobs()
        # list_jobs sorts by (created_at, job_id) — since we created them
        # sequentially, that equals the creation order.
        assert [j.job_id for j in jobs] == ids
        # And created_at is non-decreasing
        for a, b in zip(jobs, jobs[1:]):
            assert a.created_at <= b.created_at

    def test_list_jobs_skips_unreadable(self, controller: JobController, job: Job):
        bad_dir = controller.jobs_dir / "garbage"
        bad_dir.mkdir()
        # missing job.json — should be silently skipped
        jobs = controller.list_jobs()
        assert [j.job_id for j in jobs] == [job.job_id]


# ──────────────────────────────────────────────────────────────────────
# get_status / update_status
# ──────────────────────────────────────────────────────────────────────


class TestStatus:
    def test_initial_status_is_created(
        self, controller: JobController, job: Job
    ):
        assert controller.get_status(job.job_id) == JobState.CREATED

    def test_update_status_persists(self, controller: JobController, job: Job):
        controller.update_status(job.job_id, JobState.PLANNING, note="kicked off")
        assert controller.get_status(job.job_id) == JobState.PLANNING
        loaded = controller.load_job(job.job_id)
        assert loaded.history[-1].from_state == JobState.CREATED
        assert loaded.history[-1].to_state == JobState.PLANNING
        assert loaded.history[-1].note == "kicked off"

    def test_update_status_noop_no_history_entry(
        self, controller: JobController, job: Job
    ):
        before = len(job.history)
        controller.update_status(job.job_id, JobState.CREATED)
        after = len(controller.load_job(job.job_id).history)
        assert after == before

    def test_update_status_rejects_unknown(
        self, controller: JobController, job: Job
    ):
        with pytest.raises(InvalidStateError):
            controller.update_status(job.job_id, "not_a_state")


# ──────────────────────────────────────────────────────────────────────
# write_decision_ledger
# ──────────────────────────────────────────────────────────────────────


class TestDecisionLedger:
    def test_writes_markdown_with_trailing_newline(
        self, controller: JobController, job: Job
    ):
        path = controller.write_decision_ledger(
            job.job_id,
            "## Decision\n\nGo with the simpler approach.",
        )
        assert path.exists()
        text = path.read_text()
        assert text.endswith("\n")
        assert "Decision" in text

    def test_idempotent_overwrite(self, controller: JobController, job: Job):
        controller.write_decision_ledger(job.job_id, "first")
        controller.write_decision_ledger(job.job_id, "second")
        text = (controller.job_dir(job.job_id) / "decision_ledger.md").read_text()
        assert "second" in text
        assert "first" not in text

    def test_rejects_unknown_job(self, controller: JobController):
        with pytest.raises(JobNotFoundError):
            controller.write_decision_ledger("missing", "x")


# ──────────────────────────────────────────────────────────────────────
# create_worker_folders / write_worker_prompt
# ──────────────────────────────────────────────────────────────────────


class TestWorkerFolders:
    def test_creates_one_folder_per_worker(
        self, controller: JobController, job: Job
    ):
        created = controller.create_worker_folders(job.job_id)
        assert len(created) == len(job.workers)
        for spec, path in zip(job.workers, created):
            assert path.name == spec.worker_id
            assert (path / "artifacts").is_dir()

    def test_create_worker_folders_idempotent(
        self, controller: JobController, job: Job
    ):
        controller.create_worker_folders(job.job_id)
        # second call must not raise
        controller.create_worker_folders(job.job_id)

    def test_create_worker_folders_requires_workers(
        self, controller: JobController
    ):
        job = controller.create_job(
            prompt="x",
            mode=JobMode.BUILD,
            repo_root=".",
            trusted_local=True,
            workers=[],
        )
        with pytest.raises(JobControllerError, match="no workers"):
            controller.create_worker_folders(job.job_id)

    def test_write_worker_prompt_persists_flag(
        self, controller: JobController, job: Job
    ):
        wid = job.workers[0].worker_id
        path = controller.write_worker_prompt(
            job.job_id, wid, "Build the endpoint"
        )
        assert path.exists()
        assert path.read_text().rstrip() == "Build the endpoint"
        reloaded = controller.load_job(job.job_id)
        spec = reloaded.worker(wid)
        assert spec is not None
        assert spec.prompt_written is True

    def test_write_worker_prompt_rejects_unknown_worker(
        self, controller: JobController, job: Job
    ):
        with pytest.raises(JobControllerError, match="no worker"):
            controller.write_worker_prompt(job.job_id, "nope", "x")

    def test_write_worker_prompt_rejects_empty(
        self, controller: JobController, job: Job
    ):
        wid = job.workers[0].worker_id
        with pytest.raises(JobControllerError, match="prompt must not be empty"):
            controller.write_worker_prompt(job.job_id, wid, "   ")


# ──────────────────────────────────────────────────────────────────────
# collect_worker_artifacts
# ──────────────────────────────────────────────────────────────────────


class TestCollectArtifacts:
    def test_empty_when_no_artifacts(
        self, controller: JobController, job: Job
    ):
        controller.create_worker_folders(job.job_id)
        artifacts = controller.collect_worker_artifacts(job.job_id)
        assert set(artifacts.keys()) == {w.worker_id for w in job.workers}
        assert all(files == [] for files in artifacts.values())

    def test_collects_files_and_updates_count(
        self, controller: JobController, job: Job
    ):
        controller.create_worker_folders(job.job_id)
        wid = job.workers[0].worker_id
        wdir = controller._worker_dir(job.job_id, wid)
        (wdir / "artifacts" / "patch.diff").write_text("diff --git a/x b/x\n")
        (wdir / "artifacts" / "notes.md").write_text("# notes\n")
        (wdir / "artifacts" / "nested").mkdir()
        (wdir / "artifacts" / "nested" / "log.txt").write_text("hi")
        artifacts = controller.collect_worker_artifacts(job.job_id)
        files = artifacts[wid]
        assert len(files) == 3
        reloaded = controller.load_job(job.job_id)
        spec = reloaded.worker(wid)
        assert spec is not None
        assert spec.artifact_count == 3


# ──────────────────────────────────────────────────────────────────────
# write_scorecard
# ──────────────────────────────────────────────────────────────────────


class TestScorecard:
    def test_writes_scorecard_md(self, controller: JobController, job: Job):
        controller.create_worker_folders(job.job_id)
        path = controller.write_scorecard(job.job_id)
        assert path.exists()
        text = path.read_text()
        assert f"job {job.job_id}" in text
        assert "Workers" in text
        # default build mode -> single builder worker
        assert job.workers[0].worker_id in text

    def test_scorecard_includes_summary_and_scores(
        self, controller: JobController, job: Job
    ):
        wid = job.workers[0].worker_id
        path = controller.write_scorecard(
            job.job_id,
            payload={
                "summary": "Everything went green.",
                "scores": {wid: {"tests": "pass", "lint": "pass"}},
            },
        )
        text = path.read_text()
        assert "Everything went green." in text
        assert "tests" in text and "lint" in text
        assert "pass" in text

    def test_scorecard_lists_artifacts(
        self, controller: JobController, job: Job
    ):
        controller.create_worker_folders(job.job_id)
        wid = job.workers[0].worker_id
        wdir = controller._worker_dir(job.job_id, wid)
        (wdir / "artifacts" / "result.txt").write_text("ok")
        path = controller.write_scorecard(job.job_id)
        text = path.read_text()
        assert "result.txt" in text


# ──────────────────────────────────────────────────────────────────────
# prepare_github_artifacts
# ──────────────────────────────────────────────────────────────────────


class TestPrepareGithub:
    def test_emits_pr_body_and_manifest(
        self, controller: JobController, job: Job
    ):
        gdir = controller.prepare_github_artifacts(job.job_id)
        assert gdir.name == GITHUB_DIRNAME
        assert (gdir / "pr_body.md").is_file()
        manifest = json.loads((gdir / "manifest.json").read_text())
        assert manifest["job_id"] == job.job_id
        assert manifest["mode"] == job.mode
        assert "pr_body.md" in manifest["files"]
        assert "manifest.json" in manifest["files"]

    def test_includes_decision_ledger_and_scorecard_when_present(
        self, controller: JobController, job: Job
    ):
        controller.write_decision_ledger(job.job_id, "## We chose X")
        controller.write_scorecard(job.job_id, payload={"summary": "ok"})
        gdir = controller.prepare_github_artifacts(job.job_id)
        assert (gdir / "decision_ledger.md").is_file()
        assert (gdir / "scorecard.md").is_file()
        manifest = json.loads((gdir / "manifest.json").read_text())
        assert "decision_ledger.md" in manifest["files"]
        assert "scorecard.md" in manifest["files"]

    def test_pr_body_contains_prompt_and_workers(
        self, controller: JobController, job: Job
    ):
        gdir = controller.prepare_github_artifacts(job.job_id)
        body = (gdir / "pr_body.md").read_text()
        # Title is derived from the first line of the prompt
        assert "/healthz" in body
        for spec in job.workers:
            assert spec.worker_id in body

    def test_idempotent(self, controller: JobController, job: Job):
        first = controller.prepare_github_artifacts(job.job_id)
        second = controller.prepare_github_artifacts(job.job_id)
        assert first == second
        # manifest still valid after second pass
        manifest = json.loads((second / "manifest.json").read_text())
        assert manifest["job_id"] == job.job_id


# ──────────────────────────────────────────────────────────────────────
# End-to-end mini flow
# ──────────────────────────────────────────────────────────────────────


def test_end_to_end_flow(controller: JobController, tmp_path: Path):
    job = controller.create_job(
        prompt="Refactor the auth flow to drop legacy cookies",
        mode=JobMode.REFACTOR,
        repo_root=str(tmp_path),
        trusted_local=True,
    )
    controller.update_status(job.job_id, JobState.PLANNING)
    controller.create_worker_folders(job.job_id)
    for spec in job.workers:
        controller.write_worker_prompt(
            job.job_id, spec.worker_id, f"Role-specific prompt for {spec.role}"
        )
    controller.update_status(job.job_id, JobState.WORKERS_RUNNING)

    # Simulate one artifact per worker landing on disk
    for spec in job.workers:
        wdir = controller._worker_dir(job.job_id, spec.worker_id)
        (wdir / "artifacts" / "out.md").write_text(f"output from {spec.role}\n")

    controller.update_status(job.job_id, JobState.WORKERS_COMPLETE)
    controller.write_decision_ledger(
        job.job_id,
        "## Decisions\n\n- Drop legacy cookies\n- Add migration shim",
    )
    controller.write_scorecard(job.job_id, payload={"summary": "all green"})
    controller.update_status(job.job_id, JobState.SCORED)
    gdir = controller.prepare_github_artifacts(job.job_id)
    controller.update_status(job.job_id, JobState.GITHUB_READY)

    final = controller.load_job(job.job_id)
    assert final.state == JobState.GITHUB_READY
    # State transitions should be linear and recorded
    expected_states = [
        JobState.CREATED,
        JobState.PLANNING,
        JobState.WORKERS_RUNNING,
        JobState.WORKERS_COMPLETE,
        JobState.SCORED,
        JobState.GITHUB_READY,
    ]
    assert [h.to_state for h in final.history] == expected_states
    assert all(w.prompt_written for w in final.workers)
    assert all(w.artifact_count == 1 for w in final.workers)
    assert (gdir / "pr_body.md").is_file()
    assert (gdir / "decision_ledger.md").is_file()
    assert (gdir / "scorecard.md").is_file()


# ──────────────────────────────────────────────────────────────────────
# Phase 12 — module-level phase controller
# ──────────────────────────────────────────────────────────────────────
#
# These tests exercise the new ``hermes_cli.orchestrator`` module-level
# API: ``create_job``, ``load_job``, ``list_jobs``,
# ``update_job_status``, ``initialize_job_artifacts``,
# ``run_<phase>_phase``, ``request_approval`` / ``grant_approval``,
# ``resume_job``, and ``cancel_job``.
#
# The controller persists jobs to ``$HERMES_HOME/orchestrator``; the
# autouse fixture in ``tests/conftest.py`` redirects ``HERMES_HOME`` to
# a per-test tempdir, so these tests are hermetic without any explicit
# tmp_path plumbing.

from hermes_cli import orchestrator as orch  # noqa: E402
from hermes_cli import workflows as wf  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_phase12_state():
    """Reset module-level controller state between tests."""
    orch.set_continuous_listening(False)
    yield
    orch.set_continuous_listening(False)


@pytest.fixture
def phase12_job():
    return orch.create_job(
        prompt="Add a /healthz endpoint and a smoke test",
        repo_root="/srv/example",
        mode="build",
        trusted_local=True,
    )


class TestCreateJobPhase12:
    def test_create_job_records_metadata(self):
        job = orch.create_job(
            prompt="ship it",
            repo_root="/work/repo",
            mode="build",
            trusted_local=False,
        )
        assert job.id.startswith("orc-")
        assert job.prompt == "ship it"
        assert job.mode == "build"
        assert job.repo_root == "/work/repo"
        assert job.trusted_local is False
        assert job.phase == wf.PHASE_INTAKE
        assert job.status == "queued"
        assert job.phases_completed == []

    def test_create_job_rejects_empty_prompt(self):
        with pytest.raises(orch.OrchestratorError, match="prompt is required"):
            orch.create_job(
                prompt="   ",
                repo_root="/x",
                mode="build",
                trusted_local=True,
            )

    def test_create_job_initializes_artifacts(self, phase12_job):
        root = orch._job_artifacts_dir(phase12_job.id)
        assert root.is_dir()
        assert (root / "phases").is_dir()
        assert (root / "workers").is_dir()
        assert (root / "publish").is_dir()
        assert (root / "README.md").is_file()

    def test_create_job_appends_decision_ledger_entry(self, phase12_job):
        entries = orch._ledger_for(phase12_job.id).entries()
        kinds = [e.get("kind") for e in entries]
        assert "create_job" in kinds


class TestLoadJob:
    def test_load_job_returns_job(self, phase12_job):
        loaded = orch.load_job(phase12_job.id)
        assert loaded.id == phase12_job.id
        assert loaded.prompt == phase12_job.prompt

    def test_load_job_unknown_raises(self):
        with pytest.raises(orch.OrchestratorError, match="unknown job id"):
            orch.load_job("orc-does-not-exist")


class TestListJobsPhase12:
    def test_list_jobs_returns_recent_first(self):
        a = orch.create_job("a", "/x", mode="build", trusted_local=True)
        b = orch.create_job("b", "/x", mode="build", trusted_local=True)
        c = orch.create_job("c", "/x", mode="build", trusted_local=True)
        listing = orch.list_jobs()
        ids = [j.id for j in listing]
        # Newest first; only the three jobs we created.
        assert ids[:3] == [c.id, b.id, a.id]


class TestUpdateJobStatus:
    def test_update_persists(self, phase12_job):
        updated = orch.update_job_status(phase12_job.id, "running")
        assert updated.status == "running"
        # Reload to confirm persistence
        again = orch.load_job(phase12_job.id)
        assert again.status == "running"

    def test_update_records_ledger(self, phase12_job):
        orch.update_job_status(phase12_job.id, "paused")
        entries = orch._ledger_for(phase12_job.id).entries_of_kind("status")
        assert any(e.get("to") == "paused" for e in entries)

    def test_update_rejects_empty(self, phase12_job):
        with pytest.raises(orch.OrchestratorError):
            orch.update_job_status(phase12_job.id, "")


class TestInitializeJobArtifacts:
    def test_idempotent(self, phase12_job):
        first = orch.initialize_job_artifacts(phase12_job.id)
        second = orch.initialize_job_artifacts(phase12_job.id)
        assert first == second
        assert first.is_dir()


class TestSafePhases:
    """intake / research / planning / validation / retrospective never
    need approval and should run cleanly in sequence."""

    def test_run_intake_writes_note(self, phase12_job):
        job = orch.run_intake_phase(phase12_job.id)
        assert job.phase == wf.PHASE_INTAKE
        assert wf.PHASE_INTAKE in job.phases_completed
        path = orch._job_artifacts_dir(job.id) / "phases" / "intake.md"
        assert path.is_file()
        assert "Intake" in path.read_text()

    def test_research_requires_intake(self, phase12_job):
        with pytest.raises(orch.PhaseError, match="requires intake"):
            orch.run_research_phase(phase12_job.id)

    def test_planning_after_research(self, phase12_job):
        orch.run_intake_phase(phase12_job.id)
        orch.run_research_phase(phase12_job.id)
        job = orch.run_planning_phase(phase12_job.id)
        assert wf.PHASE_PLANNING in job.phases_completed
        path = orch._job_artifacts_dir(job.id) / "phases" / "planning.md"
        assert path.is_file()
        assert "Plan" in path.read_text()


class TestApprovalGate:
    """Implementation + publish must respect approval gates."""

    def _advance_to_planning(self, job_id: str) -> None:
        orch.run_intake_phase(job_id)
        orch.run_research_phase(job_id)
        orch.run_planning_phase(job_id)

    def test_implementation_requires_approval(self, phase12_job):
        self._advance_to_planning(phase12_job.id)
        with pytest.raises(orch.ApprovalRequired):
            orch.run_implementation_phase(phase12_job.id)

    def test_request_approval_records_request(self, phase12_job):
        record = orch.request_approval(phase12_job.id, wf.PHASE_IMPLEMENTATION)
        assert record["phase"] == wf.PHASE_IMPLEMENTATION
        assert record["approved"] is False
        assert record["mutates_local"] is True

    def test_grant_approval_lets_phase_proceed(self, phase12_job):
        self._advance_to_planning(phase12_job.id)
        orch.request_approval(phase12_job.id, wf.PHASE_IMPLEMENTATION)
        orch.grant_approval(phase12_job.id, wf.PHASE_IMPLEMENTATION)
        job = orch.run_implementation_phase(phase12_job.id)
        assert wf.PHASE_IMPLEMENTATION in job.phases_completed

    def test_approve_kwarg_short_circuits(self, phase12_job):
        self._advance_to_planning(phase12_job.id)
        job = orch.run_implementation_phase(phase12_job.id, approve=True)
        assert wf.PHASE_IMPLEMENTATION in job.phases_completed
        assert job.approvals[wf.PHASE_IMPLEMENTATION] is True

    def test_remote_implementation_always_requires_approval(self, phase12_job):
        self._advance_to_planning(phase12_job.id)
        # Even with trusted_local=True, remote=True without prior approval
        # must raise ApprovalRequired.
        with pytest.raises(orch.ApprovalRequired, match="remote"):
            orch.run_implementation_phase(phase12_job.id, remote=True)

    def test_continuous_listening_never_auto_implements(self, phase12_job):
        self._advance_to_planning(phase12_job.id)
        orch.set_continuous_listening(True)
        # Even calling with approve=True should be honored, but without
        # approve=True the call must raise.
        with pytest.raises(orch.ApprovalRequired, match="listening"):
            orch.run_implementation_phase(phase12_job.id)


class TestValidationAndPublish:
    def _to_implementation_done(self, job_id: str) -> None:
        orch.run_intake_phase(job_id)
        orch.run_research_phase(job_id)
        orch.run_planning_phase(job_id)
        orch.run_implementation_phase(job_id, approve=True)

    def test_validation_after_implementation(self, phase12_job):
        self._to_implementation_done(phase12_job.id)
        job = orch.run_validation_phase(phase12_job.id)
        assert wf.PHASE_VALIDATION in job.phases_completed
        path = orch._job_artifacts_dir(job.id) / "phases" / "validation.md"
        assert path.is_file()

    def test_publish_requires_approval(self, phase12_job):
        self._to_implementation_done(phase12_job.id)
        orch.run_validation_phase(phase12_job.id)
        with pytest.raises(orch.ApprovalRequired):
            orch.prepare_publish_phase(phase12_job.id)

    def test_publish_writes_bundle(self, phase12_job):
        self._to_implementation_done(phase12_job.id)
        orch.run_validation_phase(phase12_job.id)
        job = orch.prepare_publish_phase(phase12_job.id, approve=True)
        pub_dir = orch._job_artifacts_dir(job.id) / "publish"
        assert (pub_dir / "pr_body.md").is_file()
        assert (pub_dir / "manifest.json").is_file()
        manifest = json.loads((pub_dir / "manifest.json").read_text())
        assert manifest["job_id"] == job.id
        assert manifest["mode"] == "build"

    def test_remote_publish_requires_approval(self, phase12_job):
        self._to_implementation_done(phase12_job.id)
        orch.run_validation_phase(phase12_job.id)
        with pytest.raises(orch.ApprovalRequired, match="remote"):
            orch.prepare_publish_phase(phase12_job.id, remote=True)


class TestRetrospective:
    def test_retrospective_completes_job(self, phase12_job):
        orch.run_intake_phase(phase12_job.id)
        orch.run_research_phase(phase12_job.id)
        orch.run_planning_phase(phase12_job.id)
        orch.run_implementation_phase(phase12_job.id, approve=True)
        orch.run_validation_phase(phase12_job.id)
        orch.prepare_publish_phase(phase12_job.id, approve=True)
        job = orch.run_retrospective_phase(phase12_job.id)
        assert wf.PHASE_RETROSPECTIVE in job.phases_completed
        assert job.status == "succeeded"

    def test_retrospective_requires_publish(self, phase12_job):
        orch.run_intake_phase(phase12_job.id)
        orch.run_research_phase(phase12_job.id)
        orch.run_planning_phase(phase12_job.id)
        with pytest.raises(orch.PhaseError, match="publish"):
            orch.run_retrospective_phase(phase12_job.id)


class TestResumeAndCancel:
    def test_resume_paused_job(self, phase12_job):
        orch.update_job_status(phase12_job.id, "paused")
        resumed = orch.resume_job(phase12_job.id)
        assert resumed is not None
        assert resumed.status == "queued"
        assert resumed.resumed_count == 1

    def test_cancel_records_status_and_ledger(self, phase12_job):
        cancelled = orch.cancel_job(phase12_job.id, reason="user pressed ESC")
        assert cancelled.status == "cancelled"
        entries = orch._ledger_for(phase12_job.id).entries_of_kind("cancel")
        assert any("user pressed ESC" in (e.get("reason") or "") for e in entries)

    def test_cancel_is_idempotent_on_finished(self, phase12_job):
        orch.update_job_status(phase12_job.id, "succeeded")
        cancelled = orch.cancel_job(phase12_job.id)
        # Already-finished jobs are not re-cancelled.
        assert cancelled.status == "succeeded"


def test_phase12_full_flow():
    """End-to-end happy path across every phase."""
    job = orch.create_job(
        prompt="Refactor the auth flow to drop legacy cookies",
        repo_root="/srv/example",
        mode="refactor",
        trusted_local=True,
    )
    orch.run_intake_phase(job.id)
    orch.run_research_phase(job.id)
    orch.run_planning_phase(job.id)
    orch.request_approval(job.id, wf.PHASE_IMPLEMENTATION)
    orch.grant_approval(job.id, wf.PHASE_IMPLEMENTATION)
    orch.run_implementation_phase(job.id)
    orch.run_validation_phase(job.id)
    orch.request_approval(job.id, wf.PHASE_PUBLISH)
    orch.grant_approval(job.id, wf.PHASE_PUBLISH)
    orch.prepare_publish_phase(job.id)
    final = orch.run_retrospective_phase(job.id)

    expected = [
        wf.PHASE_INTAKE,
        wf.PHASE_RESEARCH,
        wf.PHASE_PLANNING,
        wf.PHASE_IMPLEMENTATION,
        wf.PHASE_VALIDATION,
        wf.PHASE_PUBLISH,
        wf.PHASE_RETROSPECTIVE,
    ]
    assert final.phases_completed == expected
    assert final.status == "succeeded"
    assert final.approvals[wf.PHASE_IMPLEMENTATION] is True
    assert final.approvals[wf.PHASE_PUBLISH] is True

    ledger_entries = orch._ledger_for(job.id).entries()
    kinds = {e.get("kind") for e in ledger_entries}
    assert "create_job" in kinds
    assert "phase_enter" in kinds
    assert "phase_complete" in kinds
    assert "approval_granted" in kinds


# ──────────────────────────────────────────────────────────────────────
# Workflow helper sanity
# ──────────────────────────────────────────────────────────────────────


class TestWorkflowsModule:
    def test_phase_specs_present(self):
        for phase in wf.PHASES_ORDERED:
            assert phase in wf.PHASE_SPECS

    def test_approval_gated_phases_marked(self):
        for phase in wf.APPROVAL_GATED_PHASES:
            assert wf.PHASE_SPECS[phase].requires_approval

    def test_next_phase_sequence(self):
        assert wf.next_phase(wf.PHASE_INTAKE) == wf.PHASE_RESEARCH
        assert wf.next_phase(wf.PHASE_RETROSPECTIVE) is None
