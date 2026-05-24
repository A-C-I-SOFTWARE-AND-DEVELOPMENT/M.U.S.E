# 12 — Legal Document Generation Policy

**Status:** Installed 2026-05-17

The HazMat Command Autonomous Enterprise Organization may produce
legal documents **as drafts**. Every draft carries a mandatory
counsel-review banner and may not be used externally, signed, or
sent to a counterparty without qualified counsel review.

## Drafts the AEO may produce

Through the Legal, Policy, Contracts & Trust Office
(`docs/agents/07-legal-policy-contracts-trust-office.md`):

- Terms of Service (ToS)
- Privacy Policy (internal + customer-facing disclosures)
- NDA (mutual and one-way)
- Pilot Agreement
- Master Services Agreement (MSA)
- Statement of Work (SOW)
- Data Processing Addendum (DPA) — extends the existing
  `docs/compliance/dpa-template.md` placeholder
- Security Addendum
- Enterprise Order Form
- Subprocessor notices and update letters
- Retention policy (operational text supporting 49 CFR §172.201(e)
  and 49 CFR §172.704(d) 7-year retention)
- App Store / Play Store disclosure copy
- Claims review memos (cross-references `governance/11`)
- Vendor procurement T&Cs review notes

The corresponding skill files in `docs/skills/` are the SOPs:
`privacy-policy-draft`, `terms-of-service-draft`, `nda-draft`,
`pilot-agreement-draft`, `msa-sow-draft`, `dpa-draft`,
`claims-substantiation-review`, `oss-license-review`,
`app-store-policy-audit`.

## Mandatory counsel-review banner

Every legal document produced by the AEO carries this banner as the
first content block after the title:

> **DRAFT — AI-ASSISTED**
>
> This document was drafted with AI assistance by an agent operating
> under the HazMat Command Autonomous Enterprise Organization
> (`docs/governance/12-legal-document-generation-policy.md`).
>
> **Qualified counsel review is required** before this document is
> shared with a counterparty, signed, executed, posted publicly, or
> used to establish a binding obligation. The text below is a
> starting point for that review; it is not legal advice and does
> not establish an attorney-client relationship.
>
> *Last drafted: YYYY-MM-DD by <division/skill name>. Counsel-review
> status: <pending | in review | approved by <name>, <date>>.*

The banner is present in every legal template under
`docs/templates/legal-document-intake-template.md` and every
legal-doc skill specifies its inclusion.

## Required inputs

Before drafting begins, the legal agent confirms the following are
on file:

1. **Product inputs** — what the product actually does today, by
   citation to capability evidence per `governance/11`. The agent
   may not promise capabilities the product does not have.
2. **Security inputs** — current security posture per
   `docs/security/threat-model.md` and `docs/iso27001/`.
3. **Privacy inputs** — current data flows, processing purposes,
   retention, sub-processors per `docs/compliance/` and
   `docs/iso27001/policies/privacy-policy.md`.
4. **Commercial inputs** — pricing, plans, entitlements per
   `src/pages/Billing.jsx` and `governance/10-feature-flag-and-
   beta-gate-registry.md`.
5. **Jurisdictional scope** — which jurisdictions apply (US,
   Canada bilingual, EU under GDPR, California under CCPA).

If any input is missing or stale, the draft halts and the agent
files a request for the missing input via `AskUserQuestion` or a
draft PR comment.

## Document consistency checks

Before a legal draft is committed, the Legal Consistency Auditor
(in division 07) confirms:

- **No capability overclaim** vs. current code/tests.
- **No retention overclaim** vs. current data flows.
- **No sub-processor omission** vs. the actual vendor list
  (`docs/compliance/sub-processor-list.md` when populated).
- **No jurisdictional overreach** (e.g., promising GDPR DSAR
  workflows without a tested DSAR procedure).
- **No fee or term inconsistency** vs. the pricing source of truth.
- **No regulatory citation error** — section numbers, version
  numbers, and dates verified against the primary source.
- **Cross-references resolve** — every "see Section X" pointer
  lands.

A consistency-check pass is recorded in the draft's metadata block.

## Cross-references to existing compliance assets

The legal office reuses these existing assets rather than
duplicating them:

- `docs/compliance/dpa-template.md` (R5-T forward-tagged) —
  baseline DPA scaffold
- `docs/compliance/retention-policy.md` (R5-T forward-tagged) —
  retention floor per 49 CFR §172.201(e), §172.704(d), §177.817(f)
- `docs/compliance/sub-processor-list.md` (R5-T forward-tagged) —
  authoritative vendor list
- `docs/compliance/gdpr-disclosure.md`,
  `docs/compliance/ccpa-disclosure.md` (R5-T forward-tagged) —
  customer-facing privacy disclosures
- `docs/iso27001/policies/privacy-policy.md` — internal privacy
  policy
- `docs/iso27001/policies/cryptography-policy.md` — encryption-in-
  transit / at-rest standards
- `docs/iso27001/policies/supplier-security-policy.md` — vendor
  controls

If any cited asset does not yet exist (R5-T tags many as forward-
work), the legal draft uses the forward-link convention from
`docs/iso27001/README.md` and labels the dependency.

## Workflow

A legal-document workflow is in
`docs/workflows/legal-document-generation.md`. The summary:

1. Trigger (procurement request, pilot opportunity, GDPR/CCPA
   change, new vendor, etc.) routed to the Legal Office.
2. Intake via `docs/templates/legal-document-intake-template.md`.
3. Research dossier (`governance/05`) if the document is new or
   substantially revised.
4. Draft by the responsible legal skill (e.g., `dpa-draft`).
5. Consistency check by the Legal Consistency Auditor.
6. Claims substantiation review for any embedded claims.
7. Commit as draft with the banner and metadata block.
8. Owner-routed to qualified counsel; counsel notes captured in the
   draft's revision history.
9. Final external use is owner-only (L4 / T6 — never agent).

## Anti-patterns

- Removing or rewording the counsel-review banner to make a draft
  look "finished." The banner is mandatory and persists until
  counsel signs off.
- Drafting a DPA that promises "encryption at rest" when the
  `cryptography-policy.md` says some at-rest paths are deferred.
- Drafting a privacy policy that lists sub-processors not present
  in `docs/compliance/sub-processor-list.md`.
- Drafting an MSA with SLA targets that exceed what the BCDR
  runbook (`docs/compliance/bcdr-runbook.md` when published) can
  meet.
- Using a vendor-provided template verbatim without integrating
  HazMat-specific terms (data residency, HazMat-specific
  retention, regulator-export commitments).
- Treating "counsel-reviewed" as a banner that can be set
  programmatically. Only the owner records counsel review.
