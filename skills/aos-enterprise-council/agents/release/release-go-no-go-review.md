---
name: release-go-no-go-review
category: release
canonical_source: recovered-agent-sources/from-hazmat-command/skills/release-go-no-go-review/SKILL.md
source_repo: hazmat-skill
subsystem: snapshot-skills
recovery_label: DIRECTLY RECOVERED
bucket: canonical
---

# release-go-no-go-review

**Category:** Release / Pilot-Readiness Layer
**Canonical source:** `recovered-agent-sources/from-hazmat-command/skills/release-go-no-go-review/SKILL.md`
**Source repo / subsystem:** `hazmat-skill` / `snapshot-skills`

## Description (verbatim frontmatter)

> Use before tagging or shipping a release. Verifies G0–G4 release governance per PUBLISH.md, runs the freeze-trigger check, and produces a binary GO / NO-GO recommendation for the owner. Aligned with docs/skills/release-go-no-go-review.md (the AE...

## Recovery provenance

- Recovered by the AOS Recovery pass on branch `claude/aos-agent-recovery-hermes-jmocw` (2026-05-24).
- Frontmatter `name:` and `description:` extracted via awk from the canonical source.
- See `../../registry/AOS_AGENT_REGISTRY_COMPLETE.md` for the full canonical/alias/mentioned bucket structure.
- See `../../registry/AOS_DUPLICATE_AND_CONFLICT_REPORT.md` for any cross-source variant diffs.

## Activation

Loaded by the top-level `SKILL.md` when the request matches this category. Hermes runtime delegates here via `delegate_task` and persists artifacts under `memory` namespace `aos/council/<slug>/<category>`.
