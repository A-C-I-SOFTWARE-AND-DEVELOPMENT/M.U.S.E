---
name: mission-brief-build
description: Use at the start of any Council Mode run or any substantive sprint that lands in a run folder under docs/aos/runs/. Produces 00-mission-brief.md by instantiating docs/templates/mission-brief-template.md. Restates owner intent, scope, exclusions, known facts, unknowns, success criteria, definition of done — without re-interpreting later.
---

# mission-brief-build

## When to use

The chief-orchestrator (or a council-planning workflow caller) is
opening a new run folder under `docs/aos/runs/YYYY-MM-DD-<slug>/`
and needs the gating input contract for Council Mode and downstream
execution.

## Inputs

- The owner's request (verbatim).
- The risk class hypothesis per `docs/governance/03-change-risk-matrix.md`.
- The proposed Council Mode tier per
  `docs/governance/16-deliberative-planning-and-council-mode.md` —
  Not-required / Lite / Standard / RC3-strategy.
- Known repo facts the mission depends on (cite paths).

## Method

1. Create the run folder if it does not exist:
   `docs/aos/runs/YYYY-MM-DD-<slug>/`.
2. Copy `docs/templates/mission-brief-template.md` to
   `docs/aos/runs/YYYY-MM-DD-<slug>/00-mission-brief.md`.
3. Paste the owner's request verbatim. Do not paraphrase.
4. Fill product, user, and technical objectives — each one
   paragraph.
5. List explicit exclusions. If something seems in scope but is
   not, name it here.
6. Build the Known Facts table with citations (file paths or
   external sources with access date).
7. Build the Uncertain Assumptions table — each entry names what
   changes if the assumption is wrong.
8. Tag risk class. If RC4, stop and convert to an owner planning
   note.
9. Tag Council Mode tier per `governance/16`. Justify if Not-required.
10. List success criteria as measurable observable outcomes.
11. List non-negotiables (always includes the five owner-only walls
    and the source-of-truth hierarchy).
12. Write Definition of Done as a checkbox list a different agent
    could verify.
13. Run `npm run council-codex:check` to confirm the run folder
    pattern is intact.

## Output

`docs/aos/runs/YYYY-MM-DD-<slug>/00-mission-brief.md` — a single
artifact that downstream agents can act on without re-interpreting
owner intent.

## Anti-patterns

- Paraphrasing the owner's request.
- "TBD" risk class on a clearly RC3 surface.
- Success criteria phrased as "feels good" rather than
  observable outcomes.
- Re-deciding scope mid-sprint after the mission brief lands
  (instead, edit the brief with a dated revision note).
- Skipping the run folder and writing the brief into a one-off
  chat reply.
