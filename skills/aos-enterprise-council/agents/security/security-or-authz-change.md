---
name: security-or-authz-change
category: security
canonical_source: recovered-agent-sources/from-hazmat-command/skills/security-or-authz-change/SKILL.md
source_repo: hazmat-skill
subsystem: snapshot-skills
recovery_label: DIRECTLY RECOVERED
bucket: canonical
---

# security-or-authz-change

**Category:** Security Layer (Assurance Office)
**Canonical source:** `recovered-agent-sources/from-hazmat-command/skills/security-or-authz-change/SKILL.md`
**Source repo / subsystem:** `hazmat-skill` / `snapshot-skills`

## Description (verbatim frontmatter)

> Use when changing authz, RBAC, RLS, audit ledger, OCR provenance, secret handling, SCIM, SSO, CSP, supply-chain dependencies, or any RC3 security surface listed in docs/governance/03-change-risk-matrix.md. Enforces maker-checker discipline, negati...

## Recovery provenance

- Recovered by the AOS Recovery pass on branch `claude/aos-agent-recovery-hermes-jmocw` (2026-05-24).
- Frontmatter `name:` and `description:` extracted via awk from the canonical source.
- See `../../registry/AOS_AGENT_REGISTRY_COMPLETE.md` for the full canonical/alias/mentioned bucket structure.
- See `../../registry/AOS_DUPLICATE_AND_CONFLICT_REPORT.md` for any cross-source variant diffs.

## Activation

Loaded by the top-level `SKILL.md` when the request matches this category. Hermes runtime delegates here via `delegate_task` and persists artifacts under `memory` namespace `aos/council/<slug>/<category>`.
