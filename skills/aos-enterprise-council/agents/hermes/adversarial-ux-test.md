---
name: adversarial-ux-test
category: hermes
canonical_source: optional-skills/dogfood/adversarial-ux-test/SKILL.md
source_repo: hermes-optional-skill
subsystem: live-optional-skills
recovery_label: DIRECTLY RECOVERED
bucket: canonical
---

# adversarial-ux-test

**Category:** Hermes-Specific Skills Layer
**Canonical source:** `optional-skills/dogfood/adversarial-ux-test/SKILL.md`
**Source repo / subsystem:** `hermes-optional-skill` / `live-optional-skills`

## Description (verbatim frontmatter)

> Roleplay the most difficult, tech-resistant user for your product. Browse the app as that persona, find every UX pain point, then filter complaints through a pragmatism layer to separate real problems from noise. Creates actionable tickets from ge...

## Recovery provenance

- Recovered by the AOS Recovery pass on branch `claude/aos-agent-recovery-hermes-jmocw` (2026-05-24).
- Frontmatter `name:` and `description:` extracted via awk from the canonical source.
- See `../../registry/AOS_AGENT_REGISTRY_COMPLETE.md` for the full canonical/alias/mentioned bucket structure.
- See `../../registry/AOS_DUPLICATE_AND_CONFLICT_REPORT.md` for any cross-source variant diffs.

## Activation

Loaded by the top-level `SKILL.md` when the request matches this category. Hermes runtime delegates here via `delegate_task` and persists artifacts under `memory` namespace `aos/council/<slug>/<category>`.
