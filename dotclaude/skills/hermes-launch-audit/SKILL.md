---
name: hermes-launch-audit
description: Ruthless launch-readiness audit for SaaS, mobile apps, web apps, investor demos, and production deployments. Use before any go-live, store submission, marketing push, or external demo. Produces a green/red gate report with evidence.
---

# Hermes Launch Audit

## Use when

- Owner asks "can I ship?", "is this ready?", "launch check".
- Before any store submission, marketing push, or investor/partner demo.
- After a major refactor before re-enabling traffic.

## Gates (each is GREEN, RED, or N-A with reason)

1. **Build & validation** — install, typecheck, lint, tests, production
   build all green on the release branch.
2. **Critical journeys smoke** — at least one end-to-end happy path for
   each primary user role.
3. **Security** — secrets not committed, authz enforced server-side,
   destructive ops gated, dependency CVEs reviewed.
4. **Privacy** — privacy policy live, data deletion path tested, telemetry
   consent state respected.
5. **Performance** — primary route p95 within target on staging; no
   regression vs previous release.
6. **Mobile / store** (if applicable) — version bumped, icons,
   screenshots, signing, permissions justified, privacy declarations
   match binary.
7. **Deployment** — preview/staging serves 200s on smoke routes; rollback
   path documented; feature flags default-safe.
8. **Monitoring** — error tracking enabled, alerts wired, on-call defined.
9. **Copy & polish** — no Lorem ipsum, no TODOs in user-facing surfaces,
   accessibility baseline met.
10. **Owner-only items** — billing, legal, store accounts, DNS, support
    address all addressed.

## Procedure

1. Invoke `repo-context-librarian` first.
2. Invoke `qa-launch-validator` for gates 1–2, 7.
3. Invoke `security-privacy-risk-officer` for gates 3–4.
4. Invoke `mobile-release-engineer` for gate 6 (if mobile).
5. Invoke `ux-polish-product-designer` for gate 9.
6. Synthesize with `hermes-final-synthesizer`.
7. Produce the gate report and single next action.

## Output

```
## Build / commit
## Gate results (table: gate | result | evidence)
## Code-side blockers (RED gates)
## Owner-only blockers
## Single next action
## Verdict: READY | NEEDS WORK | NOT READY
```

## Hard rules

- GREEN requires evidence (command + exit code, screenshot, log excerpt).
- A skipped gate is N-A with reason, never silent.
- "READY" requires zero RED gates and no open CRITICAL/HIGH security
  findings.
