"""Tests for ``hermes_cli.orchestrator_dispatch``.

The dispatcher seam runs a :class:`ParallelRunner` plan and drains each
worker's persisted usage into a :class:`JobStore`, mirroring the HTTP
``POST /jobs/{id}/workers/{worker}`` route's usage routing exactly. These tests
run against an isolated git repo in ``tmp_path`` and use real LOCAL_RUN
subprocesses (the same usage-sidecar helpers as
``tests/test_parallel_orchestration.py``).

Async style follows the repo convention used in
``tests/test_orchestrator_api.py``: a plain sync test wraps an inner coroutine
in :func:`asyncio.run` rather than relying on a pytest-asyncio marker.
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
from pathlib import Path

import pytest

from hermes_cli import orchestrator_parallel as op
from hermes_cli.orchestrator_api import JobStore
from hermes_cli.orchestrator_dispatch import run_plan_into_store
from hermes_cli.runtime_adapter import LocalRuntimeAdapter


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


def _usage_writer_command(usage_path: Path) -> list[str]:
    """A LOCAL_RUN command that writes a usage sidecar then exits 0.

    Mirrors the helper in ``tests/test_parallel_orchestration.py``: stands in
    for a worker that ran the agent and dumped ``build_usage_record`` output to
    ``usage.json``.
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


def _usage_plan(repo: Path, job_id: str, worker_id: str = "w1") -> op.ExecutionPlan:
    usage_file = op.usage_path(repo, job_id, worker_id)
    return op.ExecutionPlan(
        job_id=job_id,
        workers=[
            op.WorkerPlan(
                worker_id=worker_id,
                profile="builder",
                mode=op.ExecutionMode.LOCAL_RUN,
                command=_usage_writer_command(usage_file),
                timeout_seconds=10,
            )
        ],
    )


class _RecordingAdapter:
    """A RuntimeAdapter spy that counts ``run`` calls and delegates to a real
    LocalRuntimeAdapter, so a test can assert *whether* the adapter path ran.

    Same shape as the spy in ``tests/test_parallel_orchestration.py``.
    """

    def __init__(self, inner: LocalRuntimeAdapter) -> None:
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


def _adapter_for_worker(repo: Path, job_id: str, worker_id: str) -> LocalRuntimeAdapter:
    """A LocalRuntimeAdapter whose streams land in the worker's own dir."""

    worker_root = op.worker_dir(repo, job_id, worker_id)
    worker_root.mkdir(parents=True, exist_ok=True)
    return LocalRuntimeAdapter(workdir=worker_root)


# ─── run_plan_into_store: usage drain ─────────────────────────────────


def test_run_plan_drains_worker_and_cost_into_store(repo: Path):
    # A LOCAL_RUN worker that writes a usage sidecar → after run_plan_into_store,
    # the JobStore reflects the worker AND the accumulated cost, matching the
    # totals/by_model the HTTP worker-report path would produce.
    async def _run_test():
        store = JobStore()
        job = await store.create("dispatch", {})
        # The runner keys artifacts/cost (incl. the usage sidecar path) by
        # plan.job_id; build the plan against the created job's id so the worker
        # writes its sidecar where the runner will read it back.
        plan = _usage_plan(repo, job.id)

        statuses = await run_plan_into_store(repo, plan, store)

        assert statuses["w1"].state is op.WorkerState.COMPLETED

        refreshed = await store.get(job.id)
        # The worker block landed in the store, in the consumer report shape.
        assert "w1" in refreshed.workers
        assert refreshed.workers["w1"]["cost_usd"] == 0.0731
        assert refreshed.workers["w1"]["usage"]["input_tokens"] == 1200

        # …and the cost aggregate matches the HTTP path's accounting exactly.
        totals = refreshed.cost.totals()
        assert totals["cost_usd"] == 0.0731
        assert totals["input_tokens"] == 1200
        assert totals["output_tokens"] == 300
        assert totals["cache_read_tokens"] == 800
        assert totals["reasoning_tokens"] == 40
        assert totals["call_count"] == 1
        assert totals["by_model"] == {"anthropic/claude-opus-4-8": 0.0731}

    asyncio.run(_run_test())


def test_run_plan_returns_runner_statuses(repo: Path):
    async def _run_test():
        store = JobStore()
        job = await store.create("ret", {})
        plan = op.ExecutionPlan(
            job_id=job.id,
            workers=_usage_plan(repo, job.id).workers,
        )
        statuses = await run_plan_into_store(repo, plan, store)
        # Returns the runner's per-worker WorkerStatus map (not the store).
        assert set(statuses) == {"w1"}
        assert isinstance(statuses["w1"], op.WorkerStatus)

    asyncio.run(_run_test())


def test_run_plan_no_usage_leaves_cost_zero(repo: Path):
    # A plain worker that reports no usage must not move the cost meter — the
    # additive default the HTTP path also honors.
    async def _run_test():
        store = JobStore()
        job = await store.create("nousage", {})
        plan = op.ExecutionPlan(
            job_id=job.id,
            workers=[
                op.WorkerPlan(
                    worker_id="w1",
                    profile="builder",
                    mode=op.ExecutionMode.LOCAL_RUN,
                    command=_python_command("print('silent')"),
                    timeout_seconds=10,
                )
            ],
        )
        statuses = await run_plan_into_store(repo, plan, store)
        assert statuses["w1"].state is op.WorkerState.COMPLETED

        refreshed = await store.get(job.id)
        # No usage reported → no worker block drained, cost stays zero.
        assert refreshed.workers == {}
        assert refreshed.cost.totals()["cost_usd"] == 0.0
        assert refreshed.cost.totals()["call_count"] == 0

    asyncio.run(_run_test())


def test_run_plan_does_not_double_count(repo: Path):
    # Draining is exactly once per run: a single run_plan_into_store call folds
    # the worker's cost in once, never twice.
    async def _run_test():
        store = JobStore()
        job = await store.create("once", {})
        plan = op.ExecutionPlan(
            job_id=job.id,
            workers=_usage_plan(repo, job.id).workers,
        )
        await run_plan_into_store(repo, plan, store)

        refreshed = await store.get(job.id)
        totals = refreshed.cost.totals()
        # Cost counted exactly once: one call, single cost, not 2x.
        assert totals["call_count"] == 1
        assert totals["cost_usd"] == 0.0731
        assert totals["by_model"] == {"anthropic/claude-opus-4-8": 0.0731}

    asyncio.run(_run_test())


# ─── run_plan_into_store: adapter selection ───────────────────────────


def test_run_plan_defaults_to_inline_path(repo: Path):
    # With no adapter, every worker runs on the runner's inline subprocess path,
    # which writes each worker's streams into its OWN worker_dir (per-worker
    # isolation) — not a shared bare-adapter cwd. Assert completion, the usage
    # drain, and that the recorded stdout_path lives under the worker's dir.
    async def _run_test():
        store = JobStore()
        job = await store.create("inline-default", {})
        plan = op.ExecutionPlan(
            job_id=job.id, workers=_usage_plan(repo, job.id).workers
        )

        statuses = await run_plan_into_store(repo, plan, store)

        assert statuses["w1"].state is op.WorkerState.COMPLETED
        worker_root = op.worker_dir(repo, job.id, "w1")
        assert str(worker_root) in (statuses["w1"].stdout_path or "")

        refreshed = await store.get(job.id)
        assert refreshed.cost.totals()["cost_usd"] == 0.0731

    asyncio.run(_run_test())


def test_run_plan_uses_explicit_adapter_when_given(repo: Path):
    # A caller may opt a run onto a concrete adapter; the runner consults it
    # exactly once for the plain worker, which still completes and drains usage.
    async def _run_test():
        store = JobStore()
        job = await store.create("explicit", {})
        plan = op.ExecutionPlan(
            job_id=job.id, workers=_usage_plan(repo, job.id).workers
        )
        adapter = _RecordingAdapter(_adapter_for_worker(repo, job.id, "w1"))

        statuses = await run_plan_into_store(
            repo, plan, store, runtime_adapter=adapter
        )

        assert statuses["w1"].state is op.WorkerState.COMPLETED
        assert adapter.run_calls == 1
        refreshed = await store.get(job.id)
        assert refreshed.cost.totals()["cost_usd"] == 0.0731

    asyncio.run(_run_test())


def test_run_plan_inline_and_explicit_adapter_agree_on_cost(repo: Path):
    # The inline default and an explicit worker-rooted adapter drain identical
    # cost for a plain LOCAL_RUN worker.
    async def _run_test():
        store_inline = JobStore()
        store_adapter = JobStore()
        job_i = await store_inline.create("eq-inline", {})
        job_a = await store_adapter.create("eq-adapter", {})

        plan_i = op.ExecutionPlan(
            job_id=job_i.id, workers=_usage_plan(repo, job_i.id).workers
        )
        plan_a = op.ExecutionPlan(
            job_id=job_a.id, workers=_usage_plan(repo, job_a.id).workers
        )

        await run_plan_into_store(repo, plan_i, store_inline)  # inline default
        await run_plan_into_store(
            repo,
            plan_a,
            store_adapter,
            runtime_adapter=_adapter_for_worker(repo, job_a.id, "w1"),
        )  # explicit, worker-rooted adapter

        totals_i = (await store_inline.get(job_i.id)).cost.totals()
        totals_a = (await store_adapter.get(job_a.id)).cost.totals()
        assert totals_i == totals_a
        assert totals_i["cost_usd"] == 0.0731

    asyncio.run(_run_test())


def test_run_plan_passes_adapter_factory_through(repo: Path):
    # FU-2: the seam forwards adapter_factory to the runner; the factory-built
    # per-worker adapter runs the worker and usage still drains into the store.
    async def _run_test():
        store = JobStore()
        job = await store.create("factory", {})
        plan = op.ExecutionPlan(
            job_id=job.id, workers=_usage_plan(repo, job.id).workers
        )
        seen: list[str] = []

        def factory(worker, worker_root):
            seen.append(worker.worker_id)
            return op.per_worker_local_adapter(worker, worker_root)

        statuses = await run_plan_into_store(
            repo, plan, store, adapter_factory=factory
        )

        assert statuses["w1"].state is op.WorkerState.COMPLETED
        assert seen == ["w1"]
        refreshed = await store.get(job.id)
        assert refreshed.cost.totals()["cost_usd"] == 0.0731

    asyncio.run(_run_test())
