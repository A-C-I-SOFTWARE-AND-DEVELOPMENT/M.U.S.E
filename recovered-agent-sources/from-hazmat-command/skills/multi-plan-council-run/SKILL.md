---
name: multi-plan-council-run
description: Manual-only. Owner-triggered. Dispatches N parallel plan-generation passes for Council Mode (Lite 3 / Standard 4–6 / RC3-strategy 6+) each under a distinct lens — Market Domination, Enterprise Trust, Product Experience, Engineering Reality, Minimal High-Leverage, Moonshot Differentiation, and optional domain specialist. Materially-distinct plans only — fake diversity rejected by the scorer.
disable-model-invocation: true
---

# multi-plan-council-run

## When to use

Owner explicitly invokes Council Mode per
`docs/governance/16-deliberative-planning-and-council-mode.md`.
Mission Brief and Evidence Bundle exist in the run folder. Council
tier is set.

This skill is manual-only because Council Mode is an owner-driven
deliberation; auto-invocation on every task would create approval
fatigue and false confidence per the warnings in `governance/16`.

## Inputs

- `00-mission-brief.md` in the run folder.
- `01-evidence-bundle.md` in the run folder.
- Council Mode tier (Lite 3 / Standard 4–6 / RC3-strategy 6+).
- Optional domain specialist (HazMat regulatory / data privacy /
  fintech / legal / etc.).

## Method

1. Copy `docs/templates/multi-plan-set-template.md` to
   `03-options-or-council-plans.md` in the run folder.
2. Assign distinct lenses per tier:
   - **Lite (3):** Enterprise Trust, Engineering Reality, Minimal
     High-Leverage.
   - **Standard (4–6):** above + Market Domination + Product
     Experience (4–5); +Moonshot Differentiation for 6.
   - **RC3-strategy (6+):** all six standard lenses + domain
     specialist.
3. Dispatch one plan-generation pass per lens. **Each lens to a
   different agent / session** to avoid lens-collapse.
4. Each plan must include every section in the template (thesis,
   ship list, architecture shape, accepted trade-offs, rejected
   trade-offs, owner-only walls touched, tests, rollback, risk
   class, cost). Plans that collapse sections are returned for
   completion.
5. Run the cross-plan distinctness check at the bottom of the
   template. If plans converge on the same ship list with cosmetic
   differences, regenerate the weak plans under sharper lenses.
6. Hand off to `plan-comparison-scorecard` for scoring.

## Output

`03-options-or-council-plans.md` populated with N materially-distinct
plans. Maker-checker pairing recorded (lens → agent / session).

## Anti-patterns

- Single-session generation of all N plans (collapses lenses).
- Plans that recommend the same ship list with different wording.
- A plan that cites zero items from the Evidence Bundle.
- A plan that introduces a new commercial claim or legal text
  outside the Mission Brief's scope.
- A plan with risk class "TBD."
- A plan whose author also scores or red-teams the same set
  (violates maker-checker).
