---
name: mission-brief-build
category: executive
canonical_source: recovered-agent-sources/from-hazmat-command/skills/mission-brief-build/SKILL.md
source_repo: hazmat-skill
subsystem: snapshot-skills
recovery_label: DIRECTLY RECOVERED
bucket: canonical
---

# mission-brief-build

**Category:** Executive / Operator Layer
**Canonical source:** `recovered-agent-sources/from-hazmat-command/skills/mission-brief-build/SKILL.md`
**Source repo / subsystem:** `hazmat-skill` / `snapshot-skills`

## Description (verbatim frontmatter)

> Use at the start of any Council Mode run or any substantive sprint that lands in a run folder under docs/aos/runs/. Produces 00-mission-brief.md by instantiating docs/templates/mission-brief-template.md. Restates owner intent, scope, exclusions, k...

## Recovery provenance

- Recovered by the AOS Recovery pass on branch `claude/aos-agent-recovery-hermes-jmocw` (2026-05-24).
- Frontmatter `name:` and `description:` extracted via awk from the canonical source.
- See `../../registry/AOS_AGENT_REGISTRY_COMPLETE.md` for the full canonical/alias/mentioned bucket structure.
- See `../../registry/AOS_DUPLICATE_AND_CONFLICT_REPORT.md` for any cross-source variant diffs.

## Activation

Loaded by the top-level `SKILL.md` when the request matches this category. Hermes runtime delegates here via `delegate_task` and persists artifacts under `memory` namespace `aos/council/<slug>/<category>`.
