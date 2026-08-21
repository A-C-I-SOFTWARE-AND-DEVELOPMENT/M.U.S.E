# 00 — Commercial Delivery Standard (unconditional)

<!--
  No `paths:` frontmatter — this rule loads unconditionally at session
  start, same priority as `.claude/CLAUDE.md`. Source of truth:
  https://code.claude.com/docs/en/memory#organize-rules-with-claude-rules
-->

**Scope:** every Claude Code run in this repo, every file, every turn.
**Authority:** `AGENTS.md`, `docs/governance/00-autonomous-enterprise-organization-overview.md`.

This is what "above commercial standard" means here. It
is not a vibe. Failing any of these is grounds for the independent
reviewer (`.claude/agents/principal-code-reviewer.md`) to reject the
change.

## What "above commercial standard" means here

1. **Architectural correctness.** Read the existing pattern before
   writing. If a similar capability exists in `src/lib/**`,
   `api/_lib/**`, or `base44/functions/**`, extend it rather than
   fork it. Tenant scoping, RBAC, audit-chain provenance, OCR
   provenance, and 49 CFR / TDG rule-engine outputs are load-bearing
   — preserve them.
2. **Deterministic validation.** Every claim of "it works" is backed
   by an actual run of `npm run lint`, `npm run typecheck`,
   `npm test`, `npm run build`, and `npm run governance:check` (plus
   `npm run agentos:check` after the native activation lands). If the
   change touches an e2e-covered path, run `npm run test:e2e`. If a
   command fails, fix it — do not weaken the test.
3. **Negative-path testing.** When you change a failure mode, write
   the test that proves the failure still fails (auth denial, RLS
   block, 49 CFR rejection, OCR-low-confidence path). Asserting only
   the happy path is insufficient.
4. **Evidence-backed claims.** Commercial, compliance, security, or
   regulatory wording requires a citation a third party can verify
   (49 CFR section, TDG paragraph, NIST control, OWASP rule, vendor
   doc URL with date). No invented numbers, no rounded-up
   percentages, no "industry-leading" without a benchmark.
5. **No silent regressions.** If a change alters observable behavior
   (output shape, response code, schema, log line, exported file),
   the PR body says so. If it changes a baseline test count, the PR
   explains why the count moved.
6. **Minimal diff discipline.** Don't refactor things you weren't
   asked to refactor. Don't rename things. Don't add abstractions
   for hypothetical reuse. Don't introduce a helper for one caller.
7. **Rollback awareness.** State, in the PR, how this change is
   undone if it misbehaves in pilot. If the answer is "you can't",
   that is itself a finding — escalate to the owner.

## Anti-patterns that will be rejected

- "Marked complete" without verification commands shown.
- "All tests pass" with no count or with a count that silently
  shrank.
- New rule-engine logic with no negative test for the rejected path.
- A "fix" that mutates the test to match a behavior change instead
  of fixing the behavior.
- A migration / schema change that has no rollback plan.
- A commit that bundles a behavior change with an unrelated rename
  or cleanup.
- Generated prose that uses words like "robust", "best-in-class",
  "enterprise-grade", "AI-powered" without a citation.
- A PR that closes more than it actually changes (scope creep).
- A PR that claims a security or compliance improvement without
  evidence under `docs/security/`, `docs/iso27001/`, `docs/compliance/`,
  or `docs/research/`.

## When this rule is silent

When the standard above doesn't cover your case, fall back to:

1. `AGENTS.md` constitutional rules,
2. `docs/governance/01-source-of-truth-hierarchy.md`,
3. The path-specific rule under `.claude/rules/` for the directory
   you are working in.
