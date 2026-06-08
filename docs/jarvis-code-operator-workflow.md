# MUSE Code Operator Workflow

## Purpose

The MUSE Code Operator workflow coordinates autonomous coding work across Hermes, Claude Code, Codex, local verification, GitHub, and PR handoff. It exists to keep Builder Mode disciplined: scoped tasks, clean branch handling, independent review, tests, rollback notes, and no uncontrolled multi-agent edits.

## Role in the MUSE Stack

```text
MUSE
↓
MUSE Code Operator
↓
Claude Code Builder / Codex Reviewer / Codex Bounded Fix Worker
↓
Local Test Runner
↓
GitHub PR Publisher
```

MUSE owns intent and routing.

AOS owns planning and specialist review when judgment is needed.

Claude Code owns primary implementation.

Codex owns review, bounded fixes, refactors, or second-pass engineering.

GitHub owns source of truth.

## When to Use

Use this workflow when:

- a request needs code changes
- a repo audit leads to implementation
- a task needs Claude Code or Codex coordination
- a change needs tests and PR-ready summary
- a build should be split into implementation and review lanes
- Jeremiah asks for Builder Mode

Do not use this workflow for:

- simple conversation
- pure strategy with no implementation
- mobile voice capture before focused-mode expansion
- high-risk owner-gated actions without authorization

## Builder Mode Intake

Before building, capture:

- mission
- repo root
- current branch
- git status
- risk class
- files likely affected
- non-goals
- acceptance criteria
- verification commands
- rollback plan
- owner gates

If repo root is unknown, inspect before planning file edits.

If the working tree is dirty, identify whether changes are owned by Jeremiah, prior stages, or the current task.

## Branch and Worktree Rules

1. GitHub is the source of truth.
2. Do not edit the same branch with Claude Code and Codex at the same time.
3. Claude Code is the primary builder.
4. Codex is reviewer, bounded fix worker, refactorer, or second-pass engineer.
5. If parallel work is needed, use separate branches or worktrees.
6. Do not merge, push, publish, or deploy without explicit owner authorization.
7. Every build needs tests or an explicit reason tests were not run.

## Task Scoping

A good coding task has:

- one mission
- clear non-goals
- bounded files or subsystems
- acceptance criteria
- verification commands
- rollback plan
- expected output format

A weak coding task has:

- vague goal
- broad refactor request
- no tests
- no rollback path
- unclear owner gate
- multiple unrelated outcomes

If the task is weak, MUSE should say so and tighten it before dispatch.

## Claude Code Build Packet

Use Claude Code as the primary builder when implementation is required.

```markdown
# Claude Code Build Packet

## Mission

## Repo Root

## Branch / Worktree

## Context

## User Intent

## Files Likely Affected

## Constraints

## Non-Goals

## Acceptance Criteria

## Implementation Plan

## Commands to Run

## Verification Required

## Owner Gates

## Do Not Touch

## Return Envelope Required

Return:

- files changed
- summary of implementation
- tests run
- failures
- risks
- rollback notes
- follow-up recommendations
```

Claude Code rules:

- Keep the task bounded.
- Do not ask Claude Code to decide product strategy alone.
- Require a return envelope.
- Require verification evidence.
- Do not run Claude Code and Codex as concurrent editors on the same branch.

## Codex Review Packet

Use Codex for review, bounded fixes, refactoring, or second-pass engineering.

```markdown
# Codex Review Packet

## Mission

## Repo Root

## Branch / Commit / Diff

## Review Scope

## What Claude Changed

## Acceptance Criteria

## Risk Areas

## Specific Questions

## Commands to Run

## Allowed Actions

Choose one:

- review only
- bounded fix
- refactor only
- test repair only

## Not Allowed

- broad redesign
- unrelated refactor
- same-branch concurrent edits with Claude Code
- production deploy
- merge/push unless explicitly authorized

## Return Envelope Required

Return:

- verdict
- blocking issues
- non-blocking issues
- tests run
- suggested patch or applied patch
- residual risk
- PR summary notes
```

Codex rules:

- Do not widen scope.
- Verify claims against files and tests.
- Prefer review-only unless a bounded fix is authorized.
- If applying a fix, state exactly what changed and why.

## Local Verification

Minimum verification for code-bearing work:

```bash
git diff --check
```

Then run project-appropriate checks, such as:

```bash
python -m py_compile <changed-python-files>
python scripts/run_tests.sh
pytest <targeted-tests>
npm test
npm run lint
```

If tests are not run, state why. Acceptable reasons include:

- docs-only change
- no relevant test harness exists
- dependency unavailable in current environment
- owner requested plan-only work
- command would be destructive or require credentials

## PR Handoff

A PR-ready handoff should include:

- mission
- summary of changes
- files changed
- tests run
- test failures
- risk areas
- rollback plan
- screenshots/logs if relevant
- owner gates used
- follow-up tasks

## Rollback Plan

Before implementation, identify how to roll back:

- revert specific files
- revert commit
- remove generated docs/scripts
- restore old config
- disable new workflow

For risky code changes, prefer a branch or worktree so rollback is cheap.

## Pitfalls

1. Building before scoping.
2. Letting Claude Code and Codex edit the same branch simultaneously.
3. Treating Codex review as product approval.
4. Running broad refactors inside a small bug fix.
5. Calling work done without verification.
6. Creating a PR summary without tests or a reason tests were skipped.
7. Forgetting rollback notes.

## Done Definition

Builder Mode work is done only when:

- implementation scope is complete
- diff is reviewed
- verification ran or was explicitly deferred
- Codex reviewed or review was explicitly deferred
- rollback is documented
- PR handoff is ready
- owner gates are respected
