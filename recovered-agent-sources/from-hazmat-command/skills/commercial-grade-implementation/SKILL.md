---
name: commercial-grade-implementation
description: The default implementation workflow for any code-bearing task in this repo. Enforces architecture awareness, scoped change design, negative-path tests, documentation alignment, and the final evidence package. Builder uses this skill, principal-code-reviewer audits against it.
---

# commercial-grade-implementation

## When to use

Default for any code-bearing task in `src/`, `api/`, `base44/`,
`scripts/`, `tests/`, `supabase/`, `.github/workflows/`. If the
task is RC3, layer `security-or-authz-change` or
`compliance-rule-change` on top.

## Method

1. **Understand.** Read AGENTS.md, the matching rule under
   `.claude/rules/`, and the relevant existing files. Run
   `git grep` and read `SKIPPED.md` before assuming.
2. **Plan scoped.** Smallest change. No refactor unless required.
   No new abstraction with one caller.
3. **Architecture check.** Is there an existing pattern in
   `src/lib/**`, `api/_lib/**`, `base44/functions/**` to extend
   rather than fork?
4. **Tests planned first.** Name the assertions you will add.
   Negative path where failure modes matter.
5. **Implement.** Follow
   `.claude/rules/engineering-production-quality.md`. RC3 layers
   apply (security, compliance).
6. **Run the gate.**
   - `npm run lint`
   - `npm run typecheck`
   - `npm test` — count stable or explained
   - `npm run build`
   - `npm run governance:check`
   - `npm run agentos:check`
   - `npm run test:e2e` if the change touches an e2e-covered path
7. **Document.** Update only what materially changed: the matching
   doc under `docs/runbooks/`, `docs/security/`,
   `docs/iso27001/`, or `docs/compliance/`. Do not touch unrelated
   docs.
8. **Evidence package.** Use `pr-readiness-and-owner-handoff` to
   assemble the final PR body and owner review checklist.

## Output

- Scoped diff.
- Test additions with negative-path coverage.
- Verification command log.
- Doc updates where behavior moved.
- Draft PR body via `pr-readiness-and-owner-handoff`.

## Anti-patterns

- "Done" without showing the verification commands.
- "All tests pass" with no count.
- Bundling a behavior change with a rename.
- A new helper for one caller.
- A change that quietly alters response shape, log line, or
  schema.
