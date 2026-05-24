---
name: assurance-security-compliance-office
category: security
canonical_source: recovered-agent-sources/from-hazmat-command/agents/assurance-security-compliance-office.md
source_repo: hazmat-agent
subsystem: snapshot-agents
recovery_label: DIRECTLY RECOVERED
bucket: canonical
---

# assurance-security-compliance-office

**Category:** Security Layer (Assurance Office)
**Canonical source:** `recovered-agent-sources/from-hazmat-command/agents/assurance-security-compliance-office.md`
**Source repo / subsystem:** `hazmat-agent` / `snapshot-agents`

## Description (verbatim frontmatter)

> Independent reviewer for security, compliance, reliability, and regulator-facing change. Use on every RC3 change (authz, audit ledger, OCR provenance, regulator-facing builders, Square, SCIM, RLS, claims, legal, release). Actively tries to find de...

## Recovery provenance

- Recovered by the AOS Recovery pass on branch `claude/aos-agent-recovery-hermes-jmocw` (2026-05-24).
- Frontmatter `name:` and `description:` extracted via awk from the canonical source.
- See `../../registry/AOS_AGENT_REGISTRY_COMPLETE.md` for the full canonical/alias/mentioned bucket structure.
- See `../../registry/AOS_DUPLICATE_AND_CONFLICT_REPORT.md` for any cross-source variant diffs.

## Activation

Loaded by the top-level `SKILL.md` when the request matches this category. Hermes runtime delegates here via `delegate_task` and persists artifacts under `memory` namespace `aos/council/<slug>/<category>`.
