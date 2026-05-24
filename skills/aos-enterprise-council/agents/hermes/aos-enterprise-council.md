---
name: aos-enterprise-council
category: hermes
canonical_source: skills/aos-enterprise-council/SKILL.md
source_repo: hermes-skill
subsystem: live-skills
recovery_label: DIRECTLY RECOVERED
bucket: canonical
---

# aos-enterprise-council

**Category:** Hermes-Specific Skills Layer
**Canonical source:** `skills/aos-enterprise-council/SKILL.md`
**Source repo / subsystem:** `hermes-skill` / `live-skills`

## Description (verbatim frontmatter)

> AOS Enterprise Council — full 11-division autonomous-enterprise smart team (chief orchestrator, engineering, security/compliance, product/pilot, research/evidence, commercial, legal, knowledge-ops, code-review, codex fabric, pilot-judge) wired f...

## Recovery provenance

- Recovered by the AOS Recovery pass on branch `claude/aos-agent-recovery-hermes-jmocw` (2026-05-24).
- Frontmatter `name:` and `description:` extracted via awk from the canonical source.
- See `../../registry/AOS_AGENT_REGISTRY_COMPLETE.md` for the full canonical/alias/mentioned bucket structure.
- See `../../registry/AOS_DUPLICATE_AND_CONFLICT_REPORT.md` for any cross-source variant diffs.

## Activation

Loaded by the top-level `SKILL.md` when the request matches this category. Hermes runtime delegates here via `delegate_task` and persists artifacts under `memory` namespace `aos/council/<slug>/<category>`.
