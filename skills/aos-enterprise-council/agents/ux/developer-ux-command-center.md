---
name: developer-ux-command-center
category: ux
canonical_source: skills/developer-ux-command-center/SKILL.md
source_repo: hermes-skill
subsystem: live-skills
recovery_label: DIRECTLY RECOVERED
bucket: canonical
---

# developer-ux-command-center

**Category:** UX Layer (Product & Pilot Studio)
**Canonical source:** `skills/developer-ux-command-center/SKILL.md`
**Source repo / subsystem:** `hermes-skill` / `live-skills`

## Description (verbatim frontmatter)

> Developer-facing surface for the Hermes orchestration pipeline. Use to drive scripts/hermes-orchestrate.sh from a terminal: scaffold a job, list jobs, inspect status, and explain artifacts in plain prose.

## Recovery provenance

- Recovered by the AOS Recovery pass on branch `claude/aos-agent-recovery-hermes-jmocw` (2026-05-24).
- Frontmatter `name:` and `description:` extracted via awk from the canonical source.
- See `../../registry/AOS_AGENT_REGISTRY_COMPLETE.md` for the full canonical/alias/mentioned bucket structure.
- See `../../registry/AOS_DUPLICATE_AND_CONFLICT_REPORT.md` for any cross-source variant diffs.

## Activation

Loaded by the top-level `SKILL.md` when the request matches this category. Hermes runtime delegates here via `delegate_task` and persists artifacts under `memory` namespace `aos/council/<slug>/<category>`.
