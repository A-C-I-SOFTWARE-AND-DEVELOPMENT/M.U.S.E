---
name: master-plan-synthesis
description: Use after plan-comparison-scorecard. Produces 04-synthesized-plan.md by curating surviving ideas into a single master plan, naming rejected ideas with rationale, and surfacing unresolved owner choices rather than silently deciding them. Synthesizer must not also red-team the plan.
---

# master-plan-synthesis

## When to use

Council Mode step 6. The multi-plan set and scorecard exist. The
red-team has not yet run.

## Inputs

- `00-mission-brief.md`, `01-evidence-bundle.md`,
  `02-risk-classification.md`, `03-options-or-council-plans.md`
  (with scorecard).

## Method

1. Copy `docs/templates/synthesized-master-plan-template.md` to
   `04-synthesized-plan.md` in the run folder.
2. Confirm independence — you are not a plan author for this run,
   and you will not author `05-red-team-review.md`.
3. Write the one-paragraph final strategic thesis.
4. Populate the Decisions Adopted table — each row names the source
   plan(s), the evidence supporting the decision, and why it beat
   alternatives.
5. Populate the Decisions Rejected table — preserve every rejected
   idea with rationale (so the post-red-team revision does not
   silently re-introduce it).
6. Populate the Unresolved Owner Choices table — surface, do not
   decide. Each row names the choice, the options, the implication
   of each, and when the owner decision is needed.
7. Define implementation order (waves), each with builder /
   reviewer / verifier assignments (different agents / sessions /
   humans per `governance/06`).
8. List artifacts to create per wave (Research Dossier, ADR,
   threat model, claims memo, Codex packet as applicable).
9. List test gates that must remain green.
10. Write the master Definition of Done.
11. Note commercial / readiness implications (claims class C1–C6
    per `governance/11`; counsel-review banner if legal text
    introduced per `governance/12`).
12. Sign the Synthesizer attestation checklist.

## Output

`04-synthesized-plan.md` — single master plan that downstream
red-team challenges and that the owner approves.

## After red-team

Council Mode allows **one** revision pass after red-team. Update
the file with a dated revision note; do not silently re-author.
Preserve the original adopted/rejected audit trail.

## Anti-patterns

- Averaging plans rather than curating.
- Silently re-introducing a rejected idea.
- Silently deciding an owner choice.
- A synthesis that adds new scope not present in any plan.
- Same agent / session as the red-team reviewer.
- A "synthesis" that is actually plan A renamed.
