"""Tests for the ParallelRunner — pure-Python parts only.

The broader subprocess and git-worktree behaviour is covered by
``test_parallel_orchestration.py``. This module pins the small,
side-effect-free pieces the orchestrator depends on:

  * ``WorkerPlan`` / ``ExecutionPlan`` validation rules
  * ``parse_command`` argv splitting
  * ``request_cancel`` flag-file write
  * ``list_jobs`` / ``load_status`` filesystem contract for PROMPT_ONLY
    and HANDOFF_REQUIRED runs (no subprocess needed)

By staying away from real subprocess launches this file is safe to run
in any sandbox — including CI with no shell tools beyond Python itself.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hermes_cli import orchestrator_parallel as op


# ── plan validation ───────────────────────────────────────────────────


class TestWorkerPlanValidate:
    def test_missing_worker_id(self) -> None:
        with pytest.raises(op.OrchestratorError):
            op.WorkerPlan(
                worker_id="", profile="x", mode=op.ExecutionMode.PROMPT_ONLY
            ).validate()

    def test_missing_profile(self) -> None:
        with pytest.raises(op.OrchestratorError):
            op.WorkerPlan(
                worker_id="w", profile="", mode=op.ExecutionMode.PROMPT_ONLY
            ).validate()

    def test_negative_timeout(self) -> None:
        with pytest.raises(op.OrchestratorError, match="timeout"):
            op.WorkerPlan(
                worker_id="w",
                profile="p",
                mode=op.ExecutionMode.PROMPT_ONLY,
                timeout_seconds=-1,
            ).validate()

    def test_local_run_requires_command(self) -> None:
        with pytest.raises(op.OrchestratorError, match="no command"):
            op.WorkerPlan(
                worker_id="w",
                profile="p",
                mode=op.ExecutionMode.LOCAL_RUN,
            ).validate()

    def test_prompt_only_accepts_no_command(self) -> None:
        # Must not raise.
        op.WorkerPlan(
            worker_id="w", profile="p", mode=op.ExecutionMode.PROMPT_ONLY
        ).validate()


class TestExecutionPlanValidate:
    def _ok_worker(self, name: str = "w") -> op.WorkerPlan:
        return op.WorkerPlan(
            worker_id=name,
            profile="p",
            mode=op.ExecutionMode.PROMPT_ONLY,
        )

    def test_empty_plan_rejected(self) -> None:
        with pytest.raises(op.OrchestratorError, match="at least one worker"):
            op.ExecutionPlan(job_id="job-1", workers=[]).validate()

    def test_missing_job_id(self) -> None:
        with pytest.raises(op.OrchestratorError, match="job_id"):
            op.ExecutionPlan(
                job_id="", workers=[self._ok_worker()]
            ).validate()

    def test_low_concurrency_rejected(self) -> None:
        with pytest.raises(op.OrchestratorError, match="concurrency"):
            op.ExecutionPlan(
                job_id="j", workers=[self._ok_worker()], concurrency=0
            ).validate()

    def test_excess_concurrency_rejected(self) -> None:
        with pytest.raises(op.OrchestratorError, match="exceeds safe cap"):
            op.ExecutionPlan(
                job_id="j",
                workers=[self._ok_worker()],
                concurrency=op.MAX_CONCURRENCY + 1,
            ).validate()

    def test_duplicate_worker_ids_rejected(self) -> None:
        plan = op.ExecutionPlan(
            job_id="j",
            workers=[self._ok_worker("dup"), self._ok_worker("dup")],
        )
        with pytest.raises(op.OrchestratorError, match="duplicate"):
            plan.validate()


# ── argv parsing ──────────────────────────────────────────────────────


class TestParseCommand:
    def test_string_is_split(self) -> None:
        assert op.parse_command("echo hi") == ["echo", "hi"]

    def test_list_passes_through(self) -> None:
        assert op.parse_command(["a", "b"]) == ["a", "b"]

    def test_quotes_are_respected(self) -> None:
        assert op.parse_command('echo "hello world"') == ["echo", "hello world"]


# ── filesystem helpers ────────────────────────────────────────────────


class TestFilesystemHelpers:
    def test_job_dir_under_orchestrator(self, tmp_path: Path) -> None:
        result = op.job_dir(tmp_path, "j-1")
        # Path order matches docs: <repo>/<ORCH>/jobs/<job>
        assert result.parent.name == op.JOBS_SUBDIR
        assert result.parent.parent.name == op.ORCHESTRATOR_DIRNAME

    def test_request_cancel_writes_flag_file(self, tmp_path: Path) -> None:
        path = op.request_cancel(tmp_path, "j-1")
        assert path.exists()
        assert path.name == op.CANCEL_FLAG_FILENAME

    def test_load_status_returns_none_when_missing(self, tmp_path: Path) -> None:
        assert op.load_status(tmp_path, "j-1") is None

    def test_list_jobs_returns_empty_when_no_orchestrator(
        self, tmp_path: Path
    ) -> None:
        assert op.list_jobs(tmp_path) == []


# ── PROMPT_ONLY end-to-end (no subprocess) ────────────────────────────


class TestPromptOnlyRunner:
    def test_prompt_only_writes_status_and_prompt(self, tmp_path: Path) -> None:
        plan = op.ExecutionPlan(
            job_id="j-prompt-only",
            workers=[
                op.WorkerPlan(
                    worker_id="w1",
                    profile="planner",
                    mode=op.ExecutionMode.PROMPT_ONLY,
                    prompt="Plan the work.",
                )
            ],
        )
        runner = op.ParallelRunner(tmp_path, plan)
        statuses = runner.run()
        status = statuses["w1"]
        assert status.state == op.WorkerState.COMPLETED
        # Prompt was persisted on disk for audit.
        prompt_path = (
            op.worker_dir(tmp_path, plan.job_id, "w1") / op.PROMPT_FILENAME
        )
        assert prompt_path.exists()
        assert "Plan the work." in prompt_path.read_text()
        # status.json was emitted.
        snapshot = op.load_status(tmp_path, plan.job_id)
        assert snapshot is not None
        assert plan.job_id == snapshot.get("job_id") or "workers" in snapshot

    def test_handoff_required_writes_handoff_json(self, tmp_path: Path) -> None:
        plan = op.ExecutionPlan(
            job_id="j-handoff",
            workers=[
                op.WorkerPlan(
                    worker_id="w1",
                    profile="chatgpt",
                    mode=op.ExecutionMode.HANDOFF_REQUIRED,
                    prompt="Paste me.",
                    handoff={"destination": "chatgpt", "tool": "manual"},
                )
            ],
        )
        runner = op.ParallelRunner(tmp_path, plan)
        statuses = runner.run()
        status = statuses["w1"]
        assert status.state == op.WorkerState.AWAITING_HANDOFF
        handoff_path = (
            op.worker_dir(tmp_path, plan.job_id, "w1") / op.HANDOFF_FILENAME
        )
        assert handoff_path.exists()
        payload = json.loads(handoff_path.read_text(encoding="utf-8"))
        assert payload["destination"] == "chatgpt"

    def test_cancel_before_run_marks_all_cancelled(self, tmp_path: Path) -> None:
        plan = op.ExecutionPlan(
            job_id="j-cancel",
            workers=[
                op.WorkerPlan(
                    worker_id=f"w{n}",
                    profile="p",
                    mode=op.ExecutionMode.PROMPT_ONLY,
                )
                for n in range(2)
            ],
        )
        runner = op.ParallelRunner(tmp_path, plan)
        runner.request_cancel()
        statuses = runner.run()
        # Pre-set cancel should mark every worker as CANCELLED.
        assert all(
            s.state == op.WorkerState.CANCELLED for s in statuses.values()
        )

    def test_list_jobs_returns_completed_job(self, tmp_path: Path) -> None:
        plan = op.ExecutionPlan(
            job_id="j-listme",
            workers=[
                op.WorkerPlan(
                    worker_id="w1",
                    profile="p",
                    mode=op.ExecutionMode.PROMPT_ONLY,
                )
            ],
        )
        op.ParallelRunner(tmp_path, plan).run()
        assert "j-listme" in op.list_jobs(tmp_path)
