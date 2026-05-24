# 00 — Skill Library Overview

**Status:** Installed 2026-05-17

The Skill Library is the catalog of reusable SOPs (Standard
Operating Procedures) the AEO uses to do common work. A skill is
**not** an agent — agents *invoke* skills. A skill is a method.

## When to use a skill

Whenever a recurring procedure appears in the workflow. Examples:

- A research question about a 49 CFR section recurs → invoke
  `49cfr-rule-audit`.
- A new external claim is about to be published → invoke
  `claims-substantiation-review`.
- A new privacy-policy section is needed → invoke
  `privacy-policy-draft`.

## Skill vs. agent

- **Agent** (`docs/agents/`) — a permanent role with mission,
  authority, tools, escalation rules.
- **Skill** (`docs/skills/`) — a reusable method anyone can
  invoke. Skills are content; agents are roles. The same skill
  may be invoked by multiple agents.

## Skill anatomy (the template every skill file follows)

- **Purpose** — one sentence: what this skill does and why.
- **Triggers** — when to invoke it.
- **Required Inputs** — what the caller must provide.
- **Research Required** — what primary sources to consult before
  proceeding.
- **Step-by-Step Method** — the SOP itself, numbered.
- **Deliverable Format** — what the skill produces.
- **Quality Checklist** — what to confirm before declaring done.
- **Escalation Triggers** — what halts the skill and routes to
  whom.
- **Related Agents** — which division(s) typically invoke it.
- **Related Artifacts** — which artifact templates the skill
  produces.

## Library at a glance

### Research & Strategy (4)

- `research-dossier-build.md`
- `source-contradiction-analysis.md`
- `competitor-benchmark.md`
- `customer-pain-mining.md`

### HazMat Compliance (5)

- `49cfr-rule-audit.md`
- `shipping-paper-compliance-review.md`
- `placard-threshold-review.md`
- `erg-source-validation.md`
- `tdg-crossborder-review.md`

### Engineering & Security (6)

- `rbac-tenant-isolation-audit.md`
- `webhook-idempotency-review.md`
- `sor-cutover-risk-review.md`
- `document-renderer-regression-review.md`
- `ocr-confidence-provenance-audit.md`
- `mobile-capacitor-release-check.md`

### Assurance (6)

- `threat-model-build.md`
- `negative-test-suite-generation.md`
- `pilot-readiness-audit.md`
- `release-go-no-go-review.md`
- `compliance-evidence-matrix-build.md`
- `stub-inventory-audit.md`

### Commercial (6)

- `hazmat-market-positioning.md`
- `b2b-saas-pricing-study.md`
- `packaging-entitlements-analysis.md`
- `competitor-battlecard.md`
- `carrier-roi-model.md`
- `pilot-to-contract-conversion-plan.md`

### Legal / Trust (9)

- `privacy-policy-draft.md`
- `terms-of-service-draft.md`
- `nda-draft.md`
- `pilot-agreement-draft.md`
- `msa-sow-draft.md`
- `dpa-draft.md`
- `claims-substantiation-review.md`
- `app-store-policy-audit.md`
- `oss-license-review.md`

### Knowledge Ops (4)

- `doc-freshness-reconcile.md`
- `artifact-index-update.md`
- `agent-run-retrospective.md`
- `prompt-upgrade-synthesis.md`

## Future extensibility

The library grows as the AEO learns. The Skill Library Manager
(Knowledge Operations, `docs/agents/09`) promotes new skills when a
pattern recurs across runs. The validator
(`scripts/check-governance-index.mjs`) enforces that every skill
file has `## Purpose` and `## Step-by-Step Method`.
