# Skill — claims-substantiation-review

## Purpose

Verify every externally-visible claim against repository evidence
per `governance/11-commercial-claims-substantiation-policy.md`
before the claim is published.

## Triggers

- Any change to a public surface (`/trust` portal, `/Billing`,
  `marketing/`, `docs/rfp/answer-bank.md`, app-store listing,
  press release).
- Owner-requested review of an existing claim set.

## Required Inputs

- The proposed claim list.
- The current substantiation memos (`docs/research/claims/`).
- The repo's capability evidence (release notes, test results,
  threat model, SoA, runbooks).

## Research Required

- `governance/11` claim classes C1–C6.
- The repo's anti-claims discipline
  (`docs/iso27001/README.md` "scaffold not certify").

## Step-by-Step Method

1. For each claim, identify its class (C1–C6).
2. For each class, locate the required substantiation:
   - C1 (Factual): file + test path
   - C2 (Technical/Security): file + test + threat-model entry
   - C3 (Compliance/Regulatory): regulation citation + ISMS
     evidence
   - C4 (Customer/Traction): signed customer reference on file
   - C5 (Pricing): Billing source of truth + flag registry
   - C6 (Aspirational): explicit forward-looking labeling +
     dependency stub name
3. For any claim that cannot be substantiated, recommend:
   - delete the claim, or
   - rewrite as aspirational with proper labeling, or
   - block publication until evidence exists
4. Capture in a Claims Substantiation Memo per
   `docs/templates/claims-substantiation-template.md`.
5. Cross-check the result against the existing `/trust` portal
   copy and `docs/rfp/answer-bank.md` — no contradiction.

## Deliverable Format

A Claims Substantiation Memo under `docs/research/claims/
<YYYY-MM-DD>-<surface>.md`.

## Quality Checklist

- [ ] Every claim classified
- [ ] Every claim substantiated or labeled / removed
- [ ] No contradiction with existing public surfaces
- [ ] Memo linked from the originating PR

## Escalation Triggers

- A C3 (regulatory) claim that cannot be substantiated → halt
  publication; Risk Controller.
- A C4 customer claim without a signed reference → halt; Legal
  Office.

## Related Agents

- Claims Substantiation Agent (Legal Office)
- HazMat Market Positioning Agent (Commercial Office)
- Compliance Evidence Agent (Assurance Office)

## Related Artifacts

- `docs/templates/claims-substantiation-template.md`
