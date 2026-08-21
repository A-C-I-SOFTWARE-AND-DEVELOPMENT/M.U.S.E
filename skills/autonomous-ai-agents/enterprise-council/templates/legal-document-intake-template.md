# Legal Document Intake — <doc type / counterparty>

**Date:** YYYY-MM-DD
**Drafting Agent:** <Privacy Counsel | Product Counsel | Contract Drafting | DPA/Subprocessor | etc.>
**Document Type:** ToS | Privacy Policy | NDA | MSA | SOW | DPA | Pilot Agreement | Security Addendum | Order Form | Subprocessor Notice | Retention Policy | App-Store Disclosure | Claims Review Memo
**Counterparty:** <entity if applicable>
**Owner:** `<owner-handle>`

## Intake

| Field | Value |
|---|---|
| Purpose / permitted use | |
| Term length | |
| Jurisdiction(s) | |
| Cross-border data flow | |
| Sub-processors referenced | |
| Pricing / commercial terms | |
| SLA commitments | |
| Special clauses requested | |

## Required Inputs Confirmed

- [ ] Product capability evidence on file (substantiates any capability promise)
- [ ] Security posture cited (`docs/iso27001/` + `docs/security/threat-model.md`)
- [ ] Privacy data flows cited (`docs/iso27001/policies/privacy-policy.md`)
- [ ] Commercial terms match source of truth (`AGENTS.md` + Billing)
- [ ] Jurisdictional scope confirmed

## Mandatory Counsel-Review Banner

Every draft includes this banner verbatim at the top:

> **DRAFT — AI-ASSISTED**
>
> This document was drafted with AI assistance by an agent
> operating under the <organization> Autonomous Enterprise
> Organization (`docs/governance/12-legal-document-generation-
> policy.md`).
>
> **Qualified counsel review is required** before this document
> is shared with a counterparty, signed, executed, posted
> publicly, or used to establish a binding obligation. The text
> below is a starting point for that review; it is not legal
> advice and does not establish an attorney-client relationship.
>
> *Last drafted: YYYY-MM-DD by <division/skill name>.
> Counsel-review status: <pending | in review | approved by
> <name>, <date>>.*

## Consistency Check (by Legal Consistency Auditor)

- [ ] No capability overclaim vs. code/tests
- [ ] No retention overclaim vs. current data flows
- [ ] No sub-processor omission vs. current vendor list
- [ ] No jurisdictional overreach
- [ ] No fee / term inconsistency vs. pricing source of truth
- [ ] No regulatory citation error
- [ ] Cross-references resolve

## Hand-Off

- Filed at: `docs/compliance/<slug>.md`
- Counsel routed by: <owner>
- Counsel sign-off captured at: <link or note>
