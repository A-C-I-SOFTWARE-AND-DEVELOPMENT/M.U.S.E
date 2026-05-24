# Workflow — Enterprise Procurement Readiness

## Trigger

An enterprise carrier moves from pilot interest to formal
procurement (RFP / security questionnaire / DPA / MSA
negotiation).

## Required Divisions

Commercial Office (Enterprise Procurement Agent + Chief
Commercial Officer), Legal Office (Contract Drafting + DPA/
Subprocessor + Legal Consistency Auditor), Assurance Office
(Compliance Evidence Agent), Pilot Ops (Pilot Program Manager),
Knowledge Operations.

## Required Research Artifact

Conversion Plan (`pilot-to-contract-conversion-plan` skill).
Updated `docs/rfp/answer-bank.md` if new questions arise.
Compliance Evidence Matrix (`compliance-evidence-matrix-build`).

## Agent Topology

Prompt chain with parallel review at submission.

## Sequence

1. Enterprise Procurement Agent intakes the buyer's questions
   / RFP / questionnaire.
2. Map every question to:
   - existing `docs/rfp/answer-bank.md` entry, or
   - new answer derived from in-repo evidence, or
   - "in progress" answer pointing to a roadmap item
3. Identify procurement-blocking SKIPPED entries that matter
   for this buyer (e.g. carrier requires SCIM →
   `workos-procurement` + `supabase-tenant-scim-tokens`).
4. Compliance Evidence Agent updates / produces the matrix
   for the controls the buyer asks about.
5. Legal drafts: MSA, SOW, DPA, NDA per
   `legal-document-generation` workflow.
6. Buyer Objection Agent (Pilot Ops) drafts objection
   responses.
7. Conversion Plan finalized.
8. Owner-driven negotiation (L4 — agent does not sign / send).

## Parallelization Opportunities

- Answer-bank mapping + Compliance Evidence Matrix +
  Legal drafts can run in parallel.

## Maker-Checker Review Points

- Each legal draft per `legal-document-generation` (builder /
  reviewer / verifier).
- Conversion Plan: Enterprise Procurement Agent builder +
  Chief Commercial Officer reviewer + Risk Controller
  verifier for any commitments that imply L4 owner action.

## Final Outputs

Conversion Plan · Buyer-specific RFP responses · Compliance
Evidence Matrix · MSA + SOW + DPA drafts · NDA if needed ·
Objection responses · Retrospective.

## Acceptance Criteria

- Every buyer question answered (or labeled "in progress").
- Every legal draft has the counsel-review banner.
- Every claim substantiated per `governance/11`.
- Procurement blockers explicit and owner-routed.
- No commitment in negotiation materials that the BCDR runbook
  / SoA / pricing source of truth cannot meet.
