# Hermes 10/10 — Follow-ups Ledger (audit trail)

**Single-writer.** Per the *Parallel follow-up execution contract* in
[`CLAUDE.md`](../../CLAUDE.md), only the orchestrator session edits this
file. Parallel builder agents write their own snapshot under
[`followups/`](followups/) and never touch this ledger. On resume, read
this file first — it is how state is rebuilt with no context lost.

**Date opened:** 2026-06-05 · **Base:** `main` @ `b32db703` (all six glue-hops merged)

These are the residual follow-ups recorded in
[`10_10_PROGRAM_STATUS.md`](10_10_PROGRAM_STATUS.md). Ownership is finalized
from four read-only audits, so the parallel partition is conflict-free by
construction (no two in-flight tasks share a writable file).

## Status legend

`planned` → `building` (agent dispatched) → `in-review` (PR open, CI/Codex)
→ `merged`. Side states: `blocked` (needs a decision/owner gate),
`deferred` (out of scope for now).

## Ownership map (disjoint — the conflict-prevention guarantee)

| Task | Title | Owned files (the ONLY writable set) | Risk class | Status | Snapshot |
|---|---|---|---|---|---|
| **FU-1** | Orchestrator dispatch seam — drain `iter_worker_usage` → `JobStore` **+** default `LocalRuntimeAdapter` (old FU-1+FU-2 combined: both live in one new module) | **CREATE** `hermes_cli/orchestrator_dispatch.py` · **CREATE** `tests/test_orchestrator_dispatch.py` (imports but never writes `orchestrator_parallel`/`orchestrator_api`/`runtime_adapter`) | additive (new module; no live caller yet) | building | [`followups/fu-1-dispatch-seam.md`](followups/fu-1-dispatch-seam.md) |
| **FU-3** | JobStore durability — on-disk event log + restart rebuild | **CREATE** `hermes_cli/job_event_store.py` · **MODIFY** `hermes_cli/orchestrator_api.py` (tee in `emit_event`, new `restore_from_disk`, one line in `create_app`) · **CREATE** `tests/test_orchestrator_restart_replay.py` | **behavior change (server boot now restores) → owner-gated** | building | [`followups/fu-3-jobstore-persistence.md`](followups/fu-3-jobstore-persistence.md) |
| **FU-4** | Unified release gate — `doctor --release-gate` aggregating the 22 `--10-10` checks + ruff + a fast test slice | **CREATE** `hermes_cli/release_gate.py` · **MODIFY** `hermes_cli/main.py` (doctor subparser block only: new `--release-gate` flag + `cmd_release_gate` handler + one dispatch line) · **CREATE** `tests/test_release_gate.py` | additive | in-review (#328) | [`followups/fu-4-release-gate.md`](followups/fu-4-release-gate.md) |
| **FU-5** | Supabase status-doc correction (it is **already built** — full tool plugin + memory backend + integration adapter, **47 tests pass**; the "absent" claim was stale) | **MODIFY** `docs/launch/10_10_PROGRAM_STATUS.md` (Supabase rows only) | doc-only | in-review (#327) | [`followups/fu-5-supabase-doc.md`](followups/fu-5-supabase-doc.md) |

**Disjointness proof (pairwise):** FU-1 → {`orchestrator_dispatch.py`, its test};
FU-3 → {`job_event_store.py`, `orchestrator_api.py`, its test} (sole writer of
`orchestrator_api.py`; FU-1 only *imports* it); FU-4 → {`release_gate.py`,
`main.py`, its test} (sole writer of `main.py`); FU-5 → {the status doc}. No
writable file appears in two sets. ✓

## Parallelization plan

**Wave 1 — all four in parallel** (FU-1, FU-3, FU-4, FU-5): writable sets
proven pairwise disjoint by the four audits. Each runs on its own
branch+worktree (`claude/fu-<id>-<slug>`) cut from `main` @ `b32db703`, writes
only its snapshot + owned files, validates, and opens a **draft** PR.

Old **FU-2** (default adapter) folded into **FU-1**: audit A showed both belong
in the single new `orchestrator_dispatch.py`, so splitting them would
manufacture a conflict.

## Merge gating (per contract clause 6)

- **FU-1, FU-4, FU-5** — additive / doc-only → auto-merge on green CI.
- **FU-3** — changes server-boot behavior (restore-from-disk) → **owner-gated**:
  open draft PR, summarize the behavior change here, and wait for the owner's
  exact `Yes, with authorization.` before merging to `main`.

## Decision log (orchestrator)

- `2026-06-05` — Opened the ledger + the CLAUDE.md contract. Dispatched four
  read-only audits to produce the disjoint ownership map before any builder ran.
- `2026-06-05` — **Audit A:** no live (non-test) code constructs `ParallelRunner`
  or reaches a `JobStore`; the cost-drain and default-adapter follow-ups both
  collapse into one new seam `hermes_cli/orchestrator_dispatch.py` (it only
  *reads* the existing modules). Merged old FU-1+FU-2 → **FU-1**. Honest caveat:
  this lands the *tested drain seam*; per-job cost still reads 0 live until a
  real caller (server → dispatcher) is wired — a separate owner decision,
  recorded in the FU-1 snapshot.
- `2026-06-05` — **Audit B:** there is no `job_store.py`; `JobStore` is in
  `orchestrator_api.py`. FU-3 owns that file exclusively; FU-1 only imports it.
  FU-3 restore-on-startup changes boot behavior → **owner-gated**.
- `2026-06-05` — **Audit C:** `release_readiness_doctor.py` already implements
  the 22 `--10-10` checks; the unified gate is a thin new `hermes_cli/release_gate.py`
  (calls `run_10_10_doctor()` + ruff + a fast test slice) behind a new
  `doctor --release-gate` flag. Disjoint from the orchestrator core and Supabase;
  the only shared-registry file is `main.py`, and no other in-flight task edits
  it → FU-4 conflict-free. Moved FU-4 → building.
- `2026-06-05` — **Audit D:** Supabase is **not** absent —
  `plugins/supabase/`, `plugins/memory/supabase/`, and
  `hermes_cli/integrations/supabase.py` exist and pass 47 tests. **FU-5** reduced
  from "build integration" to "correct the stale status doc"; live SQL execution
  + pgvector recall are deferred optional follow-ons (owner-gated, new files).
- `2026-06-05` — All four writable sets pairwise disjoint → dispatched FU-1,
  FU-3, FU-4, FU-5 builders in parallel (worktrees, background).
- `2026-06-05` — **FU-5** built (`b2984b6b`) → draft PR **#327**; only the status
  doc + snapshot touched; 47 Supabase tests verified. **FU-4** built → draft PR
  **#328**; ruff/ty clean, 20 tests pass, `doctor --release-gate` exits 0. Both
  additive → merge on green. FU-1, FU-3 still building.
