# Skill — pilot-readiness-audit

## Purpose

Before any pilot demo, run a structured audit confirming the
demo path is shippable, no P0 blockers gate the demo, and no
claim in the demo deck contradicts the substantiation policy.

## Triggers

- Demo scheduled within 14 days.
- Demo branch updated within the 24-hour freeze window
  (`PUBLISH.md` pilot-week freeze rule).
- Owner requests a pre-demo audit.

## Required Inputs

- The Pilot Demo Architect's script.
- The current state of `docs/inventory/blockers-final.md`.
- The current SKIPPED.md.
- The release notes for the current build.
- The Vercel preview URL the demo will run on.

## Research Required

- `governance/09-release-freeze-and-safety-budget-policy.md` —
  the 9 freeze triggers.
- `governance/11-commercial-claims-substantiation-policy.md` —
  claim classes.
- `PUBLISH.md` — G0–G4 gates.

## Step-by-Step Method

1. Confirm `npm test` is 727/727 (or the current baseline) green
   on the demo commit.
2. Confirm no open P0 in `blockers-final.md` affects the demo
   path. Specifically check: Square access-token revocation
   confirmed; no production-path-affecting Stage 3/4 stub
   regression.
3. Walk the demo script step by step on the Vercel preview URL:
   - sign-up
   - onboarding
   - load create
   - document upload
   - OCR review with provenance badges
   - validation pass
   - assignment with hazmat-endorsement check (today the
     dispatcher UI wire-up is open — the script must either
     demonstrate the helper or skip the assignment step
     gracefully)
   - audit timeline
   - trust portal walk
4. Confirm Square is in stub mode for the demo (do not flip env
   vars for a demo).
5. For Canadian demos: confirm FR rendering is labeled
   "draft-not-certified" per `certified-translator-engagement`.
6. Check the demo deck for any claim that violates `governance/
   11` (especially C3 regulatory and C4 customer claims).
7. Sign / no-sign the Pilot Readiness Report
   (`docs/templates/pilot-readiness-report-template.md`).

## Deliverable Format

A populated Pilot Readiness Report.

## Quality Checklist

- [ ] Tests green
- [ ] No demo-blocking P0
- [ ] Demo path rehearsed on preview
- [ ] Square in stub mode
- [ ] FR labeling honored
- [ ] No unsubstantiated claim in the deck
- [ ] Sign-off signed

## Escalation Triggers

- Test failure → halt demo; Risk Controller.
- Open P0 affecting demo path → halt demo; coordinate owner
  unblock.
- Unsubstantiated commercial claim in the deck → halt deck
  publication; route to Claims Substantiation Agent.

## Related Agents

- Pilot Demo Architect (Product Studio)
- Pilot Readiness Judge (Assurance Office)
- Risk Controller (Executive Command)

## Related Artifacts

- `docs/templates/pilot-readiness-report-template.md`
- `docs/inventory/blockers-final.md`
