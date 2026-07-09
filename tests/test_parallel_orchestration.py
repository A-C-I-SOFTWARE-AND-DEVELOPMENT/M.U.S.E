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


def test_concurrent_run_overlaps_worker_sleeps(repo: Path):
    """Concurrency proven structurally, not by racing the wall clock.

    The old assertion (`elapsed < 1.0s` vs ~1.2s serial) flaked on loaded CI
    runners where three interpreter startups alone exceeded the budget
    (observed: 1.47s with genuinely concurrent workers). Instead, each worker
    prints its sleep interval; serial execution can never produce overlapping
    intervals under any load, while concurrency=3 must overlap at least one
    pair.
    """
    workers = [
        op.WorkerPlan(
            worker_id=f"w{i}",
            profile="bash",
            mode=op.ExecutionMode.LOCAL_RUN,
            command=_python_command(
                "import time",
                "start = time.time()",
                "time.sleep(0.4)",
                "print(start, time.time())",
            ),
            timeout_seconds=15,
        )
        for i in range(3)
    ]
    plan = op.ExecutionPlan(job_id="job-c", workers=workers, concurrency=3)
    statuses = op.ParallelRunner(repo, plan, poll_interval=0.05).run()

    assert all(s.state is op.WorkerState.COMPLETED for s in statuses.values())
    intervals = []
    for s in statuses.values():
        t0, t1 = Path(s.stdout_path or "").read_text(encoding="utf-8").split()
        intervals.append((float(t0), float(t1)))
    intervals.sort()
    # Sorted by start, an overlap anywhere implies an overlap between some
    # adjacent pair, so the adjacent check is sufficient.
    overlaps = sum(
        1 for (a0, a1), (b0, b1) in zip(intervals, intervals[1:]) if b0 < a1
    )
    assert overlaps >= 1, f"no overlapping sleep intervals — serial? {intervals}"


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


# ─── write_usage_sidecar (producer emit seam) ─────────────────────────


def _usage_record(**overrides) -> dict:
    """A canonical build_usage_record-shaped block (what the writer persists)."""
    rec = {
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
    rec.update(overrides)
    return rec


def test_write_usage_sidecar_roundtrips_to_consumer(repo: Path):
    # The writer emits exactly what the consumer reads back, at usage_path.
    path = op.write_usage_sidecar(repo, "job-emit", "w1", _usage_record())
    assert path == op.usage_path(repo, "job-emit", "w1")
    assert path is not None and path.exists()

    block = op._read_usage_sidecar(op.worker_dir(repo, "job-emit", "w1"))
    assert block is not None
    assert block["cost_usd"] == 0.0731
    assert block["usage"]["input_tokens"] == 1200
    assert block["usage"]["cache_read_tokens"] == 800


def test_write_usage_sidecar_feeds_cost_seam(repo: Path):
    # A written sidecar drains through the exact consumer seam into a JobCost.
    from hermes_cli.job_cost import JobCost
    from hermes_cli.orchestrator_api import _extract_usage_report

    op.write_usage_sidecar(repo, "job-emit2", "w1", _usage_record())
    block = op._read_usage_sidecar(op.worker_dir(repo, "job-emit2", "w1"))
    assert block is not None
    kwargs = _extract_usage_report(block)
    assert kwargs is not None
    job = JobCost()
    job.add_usage(**kwargs)
    totals = job.totals()
    assert totals["cost_usd"] == 0.0731
    assert totals["input_tokens"] == 1200
    assert totals["by_model"] == {"anthropic/claude-opus-4-8": 0.0731}


def test_write_usage_sidecar_noops_on_none(repo: Path):
    # Passing None (an empty turn's build_usage_record result) writes nothing.
    assert op.write_usage_sidecar(repo, "job-none", "w1", None) is None
    assert not op.usage_path(repo, "job-none", "w1").exists()


def test_write_usage_sidecar_overwrites_atomically(repo: Path):
    # A second write wins cleanly and leaves no temp file behind.
    p1 = op.write_usage_sidecar(repo, "job-ow", "w1", _usage_record(cost_usd=0.10))
    p2 = op.write_usage_sidecar(repo, "job-ow", "w1", _usage_record(cost_usd=0.20))
    assert p1 == p2
    block = op._read_usage_sidecar(op.worker_dir(repo, "job-ow", "w1"))
    assert block is not None and block["cost_usd"] == 0.20
    leftovers = list(op.worker_dir(repo, "job-ow", "w1").glob("*.tmp"))
    assert leftovers == []


def test_write_usage_sidecar_composes_with_build_usage_record(repo: Path):
    # The documented one-line pattern: hand build_usage_record's output straight
    # to the writer. A real run result (flat session totals) becomes a sidecar
    # the consumer reads; an empty turn composes to a no-op.
    from agent.conversation_loop import build_usage_record

    source = {
        "input_tokens": 1200,
        "output_tokens": 300,
        "cache_read_tokens": 800,
        "reasoning_tokens": 40,
        "estimated_cost_usd": 0.0731,
        "model": "claude-opus-4-8",
        "provider": "anthropic",
    }
    path = op.write_usage_sidecar(repo, "job-compose", "w1", build_usage_record(source))
    assert path is not None and path.exists()
    block = op._read_usage_sidecar(op.worker_dir(repo, "job-compose", "w1"))
    assert block is not None
    assert block["usage"]["input_tokens"] == 1200
    assert block["cost_usd"] == 0.0731

    # An empty turn -> build_usage_record None -> writer no-op.
    assert op.write_usage_sidecar(repo, "job-compose", "w2", build_usage_record({})) is None
    assert not op.usage_path(repo, "job-compose", "w2").exists()


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


def test_concurrent_pre_exhausted_budget_launches_nothing(repo: Path, tmp_path: Path):
    # A pre-exhausted hard budget (0.0) must start NO worker, even on the
    # concurrent path — symmetric with the sequential pre-launch check. The
    # bounded pool gates each launch, so it never races ``concurrency`` workers
    # out before the first completion.
    markers = [tmp_path / f"w{i}-ran.txt" for i in range(4)]
    workers = [
        op.WorkerPlan(
            worker_id=f"w{i}",
            profile="builder",
            mode=op.ExecutionMode.LOCAL_RUN,
            command=_marker_writer_command(markers[i]),
            timeout_seconds=10,
        )
        for i in range(4)
    ]
    plan = op.ExecutionPlan(job_id="job-zerobudget", workers=workers, concurrency=2)
    statuses = op.ParallelRunner(
        repo, plan, poll_interval=0.05, budget_hard_limit=0.0
    ).run()
    # Not one worker command executed.
    assert not any(m.exists() for m in markers)
    # Every worker is recorded as stopped (cancelled), none completed.
    assert all(s.state is op.WorkerState.CANCELLED for s in statuses.values())
    snapshot = op.load_status(repo, "job-zerobudget")
    assert snapshot is not None
    assert snapshot["budget"]["stopped"] is True


def test_concurrent_budget_stops_remaining_after_overrun(repo: Path, tmp_path: Path):
    # The first wave (within concurrency) runs and overruns the hard limit;
    # the later workers must be stopped before they launch. Deterministic
    # because bounded submission only queues w2/w3 after w0/w1 complete, by
    # which point the meter is already over the limit.
    u0 = op.usage_path(repo, "job-cbud", "w0")
    u1 = op.usage_path(repo, "job-cbud", "w1")
    m2 = tmp_path / "w2-ran.txt"
    m3 = tmp_path / "w3-ran.txt"
    workers = [
        op.WorkerPlan(
            worker_id="w0",
            profile="builder",
            mode=op.ExecutionMode.LOCAL_RUN,
            command=_cost_writer_command(u0, 5.0),
            timeout_seconds=10,
        ),
        op.WorkerPlan(
            worker_id="w1",
            profile="builder",
            mode=op.ExecutionMode.LOCAL_RUN,
            command=_cost_writer_command(u1, 5.0),
            timeout_seconds=10,
        ),
        op.WorkerPlan(
            worker_id="w2",
            profile="builder",
            mode=op.ExecutionMode.LOCAL_RUN,
            command=_marker_writer_command(m2),
            timeout_seconds=10,
        ),
        op.WorkerPlan(
            worker_id="w3",
            profile="builder",
            mode=op.ExecutionMode.LOCAL_RUN,
            command=_marker_writer_command(m3),
            timeout_seconds=10,
        ),
    ]
    plan = op.ExecutionPlan(job_id="job-cbud", workers=workers, concurrency=2)
    statuses = op.ParallelRunner(
        repo, plan, poll_interval=0.05, budget_hard_limit=1.0
    ).run()
    assert statuses["w0"].state is op.WorkerState.COMPLETED
    assert statuses["w1"].state is op.WorkerState.COMPLETED
    assert statuses["w2"].state is op.WorkerState.CANCELLED
    assert statuses["w3"].state is op.WorkerState.CANCELLED
    assert not m2.exists() and not m3.exists()
    snapshot = op.load_status(repo, "job-cbud")
    assert snapshot is not None
    assert snapshot["budget"]["stopped"] is True


# ─── runtime adapter injection (Sprint 13, additive) ──────────────────


def _local_adapter_for_worker(repo: Path, job_id: str, worker_id: str):
    """A LocalRuntimeAdapter whose streams land in the worker's own dir.

    Pointing ``workdir`` at the orchestrator's worker dir makes the adapter's
    default ``stdout.log`` / ``stderr.log`` coincide with the runner's own
    STDOUT_LOG / STDERR_LOG, so the adapter-backed run captures output in the
    same place the inline path does.
    """

    from hermes_cli.runtime_adapter import LocalRuntimeAdapter

    worker_root = op.worker_dir(repo, job_id, worker_id)
    worker_root.mkdir(parents=True, exist_ok=True)
    return LocalRuntimeAdapter(workdir=worker_root)


def test_adapter_run_matches_default_path_outcome(repo: Path):
    # Same plan, run twice: once with the default inline subprocess path, once
    # through an injected LocalRuntimeAdapter. The observable WorkerStatus
    # outcome must match (proving the adapter path is equivalent).
    def _plan(job_id: str) -> op.ExecutionPlan:
        return op.ExecutionPlan(
            job_id=job_id,
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

    default = op.ParallelRunner(
        repo, _plan("job-default"), poll_interval=0.05
    ).run()["w1"]

    adapter = _local_adapter_for_worker(repo, "job-adapter", "w1")
    via_adapter = op.ParallelRunner(
        repo, _plan("job-adapter"), poll_interval=0.05, runtime_adapter=adapter
    ).run()["w1"]

    assert default.state is op.WorkerState.COMPLETED
    assert via_adapter.state is default.state
    assert via_adapter.return_code == default.return_code == 0
    assert via_adapter.usage == default.usage  # both None
    assert "hello world" in Path(
        via_adapter.stdout_path or ""
    ).read_text(encoding="utf-8")


def test_adapter_run_failure_maps_exit_code(repo: Path):
    adapter = _local_adapter_for_worker(repo, "job-afail", "w1")
    plan = op.ExecutionPlan(
        job_id="job-afail",
        workers=[
            op.WorkerPlan(
                worker_id="w1",
                profile="bash",
                mode=op.ExecutionMode.LOCAL_RUN,
                command=_python_command(
                    "import sys", "sys.stderr.write('boom\\n')", "sys.exit(7)"
                ),
                timeout_seconds=10,
            )
        ],
    )
    s = op.ParallelRunner(
        repo, plan, poll_interval=0.05, runtime_adapter=adapter
    ).run()["w1"]
    assert s.state is op.WorkerState.FAILED
    assert s.return_code == 7
    assert "boom" in Path(s.stderr_path or "").read_text(encoding="utf-8")


@pytest.mark.live_system_guard_bypass
def test_adapter_run_timeout_maps_to_timed_out(repo: Path):
    adapter = _local_adapter_for_worker(repo, "job-atimeout", "w1")
    plan = op.ExecutionPlan(
        job_id="job-atimeout",
        workers=[
            op.WorkerPlan(
                worker_id="w1",
                profile="bash",
                mode=op.ExecutionMode.LOCAL_RUN,
                command=_python_command("import time", "time.sleep(10)"),
                timeout_seconds=1,
            )
        ],
    )
    s = op.ParallelRunner(
        repo, plan, poll_interval=0.05, runtime_adapter=adapter
    ).run()["w1"]
    assert s.state is op.WorkerState.TIMED_OUT
    assert s.error and "timeout" in s.error


def test_adapter_run_folds_usage_sidecar(repo: Path):
    # A clean adapter-backed run folds the worker's usage.json sidecar into
    # WorkerStatus.usage — same contract as the inline path.
    usage_file = op.usage_path(repo, "job-ausage", "w1")
    adapter = _local_adapter_for_worker(repo, "job-ausage", "w1")
    plan = op.ExecutionPlan(
        job_id="job-ausage",
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
    s = op.ParallelRunner(
        repo, plan, poll_interval=0.05, runtime_adapter=adapter
    ).run()["w1"]
    assert s.state is op.WorkerState.COMPLETED
    assert s.usage is not None
    assert s.usage["cost_usd"] == 0.0731
    assert s.usage["usage"]["input_tokens"] == 1200


@pytest.mark.live_system_guard_bypass
def test_adapter_run_honors_precancel_without_running(repo: Path, tmp_path: Path):
    # A cancel requested before the run starts records the worker CANCELLED and
    # never invokes the adapter's command (no marker file written).
    marker = tmp_path / "ran.txt"
    adapter = _local_adapter_for_worker(repo, "job-acancel", "w1")
    plan = op.ExecutionPlan(
        job_id="job-acancel",
        workers=[
            op.WorkerPlan(
                worker_id="w1",
                profile="bash",
                mode=op.ExecutionMode.LOCAL_RUN,
                command=_marker_writer_command(marker),
                timeout_seconds=10,
            )
        ],
    )
    runner = op.ParallelRunner(
        repo, plan, poll_interval=0.05, runtime_adapter=adapter
    )
    op.request_cancel(repo, "job-acancel")
    statuses = runner.run()
    assert statuses["w1"].state is op.WorkerState.CANCELLED
    assert not marker.exists()


def test_default_runtime_adapter_is_none(repo: Path):
    # The additive default: no adapter is wired unless one is passed.
    plan = op.ExecutionPlan(
        job_id="job-noadapter",
        workers=[op.WorkerPlan("w1", "p", op.ExecutionMode.PROMPT_ONLY, prompt="x")],
    )
    runner = op.ParallelRunner(repo, plan)
    assert runner._runtime_adapter is None


class _RecordingAdapter:
    """A RuntimeAdapter spy that counts ``run`` calls and delegates to a real
    LocalRuntimeAdapter, so a test can assert *whether* the adapter path ran."""

    def __init__(self, inner):
        self._inner = inner
        self.run_calls = 0

    @property
    def host_id(self) -> str:
        return self._inner.host_id

    @property
    def kind(self) -> str:
        return self._inner.kind

    def prepare(self) -> None:
        self._inner.prepare()

    def run(self, command, *, timeout):
        self.run_calls += 1
        return self._inner.run(command, timeout=timeout)

    def cleanup(self) -> None:
        self._inner.cleanup()


def test_adapter_used_for_plain_local_run_worker(repo: Path):
    # A plain LOCAL_RUN worker (no per-worker cwd/env/worktree) goes through the
    # injected adapter: run() is invoked exactly once and the worker completes.
    adapter = _RecordingAdapter(_local_adapter_for_worker(repo, "job-plain", "w1"))
    plan = op.ExecutionPlan(
        job_id="job-plain",
        workers=[
            op.WorkerPlan(
                worker_id="w1",
                profile="bash",
                mode=op.ExecutionMode.LOCAL_RUN,
                command=_python_command("print('hi')"),
                timeout_seconds=10,
            )
        ],
    )
    s = op.ParallelRunner(
        repo, plan, poll_interval=0.05, runtime_adapter=adapter
    ).run()["w1"]
    assert s.state is op.WorkerState.COMPLETED
    assert adapter.run_calls == 1


def test_adapter_skipped_for_placement_worker_falls_back_to_inline(repo: Path):
    # A worker that carries a per-worker env overlay must NOT be routed through a
    # shared injected adapter (whose env is a single construction-time value).
    # It falls back to the inline subprocess path that honors worker.env, so the
    # adapter's run() is never called, the worker still completes, and the env
    # var reaches the child — proving placement is honored, not silently dropped.
    adapter = _RecordingAdapter(_local_adapter_for_worker(repo, "job-envfb", "w1"))
    plan = op.ExecutionPlan(
        job_id="job-envfb",
        workers=[
            op.WorkerPlan(
                worker_id="w1",
                profile="bash",
                mode=op.ExecutionMode.LOCAL_RUN,
                command=_python_command(
                    "import os",
                    "print(os.environ.get('HERMES_FALLBACK_PROBE', 'MISSING'))",
                ),
                env={"HERMES_FALLBACK_PROBE": "present"},
                timeout_seconds=10,
            )
        ],
    )
    s = op.ParallelRunner(
        repo, plan, poll_interval=0.05, runtime_adapter=adapter
    ).run()["w1"]
    assert s.state is op.WorkerState.COMPLETED
    assert adapter.run_calls == 0  # fell back to inline; adapter unused
    assert "present" in Path(s.stdout_path or "").read_text(encoding="utf-8")


def test_needs_inline_placement_predicate():
    # The selector that keeps placement-bearing workers off the adapter path.
    def _w(*, cwd=None, env=None, use_worktree=False) -> op.WorkerPlan:
        return op.WorkerPlan(
            worker_id="w1",
            profile="p",
            mode=op.ExecutionMode.LOCAL_RUN,
            command=["true"],
            timeout_seconds=10,
            cwd=cwd,
            env=env,
            use_worktree=use_worktree,
        )

    assert op._needs_inline_placement(_w()) is False
    assert op._needs_inline_placement(_w(cwd="/tmp")) is True
    assert op._needs_inline_placement(_w(env={"A": "B"})) is True
    assert op._needs_inline_placement(_w(use_worktree=True)) is True


# ─── reschedule plan exposure (Sprint 13, observational only) ─────────


def test_compute_reschedule_plan_proposes_for_expired_idempotent_lease(
    repo: Path, tmp_path: Path
):
    # An expired + idempotent lease in the store yields a reschedule proposal.
    from hermes_cli import worker_lease as wl
    from hermes_cli.worker_lease_store import WorkerLeaseStore

    store = WorkerLeaseStore.load(directory=tmp_path / "leasestore")
    store.register_host("host_a", kind="local")
    store.register_host("host_b", kind="local")
    # Acquire a lease, then drive it to EXPIRED by folding past its deadline.
    lease = wl.WorkerLease(
        lease_id="job-x:w1",
        job_id="job-x",
        worker_id="w1",
        host_id="host_a",
        idempotent=True,
    )
    lease = wl.acquire(lease, now=100.0, ttl=30.0)  # expires at 130
    lease = wl.expire_if_stale(lease, now=200.0)
    assert lease.status is wl.LeaseStatus.EXPIRED
    store.upsert(lease)

    plan = op.ExecutionPlan(
        job_id="job-resched",
        workers=[op.WorkerPlan("w1", "p", op.ExecutionMode.PROMPT_ONLY, prompt="x")],
    )
    runner = op.ParallelRunner(repo, plan, lease_store=store)

    result = runner.compute_reschedule_plan(now=300.0)
    assert len(result) == 1
    proposal = result[0]
    assert proposal.lease_id == "job-x:w1"
    assert proposal.job_id == "job-x"
    assert proposal.from_host_id == "host_a"
    assert proposal.target_host_id in {"host_a", "host_b"}
    # Exposed on the runner for later inspection…
    assert runner.reschedule_plan == result
    # …and the lease is NOT mutated to a non-terminal/re-leased state — the
    # plan only *proposes*; the originating lease stays EXPIRED (retries are a
    # documented follow-up, never auto-executed here).
    expired_lease = store.get("job-x:w1")
    assert expired_lease is not None
    assert expired_lease.status is wl.LeaseStatus.EXPIRED


def test_compute_reschedule_plan_expires_stale_running_lease(
    repo: Path, tmp_path: Path
):
    # A still-RUNNING-but-past-deadline lease is folded to EXPIRED by the
    # store's own kernel rule, then becomes reschedulable.
    from hermes_cli import worker_lease as wl
    from hermes_cli.worker_lease_store import WorkerLeaseStore

    store = WorkerLeaseStore.load(directory=tmp_path / "leasestore")
    store.register_host("host_a", kind="local")
    lease = wl.acquire(
        wl.WorkerLease(
            lease_id="job-y:w1",
            job_id="job-y",
            worker_id="w1",
            host_id="host_a",
            idempotent=True,
        ),
        now=100.0,
        ttl=30.0,
    )  # RUNNING, expires at 130
    store.upsert(lease)
    running_lease = store.get("job-y:w1")
    assert running_lease is not None
    assert running_lease.status is wl.LeaseStatus.RUNNING

    plan = op.ExecutionPlan(
        job_id="job-resched2",
        workers=[op.WorkerPlan("w1", "p", op.ExecutionMode.PROMPT_ONLY, prompt="x")],
    )
    runner = op.ParallelRunner(repo, plan, lease_store=store)
    result = runner.compute_reschedule_plan(now=500.0)
    assert [r.lease_id for r in result] == ["job-y:w1"]


def test_compute_reschedule_plan_empty_without_lease_store(repo: Path):
    plan = op.ExecutionPlan(
        job_id="job-noresched",
        workers=[op.WorkerPlan("w1", "p", op.ExecutionMode.PROMPT_ONLY, prompt="x")],
    )
    # record_leases=False => no store is loaded; the plan is empty, not an error.
    runner = op.ParallelRunner(repo, plan, record_leases=False)
    assert runner.compute_reschedule_plan() == []
    assert runner.reschedule_plan == []


def test_compute_reschedule_plan_empty_when_nothing_retryable(
    repo: Path, tmp_path: Path
):
    # A live RUNNING lease (within deadline) is not retryable → empty plan.
    from hermes_cli import worker_lease as wl
    from hermes_cli.worker_lease_store import WorkerLeaseStore

    store = WorkerLeaseStore.load(directory=tmp_path / "leasestore")
    store.register_host("host_a", kind="local")
    lease = wl.acquire(
        wl.WorkerLease(
            lease_id="job-z:w1",
            job_id="job-z",
            worker_id="w1",
            host_id="host_a",
        ),
        now=1000.0,
        ttl=600.0,
    )
    store.upsert(lease)

    plan = op.ExecutionPlan(
        job_id="job-resched3",
        workers=[op.WorkerPlan("w1", "p", op.ExecutionMode.PROMPT_ONLY, prompt="x")],
    )
    runner = op.ParallelRunner(repo, plan, lease_store=store)
    # now is still within the lease deadline (1000 + 600 = 1600).
    assert runner.compute_reschedule_plan(now=1100.0) == []


# ─── per-worker adapter factory (FU-2, additive) ──────────────────────


def test_default_adapter_factory_is_none(repo: Path):
    # The additive default: no factory is wired unless one is passed.
    plan = op.ExecutionPlan(
        job_id="job-nofactory",
        workers=[op.WorkerPlan("w1", "p", op.ExecutionMode.PROMPT_ONLY, prompt="x")],
    )
    runner = op.ParallelRunner(repo, plan)
    assert runner._adapter_factory is None


def test_per_worker_factory_isolates_multi_worker_logs(repo: Path):
    # The exact collision that made a bare shared LocalRuntimeAdapter default
    # unsafe: two plain workers sharing one adapter clobber each other's
    # stdout.log. The per-worker factory gives each worker its own adapter
    # with streams in its own worker_root.
    seen: list[tuple[str, Path]] = []

    def factory(worker, worker_root):
        seen.append((worker.worker_id, worker_root))
        return op.per_worker_local_adapter(worker, worker_root)

    plan = op.ExecutionPlan(
        job_id="job-factory-iso",
        concurrency=2,
        workers=[
            op.WorkerPlan(
                worker_id="w1",
                profile="bash",
                mode=op.ExecutionMode.LOCAL_RUN,
                command=_python_command("print('alpha')"),
                timeout_seconds=10,
            ),
            op.WorkerPlan(
                worker_id="w2",
                profile="bash",
                mode=op.ExecutionMode.LOCAL_RUN,
                command=_python_command("print('beta')"),
                timeout_seconds=10,
            ),
        ],
    )
    statuses = op.ParallelRunner(
        repo, plan, poll_interval=0.05, adapter_factory=factory
    ).run()

    assert statuses["w1"].state is op.WorkerState.COMPLETED
    assert statuses["w2"].state is op.WorkerState.COMPLETED
    assert sorted(wid for wid, _ in seen) == ["w1", "w2"]
    out_w1 = op.worker_dir(repo, "job-factory-iso", "w1") / op.STDOUT_LOG
    out_w2 = op.worker_dir(repo, "job-factory-iso", "w2") / op.STDOUT_LOG
    assert "alpha" in out_w1.read_text(encoding="utf-8")
    assert "beta" in out_w2.read_text(encoding="utf-8")


def test_factory_decline_falls_back_to_inline(repo: Path):
    # A factory returning None declines the worker; with no shared adapter the
    # existing inline subprocess path runs it unchanged.
    declined: list[str] = []

    def factory(worker, worker_root):
        declined.append(worker.worker_id)
        return None

    plan = op.ExecutionPlan(
        job_id="job-factory-decline",
        workers=[
            op.WorkerPlan(
                worker_id="w1",
                profile="bash",
                mode=op.ExecutionMode.LOCAL_RUN,
                command=_python_command("print('inline ran')"),
                timeout_seconds=10,
            )
        ],
    )
    statuses = op.ParallelRunner(
        repo, plan, poll_interval=0.05, adapter_factory=factory
    ).run()

    assert declined == ["w1"]
    assert statuses["w1"].state is op.WorkerState.COMPLETED
    out = op.worker_dir(repo, "job-factory-decline", "w1") / op.STDOUT_LOG
    assert "inline ran" in out.read_text(encoding="utf-8")


def test_factory_adapter_honors_worker_cwd_and_env(repo: Path, tmp_path: Path):
    # Unlike a shared injected adapter (guarded by _needs_inline_placement), a
    # factory-built adapter OWNS per-worker placement: the worker's own cwd and
    # env overlay are honored on the adapter path.
    workdir = tmp_path / "fu2-cwd"
    workdir.mkdir()
    plan = op.ExecutionPlan(
        job_id="job-factory-place",
        workers=[
            op.WorkerPlan(
                worker_id="w1",
                profile="bash",
                mode=op.ExecutionMode.LOCAL_RUN,
                command=_python_command(
                    "import os",
                    "print(os.path.realpath(os.getcwd()))",
                    "print(os.environ.get('FU2_MARKER', 'missing'))",
                ),
                cwd=str(workdir),
                env={"FU2_MARKER": "fu2-value"},
                timeout_seconds=10,
            )
        ],
    )
    statuses = op.ParallelRunner(
        repo,
        plan,
        poll_interval=0.05,
        adapter_factory=op.per_worker_local_adapter,
    ).run()

    assert statuses["w1"].state is op.WorkerState.COMPLETED
    out = (
        op.worker_dir(repo, "job-factory-place", "w1") / op.STDOUT_LOG
    ).read_text(encoding="utf-8")
    assert str(workdir.resolve()) in out
    assert "fu2-value" in out


def test_per_worker_local_adapter_declines_worktree_workers():
    # Worktree cwds are resolved runner-internally; the canonical factory
    # declines so the inline path (the only one that owns them) runs the worker.
    worker = op.WorkerPlan(
        worker_id="w1",
        profile="bash",
        mode=op.ExecutionMode.LOCAL_RUN,
        command=["true"],
        use_worktree=True,
    )
    assert op.per_worker_local_adapter(worker, Path("/tmp/unused")) is None
