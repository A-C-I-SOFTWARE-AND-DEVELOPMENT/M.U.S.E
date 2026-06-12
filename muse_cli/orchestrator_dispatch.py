"""Dispatcher seam: run a :class:`ParallelRunner` plan into a :class:`JobStore`.

This is the missing hop between the two halves of the Sprint 10 per-job cost
seam. Both ends already exist and are tested:

* the **producer** — :class:`muse_cli.orchestrator_parallel.ParallelRunner`
  runs an :class:`~muse_cli.orchestrator_parallel.ExecutionPlan`, persists each
  worker's reported token/cost usage into ``status.json``, and exposes it via
  :func:`~muse_cli.orchestrator_parallel.iter_worker_usage`; and
* the **consumer** — :class:`muse_cli.orchestrator_api.JobStore` folds a
  worker report into the job's :class:`~muse_cli.job_cost.JobCost` aggregate
  via :meth:`~muse_cli.orchestrator_api.JobStore.record_worker` +
  :meth:`~muse_cli.orchestrator_api.JobStore.accumulate_cost`.

The runner is deliberately standalone — it never touches a ``JobStore`` — so
nothing drained its persisted usage into a live job's cost meter. This module is
that drain, expressed exactly like the HTTP ``POST /jobs/{id}/workers/{worker}``
route in :mod:`muse_cli.orchestrator_api`: record the worker block, then route
the usage through the module-level
:func:`~muse_cli.orchestrator_api._extract_usage_report` before calling
``accumulate_cost``. That routing matters — each ``usage`` block from
``iter_worker_usage`` carries a *plain token-bucket dict*, not a
``CanonicalUsage`` object, so ``accumulate_cost(**block)`` would mis-shape the
usage; ``_extract_usage_report`` is the converter the HTTP path already uses.

**Adapter policy — inline by default; an adapter is caller opt-in.** The runner
executes a LOCAL_RUN worker on its inline subprocess path unless a
:class:`~muse_cli.runtime_adapter.RuntimeAdapter` is injected. This seam does
**not** default one in, on purpose: a ``ParallelRunner`` holds a *single* adapter
instance shared across every worker, and a ``LocalRuntimeAdapter`` has one
construction-time ``workdir`` / stream pair — so defaulting a bare adapter would
make every plain worker in a multi-worker plan write ``stdout.log`` /
``stderr.log`` into the *same* directory, clobbering each other, instead of each
worker's own ``worker_dir`` the way the inline path does. The inline default
preserves that per-worker isolation. A caller may still pass an explicit adapter
(it then owns the workdir/stream placement); a *safe default* adapter needs a
per-worker adapter factory on the runner — a separate follow-up, not this seam.

Scope / honesty: this lands the **tested seam only**. An audit established there
is no live caller of :class:`ParallelRunner` today, so nothing in a running
server calls :func:`run_plan_into_store` yet — wiring the server's job
dispatcher to call it (so per-job cost stops reading ``0`` in a real server) is a
separate owner decision and a documented follow-up. This module imports from the
runner and the API; it never mutates them.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Optional, Union

from muse_cli.orchestrator_api import JobStore, _extract_usage_report
from muse_cli.orchestrator_parallel import (
    ExecutionPlan,
    ParallelRunner,
    WorkerStatus,
    iter_worker_usage,
)
from muse_cli.runtime_adapter import RuntimeAdapter

__all__ = ["run_plan_into_store"]


async def run_plan_into_store(
    repo: Union[str, Path],
    plan: ExecutionPlan,
    store: JobStore,
    *,
    runtime_adapter: Optional[RuntimeAdapter] = None,
) -> dict[str, WorkerStatus]:
    """Run ``plan`` via a :class:`ParallelRunner` and drain usage into ``store``.

    This is the dispatcher seam that connects the standalone runner to a live
    job's cost aggregate. It:

    1. constructs a :class:`ParallelRunner` for ``plan``. ``runtime_adapter``
       defaults to ``None`` — the runner's inline subprocess path, which gives
       each worker its own ``worker_dir`` stream files. Pass a concrete
       :class:`~muse_cli.runtime_adapter.RuntimeAdapter` to opt a run onto an
       adapter (the caller then owns its ``workdir`` / stream placement); the
       module docstring explains why no adapter is defaulted in here;
    2. runs it off the event loop via :func:`asyncio.to_thread` — the runner is
       blocking (real subprocesses, ``time.sleep`` polling), so running it inline
       would stall the loop and every other coroutine sharing it; and
    3. drains the persisted per-worker usage **exactly once** through the same
       routing the HTTP worker-report route uses: record the worker block via
       :meth:`JobStore.record_worker`, then convert it with
       :func:`~muse_cli.orchestrator_api._extract_usage_report` before
       :meth:`JobStore.accumulate_cost`. A worker that reported no usage
       contributes nothing (``_extract_usage_report`` returns ``None``).

    The single drain pass is the double-count guard: ``iter_worker_usage`` yields
    each reporting worker once, and we fold each at most once.

    Args:
        repo: The repository root the plan's artifacts live under.
        plan: The :class:`ExecutionPlan` to execute.
        store: The :class:`JobStore` whose ``plan.job_id`` job receives the
            per-worker state and accumulated cost.
        runtime_adapter: ``None`` (default) runs every worker on the runner's
            inline subprocess path; a concrete adapter opts the run onto that
            adapter.

    Returns:
        The per-worker :class:`WorkerStatus` map the runner produced.
    """

    # Normalize once: the runner / drain helpers take a ``Path``; accepting a
    # ``str`` here is a caller convenience.
    repo_path = Path(repo)
    runner = ParallelRunner(repo_path, plan, runtime_adapter=runtime_adapter)
    # The runner blocks (subprocess launches + poll-sleep loop); keep the event
    # loop free so concurrent coroutines (e.g. WebSocket fan-out) are not stalled.
    statuses = await asyncio.to_thread(runner.run)

    # Drain the persisted usage into the job's cost aggregate — exactly once per
    # run. Each ``block`` is a plain {usage: {token dict}, cost_usd, ...} report,
    # so route it through _extract_usage_report (the HTTP path's converter)
    # rather than accumulate_cost(**block): the block's ``usage`` is a dict, not a
    # CanonicalUsage-shaped object.
    for worker_id, block in iter_worker_usage(repo_path, plan.job_id):
        await store.record_worker(plan.job_id, worker_id, dict(block))
        report: Optional[dict[str, Any]] = _extract_usage_report(block)
        if report:
            await store.accumulate_cost(plan.job_id, **report)

    return statuses
