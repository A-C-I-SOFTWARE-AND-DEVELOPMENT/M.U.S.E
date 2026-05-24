---
name: pilot-readiness-judge
category: release
canonical_source: recovered-agent-sources/from-hazmat-command/agents/pilot-readiness-judge.md
source_repo: hazmat-agent
subsystem: snapshot-agents
recovery_label: DIRECTLY RECOVERED
bucket: canonical
---

# pilot-readiness-judge

**Category:** Release / Pilot-Readiness Layer
**Canonical source:** `recovered-agent-sources/from-hazmat-command/agents/pilot-readiness-judge.md`
**Source repo / subsystem:** `hazmat-agent` / `snapshot-agents`

## Description (verbatim frontmatter)

> Use before a real customer demo or pilot session. Produces a binary go / no-go verdict with named blockers. Walks the demo / pilot script end-to-end, including failure paths. Cannot be bribed by almost ready — either ready or not.

## Recovery provenance

- Recovered by the AOS Recovery pass on branch `claude/aos-agent-recovery-hermes-jmocw` (2026-05-24).
- Frontmatter `name:` and `description:` extracted via awk from the canonical source.
- See `../../registry/AOS_AGENT_REGISTRY_COMPLETE.md` for the full canonical/alias/mentioned bucket structure.
- See `../../registry/AOS_DUPLICATE_AND_CONFLICT_REPORT.md` for any cross-source variant diffs.

## Activation

Loaded by the top-level `SKILL.md` when the request matches this category. Hermes runtime delegates here via `delegate_task` and persists artifacts under `memory` namespace `aos/council/<slug>/<category>`.
