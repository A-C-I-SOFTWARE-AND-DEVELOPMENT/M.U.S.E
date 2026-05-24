---
name: complex-bug-fix
category: qa
canonical_source: recovered-agent-sources/from-hazmat-command/skills/complex-bug-fix/SKILL.md
source_repo: hazmat-skill
subsystem: snapshot-skills
recovery_label: DIRECTLY RECOVERED
bucket: canonical
---

# complex-bug-fix

**Category:** QA / Quality-Gate Layer
**Canonical source:** `recovered-agent-sources/from-hazmat-command/skills/complex-bug-fix/SKILL.md`
**Source repo / subsystem:** `hazmat-skill` / `snapshot-skills`

## Description (verbatim frontmatter)

> Use when a defect spans more than one file, more than one role, or appears to involve a regression in a tested surface. Walks the bug from reproduction through root cause, fix, negative test, regression test, and rollback plan. Aligned with docs/w...

## Recovery provenance

- Recovered by the AOS Recovery pass on branch `claude/aos-agent-recovery-hermes-jmocw` (2026-05-24).
- Frontmatter `name:` and `description:` extracted via awk from the canonical source.
- See `../../registry/AOS_AGENT_REGISTRY_COMPLETE.md` for the full canonical/alias/mentioned bucket structure.
- See `../../registry/AOS_DUPLICATE_AND_CONFLICT_REPORT.md` for any cross-source variant diffs.

## Activation

Loaded by the top-level `SKILL.md` when the request matches this category. Hermes runtime delegates here via `delegate_task` and persists artifacts under `memory` namespace `aos/council/<slug>/<category>`.
