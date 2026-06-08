# FU-11: Enforce budget hard-stop on the single-job path (+ fix readiness-doctor false-PASS)

- **Status:** in-review
- **Risk class:** behavior-change (owner-gated) — only when a budget is configured; the default (no budget) path is byte-identical
- **Branch:** `claude/fu-11-budget-should-stop` · **Base:** `main` @ `b74f9889`
- **PR:** (draft — see ledger)
- **Owner-gate required to merge?** yes — this can change runtime behavior on the single-job dispatch path when a budget is set. Awaiting `Yes, with authorization.`

## Intent (one paragraph)

The per-job budget kernel (`hermes_cli/budget_policy.py` `evaluate_budget` /
`BudgetDecision.should_stop`) was enforced only on the **parallel** runner
(`orchestrator_parallel.ParallelRunner`). The **single-job** path
(`orchestrator.dispatch_job`) never metered cost or consulted the budget, so a
single-job run could not be hard-stopped — and the release-readiness doctor's
`_check_budget_enforced` falsely reported PASS because it only checked whether
*either* orchestrator file contained the string `should_stop`/`hard_exceeded`
(the parallel file matched, masking the single-job gap). This is a P0
honesty+safety fix. After this change, `dispatch_job` meters the worker's
reported `cost_usd` (reusing the parallel path's exact extraction guards) and,
once the accrued spend reaches a configured hard limit, stops the job
(`status = "blocked"`, ledger `budget_stop`/reason `budget_exhausted`) — before
any next worker can dispatch. The doctor check is tightened to PASS only when
the single-job path actually consults the budget. With **no budget configured
(both limits `None`)** the dispatch path is unchanged.

## Owned files (the ONLY files this task may write)

- `hermes_cli/orchestrator.py`
- `hermes_cli/release_readiness_doctor.py`
- `tests/test_orchestrator_budget.py` (new)
- `docs/launch/followups/fu-11-budget-should-stop.md` (this snapshot)

> Disjoint from `hermes_cli/budget_policy.py` and
> `hermes_cli/orchestrator_parallel.py`, which were **read only** (reused, never
> modified) per the task contract.

## Plan (bounded steps)

1. Reuse `budget_policy.evaluate_budget` / `BudgetDecision.should_stop` — no new
   primitive, no edit to the policy kernel or the parallel runner.
2. In `orchestrator.py`, add never-raising helpers:
   - `_worker_reported_cost(run_result)` — mirrors `ParallelRunner._note_cost`
     guards (positive numeric `cost_usd` from `WorkerRunResult.details`, direct
     or nested under a `usage` block; bool/non-numeric/non-positive ⇒ `0.0`).
   - `_budget_stop_for_spend(spent, soft_limit, hard_limit)` — mirrors
     `ParallelRunner._budget_stop_decision` (same `evaluate_budget` call, same
     `should_stop`); returns `None` when no budget is set or the subsystem errors.
   - `_job_recorded_cost(job_id)` — sums `cost_usd` recorded in the job's ledger
     `worker_result` entries (the single-job analogue of `_spent_usd`,
     recoverable across `dispatch_job` calls).
   - `_record_budget_stop(...)` — sets `status = "blocked"` and appends a
     `budget_stop` ledger entry (reason `budget_exhausted` + the policy numbers),
     idempotently.
3. `dispatch_job` gains optional `budget_soft_limit` / `budget_hard_limit`
   kwargs (both default `None`). A **pre-dispatch** guard refuses to launch the
   next worker when a configured budget is already exhausted; a **post-result**
   guard meters this worker's cost and stops if the hard limit is now reached.
   Both guards are skipped entirely when no budget is configured.
4. Tighten `release_readiness_doctor._check_budget_enforced`: a path "enforces"
   only when it both calls `evaluate_budget` **and** acts on the stop
   (`should_stop`/`hard_exceeded`/`budget_exhausted`). PASS requires BOTH the
   single-job and parallel paths to enforce; otherwise WARN with an honest
   detail naming the missing path. Still never raises.
5. Tests in `tests/test_orchestrator_budget.py`.

## Validation

- `uv run ruff check hermes_cli/orchestrator.py hermes_cli/release_readiness_doctor.py tests/test_orchestrator_budget.py` → **All checks passed!**
- `uv run ty check <those files>` → **no new diagnostics vs base.** Two
  diagnostics remain, both not introduced here: (1) `unresolved-import: pytest`
  in the new test file (the known/exempt one — every test file emits it); (2) a
  pre-existing `unused-type-ignore-comment` warning on `orchestrator.py:154`,
  confirmed present on base `b74f9889` (verified via `git stash` check).
- `python -m pytest tests/test_orchestrator_budget.py tests/test_orchestrator_commands.py tests/test_release_readiness_doctor.py -o addopts="" -q` → **136 passed.**
  (Also ran `tests/test_worker_dispatch.py tests/test_orchestrator_events.py` →
  55 passed, confirming the default dispatch path is unchanged.)

## Assumptions (conservative readings)

- **Budget source:** `dispatch_job` has no constructor and `Job` has no budget
  field, so the budget is supplied via optional kwargs that default to `None`
  — exactly the parallel runner's "unbounded by default" semantics. This keeps
  the default path byte-identical (no new persistent state, no config schema
  change). Wiring these kwargs to a CLI/cockpit budget source is left as a
  follow-on (it does not change the default path).
- **Accrued spend across calls:** since `dispatch_job` runs one worker per call,
  the per-worker `cost_usd` is recorded into the `worker_result` ledger entry
  (purely additive) and summed by `_job_recorded_cost`, so a multi-step
  single-job loop hard-stops correctly without a new in-memory meter.
- **Reason string:** the ledger `budget_stop` entry uses `reason:
  "budget_exhausted"` (per the task) and carries the policy's
  `meter/spent/soft_limit/hard_limit/detail` for auditability; the parallel path
  uses a `status.json` `budget` block with `stopped: true` + `detail`, which is a
  different surface (status projection vs decision ledger) — the single-job path
  records into the decision ledger, matching `dispatch_job`'s existing event style.

## Residual / follow-on

- Surfacing the two new `dispatch_job` budget kwargs through a CLI flag / cockpit
  / per-job config is not done here (out of scope; default path must stay
  unchanged). The kwargs are the seam a follow-on uses.
- Soft-limit ("ask"/owner-confirmation) handling on the single-job path is not
  wired — only the **hard** stop is enforced (matching the parallel runner,
  whose soft limit is also surfaced-not-blocked at the runner layer).
