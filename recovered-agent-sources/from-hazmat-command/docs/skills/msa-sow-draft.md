# Skill — msa-sow-draft

## Purpose

Draft an MSA (Master Services Agreement) and accompanying SOW
(Statement of Work) under `governance/12` for a customer
contract.

## Triggers

- Pilot conversion approaching contract phase.
- Enterprise carrier requests our MSA template.

## Required Inputs

- Customer identity.
- Scope of services (which plans, which features, which
  jurisdictions).
- Pricing (matches `governance/10` + Billing source of truth).
- SLA commitments (matches what BCDR runbook can deliver).
- Term length, auto-renewal terms.
- Termination terms.

## Research Required

- Standard B2B SaaS MSA patterns.
- Counterparty procurement requirements.
- `docs/iso27001/` for security clauses.
- `docs/compliance/dpa-template.md` (R5-T forward) for DPA
  incorporation.

## Step-by-Step Method

1. Intake + counsel-review banner per `governance/12`.
2. MSA sections:
   - Parties, effective date, term
   - Services definition (refer to SOWs)
   - Fees and payment terms
   - SLA + service credits (if any)
   - Use of data + privacy (DPA incorporated by reference)
   - Security commitments (cross-reference ISO 27001 SoA;
     label "scaffold, not certify" per `docs/iso27001/
     README.md`)
   - Subprocessor notice obligations
   - Confidentiality
   - IP ownership (customer data stays customer's)
   - Warranties + disclaimers
   - Limitation of liability + caps
   - Indemnification
   - Termination for cause / convenience
   - Effect of termination (data export, deletion subject to
     retention obligations)
   - Insurance (if required)
   - Force majeure
   - Governing law + dispute resolution
   - Notices
   - Order of precedence (SOW > MSA > Order Form)
3. SOW sections (per engagement):
   - Services scope
   - Deliverables + acceptance criteria
   - Timeline
   - Fees
   - Customer obligations
   - Personnel
4. Legal Consistency Auditor pass — every commitment matches
   the actual deliverable.

## Deliverable Format

Draft MSA + SOW under `docs/compliance/msa-<customer>.md` and
`docs/compliance/sow-<customer>-<project>.md`.

## Quality Checklist

- [ ] Counsel-review banner on both
- [ ] SLA matches BCDR capability
- [ ] DPA incorporated
- [ ] Liability cap explicit
- [ ] Termination + data-export terms match the actual export
  capability (regulator-export bundle is real; full
  account-data-portability is partial until Supabase lands)

## Escalation Triggers

- A counterparty redline that conflicts with our SLA capability
  → halt; Privacy Counsel + Legal Consistency Auditor.

## Related Agents

- Contract Drafting Agent (Legal Office)
- Privacy Counsel Agent (Legal Office)
- Legal Consistency Auditor (Legal Office)
- Chief Commercial Officer (Commercial Office)

## Related Artifacts

- `docs/templates/legal-document-intake-template.md`
- `docs/compliance/dpa-template.md`
