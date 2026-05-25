---
name: jarvis-code-operator
description: "Run autonomous coding workflows."
version: 1.0.0
author: Jeremiah Echerd + Hermes Agent
license: MIT
platforms: [linux, termux, macos, windows]
---

# JARVIS Code Operator

JARVIS Code Operator runs scoped coding workflows across Hermes, Claude Code, Codex, local verification, GitHub, and PR handoff. It keeps Builder Mode disciplined: inspect first, scope tightly, route implementation to the right worker, verify locally, and produce a reviewable handoff.

This skill is not a decision agent. It is the coding workflow controller for build packets, review packets, rollback planning, and clean commits.

## When to Use

Use this skill when:

- A request needs code changes.
- A repo audit becomes an implementation task.
- Jeremiah asks for Builder Mode, Claude Code, Codex, a PR plan, or a code review route.
- Work should be split into primary implementation and independent review.
- A change needs local verification, rollback notes, and PR handoff.

Do not use this skill when:

- The request is pure strategy with no implementation.
- The user is only capturing a mobile idea for later focused expansion.
- The task has no acceptance criteria or is too broad to verify.
- The action requires merge, push, publish, deploy, OAuth, credentials, or production access without owner authorization.
- Claude Code and Codex would edit the same branch at the same time.

## Prerequisites

Before coding or dispatching workers, capture:

- Mission.
- Repository root.
- Current branch or worktree.
- Git status and dirty files.
- Files or subsystems likely affected.
- Constraints and non-goals.
- Acceptance criteria.
- Verification commands.
- Rollback plan.
- Owner gates.
- Whether the route is Claude Code build, Codex review, Codex bounded fix, local verification, or PR handoff.

If the repo root is unknown, inspect first. If the working tree is dirty, separate current-stage files from unrelated pre-existing changes.

## How to Run

1. Inspect the repo root and branch through Hermes tools: use `search_files` (or `read_file` on a known path) to confirm the tree, and route the git status check through `terminal` rather than calling a bare shell.
2. Capture the status snapshot by invoking `terminal` with `git status --short --branch` as the command; the wrapper enforces the session's approval and sandboxing rules.
3. Scope the task to one mission with explicit non-goals.
4. Choose the worker route.
5. Prepare a Claude Code build packet or Codex review packet, and dispatch via `delegate_task` when the work fans out to a sub-agent.
6. Apply only approved local edits through `patch` / `write_file` (or hand the packet to the chosen worker).
7. Run local verification by invoking `terminal` for each check command.
8. Prepare rollback notes and PR handoff.
9. Commit only the intended files when authorized — drive `git add <paths>` and `git commit` through `terminal`.
10. Push only after the commit succeeds and pushing is authorized; invoke `git push` through `terminal` so approval gating applies.

## Quick Reference

Primary Hermes tool surface for this skill:

- `terminal` — run git, build, lint, and test commands inside Hermes' approval and sandbox layer (replaces ad-hoc shell invocations).
- `read_file` — inspect specific files before editing.
- `search_files` — locate code, configs, and tests across the repo (replaces `grep`/`find`/`ls`).
- `patch` / `write_file` — apply scoped edits.
- `delegate_task` — hand a Claude Code build packet or Codex review packet to a sub-agent.
- `skill_view` / `skills_list` — pull in narrower skills (e.g., a language-specific build skill) before dispatching.
- `memory` — record rollback notes, owner-gate decisions, and follow-ups that must survive the session.

Worker routes:

- Claude Code Builder: primary implementation.
- Codex Reviewer: independent review and critique.
- Codex Bounded Fix Worker: small authorized repair after review.
- Local Test Runner: local checks and command verification.
- GitHub PR Publisher: PR handoff after authorization.

Branch rules:

- GitHub is the source of truth.
- Do not let Claude Code and Codex edit the same branch simultaneously.
- Use separate branches or worktrees for parallel implementation.
- Do not merge, force-push, deploy, or publish without explicit owner authorization.

## Procedure

### Repo Inspection

Drive the inspection through Hermes tools so approval, sandboxing, and output capture all apply. Invoke `terminal` once per command:

- `terminal` → `git rev-parse --show-toplevel`
- `terminal` → `git branch --show-current`
- `terminal` → `git status --short --branch`

Use `search_files` when you need to locate files by name or content rather than shelling out to `find` or `grep`. Use `read_file` to inspect any file the status surfaces.

Confirm the requested repo and branch match the live environment before edits.

### Task Scoping

A valid build task has:

- One mission.
- Clear non-goals.
- Bounded files or subsystem.
- Acceptance criteria.
- Verification commands.
- Rollback plan.
- Expected output envelope.

If the task is vague, tighten it before implementation.

### Claude Code Build Packet

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
```

Required return envelope:

```text
Files changed:
Implementation summary:
Verification run:
Failures:
Risks:
Rollback notes:
Follow-up recommendations:
```

### Codex Review Packet

Use Codex for review, bounded fixes, refactors, or second-pass engineering.

```markdown
# Codex Review Packet

## Mission
## Repo Root
## Branch / Commit / Diff
## Review Scope
## What Changed
## Acceptance Criteria
## Risk Areas
## Specific Questions
## Commands to Run
## Allowed Actions
## Not Allowed
## Return Envelope Required
```

Allowed actions must be one of:

- review only
- bounded fix
- refactor only
- test repair only

Not allowed:

- broad redesign
- unrelated refactor
- same-branch concurrent edits with Claude Code
- merge, force-push, deploy, publish, or credential changes without authorization

### Local Verification

Run each check through the `terminal` tool — never as a raw subprocess — so output is captured and approval gates apply.

Minimum whitespace check:

- `terminal` → `git diff --check`

Then run project-appropriate checks, such as:

- `terminal` → `python -m py_compile <changed-python-files>`
- `terminal` → `pytest <targeted-tests>`
- `terminal` → `npm test`
- `terminal` → `npm run lint`

If tests are skipped, state why.

### PR Handoff

Include:

- Mission.
- Summary of changes.
- Files changed.
- Tests and checks run.
- Failures or skipped checks.
- Risk areas.
- Rollback plan.
- Owner gates used.
- Follow-up tasks.

### Rollback Plan

Prefer a simple rollback:

- Revert the commit.
- Restore only changed files.
- Remove generated docs or scripts.
- Disable a workflow rather than deleting history.

### Escape hatch: raw shell

Only fall back to a bare shell when the Hermes runtime is unavailable (cold-boot recovery, broken tool registry, off-host triage). When you do, run the same `git`, `pytest`, `npm`, and `git push` commands documented above directly — but log what you ran and re-enter the Hermes flow as soon as the runtime is back so approval, sandboxing, and history capture resume.

## Pitfalls

- Coding before repo inspection. Fix: confirm repo root, branch, and status first.
- Letting Claude Code and Codex edit the same branch. Fix: serialize or split worktrees.
- Treating Codex review as product approval. Fix: Jeremiah owns approval.
- Running broad refactors inside a small task. Fix: enforce non-goals.
- Committing unrelated dirty files. Fix: commit explicit path lists only.
- Calling work done without verification. Fix: include command output or skipped-check reason.

## Verification

Before final handoff, confirm:

- Repo root and branch were checked.
- Scope, non-goals, and acceptance criteria are explicit.
- Claude Code and Codex did not edit the same branch concurrently.
- Runtime code changed only if the stage allowed it.
- Only intended files were staged and committed.
- Local verification ran or was explicitly deferred with reason.
- PR handoff includes changed files, risks, rollback notes, and owner gates.
