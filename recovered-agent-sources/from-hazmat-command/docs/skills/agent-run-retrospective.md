# Skill — agent-run-retrospective

## Purpose

After every RC2/RC3 run, produce a retrospective that feeds
the agent performance scoreboard schema and the prompt-evolution
loop.

## Triggers

- A RC2/RC3 PR is opened, merged, or closed.
- A pilot demo concludes.
- A release-freeze trigger fires (separate Postmortem skill
  follows up).

## Required Inputs

- The PR or run description.
- The workflow router intake (if filed).
- The artifacts produced.
- The maker-checker evidence captured.

## Research Required

- `governance/13-agent-evaluation-and-scoreboard.md`.
- `agent-performance-scoreboard-schema.md` (the per-run entry
  fields).

## Step-by-Step Method

1. Copy `docs/templates/agent-run-retrospective-template.md` to
   `docs/research/retros/<YYYY-MM-DD>-<slug>.md`.
2. Fill the scoring fields (RC class, topology, divisions, agents,
   research / maker-checker / verifier presence, tests added,
   doc-freshness corrections).
3. Write a short "What worked" / "What didn't" / "Recommended
   improvements" set.
4. Link from the PR.
5. After 7 days, return and fill defect-escape / rework
   fields.
6. If the run revealed a recurring pattern, route the
   "Recommended improvements" to the Prompt Evolution Agent.

## Deliverable Format

A populated retrospective markdown file.

## Quality Checklist

- [ ] Scoring fields filled
- [ ] Honest "What didn't" (not just praise)
- [ ] Recommended improvements actionable
- [ ] Linked from PR

## Escalation Triggers

- A retrospective that surfaces a governance defect (e.g. a
  workflow consistently misses a maker-checker step) → route
  to Executive Command for amendment.

## Related Agents

- Postmortem / Lessons Agent (Knowledge Operations)
- Prompt Evolution Agent (Knowledge Operations)
- Agent Performance Evaluator (Knowledge Operations)

## Related Artifacts

- `docs/templates/agent-run-retrospective-template.md`
- `docs/governance/agent-performance-scoreboard-schema.md`
