# FU-1 — Dispatcher seam: run a ParallelRunner plan into a JobStore

- **Status:** complete (tested seam; not yet wired to a live caller)
- **Risk class:** additive (new module + new tests only; no existing file modified)
- **Branch:** `claude/fu-1-dispatch-seam`
- **Base:** `origin/main` @ `b32db7033a4131c1d82d37126589a6f99112088f`
- **Owned files (created):**
  - `hermes_cli/orchestrator_dispatch.py`
  - `tests/test_orchestrator_dispatch.py`
  - `docs/launch/followups/fu-1-dispatch-seam.md` (this snapshot)

## Reviewer correction (2026-06-05)

The first build defaulted the runner's adapter to a bare `LocalRuntimeAdapter()`
and added an autouse `_isolated_cwd` fixture to hide a side effect. That default
is **unsafe for multi-worker plans**: `ParallelRunner` shares one adapter
instance across every worker, and a bare `LocalRuntimeAdapter` has a single
construction-time `workdir`/stream pair (defaulting to `cwd`), so every plain
worker would write `stdout.log`/`stderr.log` into the *same* directory,
clobbering each other instead of each landing in its own `worker_dir` (the
inline path's per-worker isolation). Corrected: **the default is now `None`
(inline)**; an adapter is *caller opt-in* only. `_default_adapter` and the
`runtime_adapter=False/True` sentinels were removed, and the masking fixture
deleted. A *safe* default adapter needs a per-worker adapter factory on the
runner — a separate follow-up, not this seam. ("default adapter injection",
the old FU-2, is therefore **deferred**, not shipped.)

## Intent

Close the missing hop in the Sprint 10 per-job cost seam. Both ends already
existed and were tested:

- **Producer** — `hermes_cli.orchestrator_parallel.ParallelRunner` runs an
  `ExecutionPlan`, persists each worker's reported token/cost usage into
  `status.json`, and exposes it via `iter_worker_usage`.
- **Consumer** — `hermes_cli.orchestrator_api.JobStore` folds a worker report
  into the job's `JobCost` via `record_worker` + `accumulate_cost`, with the
  module-level `_extract_usage_report` doing the report→kwargs conversion.

The runner is deliberately standalone (it never touches a `JobStore`), so
nothing drained its persisted usage into a live job's cost meter. This lands
that drain as a single dispatcher function, expressed **exactly** like the HTTP
`POST /jobs/{id}/workers/{worker}` route's usage routing.

## What it does

`hermes_cli/orchestrator_dispatch.py` — `async def run_plan_into_store(repo, plan, store, *, runtime_adapter=None)`:

- constructs `ParallelRunner(repo, plan, runtime_adapter=runtime_adapter)`.
  `runtime_adapter=None` (default) → the runner's **inline** subprocess path,
  which gives each worker its own `worker_dir` stream files. A concrete adapter
  opts the run onto that adapter (caller owns its `workdir`/stream placement).
  No adapter is defaulted in (see Reviewer correction).
- runs it off the event loop: `statuses = await asyncio.to_thread(runner.run)`
  (the runner is blocking — real subprocess launches + a `time.sleep` poll loop).
- drains exactly once, mirroring the HTTP route's routing:
  ```python
  for worker_id, block in iter_worker_usage(repo_path, plan.job_id):
      await store.record_worker(plan.job_id, worker_id, dict(block))
      report = _extract_usage_report(block)
      if report:
          await store.accumulate_cost(plan.job_id, **report)
  ```
  It does **not** call `accumulate_cost(**block)`: each `block["usage"]` is a
  plain token-bucket *dict*, so it must go through `_extract_usage_report` (the
  same converter the HTTP path uses).
- **Double-count guard:** single drain pass; each reporting worker folded once.
- returns `statuses`.

## Tests (`tests/test_orchestrator_dispatch.py`, 7 cases)

Async style follows `tests/test_orchestrator_api.py` (sync test wraps an inner
coroutine in `asyncio.run`). LOCAL_RUN + usage-sidecar helpers mirror
`tests/test_parallel_orchestration.py`.

- `test_run_plan_drains_worker_and_cost_into_store`: a sidecar-writing worker →
  store reflects the worker block **and** accumulated cost; totals + `by_model`
  match the HTTP path exactly.
- `test_run_plan_returns_runner_statuses`: returns the runner's `WorkerStatus` map.
- `test_run_plan_no_usage_leaves_cost_zero`: a silent worker drains nothing.
- `test_run_plan_does_not_double_count`: one call folds cost once.
- `test_run_plan_defaults_to_inline_path`: no adapter → worker completes, usage
  drains, and the recorded `stdout_path` lives under the worker's `worker_dir`
  (proves per-worker inline isolation, not a shared bare-adapter cwd).
- `test_run_plan_uses_explicit_adapter_when_given`: an explicit worker-rooted
  recording adapter is consulted exactly once and usage still drains.
- `test_run_plan_inline_and_explicit_adapter_agree_on_cost`: inline default and
  an explicit worker-rooted adapter drain identical cost.

## Validation (exact commands + results)

1. `uv run ruff check hermes_cli/orchestrator_dispatch.py tests/test_orchestrator_dispatch.py` → **All checks passed!**
2. `uv run ty check hermes_cli/orchestrator_dispatch.py` → **All checks passed!** (no new diagnostics)
3. `uv run --extra all --extra dev pytest tests/test_orchestrator_dispatch.py -o addopts="" -q` → **7 passed**

## Residual / honest limitation

1. **No live caller yet.** There is no live caller of `ParallelRunner` in the
   repo, so this module is the tested seam only. Wiring the server's job
   dispatcher to call `run_plan_into_store` is a **separate owner decision** and
   a documented follow-up; until it lands, per-job cost still reads `0` in a real
   running server.
2. **Default adapter injection deferred.** A safe default adapter needs a
   per-worker adapter factory on `ParallelRunner` (so each worker gets its own
   `workdir`/streams). That is out of this seam's owned files and is a separate
   follow-up. This module strictly imports from `orchestrator_parallel.py`,
   `orchestrator_api.py`, and `runtime_adapter.py`; it modifies none of them.
