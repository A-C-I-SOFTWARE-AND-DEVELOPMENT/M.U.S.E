# Skill — dpa-draft

## Purpose

Draft or revise the Data Processing Addendum under
`governance/12`. Extends the existing R5-T-forward-tagged
`docs/compliance/dpa-template.md` placeholder.

## Triggers

- Customer requests a DPA before signing.
- Sub-processor list change.
- New cross-border transfer.
- GDPR / SCC / CCPA-CPRA update.

## Required Inputs

- Sub-processor list (`docs/compliance/sub-processor-list.md`
  when populated).
- Cryptography policy
  (`docs/iso27001/policies/cryptography-policy.md`).
- Data inventory.
- Internal privacy policy
  (`docs/iso27001/policies/privacy-policy.md`).
- Retention policy
  (`docs/compliance/retention-policy.md` when populated).

## Research Required

- GDPR Art. 28 (processor obligations).
- SCC 2021/914 (Standard Contractual Clauses), Modules 2 and 3.
- CCPA / CPRA processor obligations.
- ISO 27001:2022 A.5.20 (supplier agreements), A.5.34 (privacy
  and protection of PII).

## Step-by-Step Method

1. Intake + counsel-review banner per `governance/12`.
2. DPA sections:
   - Definitions (Controller, Processor, Personal Data, etc.)
   - Subject matter and duration
   - Nature and purpose of processing
   - Types of personal data
   - Categories of data subjects
   - Processor obligations (GDPR Art. 28(3))
   - Sub-processor terms (incorporate by reference the
     current list; flowdown clauses)
   - International transfers (SCC 2021/914 Module 2; UK addendum
     if applicable)
   - Security measures (cross-reference cryptography policy,
     SoA)
   - Personal data breach notification SLA (matches
     incident-response runbook)
   - DSAR assistance
   - Return / deletion (subject to 49 CFR retention obligations)
   - Audit rights (proportionate; SOC 2 / ISO 27001 attestation
     once available; today "scaffold")
   - Liability
3. CCPA/CPRA addendum (Service Provider terms).
4. Legal Consistency Auditor pass — every claim consistent with
   current operational reality.

## Deliverable Format

Replaces or augments `docs/compliance/dpa-template.md` with the
counsel-review banner.

## Quality Checklist

- [ ] Counsel-review banner
- [ ] Sub-processor flowdown clauses
- [ ] SCC Module 2 referenced
- [ ] Security measures don't overstate (no "SOC 2 certified")
- [ ] Breach SLA matches runbook
- [ ] Retention floor respected

## Escalation Triggers

- Counterparty redlines on processor obligations that we cannot
  meet → halt; Privacy Counsel.

## Related Agents

- DPA / Subprocessor Agent (Legal Office)
- Privacy Counsel Agent (Legal Office)
- Legal Consistency Auditor (Legal Office)

## Related Artifacts

- `docs/compliance/dpa-template.md` (existing placeholder)
- `docs/compliance/sub-processor-list.md`
- `docs/iso27001/policies/supplier-security-policy.md`
