# 15 — Doc Freshness and Contradiction Control

**Status:** Installed 2026-05-17

Docs drift. Code, tests, and release notes move; older
documentation can quietly become wrong. This doc codifies how the
AEO detects and reconciles staleness.

## Why this matters here specifically

The repo already has at least these confirmed staleness risks as
of 2026-05-17:

- **`HANDOFF.md`** — dated 2026-04-27. Pre-dates the four Round
  hardening sprints (R1-D, R2-I/H, R3-O/N/K, R4-X/Q/S) and the
  `v1.0.0-enterprise-ready` release. Its "What's NOT done" list
  includes items that have shipped. A banner was added in Wave 1
  of the AEO install pointing readers to the v1.0.0 release notes.
- **`AUDIT.md`** — dated 2026-04-20. The "User collection leaks
  cross-tenant" finding pre-dates Stage 3 authz and RLS.
- **`AGENTS.md` §"Vercel + DNS gotcha (2026-05-03)"** — DNS state
  may have moved since.
- **`CLOUD_SYNC.md`** "NOT done yet" list (2026-05-03) — items
  may have moved.
- **`PLAY_STORE.md`** "Deliberately left NOT-DONE" list — items
  may have moved.
- **`SKIPPED.md` end-of-build rollup count (23)** vs. full active
  entry count (~26 including meta-blockers) — the rollup buckets
  don't tally meta-blockers (`supabase-project-provisioned`,
  `sor-shadow-write-wiring`, `certified-translator-engagement`).
  Not strictly stale — but a navigation aid that under-counts.

## Categories of staleness

1. **Date drift.** Doc dated N weeks/months ago; status statements
   may have moved.
2. **Capability claim drift.** Doc claims feature X is missing /
   present / planned, but live code or release notes show
   otherwise.
3. **Severity drift.** Doc assigns P0/P1 to an item whose status
   has changed.
4. **Vendor / dependency drift.** Doc cites a vendor / library /
   API endpoint that has changed.
5. **Citation rot.** External URLs that no longer resolve, or
   primary sources that have updated.
6. **Process drift.** Doc describes a procedure (CI job, npm
   script, runbook step) that no longer matches reality.
7. **Naming drift.** Doc uses an old name (e.g. the renamed
   `supabase-provenance-table` → `supabase-provenance` from
   R4-X's audit).

## Resolution flow (the `doc-freshness-reconcile` skill)

1. Identify the doc and the suspected drift.
2. Confirm against the source-of-truth hierarchy
   (`governance/01`). Live code/tests > AGENTS.md > PUBLISH.md >
   SKIPPED.md > coverage CI > blockers-final > release notes >
   ISO/security/runbooks > AEO docs > historical.
3. If the suspected drift is real, choose:
   - **Prepend a dated update note** at the top of the doc. Use
     when the original body is still mostly useful as historical
     context.
   - **Edit inline** with a dated annotation. Use for small,
     surgical corrections.
   - **Replace the doc.** Use when the doc is mostly wrong.
4. Record the reconciliation in a brief
   `agent-run-retrospective` entry so the pattern accrues.
5. If the staleness involves AGENTS.md / PUBLISH.md / SKIPPED.md,
   route through L3 maker-checker.

## When NOT to reconcile

- If the doc is **explicitly historical** (a postmortem, a
  release-tag artifact, an old retrospective). These age
  intentionally.
- If the doc is **owner-personal context** (`HANDOFF.md` was
  originally written as such). Prefer a banner over a rewrite
  unless the owner agrees.
- If reconciliation would require asserting product behavior
  the agent cannot verify — file a "Known Unknown" instead.

## Continuous cadence

- Every RC2/RC3 PR triggers a Doc Freshness Auditor pass
  (Knowledge Operations) for the docs the change touches.
- Quarterly: a sweep of root-level governance + the 12 runbooks +
  the `docs/inventory/` and `docs/compliance/` sets.

## Validator integration

`scripts/check-governance-index.mjs` catches index-link breakage
and missing required sections. It does NOT catch semantic
staleness — that is human + agent judgment. The validator is the
floor; doc-freshness discipline is the ceiling.

## Anti-patterns

- Reconciling "by deleting the stale claim." If the claim was
  there, future readers may search for it. Update or annotate;
  don't silently delete.
- Treating doc freshness as one-time cleanup. The repo will
  always have stale corners; the discipline is continuous.
- Reconciling a doc by inventing current state. If you can't
  verify, file a "Known Unknown" and route to the owner.
