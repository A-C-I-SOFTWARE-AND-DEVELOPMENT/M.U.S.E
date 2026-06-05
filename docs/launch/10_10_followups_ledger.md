# Hermes 10/10 — Follow-ups Ledger (audit trail)

**Single-writer.** Per the *Parallel follow-up execution contract* in
[`CLAUDE.md`](../../CLAUDE.md), only the orchestrator session edits this
file. Parallel builder agents write their own snapshot under
[`followups/`](followups/) and never touch this ledger. On resume, read
this file first — it is how state is rebuilt with no context lost.

**Date opened:** 2026-06-05 · **Base:** `main` @ `b32db703` (all six glue-hops merged)

These are the residual follow-ups recorded in
[`10_10_PROGRAM_STATUS.md`](10_10_PROGRAM_STATUS.md) — *not missing
kernels*, but turning opt-in seams into production behavior plus deferred
items. Each is being closed under the parallel-execution contract.

## Status legend

`planned` → `building` (agent dispatched) → `in-review` (PR open, CI/Codex)
→ `merged`. Side states: `blocked` (needs a decision/owner gate),
`deferred` (out of scope for now).

## Ownership map (disjoint — the conflict-prevention guarantee)

> Ownership is **finalized from the four read-only audits** (in flight at
> time of writing). A task does not move to `building` until its owned-file
> set here is confirmed disjoint from every other in-flight task.

| Task | Title | Owned files (writable) | Risk class | Status | Branch | Snapshot | PR |
|---|---|---|---|---|---|---|---|
| **FU-1** | Cost drain: `iter_worker_usage` → `JobStore` after a run | _pending audit A_ | behavior-additive (owner-gate if it changes a default path) | planned | — | [`followups/fu-1-cost-drain.md`](followups/fu-1-cost-drain.md) | — |
| **FU-2** | Default `LocalRuntimeAdapter` injection | _pending audit A_ | **behavior change → owner-gated** | planned | — | [`followups/fu-2-adapter-default.md`](followups/fu-2-adapter-default.md) | — |
| **FU-3** | JobStore durability: on-disk event log + restart rebuild | _pending audit B_ | **architecturally significant → owner-gated** | planned | — | [`followups/fu-3-jobstore-persistence.md`](followups/fu-3-jobstore-persistence.md) | — |
| **FU-4** | Unified release gate / `doctor --10-10` | _pending audit C_ | additive | planned | — | [`followups/fu-4-release-gate.md`](followups/fu-4-release-gate.md) | — |
| **FU-5** | Minimal Supabase (S11) integration | _pending audit D (new files)_ | additive · optional | planned | — | [`followups/fu-5-supabase.md`](followups/fu-5-supabase.md) | — |

## Parallelization plan (filled from audits)

- **Wave 1 (parallel):** the tasks whose owned-file sets are confirmed
  disjoint. Cleanest candidates up front: **FU-4** (release gate) and
  **FU-5** (Supabase, mostly new files) — they don't touch the orchestrator
  core.
- **Sequenced:** **FU-1** and **FU-2** are expected to share the orchestrator
  dispatcher → run one after the other (or as one combined PR), never in
  parallel. **FU-3** runs parallel to FU-1/FU-2 *only if* the audit confirms
  it doesn't co-edit `job_store.py` with FU-1.

## Decision log (orchestrator)

- `2026-06-05` — Opened the ledger + the CLAUDE.md contract. Dispatched four
  read-only audits (cost/adapter wiring, JobStore durability, release gate,
  Supabase) to produce the disjoint ownership map before any builder runs.
- `2026-06-05` — Flagged FU-2 and FU-3 as owner-gated (they change default
  runtime behavior); they will open as draft PRs and wait for explicit
  `Yes, with authorization.` before any merge to `main`.
