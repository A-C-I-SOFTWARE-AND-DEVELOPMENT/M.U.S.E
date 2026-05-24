# Skill — sor-cutover-risk-review

## Purpose

Review a per-domain System-of-Record cutover (legacy / in-memory
→ Supabase) for correctness, shadow-write completeness, and
rollback readiness. Carries forward R4-X's SoR resolver pattern.

## Triggers

- A `SOR_<DOMAIN>_BACKEND` env flag is about to flip.
- `sor-shadow-write-wiring` stub closes.
- `supabase-project-provisioned` meta-blocker clears.
- A drift report from `scripts/verify-sor-drift.mjs` (when
  authored).

## Required Inputs

- The domain about to cut (provenance, scim-tokens,
  role-mappings, idp-config, training-credentials, etc.).
- Current adapter at `api/_lib/sorAdapters/<domain>.supabase.mjs`.
- Cutover runbook `docs/runbooks/sor-cutover.md`.
- Checklist `docs/runbooks/sor-cutover-checklist.md`.
- 7-day shadow-write drift report (zero drift required).

## Research Required

- The corresponding SKIPPED.md entries (e.g. `supabase-provenance`,
  `supabase-tenant-scim-tokens`).
- `docs/security/rls-policy-catalog.md` for the affected table.
- `governance/09-release-freeze-and-safety-budget-policy.md`
  trigger 1 (tenant-isolation defect).

## Step-by-Step Method

1. Confirm the meta-blocker `supabase-project-provisioned` is
   actually cleared (Supabase project exists, migrations
   applied, RLS active).
2. Confirm shadow-write has run for ≥ 7 days with zero drift
   for the domain.
3. Confirm the adapter implements the full surface of the
   in-memory shim (signature parity).
4. Run the domain's tests (`tests/lib/<domain>/` and
   `tests/supabase/rls.policy.test.js` for the affected
   tables) against live Postgres.
5. Confirm the SKIPPED entry for the domain is updated to
   Resolved (or its wire-back procedure is in flight).
6. Confirm rollback: setting `SOR_<DOMAIN>_BACKEND=legacy`
   correctly reverts the adapter selection at boot.
7. Pre-flight the Pilot Readiness Judge (Assurance Office) if
   the cutover lands close to a pilot demo.

## Deliverable Format

SoR Cutover Risk Memo: pre-condition checklist, drift report
attached, test results, rollback verification.

## Quality Checklist

- [ ] Meta-blocker confirmed cleared
- [ ] 7-day zero-drift shadow-write evidence
- [ ] Adapter parity with in-memory shim
- [ ] Tests pass against live Postgres
- [ ] Rollback verified
- [ ] Pilot Readiness Judge briefed if pilot ≤ 14 days away

## Escalation Triggers

- Drift > 0 in the shadow-write window → halt the cut.
- Adapter parity failure → halt the cut.
- Cross-tenant leak in `rls.policy.test.js` against live
  Postgres → release freeze under `governance/09` trigger 1.

## Related Agents

- Data / SoR Migration Engineer (Engineering Factory)
- Independent QA / V&V Agent (Assurance Office)
- Pilot Readiness Judge (Assurance Office)

## Related Artifacts

- `docs/runbooks/sor-cutover.md`
- `docs/runbooks/sor-cutover-checklist.md`
