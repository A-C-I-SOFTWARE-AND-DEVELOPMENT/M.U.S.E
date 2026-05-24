---
name: evidence-bundle-build
category: memory
canonical_source: recovered-agent-sources/from-hazmat-command/skills/evidence-bundle-build/SKILL.md
source_repo: hazmat-skill
subsystem: snapshot-skills
recovery_label: DIRECTLY RECOVERED
bucket: canonical
---

# evidence-bundle-build

**Category:** Memory / Knowledge / Curation Layer
**Canonical source:** `recovered-agent-sources/from-hazmat-command/skills/evidence-bundle-build/SKILL.md`
**Source repo / subsystem:** `hazmat-skill` / `snapshot-skills`

## Description (verbatim frontmatter)

> Use immediately after mission-brief-build. Assembles repo facts, external citations, prior decisions, applicable standards, and risks into 01-evidence-bundle.md using docs/templates/evidence-bundle-template.md. Every claim in downstream plans must...

## Recovery provenance

- Recovered by the AOS Recovery pass on branch `claude/aos-agent-recovery-hermes-jmocw` (2026-05-24).
- Frontmatter `name:` and `description:` extracted via awk from the canonical source.
- See `../../registry/AOS_AGENT_REGISTRY_COMPLETE.md` for the full canonical/alias/mentioned bucket structure.
- See `../../registry/AOS_DUPLICATE_AND_CONFLICT_REPORT.md` for any cross-source variant diffs.

## Activation

Loaded by the top-level `SKILL.md` when the request matches this category. Hermes runtime delegates here via `delegate_task` and persists artifacts under `memory` namespace `aos/council/<slug>/<category>`.
