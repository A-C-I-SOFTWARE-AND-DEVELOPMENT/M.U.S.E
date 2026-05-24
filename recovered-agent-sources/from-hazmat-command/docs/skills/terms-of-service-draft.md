# Skill — terms-of-service-draft

## Purpose

Draft or revise HazMat Command's Terms of Service under
`governance/12`. Covers acceptable use, account responsibilities,
service availability, warranties, limitations of liability,
disputes, governing law.

## Triggers

- New product surface that materially changes ToS scope.
- New jurisdictional reach.
- Annual review.

## Required Inputs

- Current ToS (if any).
- Product capability list (release notes).
- Pricing source of truth.
- Acceptable use policy
  (`docs/iso27001/policies/acceptable-use-policy.md`).
- Subscription terms (Square billing flow specifics).

## Research Required

- Standard B2B SaaS ToS patterns.
- Jurisdictional requirements (US, Canada, EU if applicable).
- FTC dark-pattern guidance — no auto-renewal hidden in
  fine print.

## Step-by-Step Method

1. Intake + counsel-review banner per `governance/12`.
2. Sections:
   - Acceptance of terms
   - Account creation and security
   - Acceptable use (cross-reference internal policy)
   - Subscription, billing, refund terms (cross-reference Square
     flow and the plan band)
   - Service availability and changes
   - User content and data (cross-reference Privacy Policy)
   - Warranty disclaimer
   - Limitation of liability
   - Indemnification
   - Termination
   - Dispute resolution
   - Governing law
   - Changes to ToS
3. Legal Consistency Auditor pass.
4. Capture in `docs/compliance/terms-of-service.md` or
   `marketing/pages/terms.md` per repo convention.

## Deliverable Format

A draft ToS with counsel-review banner.

## Quality Checklist

- [ ] Counsel-review banner
- [ ] Billing terms match Square flow + plan band
- [ ] No warranty / SLA promise that BCDR runbook can't meet
- [ ] Termination terms match account-deletion behavior
- [ ] No dark pattern around auto-renewal

## Escalation Triggers

- Jurisdictional ambiguity → owner + Privacy Counsel.
- SLA promise that exceeds capability → halt.

## Related Agents

- Product Counsel Agent (Legal Office)
- Legal Consistency Auditor (Legal Office)
- Chief Commercial Officer (Commercial Office)

## Related Artifacts

- `docs/iso27001/policies/acceptable-use-policy.md`
- `docs/templates/legal-document-intake-template.md`
