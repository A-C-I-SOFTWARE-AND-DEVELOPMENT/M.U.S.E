# Skill — rbac-tenant-isolation-audit

## Purpose

Audit the multi-tenant + 5-role isolation guarantees of HazMat
Command across the application layer (`api/_lib/authz.mjs::
requireTenant`, `src/lib/rbac.js`) and the (authored, not yet
applied) RLS second tier (`supabase/migrations/20260515_rls_*.sql`).

## Triggers

- Any change to `api/_lib/authz.mjs`, `src/lib/rbac.js`, the SCIM
  helpers, RLS migrations, or any tenant-scoped query.
- Quarterly review.
- Pilot or RFP requiring multi-tenant assurance.

## Required Inputs

- Current authz middleware code.
- Current RBAC role table (5 roles: carrier_admin,
  safety_manager, dispatcher, driver, solo_driver).
- The 8 RLS-protected tables enumerated in
  `docs/security/rls-policy-catalog.md`.
- Test suites: `tests/api/_lib/authz.test.js`,
  `tests/supabase/rls.policy.test.js`,
  `tests/supabase/cross-tenant-fuzz.test.js` (1,000 iterations).

## Research Required

- 49 CFR §172.704(c) function-specific training scoping (drives
  some role boundaries).
- OWASP ASVS L1/L2 — V4 Access Control.
- NIST 800-53 AC-3, AC-6.
- ISO 27001:2022 A.5.15, A.5.18, A.8.3.

## Step-by-Step Method

1. Walk the authz middleware: every call site of
   `withAuthz({...})` and `requireTenant`.
2. For each role, list the routes and entities accessible.
   Compare against the 5-role audit baseline in `AUDIT.md`
   (note: `AUDIT.md` is 2026-04-20 and may be stale —
   reconfirm against live code).
3. Run `tests/supabase/cross-tenant-fuzz.test.js` (1,000
   iterations); confirm zero leakage.
4. Walk each of the 8 RLS-protected tables; confirm the policy
   set covers SELECT/INSERT/UPDATE/DELETE for each. Until
   `supabase-rls-applied` clears, this confirmation is against
   the in-memory shim
   (`tests/supabase/_rls-shim.mjs`).
5. Confirm `requireMfa` honors `MFA_ENFORCEMENT` env var; flag
   `mfa-enforcement` stub status.
6. Confirm SCIM bearer-token verification uses `timingSafeEqual`
   (`api/scim/_lib/scimAuth.mjs`); flag
   `supabase-tenant-scim-tokens` stub status.

## Deliverable Format

A Tenant Isolation Audit memo: role → permitted routes table;
RLS policy coverage table; test results; stub status.

## Quality Checklist

- [ ] Every role's access surface documented
- [ ] Cross-tenant fuzz green
- [ ] All 8 RLS tables covered
- [ ] MFA enforcement status flagged
- [ ] SCIM token storage status flagged
- [ ] No role escalation path discovered

## Escalation Triggers

- Any confirmed cross-tenant leak → Risk Controller; release
  freeze under `governance/09` trigger 1.
- Any role escalation path → release freeze under
  `governance/09` trigger 2.

## Related Agents

- Security/Authz Engineer (Engineering Factory)
- Principal Security Architect (Assurance Office)
- Threat Modeling Agent (Assurance Office)

## Related Artifacts

- `docs/security/threat-model.md`
- `docs/security/rls-policy-catalog.md`
