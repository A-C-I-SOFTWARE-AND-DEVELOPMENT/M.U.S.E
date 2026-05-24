# Skill — source-contradiction-analysis

## Purpose

Identify and reconcile contradictions among repo docs, code, and
external sources before they propagate into decisions or claims.

## Triggers

- Two or more docs in the repo make conflicting statements.
- A doc and the live code/tests disagree.
- An external source contradicts the repo's stated position.
- The `doc-freshness-reconcile` skill surfaces a candidate
  contradiction.

## Required Inputs

- The conflicting sources (file paths, URLs, sections).
- The topic the contradiction concerns.

## Research Required

The source-of-truth hierarchy in
`docs/governance/01-source-of-truth-hierarchy.md` decides who
wins.

## Step-by-Step Method

1. Quote each conflicting source verbatim with citation.
2. Apply the hierarchy from `governance/01`. The highest-ranked
   source is the verdict — unless it is itself proven wrong by
   code/tests.
3. If the verdict requires changing the lower-ranked source,
   prepare the change as a doc-freshness reconciliation (use the
   `doc-freshness-reconcile` skill).
4. If the verdict requires owner judgment (e.g. the contradiction
   is between AGENTS.md and PUBLISH.md), escalate.
5. Capture the resolution in a Contradiction Memo and link it
   from the next retrospective.

## Deliverable Format

A short Contradiction Memo (200–400 words) listing source A,
source B, the hierarchy verdict, and the reconciliation action.

## Quality Checklist

- [ ] Both sources quoted verbatim
- [ ] Hierarchy verdict applied correctly
- [ ] No "I think one is right" — verdict is sourced
- [ ] Reconciliation action committed or queued

## Escalation Triggers

- Contradictions within AGENTS.md or between AGENTS.md and
  PUBLISH.md → owner review.
- Contradictions that touch live legal or commercial claims →
  halt publication; route to Legal Consistency Auditor.

## Related Agents

- Contradiction Agent (Research & Evidence Bureau, division 02)
- Doc Freshness Auditor (Knowledge Operations, division 09)

## Related Artifacts

- `docs/governance/01-source-of-truth-hierarchy.md`
- `docs/governance/15-doc-freshness-and-contradiction-control.md`
