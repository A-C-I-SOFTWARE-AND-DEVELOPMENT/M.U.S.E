# Compliance Evidence Matrix — <scope>

**Date:** YYYY-MM-DD
**Author:** Compliance Evidence Agent (Assurance Office)
**Scope:** <e.g. "ISO 27001 A.5 + A.8" or "SOC 2 CC6" or "GDPR Art. 32">
**Framework Version:** <e.g. ISO/IEC 27001:2022>

## Evidence Table

| Control ID | Name | Status | Evidence (file / test / runbook) | Gap | Owner | Stub dep |
|---|---|---|---|---|---|---|
| <e.g. A.5.15> | Access control | implemented | `api/_lib/authz.mjs`; `src/lib/rbac.js`; `tests/api/_lib/authz.test.js` | none | Security/Authz Engineer | none |
| <e.g. A.5.18> | Access rights | partial | `docs/security/rls-policy-catalog.md` (authored, not yet applied) | RLS not yet applied to live Postgres | `<owner-handle>` | `supabase-rls-applied` |
| ... | | | | | | |

## Status Definitions

- **implemented** — control fully in place with evidence
- **partial** — partially in place; gap explicit
- **scaffold** — documented but not operational (per `docs/iso27001/README.md` "scaffold, not certify")
- **not implemented** — known gap with a roadmap item or
  stub entry

## Anti-Claim Discipline

Per `docs/governance/11-commercial-claims-substantiation-policy.md`
C3 (regulatory) class, this matrix is the substantiation for
every compliance claim. No public claim of "compliant with X"
without an "implemented" row here or a labeled "scaffold" with
the qualifier.

## Cross-References

- `docs/iso27001/statement-of-applicability.md`
- `docs/iso27001/risk-register.md`
- Linked SKIPPED entries: <list>
