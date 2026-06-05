# FU-3 — JobStore on-disk durability (restart-replay)

- **Status:** complete; built + validated + pushed. **OWNER-GATED merge** —
  the orchestrator holds the merge for explicit owner authorization.
- **Risk class:** **behavior-change / owner-gated.** Changes process-boot
  behavior (a restarted orchestrator now rehydrates jobs from disk) and starts
  writing a new per-job artifact under `HERMES_HOME`. No API signature changes;
  no schema changes to the ledger.
- **Branch / base:** `claude/fu-3-jobstore-persistence` cut from
  `origin/main` @ `b32db7033a4131c1d82d37126589a6f99112088f`.
- **Sprint gate:** Sprint-14 "restart mid-job → replay".

## Intent

The orchestrator's in-memory `JobStore` (`hermes_cli/orchestrator_api.py`)
keeps job state — and the event envelopes that produce it — purely in memory.
`hermes_cli/job_replay.rebuild_snapshot` already knows how to fold an ordered
event stream back into a `JobSnapshot`, and `GET /jobs/{id}/snapshot` exercises
it live, but there was **no durable event stream to replay from after a
restart**: `self._jobs` was rebuilt empty every process.

This change adds the missing durable seam so a restarted process replays
mid-job.

### Before / after boot behavior

- **Before:** start the orchestrator API → `JobStore` is empty. Any job that
  was mid-flight when the previous process died is gone; `GET /jobs` returns
  `{"jobs": []}` until new jobs arrive.
- **After:** start the orchestrator API (via `create_app`, persistence
  enabled) → `JobStore.restore_from_disk()` reads each job's durable
  `events.jsonl`, folds it through `rebuild_snapshot`, and reconstructs the
  `Job` in memory. `GET /jobs`, `/jobs/{id}/status`, `/jobs/{id}/snapshot`,
  `/jobs/{id}/workers` all reflect the pre-restart status / phase / workers /
  approvals / validation / publish-plan. Setting `HERMES_JOB_PERSIST=0`
  restores the old pure-in-memory behavior (no tee, no replay).

## Owned files (only these were created/modified)

- `hermes_cli/job_event_store.py` — **new.** Durable append-only per-job JSONL.
- `hermes_cli/orchestrator_api.py` — **modified.** Tee in `emit_event`;
  `JobStore.restore_from_disk` + `_job_from_snapshot`; `create_app` startup
  restore; refreshed two stale docstrings.
- `tests/test_orchestrator_restart_replay.py` — **new.** 30 tests.
- `docs/launch/followups/fu-3-jobstore-persistence.md` — **new.** This snapshot.

No other files touched. In particular: `orchestrator_parallel.py`,
`job_replay.py`, `orchestrator_events.py`, and the ledger were **not** changed.
The protected signatures (`JobStore.record_worker`, `JobStore.accumulate_cost`,
module-level `_extract_usage_report`) are unchanged.

## Design / plan

1. **`hermes_cli/job_event_store.py`** — stdlib-only, mirrors the crash-safe
   patterns in `gateway/cockpit/event_log.py`:
   - One append-only file per job at
     `${HERMES_HOME:-~/.hermes}/jobs/<job_id>/events.jsonl`.
   - `append(job_id, envelope)` — best-effort, swallows every error (never
     raises into the caller).
   - `read(job_id) -> list[dict]` — parses only **complete** lines (a line is
     complete iff it ends in `\n`), so a trailing line left by a crash
     mid-write is dropped, not raised on. Corrupt-but-complete lines are
     skipped too.
   - `iter_job_ids() -> list[str]` — reports a job id only when its
     `events.jsonl` exists, so a stray empty dir can't resurrect a phantom job.
   - `persistence_enabled()` / `PERSIST_ENV = "HERMES_JOB_PERSIST"` — opt-out
     switch. Unset ⇒ enabled. `0` / `false` / `no` / `off` / empty
     (case-insensitive) ⇒ every op becomes a no-op.
2. **`orchestrator_api.py` — the only fast-path edit** is in
   `JobStore.emit_event`: after the existing in-memory append, a best-effort
   `job_event_store.append(job_id, envelope)` wrapped in an extra `try/except`
   (belt-and-braces; the module function already swallows errors and no-ops
   when disabled). It can **never** raise into the emit path.
3. **`JobStore.restore_from_disk(self) -> int`** — iterates
   `job_event_store.iter_job_ids()`, reads each job's envelopes, folds via
   `rebuild_snapshot`, and reconstructs a `Job` via the helper
   `_job_from_snapshot`. The loaded envelopes are re-seeded onto `job.events`
   (and `job.logs`) so the live `snapshot()` route — which re-folds
   `job.events` — keeps working post-restart. A job already present in
   `self._jobs` is left untouched (the live copy wins; restore is idempotent).
   Synchronous, intended to run once at startup before the loop serves
   requests, so it does not take the async lock. Best-effort per job.
   - **Shape bridging in `_job_from_snapshot`:** `JobSnapshot.workers`
     (`{worker: state}`) → `Job.workers` (`{worker: {"state": state}}`);
     `JobSnapshot.approvals` (`{id: state}`) → `Job.approvals`
     (`list[{"id", "state"}]`). `status` / `phase` / `name` / `spec` /
     `validation` / `publish_plan` / `error` map directly.
4. **`create_app` wiring** — after `store = store or JobStore()`, restore runs
   **only** when `create_app` itself created the store (`owns_store = store is
   None`) **and** persistence is enabled. An injected/test store is never
   restored (caller owns its lifecycle). Constructing a bare `JobStore()`
   directly does **not** auto-restore — restore is wired here and only here, so
   the 100s of existing in-memory tests stay pure. Restore failures are caught
   and logged so a bad on-disk log can never crash boot.

## Validation results

Run from the worktree on branch `claude/fu-3-jobstore-persistence`.

- **ruff** — `uv run ruff check hermes_cli/job_event_store.py
  hermes_cli/orchestrator_api.py tests/test_orchestrator_restart_replay.py`
  → **All checks passed!**
- **ty** — `uv run --extra all --extra dev ty check
  hermes_cli/job_event_store.py hermes_cli/orchestrator_api.py`
  → **All checks passed!** (0 diagnostics).
  No new diagnostics vs base: the base `origin/main` `orchestrator_api.py`
  also reports 0 in the same `all`+`dev` venv. (In a minimal venv lacking the
  `[web]` extra, both base and head report an identical 35 pre-existing
  diagnostics — all from the missing `fastapi`/`uvicorn` import and the
  FastAPI-fallback `object` shims — so still **no new** diagnostics.)
- **pytest** — `uv run --extra all --extra dev pytest
  tests/test_orchestrator_restart_replay.py tests/test_job_replay.py
  tests/test_orchestrator_api.py -o addopts="" -q` → **123 passed**.
  - `test_orchestrator_restart_replay.py`: **30 passed** (new).
  - `test_job_replay.py`: **11 passed** (regression floor — green).
  - `test_orchestrator_api.py`: **82 passed** (regression floor — green;
    includes the bare-`JobStore()` and `create_app()` tests that must stay
    pure in-memory).

### Confirmation: bare-JobStore tests stayed green

`test_orchestrator_api.py` (82 passed) constructs bare `JobStore()` instances
and calls `create_app()` with no injected store throughout. They remain green
because (a) constructing `JobStore()` never auto-restores, and (b) under the
repo's autouse `_hermetic_environment` fixture each test gets a fresh empty
`HERMES_HOME` tempdir, so `create_app()`'s startup restore finds no `jobs/`
dir and no-ops. `test_list_jobs_empty` (`{"jobs": []}`) and
`test_list_jobs_after_create` (`["a", "b"]`) both still hold. A dedicated new
test (`test_bare_jobstore_does_not_auto_restore`) pins the guarantee: even with
a job already persisted to disk, a bare `JobStore().list()` is `[]`.

## Known limitation — JobCost is NOT event-sourced

`rebuild_snapshot` (`hermes_cli/job_replay.py`) has **no cost field** — cost is
accumulated via `JobStore.accumulate_cost` into `Job.cost` (a `JobCost`) and is
not emitted as events. Therefore a **restored job's cost resets to `0`** (zero
tokens, `cost_usd == 0.0`). This is acceptable for the Sprint-14 gate, which
covers **status / phase / workers / approvals** (all faithfully restored).
Event-sourcing `JobCost` — either by emitting a cost event or by persisting a
sidecar `cost.json` and reloading it in `_job_from_snapshot` — is a clean,
additive follow-up that this change deliberately does not take on (it would
require touching `job_replay.py`, which is out of scope here). The limitation
is asserted explicitly by `test_cost_not_restored_known_limitation`.

## Behavior change summary (for the owner merge gate)

> This PR gives the orchestrator's in-memory job store on-disk durability.
> Every job event is now teed, best-effort and crash-safe, to a new
> append-only file at `${HERMES_HOME:-~/.hermes}/jobs/<job_id>/events.jsonl`,
> and at startup `create_app` replays those files to reconstruct any
> mid-flight job's status, phase, workers, approvals, validation, and publish
> plan — so a restarted process resumes where it left off instead of coming up
> empty. The write path can never raise (a persistence failure leaves the live
> in-memory store untouched), the feature is opt-out via `HERMES_JOB_PERSIST=0`
> (which restores the prior pure-in-memory boot), and constructing a bare
> `JobStore()` still never touches disk, so existing behavior and the full
> in-memory test suite are preserved. The one accepted gap: per-job **cost**
> is not event-sourced, so a restored job's cost meter resets to zero — fine
> for the status/phase/workers/approvals restart-replay gate, and a documented
> additive follow-up. New on-disk artifact under `HERMES_HOME` + changed boot
> behavior are why this is classed behavior-change / owner-gated.
