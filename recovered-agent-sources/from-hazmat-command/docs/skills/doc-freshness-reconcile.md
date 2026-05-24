# Skill — doc-freshness-reconcile

## Purpose

Detect and reconcile stale documentation against the
source-of-truth hierarchy per
`governance/15-doc-freshness-and-contradiction-control.md`.

## Triggers

- Per-RC2/RC3 PR for the docs touched.
- Quarterly sweep.
- An agent encounters a contradiction during another task.

## Required Inputs

- The doc(s) suspected of staleness.
- The source-of-truth hierarchy
  (`governance/01-source-of-truth-hierarchy.md`).
- Current code/tests/release notes.

## Research Required

- The current capability set (`docs/releases/v1.0.0-enterprise-
  ready.md`).
- Active SKIPPED entries (especially recent retrofits).
- The CI workflow state.

## Step-by-Step Method

1. Identify the doc and the suspected drift category (date,
   capability, severity, vendor, citation, process, naming).
2. Apply the source-of-truth hierarchy verdict.
3. Choose the reconciliation form:
   - **Prepend a dated banner** for context-preserving updates
     (used for `HANDOFF.md` in Wave 1 of this AEO install).
   - **Inline annotation** for surgical corrections.
   - **Replace the doc** for wholesale rewrites.
4. Apply the change as RC2 (general) or RC3 (if it touches
   AGENTS.md / PUBLISH.md / SKIPPED.md).
5. Record the reconciliation in the next
   `agent-run-retrospective`.
6. Cross-update the index if the doc set's shape changed.

## Known stale docs (2026-05-17 baseline)

- `HANDOFF.md` (2026-04-27) — banner added Wave 1
- `AUDIT.md` (2026-04-20) — pre-dates Stage 3 authz/RLS
- `AGENTS.md` "Vercel + DNS gotcha (2026-05-03)" — may be stale
- `CLOUD_SYNC.md` "NOT done yet" list — may have moved
- `PLAY_STORE.md` "Deliberately NOT-DONE" — may have moved

## Deliverable Format

The reconciled doc + a retrospective note describing the
change.

## Quality Checklist

- [ ] Verdict applied per hierarchy
- [ ] Original context preserved if banner used
- [ ] No silent deletion of claims
- [ ] Retrospective note filed

## Escalation Triggers

- Stale claim that materially misleads about compliance / safety
  → escalate to Risk Controller.
- Reconciliation that requires AGENTS.md or PUBLISH.md
  amendment → L3 maker-checker.

## Related Agents

- Doc Freshness Auditor (Knowledge Operations)
- Contradiction Agent (Research Bureau)

## Related Artifacts

- `governance/01-source-of-truth-hierarchy.md`
- `governance/15-doc-freshness-and-contradiction-control.md`
