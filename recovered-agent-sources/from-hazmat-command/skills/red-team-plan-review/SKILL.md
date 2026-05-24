---
name: red-team-plan-review
description: Use after master-plan-synthesis. Independently attacks the synthesized master plan for amateur-feeling content, AI-theater, under-research, buyer/architect/security-lead objections, overbuild, under-build, unsupported assumptions, infeasibility, and rework risk. Every critique cites the Evidence Bundle. Red-team must not be the synthesizer.
---

# red-team-plan-review

## When to use

Council Mode step 7. The synthesized master plan exists at
`04-synthesized-plan.md`. The revision pass has not yet happened.

## Inputs

- `04-synthesized-plan.md` (the target).
- `01-evidence-bundle.md` (every critique cites it).
- `03-options-or-council-plans.md` + scorecard (context for what
  the synthesizer adopted vs rejected).
- `00-mission-brief.md` (scope / success criteria).

## Method

1. Copy `docs/templates/red-team-plan-review-template.md` to
   `05-red-team-review.md` in the run folder.
2. Sign the Independence Attestation: you authored no plan in
   this run, you did not synthesize, you will not author the
   post-red-team revision.
3. For each finding, fill the template entry with:
   - category (amateur-feeling / AI-theater / under-researched /
     buyer-would-reject / architect-would-reject /
     security-lead-would-reject / overbuilt / under-built /
     unsupported assumption / infeasible / causes rework),
   - evidence citation (Evidence Bundle item, repo path, or
     external source with date),
   - quote of what the plan claims,
   - why this is a defect (one paragraph, evidence-grounded),
   - most defensible remediation (one specific change).
4. Add a Cross-cutting Concerns section — owner-only walls
   touched, claims-policy compliance, source-of-truth conflicts,
   hidden budget / calendar / vendor assumptions.
5. List what the plan does well (preserve so the synthesizer does
   not over-correct).
6. Write the verdict — Approve as-is / Revise once / Return to
   plan generation / Escalate to owner.

## Output

`05-red-team-review.md` — used by the synthesizer to revise the
master plan once before owner approval.

## Anti-patterns

- Findings without evidence citations.
- A red-team that rewrites the plan from scratch.
- A red-team that proposes more than one revision pass.
- Vague critiques without specific remediation.
- "Approve as-is" on a Council Mode RC3 run without scrutiny
  (independent challenge is the point).
- Findings invented to look thorough.
