# Workflow — Complex Bug Fix

## Trigger

A defect is reported (pilot feedback, internal discovery, Sentry
alert when wired, CI failure) that touches an RC3 surface or
requires cross-division reasoning.

## Required Divisions

Executive Command, Engineering Factory, Assurance Office.
Research Bureau if a regulatory citation is involved. Legal
Office if a public claim is implicated.

## Required Research Artifact

Decision Memo (`templates/decision-memo-template.md`) is
sufficient for most fixes. Full Research Dossier required if
the defect reveals a misunderstanding of a primary source
(regulation, standard, vendor contract).

## Agent Topology

Single specialist or prompt chain (root-cause → fix → verify).

## Sequence

1. **Triage** — Chief Orchestrator classifies the defect by
   surface and severity. Determines RC class.
2. **Root cause** — Engineering Factory's relevant specialist
   reproduces the defect and traces it.
3. **Containment** — if the defect is in production, apply
   feature-flag kill switch where possible (cross-reference
   `governance/10`). If not, escalate to Risk Controller for
   release-freeze evaluation.
4. **Fix** — write the fix + a regression test that fails
   before / passes after.
5. **Verify** — Independent QA confirms the fix and that no
   adjacent tests broke. For security/compliance fixes, the
   relevant verifier signs off per `governance/06`.
6. **Postmortem** — if the defect is RC3 or caused production
   instability, Postmortem Agent (Knowledge Operations) writes
   the blameless retro.
7. **Documentation** — update SKIPPED if a stub was the cause;
   update threat model / risk register if security-relevant.

## Parallelization Opportunities

- Containment and root cause can run in parallel for a
  production defect.

## Maker-Checker Review Points

- RC3 fix: Engineering Factory builder + Independent QA
  reviewer + relevant verifier.
- Postmortem: Knowledge Operations builder + Risk Controller
  reviewer.

## Final Outputs

Decision Memo · Regression test · Updated SKIPPED if applicable
· Updated threat model / risk register if applicable ·
Postmortem if RC3 · Retrospective.

## Acceptance Criteria

- Regression test passes.
- Adjacent tests still pass.
- No new freeze trigger introduced.
- Postmortem filed for RC3 / production-impacting defects.
