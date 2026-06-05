# FU-1 — Dispatcher seam: run a ParallelRunner plan into a JobStore

- **Status:** complete (tested seam; not yet wired to a live caller)
- **Risk class:** additive (new module + new tests only; no existing file modified)
- **Branch:** `claude/fu-1-dispatch-seam`
- **Base:** `origin/main` @ `b32db7033a4131c1d82d37126589a6f99112088f`
- **Owned files (created):**
  - `hermes_cli/orchestrator_dispatch.py`
  - `tests/test_orchestrator_dispatch.py`
  - `docs/launch/followups/fu-1-dispatch-seam.md` (this snapshot)

## Intent

Close the missing hop in the Sprint 10 per-job cost seam. Both ends already
existed and were tested:

- **Producer** — `hermes_cli.orchestrator_parallel.ParallelRunner` runs an
  `ExecutionPlan`, persists each worker's reported token/cost usage into
  `status.json`, and exposes it via `iter_worker_usage(repo, job_id) ->
  list[(worker_id, block)]`.
- **Consumer** — `hermes_cli.orchestrator_api.JobStore` folds a worker report
  into the job's `JobCost` via `record_worker` + `accumulate_cost`, with the
  module-level `_extract_usage_report` doing the report→kwargs conversion.

The runner is deliberately standalone (it never touches a `JobStore`), so
nothing drained its persisted usage into a live job's cost meter. This lands
that drain as a single dispatcher function, expressed **exactly** like the HTTP
`POST /jobs/{id}/workers/{worker}` route's usage routing.

Audit note: there is **no live caller of `ParallelRunner`** in the repo today,
so this is the *tested seam* only — see the residual below.

## What it does

`hermes_cli/orchestrator_dispatch.py`:

- `async def run_plan_into_store(repo, plan, store, *, runtime_adapter=None)`:
  - constructs `ParallelRunner(repo, plan, runtime_adapter=_default_adapter(runtime_adapter))`;
  - runs it without blocking the event loop: `statuses = await asyncio.to_thread(runner.run)`
    (the runner is blocking — real subprocess launches + a `time.sleep` poll loop);
  - drains exactly once, mirroring the HTTP route's routing:
    ```python
    for worker_id, block in iter_worker_usage(repo_path, plan.job_id):
        await store.record_worker(plan.job_id, worker_id, dict(block))
        report = _extract_usage_report(block)
        if report:
            await store.accumulate_cost(plan.job_id, **report)
    ```
    It does **not** call `accumulate_cost(**block)`: each `block["usage"]` is a
    plain token-bucket *dict*, not a `CanonicalUsage`-shaped object, so it must
    go through `_extract_usage_report` (the same converter the HTTP path uses).
  - returns `statuses`.
- `def _default_adapter(runtime_adapter)`:
  - `None` (default) → a fresh `LocalRuntimeAdapter()`;
  - `False` → `None` (explicit opt-out to the runner's inline subprocess path
    for every worker);
  - a concrete adapter → passed through;
  - `True` → `TypeError` (not a valid adapter, not a meaningful sentinel —
    rejected loudly rather than handed to the runner as a bool).

  Defaulting the adapter is **observably equivalent** for plain LOCAL_RUN
  workers: the runner already routes any placement-bearing worker
  (`cwd` / `env` / `use_worktree`) back to the inline path via
  `_needs_inline_placement`, so defaulting the adapter never runs such a worker
  in the wrong directory/environment.

- **Double-count guard:** the drain is a single pass; `iter_worker_usage` yields
  each reporting worker once and each is folded at most once.

- `repo: str | Path` is normalized once to `Path` (`repo_path`) before being
  handed to the runner / `iter_worker_usage`, both of which declare `repo: Path`
  — keeps `ty` clean while allowing a `str` at the public boundary.

## Tests (`tests/test_orchestrator_dispatch.py`, 10 cases)

Async style follows `tests/test_orchestrator_api.py` (a sync test wraps an inner
coroutine in `asyncio.run`; no pytest-asyncio marker). LOCAL_RUN + usage-sidecar
helpers are mirrored from `tests/test_parallel_orchestration.py`
(`_usage_writer_command` emits the canonical `claude-opus-4-8` / `$0.0731`
block; `_RecordingAdapter` is the run-call spy).

- `_default_adapter`: `None`→`LocalRuntimeAdapter`; `False`→`None` (inline
  opt-out); concrete adapter passes through.
- `test_run_plan_drains_worker_and_cost_into_store`: a LOCAL_RUN worker writing
  a usage sidecar → the `JobStore` reflects the worker block **and** the
  accumulated cost; totals + `by_model` match the HTTP path exactly
  (`cost_usd=0.0731`, `input=1200`, `output=300`, `cache_read=800`,
  `reasoning=40`, `call_count=1`, `by_model={"anthropic/claude-opus-4-8": 0.0731}`).
- `test_run_plan_returns_runner_statuses`: returns the runner's `WorkerStatus`
  map.
- `test_run_plan_no_usage_leaves_cost_zero`: a silent worker drains nothing
  (additive default — `workers == {}`, `cost_usd == 0.0`).
- `test_run_plan_does_not_double_count`: one call folds the cost in once
  (`call_count == 1`).
- `test_run_plan_uses_default_adapter_for_plain_worker`: a recording adapter is
  invoked exactly once for a plain worker (`run_calls == 1`) and usage still
  drains.
- `test_run_plan_false_adapter_forces_inline_path`: `runtime_adapter=False`
  bypasses an injected spy (`run_calls == 0`) yet the worker completes and usage
  drains.
- `test_run_plan_inline_and_adapter_paths_agree_on_cost`: default-adapter run
  and inline run produce identical cost totals.

An autouse `_isolated_cwd` fixture chdir's each test into a throwaway dir,
because the bare default `LocalRuntimeAdapter()` defaults its `workdir` to
`Path.cwd()` and would otherwise drop `stdout.log`/`stderr.log` in the repo
root. All other test paths are absolute under their own `tmp_path/repo`, so the
chdir is otherwise inert. (Verified: post-run `git status` shows only the two
owned files, no stray logs.)

## Validation (exact commands + results)

Tooling: `ruff 0.15.10`, `ty 0.0.21`, CPython 3.11.15.

1. `uv run ruff check hermes_cli/orchestrator_dispatch.py tests/test_orchestrator_dispatch.py`
   → **All checks passed!**
2. `uv run ty check hermes_cli/orchestrator_dispatch.py`
   → **All checks passed!** (no new diagnostics)
3. `uv run --extra all --extra dev pytest tests/test_orchestrator_dispatch.py -o addopts="" -q`
   → **10 passed**
4. Regression: `uv run --extra all --extra dev pytest tests/test_parallel_orchestration.py -o addopts="" -q -k "usage or cost or adapter"`
   → **21 passed, 31 deselected**

(Additional sanity, not required: `pytest tests/test_orchestrator_api.py -k "cost or usage or accumulate or worker"` → 24 passed, 58 deselected.)

## Residual / honest limitation

**Nothing live calls `run_plan_into_store` yet.** The audit confirmed there is
no live caller of `ParallelRunner` in the repo, so this module is the tested
seam only. Wiring the server's job dispatcher to call `run_plan_into_store` —
the server→dispatcher hop — is a **separate owner decision** and a documented
follow-up. Until that lands, per-job cost still reads `0` in a real running
server (the seam is reachable and correct; it just isn't invoked by the live
HTTP/orchestration path). This module strictly *imports from*
`orchestrator_parallel.py`, `orchestrator_api.py`, and `runtime_adapter.py`; it
modifies none of them.
