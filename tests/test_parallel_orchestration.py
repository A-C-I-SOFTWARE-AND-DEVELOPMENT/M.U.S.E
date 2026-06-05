"""Tests for ``hermes_cli.orchestrator_parallel``.

These tests run against an isolated git repo in ``tmp_path``. The runner
uses real subprocesses for ``local-run`` workers so we can verify
timeout, cancellation, and exit-code handling.
"""

from __future__ import annotations

from pathlib import Path
import json
import subprocess
import sys
import threading
import time

import pytest

from hermes_cli import orchestrator_parallel as op
from hermes_cli import worktrees as wt


# ─── helpers ──────────────────────────────────────────────────────────


def _run(cmd: list[str], cwd: Path) -> str:
    proc = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, check=True)
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


def _python_command(*lines: str) -> list[str]:
    """Build a ``python -c "..."`` argv list for cross-platform tests."""

    return [sys.executable, "-c", "\n".join(lines)]


# ─── plan validation ──────────────────────────────────────────────────


def test_worker_plan_validate_requires_id_and_profile():
    with pytest.raises(op.OrchestratorError):
        op.WorkerPlan(worker_id="", profile="p", mode=op.ExecutionMode.PROMPT_ONLY).validate()
    with pytest.raises(op.OrchestratorError):
        op.WorkerPlan(worker_id="w", profile="", mode=op.ExecutionMode.PROMPT_ONLY).validate()


def test_worker_plan_local_run_requires_command():
    with pytest.raises(op.OrchestratorError, match="no command"):
        op.WorkerPlan(
            worker_id="w", profile="p", mode=op.ExecutionMode.LOCAL_RUN
        ).validate()


def test_worker_plan_local_run_rejects_destructive_command():
    with pytest.raises(op.OrchestratorError, match="forbidden token"):
        op.WorkerPlan(
            worker_id="w",
            profile="p",
            mode=op.ExecutionMode.LOCAL_RUN,
            command=["bash", "-c", "git push origin main"],
        ).validate()
    with pytest.raises(op.OrchestratorError, match="forbidden token"):
        op.WorkerPlan(
            worker_id="w",
            profile="p",
            mode=op.ExecutionMode.LOCAL_RUN,
            command=["bash", "-c", "git reset --hard"],
        ).validate()


def test_worker_plan_handoff_requires_payload():
    with pytest.raises(op.OrchestratorError, match="handoff"):
        op.WorkerPlan(
            worker_id="w", profile="p", mode=op.ExecutionMode.HANDOFF_REQUIRED
        ).validate()


def test_execution_plan_rejects_high_concurrency():
    with pytest.raises(op.OrchestratorError, match="exceeds safe cap"):
        op.ExecutionPlan(
            job_id="j",
            workers=[op.WorkerPlan("w", "p", op.ExecutionMode.PROMPT_ONLY)],
            concurrency=op.MAX_CONCURRENCY + 1,
        ).validate()


def test_execution_plan_rejects_duplicate_worker_ids():
    with pytest.raises(op.OrchestratorError, match="duplicate"):
        op.ExecutionPlan(
            job_id="j",
            workers=[
                op.WorkerPlan("w", "p", op.ExecutionMode.PROMPT_ONLY),
                op.WorkerPlan("w", "p2", op.ExecutionMode.PROMPT_ONLY),
            ],
        ).validate()


# ─── prompt-only / handoff modes ─────────────────────────────────────


def test_prompt_only_writes_prompt_and_marks_completed(repo: Path):
    plan = op.ExecutionPlan(
        job_id="job-1",
        workers=[
            op.WorkerPlan(
                worker_id="w1",
                profile="researcher",
                mode=op.ExecutionMode.PROMPT_ONLY,
                prompt="Investigate X.",
            )
        ],
    )
    runner = op.ParallelRunner(repo, plan)
    statuses = runner.run()

    s = statuses["w1"]
    assert s.state is op.WorkerState.COMPLETED
    assert s.return_code is None
    assert Path(s.prompt_path or "").read_text(encoding="utf-8") == "Investigate X."

    snapshot = op.load_status(repo, "job-1")
    assert snapshot is not None
    assert snapshot["workers"][0]["state"] == op.WorkerState.COMPLETED.value


def test_handoff_required_writes_handoff_and_marks_awaiting(repo: Path):
    plan = op.ExecutionPlan(
        job_id="job-2",
        workers=[
            op.WorkerPlan(
                worker_id="w1",
                profile="copy-paster",
                mode=op.ExecutionMode.HANDOFF_REQUIRED,
                prompt="Paste this into ChatGPT.",
                handoff={"target": "chatgpt", "intent": "draft"},
            )
        ],
    )
    statuses = op.ParallelRunner(repo, plan).run()

    s = statuses["w1"]
    assert s.state is op.WorkerState.AWAITING_HANDOFF
    payload = json.loads(Path(s.handoff_path or "").read_text(encoding="utf-8"))
    assert payload == {"target": "chatgpt", "intent": "draft"}


# ─── local-run mode ──────────────────────────────────────────────────


def test_local_run_success_captures_stdout(repo: Path):
    plan = op.ExecutionPlan(
        job_id="job-3",
        workers=[
            op.WorkerPlan(
                worker_id="w1",
                profile="bash",
                mode=op.ExecutionMode.LOCAL_RUN,
                command=_python_command("print('hello world')"),
                timeout_seconds=10,
            )
        ],
    )
    statuses = op.ParallelRunner(repo, plan, poll_interval=0.05).run()

    s = statuses["w1"]
    assert s.state is op.WorkerState.COMPLETED
    assert s.return_code == 0
    assert "hello world" in Path(s.stdout_path or "").read_text(encoding="utf-8")
    assert Path(s.stderr_path or "").read_text(encoding="utf-8") == ""


def test_local_run_failure_records_exit_code(repo: Path):
    plan = op.ExecutionPlan(
        job_id="job-4",
        workers=[
            op.WorkerPlan(
                worker_id="w1",
                profile="bash",
                mode=op.ExecutionMode.LOCAL_RUN,
                command=_python_command(
                    "import sys",
                    "sys.stderr.write('boom\\n')",
                    "sys.exit(7)",
                ),
                timeout_seconds=10,
            )
        ],
    )
    statuses = op.ParallelRunner(repo, plan, poll_interval=0.05).run()

    s = statuses["w1"]
    assert s.state is op.WorkerState.FAILED
    assert s.return_code == 7
    assert "boom" in Path(s.stderr_path or "").read_text(encoding="utf-8")


@pytest.mark.live_system_guard_bypass
def test_local_run_times_out(repo: Path):
    plan = op.ExecutionPlan(
        job_id="job-5",
        workers=[
            op.WorkerPlan(
                worker_id="w1",
                profile="bash",
                mode=op.ExecutionMode.LOCAL_RUN,
                command=_python_command(
                    "import time",
                    "time.sleep(10)",
                ),
                timeout_seconds=1,
            )
        ],
    )
    statuses = op.ParallelRunner(repo, plan, poll_interval=0.05).run()

    s = statuses["w1"]
    assert s.state is op.WorkerState.TIMED_OUT
    assert s.error and "timeout" in s.error


def test_local_run_command_not_found(repo: Path):
    plan = op.ExecutionPlan(
        job_id="job-6",
        workers=[
            op.WorkerPlan(
                worker_id="w1",
                profile="bash",
                mode=op.ExecutionMode.LOCAL_RUN,
                command=["definitely-not-a-real-binary-2026"],
                timeout_seconds=5,
            )
        ],
    )
    statuses = op.ParallelRunner(repo, plan, poll_interval=0.05).run()
    s = statuses["w1"]
    assert s.state is op.WorkerState.FAILED
    assert s.error and "command not found" in s.error


# ─── concurrency / cancellation ──────────────────────────────────────


def test_concurrent_run_finishes_under_sum_of_durations(repo: Path):
    workers = [
        op.WorkerPlan(
            worker_id=f"w{i}",
            profile="bash",
            mode=op.ExecutionMode.LOCAL_RUN,
            command=_python_command("import time", "time.sleep(0.4)"),
            timeout_seconds=5,
        )
        for i in range(3)
    ]
    plan = op.ExecutionPlan(job_id="job-c", workers=workers, concurrency=3)
    start = time.monotonic()
    statuses = op.ParallelRunner(repo, plan, poll_interval=0.05).run()
    elapsed = time.monotonic() - start

    assert all(s.state is op.WorkerState.COMPLETED for s in statuses.values())
    # sequential would be ~1.2s; concurrent should be well under that
    assert elapsed < 1.0, f"concurrent run took {elapsed:.2f}s — not concurrent?"


def test_sequential_run_is_serial(repo: Path):
    workers = [
        op.WorkerPlan(
            worker_id=f"w{i}",
            profile="bash",
            mode=op.ExecutionMode.LOCAL_RUN,
            command=_python_command("import time", "time.sleep(0.2)"),
            timeout_seconds=5,
        )
        for i in range(2)
    ]
    plan = op.ExecutionPlan(job_id="job-s", workers=workers, concurrency=1)
    start = time.monotonic()
    op.ParallelRunner(repo, plan, poll_interval=0.05).run()
    elapsed = time.monotonic() - start
    # Two 0.2s sleeps in sequence should be >= 0.4s; concurrent would be ~0.2s
    assert elapsed >= 0.35


@pytest.mark.live_system_guard_bypass
def test_cancel_flag_aborts_running_worker(repo: Path):
    plan = op.ExecutionPlan(
        job_id="job-cancel",
        workers=[
            op.WorkerPlan(
                worker_id="w1",
                profile="bash",
                mode=op.ExecutionMode.LOCAL_RUN,
                command=_python_command("import time", "time.sleep(20)"),
                timeout_seconds=30,
            )
        ],
    )
    runner = op.ParallelRunner(repo, plan, poll_interval=0.05)

    def _trip_cancel():
        time.sleep(0.3)
        op.request_cancel(repo, "job-cancel")

    t = threading.Thread(target=_trip_cancel, daemon=True)
    t.start()
    statuses = runner.run()
    t.join(timeout=5)

    s = statuses["w1"]
    assert s.state is op.WorkerState.CANCELLED
    assert op.cancel_flag_path(repo, "job-cancel").exists()


def test_status_callback_is_invoked(repo: Path):
    seen: list[tuple[str, str]] = []

    def cb(status: op.WorkerStatus) -> None:
        seen.append((status.worker_id, status.state.value))

    plan = op.ExecutionPlan(
        job_id="job-cb",
        workers=[
            op.WorkerPlan(
                worker_id="w1",
                profile="p",
                mode=op.ExecutionMode.PROMPT_ONLY,
                prompt="x",
            )
        ],
    )
    op.ParallelRunner(repo, plan, on_status=cb).run()
    assert any(state == op.WorkerState.COMPLETED.value for (_, state) in seen)


# ─── worktree integration ────────────────────────────────────────────


def test_worktree_mode_provisions_isolated_branches(repo: Path):
    plan = op.ExecutionPlan(
        job_id="job-wt",
        workers=[
            op.WorkerPlan(
                worker_id=f"w{i}",
                profile="p",
                mode=op.ExecutionMode.LOCAL_RUN,
                command=_python_command("print('done')"),
                timeout_seconds=10,
                use_worktree=True,
            )
            for i in range(2)
        ],
        concurrency=2,
        use_worktrees=True,
    )
    statuses = op.ParallelRunner(repo, plan, poll_interval=0.05).run()

    assert {s.state for s in statuses.values()} == {op.WorkerState.COMPLETED}

    # git branch shows ``+ name`` for branches checked out in another
    # worktree and ``* name`` for the currently active one. Strip both.
    branches = sorted(
        line.lstrip(" *+").strip()
        for line in _run(["git", "branch"], repo).splitlines()
        if line.strip()
    )
    assert "hermes/job-wt/w0" in branches
    assert "hermes/job-wt/w1" in branches

    infos = wt.list_worktrees(repo)
    assert {i.worker_id for i in infos} == {"w0", "w1"}


def test_cleanup_job_worktrees_requires_confirm(repo: Path):
    plan = op.ExecutionPlan(
        job_id="job-clean",
        workers=[
            op.WorkerPlan(
                worker_id="w1",
                profile="p",
                mode=op.ExecutionMode.PROMPT_ONLY,
                prompt="x",
                use_worktree=True,
            )
        ],
        use_worktrees=True,
    )
    op.ParallelRunner(repo, plan).run()

    # default: no destructive action
    removed = op.cleanup_job_worktrees(repo, "job-clean")
    assert removed == []
    assert wt.worktree_path(repo, "job-clean", "w1").exists()

    # opt-in: actually cleans up
    removed = op.cleanup_job_worktrees(
        repo, "job-clean", confirm_destructive=True, delete_branches=True
    )
    assert removed == ["w1"]
    assert not wt.worktree_path(repo, "job-clean", "w1").exists()


# ─── persistence ─────────────────────────────────────────────────────


def test_status_json_is_written_each_update(repo: Path):
    plan = op.ExecutionPlan(
        job_id="job-status",
        workers=[
            op.WorkerPlan(
                worker_id="w1",
                profile="p",
                mode=op.ExecutionMode.PROMPT_ONLY,
                prompt="x",
            ),
            op.WorkerPlan(
                worker_id="w2",
                profile="p",
                mode=op.ExecutionMode.HANDOFF_REQUIRED,
                handoff={"target": "claude"},
            ),
        ],
    )
    op.ParallelRunner(repo, plan).run()

    payload = op.load_status(repo, "job-status")
    assert payload is not None
    assert payload["job_id"] == "job-status"
    assert payload["created_at"] <= payload["updated_at"]
    states = {w["worker_id"]: w["state"] for w in payload["workers"]}
    assert states["w1"] == op.WorkerState.COMPLETED.value
    assert states["w2"] == op.WorkerState.AWAITING_HANDOFF.value


def test_list_jobs_reflects_completed_runs(repo: Path):
    for jid in ("alpha", "beta"):
        plan = op.ExecutionPlan(
            job_id=jid,
            workers=[
                op.WorkerPlan(
                    worker_id="w1",
                    profile="p",
                    mode=op.ExecutionMode.PROMPT_ONLY,
                    prompt="x",
                )
            ],
        )
        op.ParallelRunner(repo, plan).run()

    assert op.list_jobs(repo) == ["alpha", "beta"]


# ─── usage emission (producer side of the per-job cost seam) ──────────


def _usage_writer_command(usage_path: Path) -> list[str]:
    """A LOCAL_RUN command that writes a usage sidecar then exits 0.

    Stands in for a real worker that ran the agent and dumped
    ``agent.conversation_loop.build_usage_record`` to ``usage.json``.
    """

    payload = {
        "usage": {
            "input_tokens": 1200,
            "output_tokens": 300,
            "cache_read_tokens": 800,
            "cache_write_tokens": 0,
            "reasoning_tokens": 40,
        },
        "cost_usd": 0.0731,
        "model": "claude-opus-4-8",
        "provider": "anthropic",
    }
    return _python_command(
        "import json, pathlib",
        f"p = pathlib.Path(r{str(usage_path)!r})",
        "p.parent.mkdir(parents=True, exist_ok=True)",
        f"p.write_text(json.dumps({payload!r}), encoding='utf-8')",
        "print('worked')",
    )


def test_local_run_success_emits_usage_block(repo: Path):
    usage_file = op.usage_path(repo, "job-usage", "w1")
    plan = op.ExecutionPlan(
        job_id="job-usage",
        workers=[
            op.WorkerPlan(
                worker_id="w1",
                profile="builder",
                mode=op.ExecutionMode.LOCAL_RUN,
                command=_usage_writer_command(usage_file),
                timeout_seconds=10,
            )
        ],
    )
    statuses = op.ParallelRunner(repo, plan, poll_interval=0.05).run()

    s = statuses["w1"]
    assert s.state is op.WorkerState.COMPLETED
    # The runner folded the worker's sidecar into WorkerStatus.usage in the
    # exact {usage, cost_usd, model, provider} shape the consumer reads.
    assert s.usage == {
        "usage": {
            "input_tokens": 1200,
            "output_tokens": 300,
            "cache_read_tokens": 800,
            "reasoning_tokens": 40,
        },
        "cost_usd": 0.0731,
        "model": "claude-opus-4-8",
        "provider": "anthropic",
    }

    # …and it is persisted into status.json verbatim.
    snapshot = op.load_status(repo, "job-usage")
    assert snapshot is not None
    worker_row = snapshot["workers"][0]
    assert worker_row["usage"] == s.usage


def test_local_run_without_sidecar_emits_no_usage(repo: Path):
    plan = op.ExecutionPlan(
        job_id="job-nousage",
        workers=[
            op.WorkerPlan(
                worker_id="w1",
                profile="builder",
                mode=op.ExecutionMode.LOCAL_RUN,
                command=_python_command("print('no usage here')"),
                timeout_seconds=10,
            )
        ],
    )
    statuses = op.ParallelRunner(repo, plan, poll_interval=0.05).run()

    s = statuses["w1"]
    assert s.state is op.WorkerState.COMPLETED
    # No sidecar => additive default: cost meter stays untouched.
    assert s.usage is None
    snapshot = op.load_status(repo, "job-nousage")
    assert snapshot is not None
    assert snapshot["workers"][0]["usage"] is None


def test_failed_worker_does_not_emit_usage(repo: Path):
    # Even if a sidecar exists, a non-zero exit is not trusted to have a
    # complete record — usage is only read on clean exit.
    usage_file = op.usage_path(repo, "job-failusage", "w1")
    payload = {"usage": {"input_tokens": 10}, "cost_usd": 0.01}
    plan = op.ExecutionPlan(
        job_id="job-failusage",
        workers=[
            op.WorkerPlan(
                worker_id="w1",
                profile="builder",
                mode=op.ExecutionMode.LOCAL_RUN,
                command=_python_command(
                    "import json, pathlib, sys",
                    f"p = pathlib.Path(r{str(usage_file)!r})",
                    "p.parent.mkdir(parents=True, exist_ok=True)",
                    f"p.write_text(json.dumps({payload!r}), encoding='utf-8')",
                    "sys.exit(3)",
                ),
                timeout_seconds=10,
            )
        ],
    )
    statuses = op.ParallelRunner(repo, plan, poll_interval=0.05).run()

    s = statuses["w1"]
    assert s.state is op.WorkerState.FAILED
    assert s.usage is None


def test_iter_worker_usage_yields_reported_blocks(repo: Path):
    usage_file = op.usage_path(repo, "job-iter", "w1")
    plan = op.ExecutionPlan(
        job_id="job-iter",
        workers=[
            op.WorkerPlan(
                worker_id="w1",
                profile="builder",
                mode=op.ExecutionMode.LOCAL_RUN,
                command=_usage_writer_command(usage_file),
                timeout_seconds=10,
            ),
            op.WorkerPlan(
                worker_id="w2",
                profile="builder",
                mode=op.ExecutionMode.LOCAL_RUN,
                command=_python_command("print('silent')"),
                timeout_seconds=10,
            ),
        ],
        concurrency=1,
    )
    op.ParallelRunner(repo, plan, poll_interval=0.05).run()

    reported = dict(op.iter_worker_usage(repo, "job-iter"))
    # Only the worker that wrote a sidecar shows up.
    assert set(reported) == {"w1"}
    assert reported["w1"]["cost_usd"] == 0.0731
    assert reported["w1"]["usage"]["input_tokens"] == 1200


def test_iter_worker_usage_empty_for_unknown_job(repo: Path):
    assert op.iter_worker_usage(repo, "no-such-job") == []


def test_emitted_usage_round_trips_through_consumer_seam(repo: Path):
    # End-to-end proof: a worker's emitted block, once persisted, folds into a
    # JobCost via the exact consumer seam #301 shipped — with no translation.
    from hermes_cli.job_cost import JobCost
    from hermes_cli.orchestrator_api import _extract_usage_report

    usage_file = op.usage_path(repo, "job-roundtrip", "w1")
    plan = op.ExecutionPlan(
        job_id="job-roundtrip",
        workers=[
            op.WorkerPlan(
                worker_id="w1",
                profile="builder",
                mode=op.ExecutionMode.LOCAL_RUN,
                command=_usage_writer_command(usage_file),
                timeout_seconds=10,
            )
        ],
    )
    op.ParallelRunner(repo, plan, poll_interval=0.05).run()

    job = JobCost()
    for _worker_id, block in op.iter_worker_usage(repo, "job-roundtrip"):
        kwargs = _extract_usage_report(block)
        assert kwargs is not None
        job.add_usage(**kwargs)

    totals = job.totals()
    assert totals["input_tokens"] == 1200
    assert totals["output_tokens"] == 300
    assert totals["cache_read_tokens"] == 800
    assert totals["reasoning_tokens"] == 40
    assert totals["cost_usd"] == 0.0731
    assert totals["call_count"] == 1
    assert totals["by_model"] == {"anthropic/claude-opus-4-8": 0.0731}


# ─── _sanitize_usage_block (defensive parsing) ────────────────────────


def test_sanitize_usage_block_drops_non_positive_and_junk():
    assert op._sanitize_usage_block("not a dict") is None
    assert op._sanitize_usage_block({"usage": {"input_tokens": 0}, "cost_usd": 0.0}) is None
    assert op._sanitize_usage_block({"usage": {"input_tokens": -5}}) is None
    # bool must not slip through as 1 token / $1.
    assert op._sanitize_usage_block({"usage": {"input_tokens": True}}) is None
    assert op._sanitize_usage_block({"cost_usd": True}) is None
    # Negative cost is dropped but positive tokens still count.
    assert op._sanitize_usage_block({"usage": {"input_tokens": 5}, "cost_usd": -1}) == {
        "usage": {"input_tokens": 5},
        "cost_usd": 0.0,
    }
    # Cost-only entry is valid.
    assert op._sanitize_usage_block({"cost_usd": 0.5}) == {"cost_usd": 0.5}


def test_read_usage_sidecar_tolerates_missing_and_malformed(tmp_path: Path):
    # Missing file.
    assert op._read_usage_sidecar(tmp_path) is None
    # Malformed JSON.
    (tmp_path / op.USAGE_FILENAME).write_text("{not json", encoding="utf-8")
    assert op._read_usage_sidecar(tmp_path) is None


# ─── budget hard-stop (Sprint 10 enforcement) ─────────────────────────


def _cost_writer_command(usage_path: Path, cost: float) -> list[str]:
    """A LOCAL_RUN worker that reports ``cost`` USD via its usage sidecar."""

    payload = {"cost_usd": cost, "model": "test", "provider": "test"}
    return _python_command(
        "import json, pathlib",
        f"p = pathlib.Path(r{str(usage_path)!r})",
        "p.parent.mkdir(parents=True, exist_ok=True)",
        f"p.write_text(json.dumps({payload!r}), encoding='utf-8')",
    )


def _marker_writer_command(marker: Path) -> list[str]:
    """A worker whose only effect is to create ``marker`` — proves it ran."""

    return _python_command(
        "import pathlib",
        f"pathlib.Path(r{str(marker)!r}).write_text('ran', encoding='utf-8')",
    )


def test_sequential_budget_hard_stop_halts_remaining_workers(
    repo: Path, tmp_path: Path
):
    # w1 reports a cost over the hard limit; the runner must NOT launch w2.
    usage_file = op.usage_path(repo, "job-budget", "w1")
    marker = tmp_path / "w2-ran.txt"
    plan = op.ExecutionPlan(
        job_id="job-budget",
        workers=[
            op.WorkerPlan(
                worker_id="w1",
                profile="builder",
                mode=op.ExecutionMode.LOCAL_RUN,
                command=_cost_writer_command(usage_file, 5.0),
                timeout_seconds=10,
            ),
            op.WorkerPlan(
                worker_id="w2",
                profile="builder",
                mode=op.ExecutionMode.LOCAL_RUN,
                command=_marker_writer_command(marker),
                timeout_seconds=10,
            ),
        ],
        concurrency=1,
    )
    statuses = op.ParallelRunner(
        repo, plan, poll_interval=0.05, budget_hard_limit=1.0
    ).run()

    assert statuses["w1"].state is op.WorkerState.COMPLETED
    w1_usage = statuses["w1"].usage
    assert w1_usage is not None and w1_usage["cost_usd"] == 5.0
    # w2 was stopped before launch; its command never executed.
    assert statuses["w2"].state is op.WorkerState.CANCELLED
    assert "limit" in (statuses["w2"].error or "")
    assert not marker.exists()
    # The hard stop is recorded in status.json for audit.
    snapshot = op.load_status(repo, "job-budget")
    assert snapshot is not None
    assert snapshot["budget"]["stopped"] is True
    assert snapshot["budget"]["spent"] == 5.0
    assert snapshot["budget"]["hard_limit"] == 1.0


def test_no_budget_limit_runs_all_workers(repo: Path, tmp_path: Path):
    # Behavior-preserving default: with no budget, every worker runs even when
    # it reports a large cost, and no budget block is written.
    usage_file = op.usage_path(repo, "job-nobudget", "w1")
    marker = tmp_path / "w2-ran.txt"
    plan = op.ExecutionPlan(
        job_id="job-nobudget",
        workers=[
            op.WorkerPlan(
                worker_id="w1",
                profile="builder",
                mode=op.ExecutionMode.LOCAL_RUN,
                command=_cost_writer_command(usage_file, 99.0),
                timeout_seconds=10,
            ),
            op.WorkerPlan(
                worker_id="w2",
                profile="builder",
                mode=op.ExecutionMode.LOCAL_RUN,
                command=_marker_writer_command(marker),
                timeout_seconds=10,
            ),
        ],
        concurrency=1,
    )
    statuses = op.ParallelRunner(repo, plan, poll_interval=0.05).run()
    assert statuses["w1"].state is op.WorkerState.COMPLETED
    assert statuses["w2"].state is op.WorkerState.COMPLETED
    assert marker.exists()
    snapshot = op.load_status(repo, "job-nobudget")
    assert snapshot is not None
    assert "budget" not in snapshot


def test_budget_within_limit_keeps_running(repo: Path, tmp_path: Path):
    # Spend stays under the hard limit → the next worker still runs.
    usage_file = op.usage_path(repo, "job-underbudget", "w1")
    marker = tmp_path / "w2-ran.txt"
    plan = op.ExecutionPlan(
        job_id="job-underbudget",
        workers=[
            op.WorkerPlan(
                worker_id="w1",
                profile="builder",
                mode=op.ExecutionMode.LOCAL_RUN,
                command=_cost_writer_command(usage_file, 0.25),
                timeout_seconds=10,
            ),
            op.WorkerPlan(
                worker_id="w2",
                profile="builder",
                mode=op.ExecutionMode.LOCAL_RUN,
                command=_marker_writer_command(marker),
                timeout_seconds=10,
            ),
        ],
        concurrency=1,
    )
    statuses = op.ParallelRunner(
        repo, plan, poll_interval=0.05, budget_hard_limit=1.0
    ).run()
    assert statuses["w2"].state is op.WorkerState.COMPLETED
    assert marker.exists()
    snapshot = op.load_status(repo, "job-underbudget")
    assert snapshot is not None
    assert "budget" not in snapshot


def test_invalid_budget_limits_rejected(repo: Path):
    plan = op.ExecutionPlan(
        job_id="job-badbudget",
        workers=[
            op.WorkerPlan(
                worker_id="w1",
                profile="builder",
                mode=op.ExecutionMode.PROMPT_ONLY,
                prompt="x",
            )
        ],
    )
    with pytest.raises(op.OrchestratorError, match="budget_soft_limit must be <="):
        op.ParallelRunner(repo, plan, budget_soft_limit=5.0, budget_hard_limit=1.0)
