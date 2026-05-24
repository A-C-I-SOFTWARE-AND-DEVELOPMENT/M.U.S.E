---
name: enterprise-orchestrator
category: hermes
canonical_source: recovered-agent-sources/from-hermes-agent/enterprise-council/orchestrator/SKILL.md
source_repo: recovered-hermes-skill
subsystem: snapshot-skills
recovery_label: DIRECTLY RECOVERED
bucket: canonical
---

# enterprise-orchestrator

**Category:** Hermes-Specific Skills Layer
**Canonical source:** `recovered-agent-sources/from-hermes-agent/enterprise-council/orchestrator/SKILL.md`
**Source repo / subsystem:** `recovered-hermes-skill` / `snapshot-skills`

## Description (verbatim frontmatter)

> Decompose a one-tap enterprise goal into autonomous tasks across domain agents.

## Aliases (other sources defining the same `name:`)

- `skills/enterprise-council/orchestrator/SKILL.md` — `hermes-skill` / `live-skills`

## Recovery provenance

- Recovered by the AOS Recovery pass on branch `claude/aos-agent-recovery-hermes-jmocw` (2026-05-24).
- Frontmatter `name:` and `description:` extracted via awk from the canonical source.
- See `../../registry/AOS_AGENT_REGISTRY_COMPLETE.md` for the full canonical/alias/mentioned bucket structure.
- See `../../registry/AOS_DUPLICATE_AND_CONFLICT_REPORT.md` for any cross-source variant diffs.

## Activation

Loaded by the top-level `SKILL.md` when the request matches this category. Hermes runtime delegates here via `delegate_task` and persists artifacts under `memory` namespace `aos/council/<slug>/<category>`.
