---
name: complex-bug-fix
description: Use when a defect spans more than one file, more than one role, or appears to involve a regression in a tested surface. Walks the bug from reproduction through root cause, fix, negative test, regression test, and rollback plan. Aligned with docs/workflows/complex-bug-fix.md.
---

# complex-bug-fix

## When to use

A reported bug that:

- spans multiple files or modules,
- crosses a role boundary,
- regressed a previously tested surface,
- involves an RC3 surface (authz, audit, OCR, regulator-facing,
  Square, SCIM, RLS, claims, legal, release),
- or whose root cause is non-obvious.

For one-file localized bugs, the engineering-production-quality
rule is enough — you do not need this skill.

## Method

1. **Reproduce.** Write the exact reproduction steps. If you cannot
   reproduce, stop and request more information.
2. **Bisect.** `git log -- <file>` on the suspect path. Identify
   the commit that introduced the regression. Read the PR.
3. **Root cause.** Name the precise mechanism. Not "race
   condition" — name the two operations that race. Not "off by
   one" — name the index that is off.
4. **Negative test first.** Write the test that fails with current
   `main` and would pass with the fix. Commit it as the first
   change in the PR (RC0 if you wish to stage it; otherwise
   include with the fix).
5. **Fix.** Smallest change that turns the failing test green
   without altering unrelated behavior. Follow
   `.claude/rules/engineering-production-quality.md`. For RC3
   surfaces follow
   `.claude/rules/security-authz-and-trust-boundaries.md` and
   `.claude/rules/hazmat-compliance-and-regulated-output.md`.
6. **Regression coverage.** Verify the original repro now passes
   and the negative test continues to fail correctly on the
   buggy code path.
7. **Verify.** `npm run lint`, `npm run typecheck`, `npm test`,
   `npm run build`, `npm run governance:check`,
   `npm run agentos:check`. e2e when warranted.
8. **Rollback plan.** State the exact revert step. If reverting
   would re-open the bug, state that.
9. Hand off to `principal-code-reviewer` and (RC3) to
   `assurance-security-compliance-office`.

## Output

A scoped PR with:

- reproduction steps,
- root cause statement (the mechanism, not a guess),
- the failing test added,
- the fix,
- the verification commands,
- a rollback plan.

## Anti-patterns

- "Should be fixed" without a failing test that now passes.
- A fix that also refactors three other files.
- Fixing the symptom (an exception) without the mechanism (why the
  unreachable state became reachable).
- Stamping the test to match the buggy output.
