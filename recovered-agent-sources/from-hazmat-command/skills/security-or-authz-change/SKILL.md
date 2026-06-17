---
name: security-or-authz-change
description: Use when changing authz, RBAC, RLS, audit ledger, OCR provenance, secret handling, SCIM, SSO, CSP, supply-chain dependencies, or any RC3 security surface listed in docs/governance/03-change-risk-matrix.md. Enforces maker-checker discipline, negative tests, and source citations. Aligned with docs/workflows/security-or-authz-change.md.
---

# security-or-authz-change

## When to use

Activated automatically by `chief-orchestrator` whenever the changed
paths intersect with the RC3 surfaces in
`docs/governance/03-change-risk-matrix.md`. Mandatory
maker-checker discipline.

## Method

1. **Research dossier first.** Run `research-dossier-build` and
   cite the relevant standard (NIST SP, OWASP rule, CWE, ISO 27001
   control). Save under `docs/research/`.
2. **Threat model delta.** Either update the existing threat model
   for this surface (under `docs/security/` or `docs/iso27001/`)
   or note explicitly why no update is needed.
3. **Negative tests planned upfront.** For each role
   (`carrier_admin`, `safety_manager`, `dispatcher`, `driver`,
   `solo_driver`): which rejection path is tested by this PR?
4. **Implement.** Follow
   `.claude/rules/security-authz-and-trust-boundaries.md`.
5. **Audit ledger / OCR provenance integrity preserved.**
   Append-only, monotonic sequence, full provenance fields on
   regulator-facing artifacts.
6. **Verify.**
   - `npm run lint`, `npm run typecheck`
   - `npm test` — count stable or explained
   - `npm run build`
   - `npm run test:e2e` (covered path)
   - `npm run governance:check`
   - `npm run agentos:check`
   - CI: dependency audit `--audit-level=high`, gitleaks working
     tree, semgrep (review findings), governance index.
7. **Independent review.** Hand off to
   `assurance-security-compliance-office`. Builder cannot self-review.
8. **Third verifier.** `research-evidence-bureau` confirms citations.
9. **PR.** Draft only. Use `pr-readiness-and-owner-handoff` to
   assemble the final body.

## Output

- A research dossier under `docs/research/`.
- A threat-model update (or a justification for none).
- Code change with negative-test coverage.
- Verification command log.
- Independent reviewer note and verifier note.
- Draft PR.

## Anti-patterns

- Loosening an existing control "for now".
- Adding a "re-enable later" deferral comment next to an authz check.
- A new SCIM / SSO path with no malformed-payload test.
- A migration to an RC3 surface with no rollback plan.
