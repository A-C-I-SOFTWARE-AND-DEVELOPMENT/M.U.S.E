# 00 — Workflow Overview

**Status:** Installed 2026-05-17

Workflow playbooks describe end-to-end orchestrations. Each plays
selects divisions, sequences their activation, and defines the
expected artifacts. The workflow router
(`docs/governance/04-workflow-router.md`) picks the topology;
playbooks are the topology made concrete for a recurring
situation.

## Playbooks

| Playbook | When to use |
|---|---|
| `new-product-or-major-feature.md` | A feature spanning multiple divisions from research through launch |
| `complex-bug-fix.md` | A defect that touches an RC3 surface or requires cross-division reasoning |
| `security-or-authz-change.md` | Any change to `api/_lib/authz.mjs`, RLS, MFA, SCIM, audit ledger |
| `compliance-rule-change.md` | Any change to 49 CFR / TDG rule engines or to ISO 27001 evidence |
| `pricing-and-packaging.md` | Any plan-band or entitlement change |
| `marketing-gtm.md` | Any positioning / campaign / public-facing copy update |
| `legal-document-generation.md` | Any contract, policy, or counsel-required draft |
| `pilot-demo-readiness.md` | Pre-pilot orchestration including the Pilot Readiness Judge |
| `enterprise-procurement-readiness.md` | RFP / security questionnaire / DPA negotiation prep |

## Common shape

Every playbook documents:

- **Trigger** — what initiates the workflow
- **Required Divisions** — which agent divisions must be active
- **Required Research Artifact** — research dossier, decision
  memo, or none
- **Agent Topology** — which router topology applies
- **Sequence** — the ordered steps
- **Parallelization Opportunities** — where steps can run
  concurrently
- **Maker-Checker Review Points** — explicit per `governance/06`
- **Final Outputs** — durable artifacts
- **Acceptance Criteria** — what "done" looks like

## Adding a playbook

If a recurring situation lacks a playbook, the Chief of Staff
(Executive Command) drafts one using the same shape and lands it
under `docs/workflows/`. Add a line to this overview and to
`docs/AUTONOMOUS_ORGANIZATION_INDEX.md`.
