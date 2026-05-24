---
name: codex-implementation-fabric
category: codex
canonical_source: recovered-agent-sources/from-hazmat-command/agents/codex-implementation-fabric.md
source_repo: hazmat-agent
subsystem: snapshot-agents
recovery_label: DIRECTLY RECOVERED
bucket: canonical
---

# codex-implementation-fabric

**Category:** Codex Layer
**Canonical source:** `recovered-agent-sources/from-hazmat-command/agents/codex-implementation-fabric.md`
**Source repo / subsystem:** `hazmat-agent` / `snapshot-agents`

## Description (verbatim frontmatter)

> Thin wrapper for the Codex bounded-implementation fabric. Authority cap L3, trust zones T3+T4 only — never L4 or T5/T6. Owner-only walls forbidden. Dispatches scoped Codex Task Packets, validates the return envelope, hands the diff to principal-...

## Recovery provenance

- Recovered by the AOS Recovery pass on branch `claude/aos-agent-recovery-hermes-jmocw` (2026-05-24).
- Frontmatter `name:` and `description:` extracted via awk from the canonical source.
- See `../../registry/AOS_AGENT_REGISTRY_COMPLETE.md` for the full canonical/alias/mentioned bucket structure.
- See `../../registry/AOS_DUPLICATE_AND_CONFLICT_REPORT.md` for any cross-source variant diffs.

## Activation

Loaded by the top-level `SKILL.md` when the request matches this category. Hermes runtime delegates here via `delegate_task` and persists artifacts under `memory` namespace `aos/council/<slug>/<category>`.
