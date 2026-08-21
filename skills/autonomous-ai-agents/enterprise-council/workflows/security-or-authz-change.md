# Workflow — Security or Authz Change

## Trigger

Any change to `api/_lib/authz.mjs`, `src/lib/rbac.js`, the SCIM
helpers, RLS migrations, MFA enrollment, the audit ledger, CSP
headers, or any code path on an RC3 security surface per
`governance/03`.

## Required Divisions

Executive Command, Research Bureau (Security Standards),
Engineering Factory (Security/Authz Engineer + Backend Engineer),
Assurance Office (Principal Security Architect + Threat Modeling
+ Negative/Fuzz Test + Compliance Evidence + Independent QA).

## Required Research Artifact

Research Dossier required. Threat Model entry mandatory.

## Agent Topology

Prompt chain with parallel review panel at verify.

## Sequence

1. **Intake** — Chief Orchestrator + Risk Controller jointly
   confirm the change is in scope (no production-DNS / Vercel
   production / Base44 Publish overlap — those are L4).
2. **Research** — Security Standards Research Agent cites NIST
   800-53 family + OWASP ASVS chapter + ISO 27001:2022 Annex A
   controls.
3. **Threat model** — Threat Modeling Agent adds a STRIDE entry
   per `threat-model-build`.
4. **Implement** — Security/Authz Engineer writes the change;
   pair-programs (logically) with Principal Security Architect.
5. **Negative tests** — Negative/Fuzz Test Agent extends the
   1,000-iteration cross-tenant fuzz pattern as appropriate
   (`negative-test-suite-generation`).
6. **Review** — parallel panel:
   - Independent QA confirms tests pass + adjacent suites
   - Principal Security Architect approves the design
   - Compliance Evidence Agent updates SoA / risk register
   - Threat Modeling Agent re-confirms STRIDE coverage
7. **Risk Controller** — final review before G0 sign-off.
8. **Owner publish** — G3.
9. **G4** — Sentry-monitored stabilization 24h (when DSN set).

## Parallelization Opportunities

- Research and Threat model can run before Implement.
- All four review-panel roles run in parallel post-Implement.

## Maker-Checker Review Points

- Builder: Security/Authz Engineer.
- Reviewer: Principal Security Architect.
- Verifier: Threat Modeling Agent + Compliance Evidence Agent.

## Final Outputs

Research Dossier · Threat Model entry · Code + tests · Updated
SoA + risk register if applicable · Retrospective.

## Acceptance Criteria

- Tests green including the new negative cases.
- 1,000-iteration cross-tenant fuzz green.
- No new freeze trigger.
- STRIDE coverage on the new surface.
- Compliance Evidence updated.
