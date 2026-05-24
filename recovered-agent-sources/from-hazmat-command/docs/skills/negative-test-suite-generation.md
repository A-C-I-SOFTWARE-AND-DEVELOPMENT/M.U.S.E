# Skill — negative-test-suite-generation

## Purpose

Add negative tests to a feature — cross-tenant abuse, auth
bypass, replay, race, malformed input. Pattern follows R3-N's
1,000-iteration cross-tenant fuzz at
`tests/supabase/cross-tenant-fuzz.test.js`.

## Triggers

- A new RC3 surface ships.
- A reported defect with no regression test.
- A negative-coverage gap surfaced by Assurance.

## Required Inputs

- The surface under test.
- The existing happy-path tests.
- The existing fuzz / negative patterns in the repo.

## Research Required

- OWASP ASVS L1/L2 — the chapter relevant to the surface.
- The repo's existing fuzz pattern at
  `tests/supabase/cross-tenant-fuzz.test.js`.
- Vitest concurrency model for race tests.

## Step-by-Step Method

1. Enumerate negative cases by category:
   - Cross-tenant: tenant A's actor accessing tenant B's data.
   - Auth bypass: missing / malformed / expired / wrong-issuer
     JWT.
   - Replay: same webhook / request retried; same nonce.
   - Race: concurrent writes to the same record.
   - Malformed input: out-of-range, missing required, type
     mismatch, oversized payload, control-character injection,
     SQL/JS injection attempts (defense-in-depth even with
     parameterized queries).
   - Rate-limit bypass: burst from two synthetic tenants.
2. For each, write a Vitest test that constructs the negative
   case explicitly. Use property-based fuzz patterns where
   appropriate.
3. Run the suite; confirm all negative tests **fail closed**
   (the system rejects the abuse).
4. Update `docs/security/threat-model.md` if a new threat surfaces.

## Deliverable Format

New / extended test files under `tests/` plus a memo summarizing
the negative coverage added.

## Quality Checklist

- [ ] All applicable categories covered
- [ ] Cross-tenant test included (always)
- [ ] Tests fail closed
- [ ] No happy-path test broken
- [ ] Threat-model updated if a new finding emerged

## Escalation Triggers

- A negative test that exposes an actual defect → halt; release
  freeze under `governance/09` if it's a category 1/2 trigger.

## Related Agents

- Negative / Fuzz Test Agent (Assurance Office)
- Independent QA / V&V Agent (Assurance Office)

## Related Artifacts

- `tests/supabase/cross-tenant-fuzz.test.js` (the reference
  pattern)
