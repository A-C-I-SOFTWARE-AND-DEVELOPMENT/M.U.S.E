---
name: knowledge-operations-self-improvement
category: memory
canonical_source: recovered-agent-sources/from-hazmat-command/agents/knowledge-operations-self-improvement.md
source_repo: hazmat-agent
subsystem: snapshot-agents
recovery_label: DIRECTLY RECOVERED
bucket: canonical
---

# knowledge-operations-self-improvement

**Category:** Memory / Knowledge / Curation Layer
**Canonical source:** `recovered-agent-sources/from-hazmat-command/agents/knowledge-operations-self-improvement.md`
**Source repo / subsystem:** `hazmat-agent` / `snapshot-agents`

## Description (verbatim frontmatter)

> Use to maintain durable artifacts — the index, the doc-freshness ledger, the agent-run retrospective, the prompt/system quality log. Reconciles contradictions, removes stale claims, updates HANDOFF.md only when materially better. Does not write ...

## Recovery provenance

- Recovered by the AOS Recovery pass on branch `claude/aos-agent-recovery-hermes-jmocw` (2026-05-24).
- Frontmatter `name:` and `description:` extracted via awk from the canonical source.
- See `../../registry/AOS_AGENT_REGISTRY_COMPLETE.md` for the full canonical/alias/mentioned bucket structure.
- See `../../registry/AOS_DUPLICATE_AND_CONFLICT_REPORT.md` for any cross-source variant diffs.

## Activation

Loaded by the top-level `SKILL.md` when the request matches this category. Hermes runtime delegates here via `delegate_task` and persists artifacts under `memory` namespace `aos/council/<slug>/<category>`.
