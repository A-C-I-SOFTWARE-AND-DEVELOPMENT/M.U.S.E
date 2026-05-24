# Skill — packaging-entitlements-analysis

## Purpose

Decide which features are in which plan (Solo / Team / Fleet /
Enterprise) and keep the entitlement matrix consistent with the
feature-flag registry and the Billing UI.

## Triggers

- A new feature ships and needs a plan assignment.
- A pricing study recommends a packaging change.
- A customer asks "what's in Team?"
- A flag-registry change.

## Required Inputs

- Current plan band (Solo $29 / Team $79 / Fleet $199 /
  Enterprise).
- Current feature inventory (release notes + flag registry).
- Customer pain themes by persona.
- Competitor packaging benchmarks.

## Research Required

- The feature-flag registry
  (`governance/10-feature-flag-and-beta-gate-registry.md`).
- The current `src/pages/Billing.jsx` cards.
- Competitor packaging from `competitor-benchmark`.

## Step-by-Step Method

1. List every feature in the product (capabilities at the
   v1.0.0 release tag + anything since).
2. For each, decide plan availability:
   - **Solo:** core compliance + audit chain + basic OCR.
   - **Team:** + dispatcher flow + multi-user RBAC.
   - **Fleet:** + bilingual EN/FR + advanced training-dossier
     features + email integration.
   - **Enterprise:** + SCIM/SSO (gated by `workos-procurement`)
     + S3-anchored audit (gated by `s3-object-lock`) +
     dedicated support + DPA.
3. Cross-check each Enterprise feature against its SKIPPED
   entry — features gated by procurement stubs must be labeled
   "available with procurement-completed setup."
4. Update the entitlements column in the GTM Brief and the
   `/Billing` cards spec (the actual `src/pages/Billing.jsx`
   change is Engineering Factory's work).
5. Confirm the packaging is consistent with the C5 (pricing)
   claim class per `governance/11`.

## Deliverable Format

A Packaging Matrix table + change request for `src/pages/
Billing.jsx`.

## Quality Checklist

- [ ] Every feature assigned a tier
- [ ] Procurement-gated features labeled
- [ ] Matrix matches Billing UI spec
- [ ] No tier promises a stubbed-only capability

## Escalation Triggers

- A feature whose plan assignment conflicts with current
  customer expectations (per pilot feedback) → halt; Chief
  Commercial Officer.

## Related Agents

- Packaging & Entitlements Agent (Commercial Office)
- Pricing Science Agent (Commercial Office)
- Frontend Product Engineer (Engineering Factory)

## Related Artifacts

- `docs/governance/10-feature-flag-and-beta-gate-registry.md`
- `src/pages/Billing.jsx`
