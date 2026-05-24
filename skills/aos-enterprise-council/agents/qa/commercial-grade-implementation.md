---
name: commercial-grade-implementation
category: qa
canonical_source: recovered-agent-sources/from-hazmat-command/skills/commercial-grade-implementation/SKILL.md
source_repo: hazmat-skill
subsystem: snapshot-skills
recovery_label: DIRECTLY RECOVERED
bucket: canonical
---

# commercial-grade-implementation

**Category:** QA / Quality-Gate Layer
**Canonical source:** `recovered-agent-sources/from-hazmat-command/skills/commercial-grade-implementation/SKILL.md`
**Source repo / subsystem:** `hazmat-skill` / `snapshot-skills`

## Description (verbatim frontmatter)

> The default implementation workflow for any code-bearing task in this repo. Enforces architecture awareness, scoped change design, negative-path tests, documentation alignment, and the final evidence package. Builder uses this skill, principal-cod...

## Recovery provenance

- Recovered by the AOS Recovery pass on branch `claude/aos-agent-recovery-hermes-jmocw` (2026-05-24).
- Frontmatter `name:` and `description:` extracted via awk from the canonical source.
- See `../../registry/AOS_AGENT_REGISTRY_COMPLETE.md` for the full canonical/alias/mentioned bucket structure.
- See `../../registry/AOS_DUPLICATE_AND_CONFLICT_REPORT.md` for any cross-source variant diffs.

## Activation

Loaded by the top-level `SKILL.md` when the request matches this category. Hermes runtime delegates here via `delegate_task` and persists artifacts under `memory` namespace `aos/council/<slug>/<category>`.
