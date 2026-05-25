---
description: Generate a Codex / Claude coordinated workflow for building, reviewing, testing, and merging a change
---

# /codex-claude-sync

## Purpose

Produce a coordinated workflow that uses Claude as planner, Codex (or a
second Claude session) as implementer, and a separate session as verifier,
with explicit handoff prompts and a merge gate.

## When to use

- A change is large enough that separating planner / implementer /
  verifier roles is worth the overhead.
- A previous solo run drifted from plan or rubber-stamped a broken
  change.
- You want a repeatable two-coder workflow.

## Agents activated

1. `repo-context-librarian` (first)
2. `codex-claude-workflow-coordinator` (owns the prompts)
3. `prompt-systems-engineer` (reviews the three prompts for quality)
4. `security-privacy-risk-officer` (if change is security-sensitive)
5. `hermes-final-synthesizer` (only if competing workflow designs exist)

Skill invoked: `codex-claude-synergy-workflow`.

## Required workflow

1. Mission brief: the change, the branch, the validation commands, the
   acceptance criteria, the rollback plan.
2. Coordinator drafts:
   - Task Packet (for the planner to issue to the implementer)
   - Return Envelope schema (for the implementer)
   - Verifier prompt (for the third session)
3. Prompt engineer reviews each for vagueness, role stacking, missing
   output format.
4. Owner receives three copy/paste prompts and a merge checklist.

## Required output format

```
## Goal
## Roles assigned
- planner: <Claude session>
- implementer: <Codex or different Claude session>
- verifier: <third session, must be different>

## Planner prompt (copy/paste)
\`\`\`
<planner prompt>
\`\`\`

## Implementer prompt (copy/paste)
\`\`\`
<implementer prompt, with Task Packet schema and the actual packet>
\`\`\`

## Verifier prompt (copy/paste)
\`\`\`
<verifier prompt, with Return Envelope schema and validation re-run steps>
\`\`\`

## Owner checklist before merge
- [ ] Verifier APPROVED
- [ ] CI green on the branch
- [ ] Files changed ⊆ files allowed (confirmed by verifier)
- [ ] Rollback plan documented in PR body
```

## Validation requirements

- Planner and verifier MUST be different sessions — coordinator enforces
  this in the prompt.
- Implementer's `files_changed` MUST be a subset of `files_allowed`.
- Verifier MUST re-execute validation commands, not trust reported exit
  codes — verifier prompt enforces this.
- No "done" without evidence the next role can consume.
