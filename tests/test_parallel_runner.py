"""Tests for ``muse_cli.parallel_runner`` (Phase 13).

These run against an ephemeral git repo in ``tmp_path``. Subprocess
based workers use ``sys.executable -c "..."`` so they are deterministic
on Linux, macOS, and Windows runners.
"""

from __future__ import annotations

from pathlib import Path
import json
import subprocess
import sys
import threading
import time

import pytest

from muse_cli import parallel_runner as pr
from muse_cli import worktrees as wt


# ─── fixtures / helpers ──────────────────────────────────────────────


def _run(cmd: list[str], cwd: Path) -> str:
    proc = subprocess.run(
        cmd, cwd=str(cwd), capture_output=True, text=True, check=True
    )
    return proc.stdout


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    path = tmp_path / "repo"
    path.mkdir()
    _run(["git", "init", "-q", "-b", "main"], path)
    _run(["git", "config", "user.email", "test@example.com"], path)
    _run(["git", "config", "user.name", "Test"], path)
    _run(["git", "config", "commit.gpgsign", "false"], path)
    (path / "README.md").write_text("hello\n", encoding="utf-8")
    _run(["git", "add", "README.md"], path)
    _run(["git", "commit", "-q", "-m", "init"], path)
    return path


def _py(*lines: str) -> list[str]:
    return [sys.executable, "-c", "\n".join(lines)]


# ─── ExecutionPlan / WorkerPlan validation ───────────────────────────


def test_worker_plan_requires_id_and_profile():
    with pytest.raises(pr.RunnerError):
        pr.WorkerPlan(
            worker_id="", profile="p", mode=pr.ExecutionMode.PROMPT_ONLY
        ).validate()
    with pytest.raises(pr.RunnerError):
        pr.WorkerPlan(
            worker_id="w", profile="", mode=pr.ExecutionMode.PROMPT_ONLY
        ).validate()


def test_worker_plan_local_run_requires_command():
    with pytest.raises(pr.RunnerError, match="requires a command"):
        pr.WorkerPlan(
            worker_id="w", profile="p", mode=pr.ExecutionMode.LOCAL_RUN
        ).validate()


def test_worker_plan_remote_run_requires_command():
    with pytest.raises(pr.RunnerError, match="requires a command"):
        pr.WorkerPlan(
            worker_id="w", profile="p", mode=pr.ExecutionMode.REMOTE_RUN
        ).validate()


@pytest.mark.parametrize(
    "command",
    [
        ["bash", "-c", "git push origin main"],
        ["bash", "-c", "git reset --hard HEAD~5"],
        ["sh", "-c", "rm -rf /"],
        ["bash", "-c", "git push --force"],
    ],
)
def test_worker_plan_rejects_destructive_commands(command: list[str]):
    with pytest.raises(pr.RunnerError, match="forbidden token"):
        pr.WorkerPlan(
            worker_id="w",
            profile="p",
            mode=pr.ExecutionMode.LOCAL_RUN,
            command=command,
        ).validate()


def test_worker_plan_handoff_requires_payload():
    with pytest.raises(pr.RunnerError, match="handoff"):
        pr.WorkerPlan(
            worker_id="w", profile="p", mode=pr.ExecutionMode.HANDOFF_REQUIRED
        ).validate()


def test_worker_plan_timeout_must_be_positive():
    with pytest.raises(pr.RunnerError, match="timeout_seconds"):
        pr.WorkerPlan(
            worker_id="w",
            profile="p",
            mode=pr.ExecutionMode.PROMPT_ONLY,
            timeout_seconds=0,
        ).validate()


def test_worker_plan_timeout_capped():
    with pytest.raises(pr.RunnerError, match="exceeds cap"):
        pr.WorkerPlan(
            worker_id="w",
            profile="p",
            mode=pr.ExecutionMode.PROMPT_ONLY,
            timeout_seconds=pr.MAX_TIMEOUT_SECONDS + 1,
        ).validate()


def test_execution_plan_rejects_high_concurrency():
    with pytest.raises(pr.RunnerError, match="exceeds safe cap"):
        pr.ExecutionPlan(
            job_id="j",
            workers=[pr.WorkerPlan("w", "p", pr.ExecutionMode.PROMPT_ONLY)],
            concurrency=pr.MAX_CONCURRENCY + 1,
        ).validate()


def test_execution_plan_rejects_duplicate_worker_ids():
    with pytest.raises(pr.RunnerError, match="duplicate"):
        pr.ExecutionPlan(
            job_id="j",
            workers=[
                pr.WorkerPlan("w", "p", pr.ExecutionMode.PROMPT_ONLY),
                pr.WorkerPlan("w", "p2", pr.ExecutionMode.PROMPT_ONLY),
            ],
        ).validate()


def test_execution_plan_default_approval_is_pending():
    plan = pr.ExecutionPlan(
        job_id="j",
        workers=[pr.WorkerPlan("w", "p", pr.ExecutionMode.PROMPT_ONLY)],
    )
    assert plan.approval_state is pr.ApprovalState.PENDING


def test_execution_plan_has_remote_run_helper():
    plan = pr.ExecutionPlan(
        job_id="j",
        workers=[
            pr.WorkerPlan(
                "w",
                "p",
                pr.ExecutionMode.REMOTE_RUN,
                command=_py("print(1)"),
            )
        ],
    )
    assert plan.has_remote_run() is True
    other = pr.ExecutionPlan(
        job_id="j2",
        workers=[pr.WorkerPlan("w", "p", pr.ExecutionMode.PROMPT_ONLY)],
    )
    assert other.has_remote_run() is False


def test_with_approval_returns_new_plan():
    plan = pr.ExecutionPlan(
        job_id="j",
        workers=[pr.WorkerPlan("w", "p", pr.ExecutionMode.PROMPT_ONLY)],
    )
    approved = plan.with_approval(pr.ApprovalState.APPROVED)
    assert approved is not plan
    assert approved.approval_state is pr.ApprovalState.APPROVED
    assert plan.approval_state is pr.ApprovalState.PENDING


# ─── prompt-only / handoff modes ─────────────────────────────────────


def test_prompt_only_marks_completed_and_writes_prompt(repo: Path):
    plan = pr.ExecutionPlan(
        job_id="job-1",
        workers=[
            pr.WorkerPlan(
                worker_id="w1",
                profile="researcher",
                mode=pr.ExecutionMode.PROMPT_ONLY,
                prompt="Investigate X.",
            )
        ],
    )
    statuses = pr.ParallelRunner(repo, plan).run()
    s = statuses["w1"]
    assert s.state is pr.WorkerState.COMPLETED
    assert s.return_code is None
    assert Path(s.prompt_path or "").read_text(encoding="utf-8") == "Investigate X."


def test_handoff_required_writes_handoff(repo: Path):
    plan = pr.ExecutionPlan(
        job_id="job-2",
        workers=[
            pr.WorkerPlan(
                worker_id="w1",
                profile="copy-paster",
                mode=pr.ExecutionMode.HANDOFF_REQUIRED,
                prompt="Paste this elsewhere.",
                handoff={"target": "chatgpt", "intent": "draft"},
            )
        ],
    )
    statuses = pr.ParallelRunner(repo, plan).run()
    s = statuses["w1"]
    assert s.state is pr.WorkerState.AWAITING_HANDOFF
    payload = json.loads(Path(s.handoff_path or "").read_text(encoding="utf-8"))
    assert payload == {"target": "chatgpt", "intent": "draft"}


# ─── local-run mode ──────────────────────────────────────────────────


def test_local_run_captures_stdout(repo: Path):
    plan = pr.ExecutionPlan(
        job_id="job-3",
        workers=[
            pr.WorkerPlan(
                worker_id="w1",
                profile="bash",
                mode=pr.ExecutionMode.LOCAL_RUN,
                command=_py("print('hello world')"),
                timeout_seconds=10,
            )
        ],
    )
    statuses = pr.ParallelRunner(repo, plan, poll_interval=0.05).run()
    s = statuses["w1"]
    assert s.state is pr.WorkerState.COMPLETED
    assert s.return_code == 0
    assert "hello world" in Path(s.stdout_path or "").read_text(encoding="utf-8")


def test_local_run_failure_records_exit_code(repo: Path):
    plan = pr.ExecutionPlan(
        job_id="job-4",
        workers=[
            pr.WorkerPlan(
                worker_id="w1",
                profile="bash",
                mode=pr.ExecutionMode.LOCAL_RUN,
                command=_py(
                    "import sys",
                    "sys.stderr.write('boom\\n')",
                    "sys.exit(7)",
                ),
                timeout_seconds=10,
            )
        ],
    )
    statuses = pr.ParallelRunner(repo, plan, poll_interval=0.05).run()
    s = statuses["w1"]
    assert s.state is pr.WorkerState.FAILED
    assert s.return_code == 7
    assert "boom" in Path(s.stderr_path or "").read_text(encoding="utf-8")


def test_local_run_command_not_found(repo: Path):
    plan = pr.ExecutionPlan(
        job_id="job-nf",
        workers=[
            pr.WorkerPlan(
                worker_id="w1",
                profile="bash",
                mode=pr.ExecutionMode.LOCAL_RUN,
                command=["definitely-not-a-real-binary-2026"],
                timeout_seconds=5,
            )
        ],
    )
    statuses = pr.ParallelRunner(repo, plan, poll_interval=0.05).run()
    s = statuses["w1"]
    assert s.state is pr.WorkerState.FAILED
    assert s.error and "command not found" in s.error


# ─── remote-run gating ───────────────────────────────────────────────


def test_remote_run_blocked_without_approval(repo: Path):
    plan = pr.ExecutionPlan(
        job_id="job-r",
        workers=[
            pr.WorkerPlan(
                worker_id="w1",
                profile="remote",
                mode=pr.ExecutionMode.REMOTE_RUN,
                command=_py("print('should not run')"),
                timeout_seconds=5,
            )
        ],
        approval_state=pr.ApprovalState.PENDING,
    )
    statuses = pr.ParallelRunner(repo, plan, poll_interval=0.05).run()
    s = statuses["w1"]
    assert s.state is pr.WorkerState.BLOCKED_BY_APPROVAL
    assert s.error and "approval" in s.error.lower()
    # The stdout log file should NOT have been opened — no subprocess ran.
    assert s.stdout_path is None


def test_remote_run_rejected_state_also_blocks(repo: Path):
    plan = pr.ExecutionPlan(
        job_id="job-rj",
        workers=[
            pr.WorkerPlan(
                worker_id="w1",
                profile="remote",
                mode=pr.ExecutionMode.REMOTE_RUN,
                command=_py("print('nope')"),
            )
        ],
        approval_state=pr.ApprovalState.REJECTED,
    )
    statuses = pr.ParallelRunner(repo, plan).run()
    assert statuses["w1"].state is pr.WorkerState.BLOCKED_BY_APPROVAL


def test_remote_run_executes_when_approved(repo: Path):
    plan = pr.ExecutionPlan(
        job_id="job-ra",
        workers=[
            pr.WorkerPlan(
                worker_id="w1",
                profile="remote",
                mode=pr.ExecutionMode.REMOTE_RUN,
                command=_py("print('remote ok')"),
                timeout_seconds=10,
            )
        ],
        approval_state=pr.ApprovalState.APPROVED,
    )
    statuses = pr.ParallelRunner(repo, plan, poll_interval=0.05).run()
    s = statuses["w1"]
    assert s.state is pr.WorkerState.COMPLETED
    assert "remote ok" in Path(s.stdout_path or "").read_text(encoding="utf-8")


# ─── concurrency / cancellation ──────────────────────────────────────


def test_concurrent_run_is_faster_than_serial(repo: Path):
    def _run(concurrency: int) -> float:
        workers = [
            pr.WorkerPlan(
                worker_id=f"w{i}",
                profile="bash",
                mode=pr.ExecutionMode.LOCAL_RUN,
                command=_py("import time", "time.sleep(0.4)"),
                timeout_seconds=10,
            )
            for i in range(3)
        ]
        plan = pr.ExecutionPlan(
            job_id=f"job-c{concurrency}", workers=workers, concurrency=concurrency
        )
        start = time.monotonic()
        statuses = pr.ParallelRunner(repo, plan, poll_interval=0.05).run()
        elapsed = time.monotonic() - start
        assert all(s.state is pr.WorkerState.COMPLETED for s in statuses.values())
        return elapsed

    # Compare against a serial baseline measured under the SAME conditions, so
    # the assertion holds regardless of absolute machine / CI-runner load (the
    # old hard `< 1.1s` wall-clock flaked on busy runners). Three 0.4s sleeps
    # overlap under concurrency=3, so the concurrent run must beat the serial
    # run (~1.2s of sleeps) by a clear margin.
    serial = _run(1)
    concurrent = _run(3)
    assert concurrent < serial - 0.3, (
        f"concurrent={concurrent:.2f}s not clearly faster than serial={serial:.2f}s"
    )


def test_sequential_run_is_serial(repo: Path):
    workers = [
        pr.WorkerPlan(
            worker_id=f"w{i}",
            profile="bash",
            mode=pr.ExecutionMode.LOCAL_RUN,
            command=_py("import time", "time.sleep(0.25)"),
            timeout_seconds=10,
        )
        for i in range(2)
    ]
    plan = pr.ExecutionPlan(job_id="job-s", workers=workers, concurrency=1)
    start = time.monotonic()
    pr.ParallelRunner(repo, plan, poll_interval=0.05).run()
    elapsed = time.monotonic() - start
    assert elapsed >= 0.4


@pytest.mark.live_system_guard_bypass
def test_cancel_flag_aborts_running_worker(repo: Path):
    plan = pr.ExecutionPlan(
        job_id="job-cancel",
        workers=[
            pr.WorkerPlan(
                worker_id="w1",
                profile="bash",
                mode=pr.ExecutionMode.LOCAL_RUN,
                command=_py("import time", "time.sleep(30)"),
                timeout_seconds=60,
            )
        ],
    )
    runner = pr.ParallelRunner(repo, plan, poll_interval=0.05)

    def _trip():
        time.sleep(0.4)
        pr.request_cancel(repo, "job-cancel")

    t = threading.Thread(target=_trip, daemon=True)
    t.start()
    statuses = runner.run()
    t.join(timeout=10)

    assert statuses["w1"].state is pr.WorkerState.CANCELLED
    assert pr.cancel_flag_path(repo, "job-cancel").exists()


@pytest.mark.live_system_guard_bypass
def test_runner_request_cancel_method(repo: Path):
    plan = pr.ExecutionPlan(
        job_id="job-c2",
        workers=[
            pr.WorkerPlan(
                worker_id="w1",
                profile="bash",
                mode=pr.ExecutionMode.LOCAL_RUN,
                command=_py("import time", "time.sleep(30)"),
                timeout_seconds=60,
            )
        ],
    )
    runner = pr.ParallelRunner(repo, plan, poll_interval=0.05)

    def _trip():
        time.sleep(0.4)
        runner.request_cancel()

    t = threading.Thread(target=_trip, daemon=True)
    t.start()
    statuses = runner.run()
    t.join(timeout=10)
    assert statuses["w1"].state is pr.WorkerState.CANCELLED


def test_clear_cancel_removes_flag(repo: Path):
    pr.request_cancel(repo, "j")
    assert pr.cancel_flag_path(repo, "j").exists()
    assert pr.clear_cancel(repo, "j") is True
    assert not pr.cancel_flag_path(repo, "j").exists()
    assert pr.clear_cancel(repo, "j") is False


def test_status_callback_invoked(repo: Path):
    seen: list[tuple[str, str]] = []

    def cb(status: pr.WorkerStatus) -> None:
        seen.append((status.worker_id, status.state.value))

    plan = pr.ExecutionPlan(
        job_id="job-cb",
        workers=[
            pr.WorkerPlan(
                worker_id="w1",
                profile="p",
                mode=pr.ExecutionMode.PROMPT_ONLY,
                prompt="x",
            )
        ],
    )
    pr.ParallelRunner(repo, plan, on_status=cb).run()
    assert any(state == pr.WorkerState.COMPLETED.value for _, state in seen)


# ─── resume ──────────────────────────────────────────────────────────


def test_resume_skips_completed_workers(repo: Path):
    plan = pr.ExecutionPlan(
        job_id="job-resume",
        workers=[
            pr.WorkerPlan(
                worker_id="w1",
                profile="p",
                mode=pr.ExecutionMode.PROMPT_ONLY,
                prompt="first",
            ),
            pr.WorkerPlan(
                worker_id="w2",
                profile="p",
                mode=pr.ExecutionMode.LOCAL_RUN,
                command=_py("print('second')"),
                timeout_seconds=10,
            ),
        ],
    )
    first = pr.ParallelRunner(repo, plan, poll_interval=0.05).run()
    assert first["w1"].state is pr.WorkerState.COMPLETED
    assert first["w2"].state is pr.WorkerState.COMPLETED

    # Second pass with resume=True should skip both as already done.
    second = pr.ParallelRunner(repo, plan, poll_interval=0.05, resume=True).run()
    assert second["w1"].state is pr.WorkerState.SKIPPED_RESUMED
    assert second["w2"].state is pr.WorkerState.SKIPPED_RESUMED


def test_resume_reruns_failed_workers(repo: Path):
    plan = pr.ExecutionPlan(
        job_id="job-resume-fail",
        workers=[
            pr.WorkerPlan(
                worker_id="w1",
                profile="bash",
                mode=pr.ExecutionMode.LOCAL_RUN,
                command=_py("import sys", "sys.exit(3)"),
                timeout_seconds=5,
            ),
        ],
    )
    first = pr.ParallelRunner(repo, plan, poll_interval=0.05).run()
    assert first["w1"].state is pr.WorkerState.FAILED
    assert first["w1"].attempt == 1

    # Rerun with a green command and resume — failed workers should retry.
    plan2 = pr.ExecutionPlan(
        job_id="job-resume-fail",
        workers=[
            pr.WorkerPlan(
                worker_id="w1",
                profile="bash",
                mode=pr.ExecutionMode.LOCAL_RUN,
                command=_py("print('green')"),
                timeout_seconds=5,
            ),
        ],
    )
    second = pr.ParallelRunner(repo, plan2, poll_interval=0.05, resume=True).run()
    assert second["w1"].state is pr.WorkerState.COMPLETED
    assert second["w1"].attempt == 2


def test_resume_without_prior_status_is_safe(repo: Path):
    plan = pr.ExecutionPlan(
        job_id="job-resume-fresh",
        workers=[
            pr.WorkerPlan(
                worker_id="w1",
                profile="p",
                mode=pr.ExecutionMode.PROMPT_ONLY,
                prompt="x",
            )
        ],
    )
    statuses = pr.ParallelRunner(repo, plan, resume=True).run()
    assert statuses["w1"].state is pr.WorkerState.COMPLETED


# ─── worktree integration ────────────────────────────────────────────


def test_worktree_mode_provisions_isolated_branches(repo: Path):
    plan = pr.ExecutionPlan(
        job_id="job-wt",
        workers=[
            pr.WorkerPlan(
                worker_id=f"w{i}",
                profile="p",
                mode=pr.ExecutionMode.LOCAL_RUN,
                command=_py("print('done')"),
                timeout_seconds=10,
                use_worktree=True,
            )
            for i in range(2)
        ],
        concurrency=2,
        use_worktrees=True,
    )
    statuses = pr.ParallelRunner(repo, plan, poll_interval=0.05).run()
    assert {s.state for s in statuses.values()} == {pr.WorkerState.COMPLETED}

    branches = sorted(
        line.lstrip(" *+").strip()
        for line in _run(["git", "branch"], repo).splitlines()
        if line.strip()
    )
    assert "hermes/job-wt/w0" in branches
    assert "hermes/job-wt/w1" in branches

    infos = wt.list_worktrees(repo)
    assert {i.worker_id for i in infos} == {"w0", "w1"}


def test_worktree_creation_refuses_dirty_repo(repo: Path):
    (repo / "dirty.txt").write_text("x", encoding="utf-8")
    plan = pr.ExecutionPlan(
        job_id="job-dirty",
        workers=[
            pr.WorkerPlan(
                worker_id="w1",
                profile="p",
                mode=pr.ExecutionMode.PROMPT_ONLY,
                prompt="x",
                use_worktree=True,
            )
        ],
        use_worktrees=True,
    )
    runner = pr.ParallelRunner(repo, plan)
    with pytest.raises(wt.WorktreeError, match="uncommitted"):
        runner.run()


def test_cleanup_job_worktrees_requires_confirm(repo: Path):
    plan = pr.ExecutionPlan(
        job_id="job-clean",
        workers=[
            pr.WorkerPlan(
                worker_id="w1",
                profile="p",
                mode=pr.ExecutionMode.PROMPT_ONLY,
                prompt="x",
                use_worktree=True,
            )
        ],
        use_worktrees=True,
    )
    pr.ParallelRunner(repo, plan).run()

    removed = pr.cleanup_job_worktrees(repo, "job-clean")
    assert removed == []
    assert wt.worktree_path(repo, "job-clean", "w1").exists()

    removed = pr.cleanup_job_worktrees(
        repo, "job-clean", confirm_destructive=True, delete_branches=True
    )
    assert removed == ["w1"]
    assert not wt.worktree_path(repo, "job-clean", "w1").exists()


# ─── persistence ─────────────────────────────────────────────────────


def test_status_json_includes_approval_state(repo: Path):
    plan = pr.ExecutionPlan(
        job_id="job-status",
        workers=[
            pr.WorkerPlan(
                worker_id="w1",
                profile="p",
                mode=pr.ExecutionMode.PROMPT_ONLY,
                prompt="x",
            )
        ],
        approval_state=pr.ApprovalState.APPROVED,
        description="Phase-13 status test",
    )
    pr.ParallelRunner(repo, plan).run()
    payload = pr.load_status(repo, "job-status")
    assert payload is not None
    assert payload["approval_state"] == "approved"
    assert payload["description"] == "Phase-13 status test"
    assert payload["created_at"] <= payload["updated_at"]


def test_list_jobs_returns_completed_runs(repo: Path):
    for jid in ("alpha", "beta"):
        plan = pr.ExecutionPlan(
            job_id=jid,
            workers=[
                pr.WorkerPlan(
                    worker_id="w1",
                    profile="p",
                    mode=pr.ExecutionMode.PROMPT_ONLY,
                    prompt="x",
                )
            ],
        )
        pr.ParallelRunner(repo, plan).run()
    assert pr.list_jobs(repo) == ["alpha", "beta"]


def test_parse_command_handles_strings_and_lists():
    assert pr.parse_command("python -c 'print(1)'") == [
        "python",
        "-c",
        "print(1)",
    ]
    assert pr.parse_command(["python", "-c", "print(1)"]) == [
        "python",
        "-c",
        "print(1)",
    ]


def test_worker_status_from_dict_handles_unknown_state():
    s = pr.WorkerStatus.from_dict(
        {
            "worker_id": "w1",
            "profile": "p",
            "mode": "prompt-only",
            "state": "garbage-not-a-state",
        }
    )
    assert s.state is pr.WorkerState.PENDING
