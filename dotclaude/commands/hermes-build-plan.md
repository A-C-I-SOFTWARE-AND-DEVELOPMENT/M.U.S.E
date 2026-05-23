---
description: Create a staged implementation plan for the current task using all relevant agents
---

# /hermes-build-plan

## Purpose

Produce a staged implementation plan (this PR / next PR / owner actions)
for the task at hand, using the right specialists, ready to execute.

## When to use

- A non-trivial feature, fix, or refactor is on the table and you want a
  plan before code is written.
- A previous attempt drifted; you want a scoped plan with explicit
  acceptance criteria.

## Agents activated

1. `repo-context-librarian` (first)
2. `aos-systems-architect` (if the change touches agent/AOS architecture)
3. `fullstack-implementation-engineer` (always — owns the diff plan)
4. `security-privacy-risk-officer` (if the change touches auth / secrets /
   user data / external APIs)
5. `ux-polish-product-designer` (if the change touches user-facing UI)
6. `nourish-product-specialist` (if Nourish-specific)
7. `mobile-release-engineer` (if the change affects mobile build/release)
8. `prompt-systems-engineer` (if the change includes prompts or agents)
9. `hermes-final-synthesizer` (last)

## Required workflow

1. Mission brief (one paragraph).
2. Repo map.
3. Specialists contribute scoped sub-plans for their domain.
4. Implementation engineer assembles them into a staged plan with:
   - Files to read.
   - Files to change (with one-line reason each).
   - Acceptance criteria (executable).
   - Validation commands.
   - Rollback plan.
5. Synthesizer produces the final plan with owner-blocker separation.

## Required output format

```
## Goal (one sentence)
## Out of scope
## Stage 1 — this PR
- Files to read
- Files to change (path → reason)
- Acceptance criteria (executable)
- Validation commands
- Rollback
## Stage 2 — next PR (if needed)
## Stage 3 — owner-only actions
## Risks and how the plan handles them
## Single next action
```

## Validation requirements

- Every acceptance criterion is executable (a command, a test, a visible
  behavior change), not a wish.
- No file is in the change list without a one-line reason.
- Rollback plan is concrete (revert commit, previous tag, migration
  down-revision), not "git revert".
