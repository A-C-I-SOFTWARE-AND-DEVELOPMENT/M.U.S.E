---
name: engineering-architecture-factory
category: architecture
canonical_source: recovered-agent-sources/from-hazmat-command/agents/engineering-architecture-factory.md
source_repo: hazmat-agent
subsystem: snapshot-agents
recovery_label: DIRECTLY RECOVERED
bucket: canonical
---

# engineering-architecture-factory

**Category:** Software Architecture Layer
**Canonical source:** `recovered-agent-sources/from-hazmat-command/agents/engineering-architecture-factory.md`
**Source repo / subsystem:** `hazmat-agent` / `snapshot-agents`

## Description (verbatim frontmatter)

> Primary implementation agent for HazMat Command product code. Use for code changes to src/, api/, base44/, scripts/, supabase/, tests/, and CI workflows. Respects existing architecture, writes commercial-grade code and tests, and produces minimal ...

## Recovery provenance

- Recovered by the AOS Recovery pass on branch `claude/aos-agent-recovery-hermes-jmocw` (2026-05-24).
- Frontmatter `name:` and `description:` extracted via awk from the canonical source.
- See `../../registry/AOS_AGENT_REGISTRY_COMPLETE.md` for the full canonical/alias/mentioned bucket structure.
- See `../../registry/AOS_DUPLICATE_AND_CONFLICT_REPORT.md` for any cross-source variant diffs.

## Activation

Loaded by the top-level `SKILL.md` when the request matches this category. Hermes runtime delegates here via `delegate_task` and persists artifacts under `memory` namespace `aos/council/<slug>/<category>`.
