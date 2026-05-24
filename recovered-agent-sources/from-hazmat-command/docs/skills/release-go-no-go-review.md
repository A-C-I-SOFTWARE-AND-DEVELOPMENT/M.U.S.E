# Skill — release-go-no-go-review

## Purpose

Make an explicit go / no-go recommendation on a candidate
release at G2 (Preview Verification Gate) before G3 (Owner
Publish).

## Triggers

- A PR is reviewable and the owner is about to enter the
  preview-and-publish flow.
- A scheduled release cycle.

## Required Inputs

- The candidate PR.
- The G1 CI status (all jobs green).
- The Independent QA / V&V Agent's sign-off.
- The relevant domain reviewer's sign-off (Security Architect,
  Compliance Evidence, etc. per the change).
- The freeze-trigger status (`governance/09`).
- The pilot calendar.

## Research Required

- `PUBLISH.md` G0–G4 definitions.
- The risk-class tag on the PR.
- Recent rework / defect-escape rate from
  `agent-performance-scoreboard-schema.md`.

## Step-by-Step Method

1. Confirm every required PR-template field is filled.
2. Confirm CI is green on the PR head.
3. Confirm the maker-checker fields are populated for RC2/RC3.
4. Confirm no release-freeze trigger is active.
5. For RC3: confirm the verifier role (security / compliance /
   legal / commercial-claims as applicable) signed off.
6. Confirm any new commercial claim has a substantiation memo;
   any new legal draft has the counsel-review banner.
7. Confirm the pilot-week freeze window is not active (or, if
   active, the change is a security-relevant safety update with
   owner approval).
8. Write the go / no-go memo with explicit conditions if go.
9. Hand off to the owner.

## Deliverable Format

A short Go / No-Go memo (200–400 words) appended to the PR
description or filed under `docs/research/retros/`.

## Quality Checklist

- [ ] CI green
- [ ] Maker-checker confirmed for RC2/RC3
- [ ] No freeze trigger active
- [ ] Verifier confirmed for security/compliance/legal/commercial
- [ ] Commercial / legal banners present
- [ ] Freeze window honored
- [ ] Explicit recommendation

## Escalation Triggers

- Any unresolved blocker → no-go.
- Freeze trigger active → no-go.
- Conflict with pilot-week freeze → no-go unless owner
  explicitly overrides.

## Related Agents

- Pilot Readiness Judge (Assurance Office)
- Risk Controller (Executive Command)
- Chief Orchestrator (Executive Command)

## Related Artifacts

- The PR template (`.github/PULL_REQUEST_TEMPLATE.md`)
- `docs/inventory/blockers-final.md`
