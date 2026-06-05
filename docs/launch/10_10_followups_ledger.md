# Hermes 10/10 — Follow-ups Ledger (audit trail)

**Single-writer.** Per the *Parallel follow-up execution contract* in
[`CLAUDE.md`](../../CLAUDE.md), only the orchestrator session edits this
file. Parallel builder agents write their own snapshot under
[`followups/`](followups/) and never touch this ledger. On resume, read
this file first — it is how state is rebuilt with no context lost.

**Date opened:** 2026-06-05 · **Base:** `main` @ `b32db703` (all six glue-hops merged)

Residual 10/10 follow-ups from [`10_10_PROGRAM_STATUS.md`](10_10_PROGRAM_STATUS.md),
closed in parallel under the contract. Ownership finalized from four read-only
audits → conflict-free partition (no two in-flight tasks shared a writable file).

## Status legend

`planned` → `building` → `in-review` (PR open) → `merged`. Side states:
`blocked` (needs a decision/owner gate), `deferred`.

## Ownership map + outcomes

| Task | Title | Owned files | Risk | Status |
|---|---|---|---|---|
| **FU-1** | Dispatch seam — drain `iter_worker_usage` → `JobStore` (+ adapter passthrough) | `hermes_cli/orchestrator_dispatch.py` + test | additive | **merged → #329** (`c118e200`) |
| **FU-3** | JobStore durability — on-disk event log + restart rebuild | `hermes_cli/job_event_store.py` · `hermes_cli/orchestrator_api.py` · test | **behavior change → owner-gated** | **merged → #330** (`842b0d53`, owner-authorized) |
| **FU-4** | Unified release gate — `doctor --release-gate` | `hermes_cli/release_gate.py` · `hermes_cli/main.py` (doctor block) · test | additive | **merged → #328** (`ca8420ae`) |
| **FU-5** | Supabase status-doc correction (it was already built — 47 tests pass) | `docs/launch/10_10_PROGRAM_STATUS.md` | doc-only | **merged → #327** (`f0592da9`) |

Tracking/governance PR (contract + this ledger): **#326** (merges last).

## Review-driven corrections (orchestrator)

- **FU-1 — default adapter was unsafe.** The first build defaulted a bare shared
  `LocalRuntimeAdapter`; for a multi-worker plan that collides every plain
  worker's `stdout.log`/`stderr.log` in one dir. Corrected to **inline default**
  (per-worker isolation); adapter is caller opt-in. A safe default adapter needs
  a per-worker adapter factory on the runner — **deferred** (old "FU-2").
- **FU-3 — CodeQL path-traversal.** CodeQL flagged caller-supplied `job_id` used
  in the `events.jsonl` path. Fixed by routing `job_id` through the canonical
  `worktrees.sanitize_segment` allow-list (`/` and `..` cannot survive),
  never-raising; added traversal + blank-id regression tests. (`d921a2cb`)

## Honest residuals (not closed by these PRs)

- **Per-job cost still reads 0 live.** FU-1 lands the tested drain seam, but
  there is no live caller of `ParallelRunner` — wiring the server's job
  dispatcher to `run_plan_into_store` is a separate owner decision.
- **Default adapter injection** (old FU-2) deferred — needs a per-worker adapter
  factory on the runner.
- **FU-3 restored-job cost resets to 0** — `JobCost` isn't event-sourced; fine
  for the status/phase/workers/approvals restart gate, a documented follow-up.

## Decision log

- `2026-06-05` — Contract + ledger opened; four read-only audits → disjoint map.
- `2026-06-05` — **Audit A:** no live `ParallelRunner`→`JobStore` caller; cost-drain
  + adapter collapse into one new seam → FU-1.
- `2026-06-05` — **Audit B:** no `job_store.py` (`JobStore` is in `orchestrator_api.py`);
  FU-3 restore-on-boot → owner-gated.
- `2026-06-05` — **Audit C:** unified gate = thin new `release_gate.py` behind
  `doctor --release-gate`; only shared file is `main.py`, edited by no other task → FU-4.
- `2026-06-05` — **Audit D:** Supabase already shipped (47 tests) → FU-5 reduced to a
  doc correction.
- `2026-06-05` — All four built in parallel (worktrees). FU-1 reviewer-corrected;
  FU-3 CodeQL-fixed. **Merged FU-5 (#327), FU-4 (#328), FU-1 (#329)** on green
  (FU-4's only red was the known Android AvatarPicker flake — proven: the
  doc-only sibling PR passed the same Android job at the same time).
- `2026-06-05` — **FU-3 (#330) held for owner authorization** (behavior-changing:
  server boot now restores jobs from disk + writes a new on-disk artifact).
- `2026-06-05` — **FU-3 CodeQL is a verified false-positive.** CodeQL's
  `py/path-injection` flags `job_id` → events-log path, but the code is provably
  safe: `sanitize_segment` reduces `job_id` to a single `[A-Za-z0-9_.-]`
  component (`/` and `..` cannot survive) and `realpath`+`commonpath` re-confirm
  containment. Three canonical mitigations (allow-list, `is_relative_to`,
  `realpath`/`commonpath`) are not recognized by this repo's CodeQL model. The
  readable `jobs/<job_id>/` layout is **kept** (a hash-dir redesign would clear
  the FP but worsen on-disk inspectability — a real cost for a cosmetic gain).
  Resolution deferred to the owner: dismiss the FP in the Security tab
  (recommended) at merge time.
- `2026-06-05` — **Recommendation (factual): land the contract, hold FU-3.**
  #326 (this contract + ledger) merged as the explicit deliverable; FU-3 (#330)
  stays a clean, validated open draft awaiting the owner's exact
  `Yes, with authorization.` + FP dismissal. No behavior change reaches `main`
  without explicit owner consent.
- `2026-06-05` — **Owner authorized (`Yes, with authorization.`) → FU-3 merged
  (#330, `842b0d53`).** Pre-merge, the path-traversal defense was re-verified
  against the actual code: `sanitize_segment` destroys every `/` (→ `-`) so no
  separator survives into a path component, rejects pure-`..`/dot segments
  (`.strip("-.")` → empty → raise), and `realpath`+`commonpath` backstops it —
  two independent barriers. Merge was mechanically clean (`mergeable_state:
  unstable` ⇒ only the non-required CodeQL-FP + Android flake were red; every
  required gate green). **All four follow-ups + the contract are now on `main`.**
  Residual: dismiss the CodeQL FP in the Security tab (cosmetic); the
  restored-job cost-meter reset stays a documented follow-up.
