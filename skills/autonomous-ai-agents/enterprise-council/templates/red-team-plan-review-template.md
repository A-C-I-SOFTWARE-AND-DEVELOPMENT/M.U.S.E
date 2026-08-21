# Red-Team Plan Review — <short title>

**Date:** YYYY-MM-DD
**Author (red-team):** <agent / session — must NOT be the synthesizer>
**Run folder:** `docs/aos/runs/YYYY-MM-DD-<slug>/`
**Artifact slot:** `05-red-team-review.md`
**Companion governance:** `docs/governance/16-deliberative-planning-and-council-mode.md`,
`docs/governance/06-maker-checker-independent-review.md`

> The red-team's job is to find what the synthesizer missed.
> Critiques must cite the Evidence Bundle. Persuasive prose without
> citations is rejected on review per `governance/05` and
> `governance/16`.

## Independence attestation

- [ ] I did not author any plan in `03-options-or-council-plans.md`.
- [ ] I did not author `04-synthesized-plan.md`.
- [ ] I will not author the post-red-team revision; the synthesizer
  will.

## Review pass

For each finding, fill the template below. Add as many findings as
warranted; do not invent findings to look thorough.

### Finding F1 — <short title>

**Category:** <pick one>
- amateur-feeling
- AI-theater (uncited claim / vague language / marketing-flavored prose)
- under-researched
- buyer-would-reject (cite which persona — fleet ops, safety
  manager, dispatcher, procurement, security lead, compliance officer)
- enterprise-architect-would-reject
- security-lead-would-reject
- overbuilt (more scope than the Mission Brief requested)
- under-built (less than the success criteria require)
- unsupported assumption
- infeasible in the proposed sprint
- causes rework later

**Evidence citation:**
- Evidence Bundle item: <ID>
- Repo path: `<path>`
- External source: `<URL or section ref>`
- Date checked: YYYY-MM-DD

**What the synthesized plan claims:** <quote>

**Why this is a defect:** <one paragraph, evidence-grounded>

**Most defensible remediation:** <one specific change to the
synthesized plan — preserve the rest>

---

### Finding F2 — <short title>

<repeat the template>

---

## Cross-cutting concerns

- Owner-only walls touched (any plan elements that would require
  L4 action and were not surfaced as such):
- Claims policy compliance (uncited claims per `governance/11`):
- Source-of-truth conflicts (anything in the plan that contradicts
  AGENTS.md, PUBLISH.md, SKIPPED.md, live code):
- Hidden assumptions about budget, calendar, vendor availability:

## What the plan does well (preserve)

- <named strength 1 — be specific>
- <named strength 2 — be specific>

A red-team that finds zero strengths is a low-quality red-team;
state what should not be revised so the synthesizer does not
over-correct.

## Verdict

- [ ] **Approve as-is** — no findings of severity warranting
  revision.
- [ ] **Revise once** — findings F___, F___ require revision; the
  synthesizer applies the single allowed revision pass.
- [ ] **Return to plan generation** — the synthesized plan is not
  recoverable in one revision; regenerate plans against a sharper
  Mission Brief.
- [ ] **Escalate to owner** — a finding requires an owner decision
  before synthesis can be completed.

## Anti-patterns rejected on sight

- A red-team writeup with zero citations.
- A red-team writeup that re-derives the synthesizer's plan from
  scratch.
- A red-team writeup that proposes more than one revision pass.
- A red-team writeup whose findings cannot be acted on (no
  specific remediation).
- A red-team verdict of "Approve as-is" on a Council Mode RC3
  run (independent challenge is the point; a clean approval
  without scrutiny is suspect).
