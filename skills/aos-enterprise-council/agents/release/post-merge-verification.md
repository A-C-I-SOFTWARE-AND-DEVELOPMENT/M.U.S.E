---
name: post-merge-verification
category: release
canonical_source: recovered-agent-sources/from-hazmat-command/skills/post-merge-verification/SKILL.md
source_repo: hazmat-skill
subsystem: snapshot-skills
recovery_label: DIRECTLY RECOVERED
bucket: canonical
---

# post-merge-verification

**Category:** Release / Pilot-Readiness Layer
**Canonical source:** `recovered-agent-sources/from-hazmat-command/skills/post-merge-verification/SKILL.md`
**Source repo / subsystem:** `hazmat-skill` / `snapshot-skills`

## Description (verbatim frontmatter)

> Use immediately after an owner-approved merge to main. Confirms the merge commit, the CI state on main, the documented baseline, the relevant docs, and any release notes / tags needed. Recommends the next work without overstepping.

## Recovery provenance

- Recovered by the AOS Recovery pass on branch `claude/aos-agent-recovery-hermes-jmocw` (2026-05-24).
- Frontmatter `name:` and `description:` extracted via awk from the canonical source.
- See `../../registry/AOS_AGENT_REGISTRY_COMPLETE.md` for the full canonical/alias/mentioned bucket structure.
- See `../../registry/AOS_DUPLICATE_AND_CONFLICT_REPORT.md` for any cross-source variant diffs.

## Activation

Loaded by the top-level `SKILL.md` when the request matches this category. Hermes runtime delegates here via `delegate_task` and persists artifacts under `memory` namespace `aos/council/<slug>/<category>`.
