---
name: execution-blueprint-compile
description: Use after owner approves the revised synthesized master plan. Converts the approved plan into the implementation contract — epics, waves, PR sequence, subagent assignments, Codex packets, validation commands, acceptance criteria, rollback plan, owner-only action list. Produces 06-execution-blueprint.md. No new strategic decisions; only execution shape.
---

# execution-blueprint-compile

## When to use

Council Mode step 10. The synthesized master plan has been revised
once after red-team. The owner has approved in writing (PR comment,
commit message, or appended approval block in
`04-synthesized-plan.md`).

If owner approval is not recorded, this skill stops and surfaces
the missing approval.

## Inputs

- `04-synthesized-plan.md` (post-revision, with owner approval).
- `05-red-team-review.md`.
- `02-risk-classification.md`.
- The matching execution workflow in `docs/workflows/` (e.g.
  `security-or-authz-change.md`, `compliance-rule-change.md`,
  `codex-implementation-fabric.md`).

## Method

1. Copy `docs/templates/execution-blueprint-template.md` to
   `06-execution-blueprint.md` in the run folder.
2. Paste the owner approval reference (URL, SHA, or block) at the
   top. If missing, stop.
3. Build the Epics table — each epic gets a wave, owner subagent,
   reviewer, and (RC3) verifier.
4. Build the PR sequence — each PR carries title, branch, risk
   class, matching workflow playbook, builder, reviewer, verifier,
   allow-listed files, forbidden files, tests added or changed,
   validators that must remain green, acceptance check, rollback
   procedure.
5. If any wave dispatches Codex, instantiate
   `docs/templates/codex-task-package-template.md` for each packet
   and record the packet ID in the Codex Packets table. The packet
   allow-list excludes constitutional surfaces per `governance/17`.
6. List validation commands that must remain green.
7. List sprint-wide acceptance criteria.
8. Fill the Rollback Plan table — each wave names a revert SHA or
   PR and a doc procedure.
9. Fill the Owner-Only Action List — every L4 action this sprint
   surfaces, with runbook and the wave it blocks.
10. List doc updates required.
11. Confirm no new strategic decisions snuck in (this is a
    compile pass, not a synthesis pass).

## Output

`06-execution-blueprint.md` — read by chief-orchestrator and each
execution-workflow caller to schedule the implementation.

## Anti-patterns

- Blueprint without an owner approval reference.
- PR sequence whose builder equals reviewer.
- Codex packet allow-list that includes a constitutional surface.
- A wave with no stated rollback.
- New strategic decisions made in the blueprint that were not in
  the synthesized master plan.
- Owner-only actions embedded in PRs instead of surfaced for the
  owner.
- A blueprint that skips a validator from the standard set without
  justification.
