---
paths:
  - "tests/**"
  - "playwright.config.js"
  - "vitest.config.js"
  - "vitest.setup.js"
  - "scripts/check-*.mjs"
  - "**/*.test.{js,jsx,ts,tsx,mjs}"
  - "**/*.spec.{js,ts}"
---

# Testing and verification

**Path scope (auto-activates):** test files and test infrastructure
per the `paths` frontmatter above. Original list: `tests/**`,
`playwright.config.js`, `vitest.config.js`,
`vitest.setup.js`, `scripts/check-*.mjs`,
`scripts/audit-merkle-anchor.mjs` test surface,
any product file whose change touches a tested surface.

**Authority:** `AGENTS.md`,
`docs/governance/06-maker-checker-independent-review.md`,
`docs/skills/negative-test-suite-generation.md`,
`.claude/rules/00-commercial-delivery-standard.md`.

Tests in this repo are not decoration. They are the verifier. The
727-baseline at v1.0.0-enterprise-ready is the floor — `npm test`
must remain green on every PR.

## Discipline on test files

1. **Tests catch regressions, not implementation.** A test that
   merely mirrors the implementation will pass even when the
   implementation is wrong. Prefer tests that pin observable
   behavior (HTTP shape, generated PDF text, rule-engine verdict)
   against a source the test does not itself import from the file
   under test.
2. **Negative tests where failure modes matter.** Authz tests must
   cover the rejected case. Rule-engine tests must cover the
   non-compliant case. OCR-provenance tests must cover the
   low-confidence path. SCIM tests must cover the malformed-payload
   path.
3. **Do not weaken assertions to make CI green.** If a test starts
   failing because the shipped behavior changed, the right move is
   one of:
   - fix the code so the test passes, or
   - update the test AND the doc, AND explain in the PR why the
     shipped behavior is authoritative now (with an architectural
     reason or a regulation citation).
   Lowering an assertion silently is rejected on sight.
4. **Test count is informational.** A reduction in `npm test` count
   without a documented reason is a finding. A net-new flaky test
   is a finding.
5. **Changes to test infrastructure are RC2.** Anything that alters
   what gets executed, what is skipped, or how a runner reports
   failures (`vitest.setup.js`, `playwright.config.js`, env-only
   skips) requires explicit PR justification.
6. **Tests for tests.** Validators (`scripts/check-*.mjs`) should be
   deterministic and their failure messages should name the file
   and the line that violated the rule. Vague "validation failed"
   is rejected.

## Anti-patterns rejected on sight

- `expect(...).toBeDefined()` where the original expectation was
  shape-specific.
- `expect(...).toBeTruthy()` replacing a structural assertion.
- A new `it.skip(...)` without a SKIPPED.md entry referencing it.
- A flaky test "fixed" with a retry instead of a determinism fix.
- A change that removes negative tests in the same PR that
  introduces new behavior.
- A new test that only re-derives the implementation's outputs
  from the same module.
