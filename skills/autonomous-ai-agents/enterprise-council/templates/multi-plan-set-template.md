# Multi-Plan Set — <short title>

**Date:** YYYY-MM-DD
**Authors:** one distinct agent / session per plan (see Maker-Checker)
**Run folder:** `docs/aos/runs/YYYY-MM-DD-<slug>/`
**Artifact slot:** `03-options-or-council-plans.md` (paired with
the scorecard from `plan-comparison-matrix-template.md`)
**Companion governance:** `docs/governance/16-deliberative-planning-and-council-mode.md`

> Council plans must be **materially distinct**. Fake diversity is
> worse than one clear plan. Each plan in this set is authored under
> a different lens, with a different objective function, drawing
> from the same Evidence Bundle but emphasizing different items.

## Lens assignments

| Plan | Lens | Optimizes for | Author (agent/session) |
|---|---|---|---|
| A | Market Domination | category leadership, premium narrative, differentiation | |
| B | Enterprise Trust | procurement confidence, no overclaiming, citation discipline | |
| C | Product Experience | UX flow, IA, CTA hierarchy, emotional clarity | |
| D | Engineering Reality | clean implementation, maintainability, risk containment | |
| E | Minimal High-Leverage | max perceived maturity, min risky change, best ROI for one sprint | |
| F | Moonshot Differentiation | moat, category creation, defensibility | |
| (+) | Domain specialist (privacy / fintech / legal / data / regulated) | regulatory or vertical fit | |

Drop a plan only when its lens is genuinely irrelevant; justify in
the comparison matrix.

## Mandatory plan shape

Each plan below must contain every section. Do not collapse
sections to fit a smaller plan — collapse the plan instead.

---

### Plan A — Market Domination

**Lens:** category leadership, premium narrative, differentiation.

**Author:** <agent / session>
**Evidence items relied on:** <item IDs from the Evidence Bundle>

#### Thesis (one paragraph)

#### What ships in this sprint

- <user-visible change 1>
- <user-visible change 2>

#### Architecture / system shape

#### Trade-offs accepted

#### Trade-offs rejected (and why)

#### Owner-only walls touched

#### Tests added or changed

#### Rollback plan

#### Risk class (RC0–RC4)

#### Cost (effort and calendar)

---

### Plan B — Enterprise Trust

**Lens:** procurement confidence, no overclaiming, citation discipline.

<repeat the same nine sections>

---

### Plan C — Product Experience

<repeat>

---

### Plan D — Engineering Reality

<repeat>

---

### Plan E — Minimal High-Leverage

<repeat>

---

### Plan F — Moonshot Differentiation

<repeat>

---

### Plan + — Domain Specialist (optional)

<repeat>

---

## Maker-checker for this artifact

- Each plan was authored by a different agent / session.
- No plan was authored by the synthesizer who will produce
  `04-synthesized-plan.md`.
- No plan was authored by the red-team reviewer who will produce
  `05-red-team-review.md`.
- The pairing is recorded in the run folder's session ledger or in
  the dispatching skill's output.

## Cross-plan distinctness check

Before handing off to scoring, the author of this artifact confirms:

- [ ] Each plan recommends a different ship list (or a clearly
  different sequencing).
- [ ] Each plan accepts a different trade-off.
- [ ] Each plan would lose differently if it failed.

If any of these is unchecked, the plan set is not materially
distinct — regenerate the weak plans under sharper lenses.

## Anti-patterns rejected on sight

- Six plans converging on the same ship list with cosmetic wording
  differences.
- A plan that cites no items from the Evidence Bundle.
- A plan that introduces a new commercial claim, legal sentence,
  or pricing copy not in scope per the Mission Brief.
- A plan whose risk class is "TBD."
