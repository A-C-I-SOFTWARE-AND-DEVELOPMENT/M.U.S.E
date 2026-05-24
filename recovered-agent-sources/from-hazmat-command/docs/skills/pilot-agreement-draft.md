# Skill — pilot-agreement-draft

## Purpose

Draft a Pilot Agreement under `governance/12` that lets HazMat
Command and a carrier run a time-boxed evaluation with explicit
scope, success criteria, data handling, and conversion path.

## Triggers

- A pilot opportunity is qualified and ready to start.
- Owner asks for a pilot template.

## Required Inputs

- Carrier identity and contact.
- Pilot scope (which features in scope, which roles using,
  which data set).
- Pilot duration (typical 30–90 days).
- Success criteria (objective, measurable).
- Pricing for the pilot (typically free or discounted).
- Conversion path (auto-convert on success vs. opt-in).

## Research Required

- Counterparty's procurement requirements (DPA, security,
  insurance).
- Current `docs/rfp/answer-bank.md` for buyer-facing answers.
- Current `SKIPPED.md` for procurement blockers that affect
  pilot deliverability (e.g. carrier requires SCIM →
  `workos-procurement`).

## Step-by-Step Method

1. Intake + counsel-review banner per `governance/12`.
2. Sections:
   - Parties + effective date
   - Scope of pilot (features in / out)
   - Pilot term
   - Pilot pricing (or fee waiver)
   - Acceptance and success criteria
   - Data handling — incorporate DPA by reference if applicable
     (`docs/compliance/dpa-template.md`)
   - Confidentiality (NDA-equivalent)
   - Service availability expectations during pilot
   - Support contact
   - Conversion path on success
   - Termination
   - No commitment to ongoing service (pilot is not GA)
3. Cross-check the in-scope features against `SKIPPED.md` —
   any pilot-blocking gap → halt; route to owner.

## Deliverable Format

A draft Pilot Agreement under `docs/compliance/pilot-
agreement-<carrier>.md` with the counsel-review banner.

## Quality Checklist

- [ ] Counsel-review banner
- [ ] Success criteria measurable
- [ ] Data handling addressed (or DPA by reference)
- [ ] No SLA promise the BCDR runbook can't meet
- [ ] No pilot scope claim on a stubbed feature without
  explicit "in pilot only" caveat

## Escalation Triggers

- A carrier requirement that the pilot cannot satisfy → halt;
  route to owner.

## Related Agents

- Contract Drafting Agent (Legal Office)
- Pilot Program Manager (Pilot Ops)
- Enterprise Procurement Agent (Commercial Office)

## Related Artifacts

- `docs/templates/legal-document-intake-template.md`
- `docs/compliance/dpa-template.md`
