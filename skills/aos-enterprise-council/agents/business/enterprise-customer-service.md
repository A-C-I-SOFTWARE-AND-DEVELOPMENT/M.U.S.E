---
name: enterprise-customer-service
category: business
canonical_source: recovered-agent-sources/from-hermes-agent/enterprise-council/customer-service/SKILL.md
source_repo: recovered-hermes-skill
subsystem: snapshot-skills
recovery_label: DIRECTLY RECOVERED
bucket: canonical
---

# enterprise-customer-service

**Category:** Business / Commercial / Legal Layer
**Canonical source:** `recovered-agent-sources/from-hermes-agent/enterprise-council/customer-service/SKILL.md`
**Source repo / subsystem:** `recovered-hermes-skill` / `snapshot-skills`

## Description (verbatim frontmatter)

> CS leaf: ticket classification, knowledge base retrieval, escalation, mass communications.

## Aliases (other sources defining the same `name:`)

- `skills/enterprise-council/customer-service/SKILL.md` — `hermes-skill` / `live-skills`

## Recovery provenance

- Recovered by the AOS Recovery pass on branch `claude/aos-agent-recovery-hermes-jmocw` (2026-05-24).
- Frontmatter `name:` and `description:` extracted via awk from the canonical source.
- See `../../registry/AOS_AGENT_REGISTRY_COMPLETE.md` for the full canonical/alias/mentioned bucket structure.
- See `../../registry/AOS_DUPLICATE_AND_CONFLICT_REPORT.md` for any cross-source variant diffs.

## Activation

Loaded by the top-level `SKILL.md` when the request matches this category. Hermes runtime delegates here via `delegate_task` and persists artifacts under `memory` namespace `aos/council/<slug>/<category>`.
