---
name: post-merge-verification
description: Use immediately after an owner-approved merge to main. Confirms the merge commit, the CI state on main, the documented baseline, the relevant docs, and any release notes / tags needed. Recommends the next work without overstepping.
disable-model-invocation: true
---

# post-merge-verification

## When to use

The owner has merged a PR to `main`. Run this skill to confirm
ground truth and produce the post-merge state report.

## Method

1. **Confirm the merge SHA.** Read the latest commit on `main`.
   Confirm it matches the PR's expected squash / merge title.
2. **Reset local main if needed.** If the PR was squash-merged,
   local `main` and remote `main` may diverge; `git reset --hard
   origin/main` is the right move (not destructive — local main
   tracks remote).
3. **CI on main.** Confirm the post-merge CI run on `main` is
   green (lint/typecheck/test/build, dependency audit, gitleaks,
   semgrep, e2e, governance index, agentos check).
4. **Baseline drift.** Confirm `npm test` count matches the
   documented baseline or that the change in baseline is
   accompanied by a doc update.
5. **Doc freshness.** Confirm the matching doc under
   `docs/governance/`, `docs/security/`, `docs/iso27001/`,
   `docs/compliance/`, `docs/runbooks/`, or `HANDOFF.md` was
   updated in the same PR (or that no update was needed).
6. **Release tag / notes.** Only if the PR was tagged for a
   release: confirm the tag, confirm release notes under
   `docs/releases/`. No agent creates production tags.
7. **Recommend next work.** Look at `SKIPPED.md` (active stubs),
   `docs/inventory/blockers-final.md` (launch blockers), and the
   most recent retrospective. Propose the next task in order of
   pilot value. Do not start it without owner approval.

## Output

A short post-merge report:

- merge SHA,
- CI state on main,
- baseline drift status,
- doc-freshness status,
- recommended next task with rationale.

## Anti-patterns

- "Merged, all green" without checking the post-merge CI run.
- Starting the next task before owner approval.
- Creating a production tag autonomously.
- Letting baseline drift pass without explanation.
