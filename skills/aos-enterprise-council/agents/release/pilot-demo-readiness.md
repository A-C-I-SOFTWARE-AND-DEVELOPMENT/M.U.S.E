---
name: pilot-demo-readiness
category: release
canonical_source: recovered-agent-sources/from-hazmat-command/skills/pilot-demo-readiness/SKILL.md
source_repo: hazmat-skill
subsystem: snapshot-skills
recovery_label: DIRECTLY RECOVERED
bucket: canonical
---

# pilot-demo-readiness

**Category:** Release / Pilot-Readiness Layer
**Canonical source:** `recovered-agent-sources/from-hazmat-command/skills/pilot-demo-readiness/SKILL.md`
**Source repo / subsystem:** `hazmat-skill` / `snapshot-skills`

## Description (verbatim frontmatter)

> Use to prepare for and judge readiness of a real customer demo or pilot session. Walks the demo end-to-end including failure paths, bilingual rendering, audit-ledger export, OCR low-confidence path, and verifies no owner-only-wall dependency on de...

## Recovery provenance

- Recovered by the AOS Recovery pass on branch `claude/aos-agent-recovery-hermes-jmocw` (2026-05-24).
- Frontmatter `name:` and `description:` extracted via awk from the canonical source.
- See `../../registry/AOS_AGENT_REGISTRY_COMPLETE.md` for the full canonical/alias/mentioned bucket structure.
- See `../../registry/AOS_DUPLICATE_AND_CONFLICT_REPORT.md` for any cross-source variant diffs.

## Activation

Loaded by the top-level `SKILL.md` when the request matches this category. Hermes runtime delegates here via `delegate_task` and persists artifacts under `memory` namespace `aos/council/<slug>/<category>`.
