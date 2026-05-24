# Skill — compliance-evidence-matrix-build

## Purpose

Produce or update a Compliance Evidence Matrix mapping controls
(ISO 27001:2022 Annex A, NIST 800-53, SOC 2 TSC) to the
in-repo evidence that satisfies them.

## Triggers

- A new RFP / security questionnaire request.
- A new control surface lands (e.g. RLS migrations apply →
  closes `supabase-rls-applied`).
- A periodic ISMS review.

## Required Inputs

- The control framework subset (e.g. ISO 27001 A.5 + A.8; NIST
  AC + AU + SC families; SOC 2 CC6 + CC7).
- The current `docs/iso27001/statement-of-applicability.md`
  (93-control SoA, R5-U-authored).
- The current `docs/iso27001/risk-register.md`.
- The current `docs/iso27001/policies/**`.
- The current `docs/security/**`.

## Research Required

- The control text for each row.
- The repo's runbooks for operational evidence.

## Step-by-Step Method

1. Copy `docs/templates/compliance-evidence-matrix-template.md`.
2. List the controls in scope. For each, populate:
   - Control ID + name + text (or summary)
   - Status: implemented / partial / scaffold / not implemented
   - Evidence: file paths (`api/_lib/authz.mjs`,
     `docs/iso27001/risk-register.md`,
     `tests/supabase/cross-tenant-fuzz.test.js`, etc.)
   - Gap: what's missing
   - Owner: division responsible
3. For any "scaffold" or "not implemented" row, link the
   corresponding `SKIPPED.md` entry or roadmap item.
4. Cross-check against `docs/iso27001/statement-of-applicability.
   md`. If the matrix and SoA disagree, reconcile via
   `source-contradiction-analysis`.
5. Mark every claim that depends on a stubbed surface as
   conditional on the stub's closure (e.g. "A.5.18
   access-rights review — partial; depends on
   `supabase-rls-applied`").

## Deliverable Format

A populated matrix under `docs/compliance/<scope>-evidence-
matrix.md`. Or, for an ISO-wide refresh, an updated SoA.

## Quality Checklist

- [ ] Every row cites in-repo evidence or labels gap
- [ ] No claim overstates ("scaffold, not certify"
  discipline)
- [ ] SoA and matrix consistent
- [ ] Stub dependencies named

## Escalation Triggers

- Any control claimed "implemented" without evidence → halt;
  Compliance Evidence Agent review.

## Related Agents

- Compliance Evidence Agent (Assurance Office)
- Security Standards Research Agent (Research Bureau)

## Related Artifacts

- `docs/templates/compliance-evidence-matrix-template.md`
- `docs/iso27001/statement-of-applicability.md`
- `docs/iso27001/risk-register.md`
