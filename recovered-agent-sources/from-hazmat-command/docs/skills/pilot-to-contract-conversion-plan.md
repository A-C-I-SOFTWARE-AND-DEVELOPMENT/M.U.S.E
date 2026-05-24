# Skill — pilot-to-contract-conversion-plan

## Purpose

Produce a step-by-step plan to convert a pilot carrier into a
signed contract: success criteria, evidence collection,
objection handling, procurement readiness, contract path.

## Triggers

- A pilot is approved / starting.
- A pilot is in week-2+ and approaching the conversion window.
- An owner asks "what would it take to close X?"

## Required Inputs

- Pilot scope (which features in scope, which roles using).
- Pilot success criteria (defined at start, ideally per the
  Pilot Program Manager's plan).
- Carrier procurement requirements (security questionnaire,
  DPA, sub-processor list, MSA template preferences).

## Research Required

- The current state of:
  - `docs/rfp/answer-bank.md` (62 Q)
  - `docs/rfp/dry-run.md` (30 Q)
  - `docs/compliance/dpa-template.md` (R5-T forward-tagged)
  - `docs/compliance/sub-processor-list.md` (R5-T forward-tagged)
- The current `SKIPPED.md` for any procurement blockers that
  affect the carrier (WorkOS, Supabase, S3 Object Lock, etc.).

## Step-by-Step Method

1. Confirm pilot success criteria are met (or document the gap).
2. Collect evidence: audit chain extracts, OCR confidence
   distributions, inspection-prep time deltas, dispatcher
   adoption rates.
3. Anticipate objections — use Buyer Objection Agent +
   `competitor-battlecard` for the carrier's incumbent tool.
4. Map every procurement document the carrier will ask for to
   an existing repo asset:
   - DPA → `docs/compliance/dpa-template.md` (draft;
     counsel-review required per `governance/12`)
   - sub-processor list → `docs/compliance/sub-processor-list.md`
   - security questionnaire → `docs/rfp/answer-bank.md`
   - SOC 2 / ISO 27001 attestation → labeled "scaffold, not
     certify" per `docs/iso27001/README.md` — disclose status
     candidly
5. Identify the procurement blockers that affect this carrier
   specifically (e.g. carrier requires SCIM → flag
   `workos-procurement` + `supabase-tenant-scim-tokens`).
6. Produce a Conversion Plan with: timeline, owner actions,
   carrier actions, expected close date, sign-off gate.

## Deliverable Format

A Conversion Plan memo under `docs/research/pilots/<YYYY-MM-DD>-
<carrier>-conversion.md`.

## Quality Checklist

- [ ] Success criteria evidence collected
- [ ] Every objection has an answer
- [ ] Every procurement doc mapped
- [ ] Procurement blockers explicit and owner-routed
- [ ] No claim made in the plan that isn't substantiated

## Escalation Triggers

- A carrier ask that requires an L4 owner action (DPA
  signature, sub-processor list update, ad spend) → file as
  owner-action with the runbook reference.
- Any commercial claim in the close materials → route to
  Claims Substantiation Agent.

## Related Agents

- Pilot Program Manager (Pilot Ops)
- Enterprise Procurement Agent (Commercial Office)
- Contract Drafting Agent (Legal Office)
- Buyer Objection Agent (Pilot Ops)

## Related Artifacts

- `docs/templates/pilot-readiness-report-template.md`
- `docs/rfp/answer-bank.md`
