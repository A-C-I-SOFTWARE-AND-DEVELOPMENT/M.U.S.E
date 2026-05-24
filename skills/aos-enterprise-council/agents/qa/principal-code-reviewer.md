---
name: principal-code-reviewer
category: qa
canonical_source: recovered-agent-sources/from-hazmat-command/agents/principal-code-reviewer.md
source_repo: hazmat-agent
subsystem: snapshot-agents
recovery_label: DIRECTLY RECOVERED
bucket: canonical
---

# principal-code-reviewer

**Category:** QA / Quality-Gate Layer
**Canonical source:** `recovered-agent-sources/from-hazmat-command/agents/principal-code-reviewer.md`
**Source repo / subsystem:** `hazmat-agent` / `snapshot-agents`

## Description (verbatim frontmatter)

> Hard-nosed independent code reviewer. Use on every code-bearing PR before owner review. Catches AI slop, architecture shortcuts, weak tests, missing edge cases, silent behavioral drift, scope creep, and the looks done but isn't failure mode. Canno...

## Recovery provenance

- Recovered by the AOS Recovery pass on branch `claude/aos-agent-recovery-hermes-jmocw` (2026-05-24).
- Frontmatter `name:` and `description:` extracted via awk from the canonical source.
- See `../../registry/AOS_AGENT_REGISTRY_COMPLETE.md` for the full canonical/alias/mentioned bucket structure.
- See `../../registry/AOS_DUPLICATE_AND_CONFLICT_REPORT.md` for any cross-source variant diffs.

## Activation

Loaded by the top-level `SKILL.md` when the request matches this category. Hermes runtime delegates here via `delegate_task` and persists artifacts under `memory` namespace `aos/council/<slug>/<category>`.
