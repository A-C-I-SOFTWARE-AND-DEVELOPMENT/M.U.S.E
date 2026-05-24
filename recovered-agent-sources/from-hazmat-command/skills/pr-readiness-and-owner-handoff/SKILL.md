---
name: pr-readiness-and-owner-handoff
description: Use at the end of every substantive run to assemble the final PR body and the owner review checklist. Produces "what changed, why, what was tested, what to inspect, what risk remains, exact next move" — the owner handoff actually needed. Always opens PRs as draft per AGENTS.md.
---

# pr-readiness-and-owner-handoff

## When to use

At the end of every substantive run, before opening the PR.

## Method

1. **Walk the diff.** Confirm the change matches the task and
   nothing else slipped in.
2. **Confirm verification commands ran.** Paste the actual
   command set executed. No verification = not ready.
3. **Risk class.** Tag RC0 / RC1 / RC2 / RC3 per
   `docs/governance/03-change-risk-matrix.md`. When in doubt,
   escalate one class up.
4. **Affected domains.** Check each domain box in
   `.github/PULL_REQUEST_TEMPLATE.md`.
5. **Independent reviewer + verifier.** Name them. For RC3
   surfaces this is required.
6. **What is now better.** One sentence on the concrete
   improvement for the user / operator / owner.
7. **What is NOT in this PR.** Explicitly. Scope creep is
   rejected by listing what was deliberately out of scope.
8. **Owner review checklist.** Name the 5–12 files the owner
   should inspect first. Name what to look for. Name what
   would count as a merge blocker.
9. **Rollback.** SHA-level. "git revert <SHA>" plus what side
   effects to undo (env vars, feature flags).
10. **PR open.** Draft only. Never ready-for-review. Use
    `mcp__github__create_pull_request` with `draft: true`.

## Output

A complete draft PR with:

- Summary (1–3 sentences),
- Risk class,
- Affected domains checked accurately,
- Tests run with truthful counts,
- Independent reviewer + verifier notes,
- "What this PR is NOT",
- Owner review checklist (exact files + what to look for),
- Rollback procedure,
- Links to relevant research dossier / ADR / threat model.

## Anti-patterns

- A PR body that uses words like "should", "may", "approximately"
  without specifics.
- Marking ready-for-review. Always draft.
- "Tests pass" without a count.
- An empty rollback plan.
- A checklist that says "review the code" without naming files.
