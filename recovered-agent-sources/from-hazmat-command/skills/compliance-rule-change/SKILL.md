---
name: compliance-rule-change
description: Use when changing 49 CFR / TDG rule-engine logic, ERG data, placard thresholds, shipping-paper builders, training dossier (172 Subpart H), bilingual rendering, or any regulator-facing artifact. Requires regulator-text citation, regression tests, and Research Bureau verification. Aligned with docs/workflows/compliance-rule-change.md.
---

# compliance-rule-change

## When to use

Activated automatically by `chief-orchestrator` whenever the changed
paths intersect with the regulator-facing scope in
`.claude/rules/hazmat-compliance-and-regulated-output.md`.

## Method

1. **Research dossier first.** Run `research-dossier-build`. Cite
   the exact 49 CFR section, TDG paragraph, UN/DOT number, ERG
   edition + page, special provision. Quote the regulation; do
   not paraphrase.
2. **Identify canonical cases.** For the rule being changed:
   - the canonical compliant case,
   - the canonical non-compliant case,
   - at least one near-boundary case (placard threshold, exception
     limit, packaging group boundary).
3. **Tests first.** Add tests for the three cases above before
   touching the rule engine. Confirm the existing rule engine
   fails the test the change is supposed to fix.
4. **Implement.** Follow
   `.claude/rules/hazmat-compliance-and-regulated-output.md`.
   Preserve citations on every line of generated output. Preserve
   bilingual parity.
5. **Regression sweep.** `npm test` count stable. If the count
   moved, explain.
6. **Provenance preserved.** Each artifact still carries:
   regulation citation, edition / page, generator version,
   timestamp. The audit ledger reflects the change.
7. **Verify.** Same command set as `security-or-authz-change`.
8. **Independent review.** Assurance Office + Research Bureau
   (third verifier on regulator-facing).

## Output

- Dossier under `docs/research/` with quoted regulation text.
- Test additions for the three canonical cases.
- Code change.
- Verifier note from Research Bureau.
- Draft PR via `pr-readiness-and-owner-handoff`.

## Anti-patterns

- Editing a placard threshold without citing § 172.504.
- Changing ERG data without citing edition and page.
- Removing a citation because the line got long.
- Translating only one side of a bilingual artifact.
- "Improving clarity" of regulator text with no citation.
