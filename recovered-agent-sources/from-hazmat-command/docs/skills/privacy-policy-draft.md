# Skill — privacy-policy-draft

## Purpose

Draft or revise HazMat Command's customer-facing Privacy Policy
under `governance/12-legal-document-generation-policy.md`. The
internal privacy policy at
`docs/iso27001/policies/privacy-policy.md` is the boundary
document: external disclosures cannot promise what internal
policy disallows.

## Triggers

- New data flow added (new vendor, new collection point, new
  cross-border transfer).
- GDPR / CCPA / CPRA change.
- Pilot or RFP requires an updated customer-facing privacy
  notice.
- Annual review.

## Required Inputs

- Internal privacy policy
  (`docs/iso27001/policies/privacy-policy.md`).
- Data inventory (`docs/inventory/`).
- Sub-processor list (`docs/compliance/sub-processor-list.md`
  when populated).
- GDPR / CCPA disclosure drafts
  (`docs/compliance/gdpr-disclosure.md`,
  `docs/compliance/ccpa-disclosure.md` — R5-T forward-tagged).
- Cryptography policy
  (`docs/iso27001/policies/cryptography-policy.md`).
- Retention floor: 49 CFR §172.201(e), §172.704(d),
  §177.817(f) — 7 years for regulator-tied records.

## Research Required

- GDPR Articles 13–14 (notice at collection).
- CCPA / CPRA Notice at Collection requirements.
- ISO 27001:2022 A.5.34 (privacy and protection of PII).
- NIST Privacy Framework (Identify-P / Govern-P / Control-P /
  Communicate-P / Protect-P).

## Step-by-Step Method

1. Copy `docs/templates/legal-document-intake-template.md` and
   fill the intake fields.
2. Confirm the mandatory counsel-review banner from
   `governance/12` is present at the top of the draft.
3. Section-by-section draft:
   - Identity of controller(s) and processor(s)
   - Categories of personal data collected
   - Sources of personal data (collected from user; OCR'd from
     user uploads — provenance is RC3 surface)
   - Purposes of processing
   - Legal bases (GDPR Art. 6) for each purpose
   - Recipients (sub-processors per current list)
   - Cross-border transfers (SCC 2021/914 referenced)
   - Retention periods (cross-reference 49 CFR retention)
   - Data-subject rights (access, rectification, erasure subject
     to retention obligations, portability, objection,
     restriction)
   - DSAR process + SLA (GDPR-mandated 1 month; we target 14
     days — must match what we can actually deliver)
   - Children's data (none collected)
   - Security overview (cross-references SoA)
   - Updates to this policy
4. Run the Legal Consistency Auditor: every claim consistent
   with internal policy, sub-processor list, retention policy,
   cryptography policy.
5. Capture in `docs/compliance/` (replacing or augmenting
   existing forward-tagged R5-T placeholder).

## Deliverable Format

A draft Privacy Policy committed under `docs/compliance/
privacy-policy-customer-facing.md` with the counsel-review
banner.

## Quality Checklist

- [ ] Counsel-review banner present at top
- [ ] Every data flow listed
- [ ] Every sub-processor listed (or "list maintained
  separately at <path>")
- [ ] No retention overpromise (e.g. cannot promise erasure of
  records under 7-year DOT retention)
- [ ] DSAR SLA matches deliverable
- [ ] Cross-references resolve

## Escalation Triggers

- Internal policy missing for a claim the draft wants to make →
  halt; route to Privacy Counsel + R5-U internal policy update.
- New cross-border transfer with no SCC mechanism → halt;
  Privacy Counsel.

## Related Agents

- Privacy Counsel Agent (Legal Office)
- Legal Consistency Auditor (Legal Office)
- Compliance Evidence Agent (Assurance Office)

## Related Artifacts

- `docs/templates/legal-document-intake-template.md`
- `docs/iso27001/policies/privacy-policy.md`
- `docs/compliance/dpa-template.md` (cross-reference)
