"""Dispatcher seam: run a :class:`ParallelRunner` plan into a :class:`JobStore`.

This is the missing hop between the two halves of the Sprint 10 per-job cost
seam. Both ends already exist and are tested:

* the **producer** — :class:`hermes_cli.orchestrator_parallel.ParallelRunner`
  runs an :class:`~hermes_cli.orchestrator_parallel.ExecutionPlan`, persists each
  worker's reported token/cost usage into ``status.json``, and exposes it via
  :func:`~hermes_cli.orchestrator_parallel.iter_worker_usage`; and
* the **consumer** — :class:`hermes_cli.orchestrator_api.JobStore` folds a
  worker report into the job's :class:`~hermes_cli.job_cost.JobCost` aggregate
  via :meth:`~hermes_cli.orchestrator_api.JobStore.record_worker` +
  :meth:`~hermes_cli.orchestrator_api.JobStore.accumulate_cost`.

The runner is deliberately standalone — it never touches a ``JobStore`` — so
nothing drained its persisted usage into a live job's cost meter. This module is
that drain, expressed exactly like the HTTP ``POST /jobs/{id}/workers/{worker}``
route in :mod:`hermes_cli.orchestrator_api`: record the worker block, then route
the usage through the module-level
:func:`~hermes_cli.orchestrator_api._extract_usage_report` before calling
``accumulate_cost``. That routing matters — each ``usage`` block from
``iter_worker_usage`` carries a *plain token-bucket dict*, not a
``CanonicalUsage`` object, so ``accumulate_cost(**block)`` would mis-shape the
usage; ``_extract_usage_report`` is the converter the HTTP path already uses.

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
from typing import TYPE_CHECKING, Any, Optional, Union

from hermes_cli.orchestrator_api import JobStore, _extract_usage_report
from hermes_cli.orchestrator_parallel import (
    ExecutionPlan,
    ParallelRunner,
    WorkerStatus,
    iter_worker_usage,
)
from hermes_cli.runtime_adapter import LocalRuntimeAdapter, RuntimeAdapter

if TYPE_CHECKING:  # pragma: no cover - typing only
    pass

__all__ = ["run_plan_into_store", "_default_adapter"]


def _default_adapter(
    runtime_adapter: Union[RuntimeAdapter, bool, None],
) -> Optional[RuntimeAdapter]:
    """Resolve the runtime adapter :func:`run_plan_into_store` hands the runner.

    The default is a :class:`~hermes_cli.runtime_adapter.LocalRuntimeAdapter`
    rather than ``None`` (the runner's own default, the inline subprocess path).
    For a *plain* LOCAL_RUN worker the two are observably equivalent — the
    adapter-backed run maps onto the same
    :class:`~hermes_cli.orchestrator_parallel.WorkerStatus` fields (terminal
    state, return code, captured streams, folded usage). For a worker that
    carries per-worker placement the adapter cannot honor — its own ``cwd``, an
    ``env`` overlay, or a worktree-derived cwd — the runner *already* keeps it on
    the inline path via
    :func:`~hermes_cli.orchestrator_parallel._needs_inline_placement`, so
    defaulting the adapter never silently runs such a worker in the wrong
    directory/environment. Defaulting it here therefore changes nothing
    observable for plain LOCAL_RUN workers while making the dispatcher's
    execution path explicit.

    The three resolutions:

    * ``runtime_adapter is False`` — an explicit opt-out: return ``None`` so the
      runner uses its inline subprocess path for *every* worker (the historical
      default). Use this to force the inline path even for plain workers.
    * a concrete :class:`RuntimeAdapter` — passed straight through.
    * ``None`` (the default) — a fresh
      :class:`~hermes_cli.runtime_adapter.LocalRuntimeAdapter`.
    """

    if runtime_adapter is None:
        return LocalRuntimeAdapter()
    if isinstance(runtime_adapter, bool):
        # ``False`` is the explicit inline opt-out. ``True`` is not a valid
        # adapter and is not a meaningful sentinel — reject it loudly rather
        # than hand the runner a bool it would try to ``.run`` on.
        if runtime_adapter is False:
            return None
        raise TypeError(
            "runtime_adapter=True is not valid; pass an adapter, None, or False"
        )
    return runtime_adapter


async def run_plan_into_store(
    repo: Union[str, Path],
    plan: ExecutionPlan,
    store: JobStore,
    *,
    runtime_adapter: Union[RuntimeAdapter, bool, None] = None,
) -> dict[str, WorkerStatus]:
    """Run ``plan`` via a :class:`ParallelRunner` and drain usage into ``store``.

    This is the dispatcher seam that connects the standalone runner to a live
    job's cost aggregate. It:

    1. constructs a :class:`ParallelRunner` for ``plan`` with the adapter
       resolved by :func:`_default_adapter` (a
       :class:`~hermes_cli.runtime_adapter.LocalRuntimeAdapter` unless overridden
       / opted out with ``runtime_adapter=False``);
    2. runs it off the event loop via :func:`asyncio.to_thread` — the runner is
       blocking (real subprocesses, ``time.sleep`` polling), so running it inline
       would stall the loop and every other coroutine sharing it; and
    3. drains the persisted per-worker usage **exactly once** through the same
       routing the HTTP worker-report route uses: record the worker block via
       :meth:`JobStore.record_worker`, then convert it with
       :func:`~hermes_cli.orchestrator_api._extract_usage_report` before
       :meth:`JobStore.accumulate_cost`. A worker that reported no usage
       contributes nothing (``_extract_usage_report`` returns ``None``).

    The single drain pass is the double-count guard: ``iter_worker_usage`` yields
    each reporting worker once, and we fold each at most once, so calling this for
    a job that already accumulated cost from another source still only adds this
    run's usage one time.

    Args:
        repo: The repository root the plan's artifacts live under.
        plan: The :class:`ExecutionPlan` to execute.
        store: The :class:`JobStore` whose ``plan.job_id`` job receives the
            per-worker state and accumulated cost.
        runtime_adapter: Adapter override. ``None`` (default) uses a
            :class:`~hermes_cli.runtime_adapter.LocalRuntimeAdapter`; ``False``
            forces the runner's inline subprocess path; a concrete adapter is
            used as-is. See :func:`_default_adapter`.

    Returns:
        The per-worker :class:`WorkerStatus` map the runner produced.
    """

    # Normalize once: the runner / drain helpers take a ``Path``; accepting a
    # ``str`` here is a caller convenience.
    repo_path = Path(repo)
    runner = ParallelRunner(
        repo_path,
        plan,
        runtime_adapter=_default_adapter(runtime_adapter),
    )
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
