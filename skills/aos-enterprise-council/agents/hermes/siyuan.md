---
name: siyuan
category: hermes
canonical_source: optional-skills/productivity/siyuan/SKILL.md
source_repo: hermes-optional-skill
subsystem: live-optional-skills
recovery_label: DIRECTLY RECOVERED
bucket: canonical
---

# siyuan

**Category:** Hermes-Specific Skills Layer
**Canonical source:** `optional-skills/productivity/siyuan/SKILL.md`
**Source repo / subsystem:** `hermes-optional-skill` / `live-optional-skills`

## Description (verbatim frontmatter)

> SiYuan Note API for searching, reading, creating, and managing blocks and documents in a self-hosted knowledge base via curl.

## Recovery provenance

- Recovered by the AOS Recovery pass on branch `claude/aos-agent-recovery-hermes-jmocw` (2026-05-24).
- Frontmatter `name:` and `description:` extracted via awk from the canonical source.
- See `../../registry/AOS_AGENT_REGISTRY_COMPLETE.md` for the full canonical/alias/mentioned bucket structure.
- See `../../registry/AOS_DUPLICATE_AND_CONFLICT_REPORT.md` for any cross-source variant diffs.

## Activation

Loaded by the top-level `SKILL.md` when the request matches this category. Hermes runtime delegates here via `delegate_task` and persists artifacts under `memory` namespace `aos/council/<slug>/<category>`.
