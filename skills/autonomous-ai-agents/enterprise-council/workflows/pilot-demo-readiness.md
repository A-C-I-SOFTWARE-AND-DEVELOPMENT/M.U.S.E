# Workflow — Pilot / Demo Readiness

## Trigger

A pilot or demo is scheduled within 14 days, or the current
pilot is in its closing window.

## Required Divisions

Executive Command (Pilot Demo Architect coordination, Risk
Controller, Chief of Staff), Product Studio (Pilot Demo
Architect), Assurance Office (Pilot Readiness Judge),
Commercial Office (sales / objection prep), Knowledge Operations
(retrospective).

## Required Research Artifact

Pilot Readiness Report
(`templates/pilot-readiness-report-template.md`) populated
and signed.

## Agent Topology

Parallel review panel converging on the Pilot Readiness Judge.

## Sequence

1. **Demo script** — Pilot Demo Architect writes / refreshes
   the script (`pilot-readiness-audit` skill input).
2. **Pre-flight** — Pilot Readiness Judge runs the audit:
   - tests 727/727 green
   - no demo-blocking P0 in `blockers-final.md`
   - Square in stub mode (do not flip env vars for a demo)
   - FR rendering labeled "draft-not-certified" for Canadian
     demos
   - no unsubstantiated claim in the deck
3. **Rehearsal** — walk the demo on the Vercel preview URL end
   to end.
4. **Pilot-week freeze** — `PUBLISH.md` 24h freeze rule active
   from T-24h to demo conclusion.
5. **Demo runs** — owner-driven.
6. **Debrief** — Field Feedback Analyst (Pilot Ops, division 08)
   captures observations.
7. **Retrospective** — Knowledge Operations files.

## Parallelization Opportunities

- Demo script + Pre-flight audit can run in parallel until
  rehearsal.

## Maker-Checker Review Points

- Builder: Pilot Demo Architect.
- Reviewer: Pilot Readiness Judge.
- Verifier: Risk Controller (final go/no-go).

## Final Outputs

Demo script · Pilot Readiness Report (signed) · Field
observations · Retrospective.

## Acceptance Criteria

- Pilot Readiness Judge signed.
- No freeze trigger active.
- Pilot-week freeze rule honored.
- Demo walked on Vercel preview at least once before showtime.
