# Skill — stub-inventory-audit

## Purpose

Audit `SKIPPED.md` ↔ live `TODO(stub:<name>):` token coverage and
keep the bidirectional pairing the CI gate
(`tests/inventory/skipped-coverage.test.js`) enforces. Carries
forward R4-X's end-of-build inventory discipline.

## Triggers

- A new stub is introduced.
- An existing stub is closed.
- Pre-pilot inventory review.
- Quarterly review.

## Required Inputs

- Current SKIPPED.md.
- Current code-site index (`docs/inventory/todo-stub-sites.md`).
- Coverage matrix (`docs/inventory/skipped-coverage.md`).
- CI gate (`tests/inventory/skipped-coverage.test.js`).

## Research Required

- The CI gate's allow-list (`EXPLICIT_DOCS_ENTRIES`,
  `RESOLVED_ENTRIES`) and the header / body parsing rules.
- `governance/03-change-risk-matrix.md` for any new stub's RC
  classification.

## Step-by-Step Method

1. Run `git grep -n 'TODO(stub:' -- src/ public/ api/ base44/
   docs/ scripts/ marketing/` to get the live inventory.
2. Run `npm test -- tests/inventory/skipped-coverage.test.js`;
   confirm green.
3. For each stub, verify the Deferred-Risk Schema fields are
   populated (Risk Class, Release Severity, Default Safe?,
   Customer Visible?, Security Impact, Compliance Impact,
   Owner, Review Date, Exit Condition, Escalation Rule,
   Evidence Link).
4. For each stub whose Review Date is lapsed, escalate to the
   Chief of Staff (Executive Command) for owner attention.
5. For each Resolved entry, confirm tokens are either removed
   or appear only as narrative references (no trailing colon).
6. Update `docs/inventory/skipped-coverage.md` if any pairing
   changed.
7. Update `docs/inventory/todo-stub-sites.md` per-site index.

## Deliverable Format

A Stub Inventory Audit Memo + updated `docs/inventory/`
artifacts.

## Quality Checklist

- [ ] CI gate green
- [ ] All Deferred-Risk fields populated
- [ ] No lapsed Review Date without escalation
- [ ] Resolved entries clean
- [ ] Cross-reference docs updated

## Escalation Triggers

- CI gate failure → halt all G3 publish work until reconciled.
- A lapsed P0 stub Review Date → Chief of Staff alert + owner.

## Related Agents

- Artifact Registry Agent (Knowledge Operations)
- Chief of Staff Agent (Executive Command)
- Compliance Evidence Agent (Assurance Office)

## Related Artifacts

- `SKIPPED.md`
- `docs/inventory/blockers-final.md`
- `docs/inventory/skipped-coverage.md`
- `docs/inventory/todo-stub-sites.md`
