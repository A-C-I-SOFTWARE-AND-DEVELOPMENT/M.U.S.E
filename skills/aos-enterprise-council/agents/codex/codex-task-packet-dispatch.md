---
name: codex-task-packet-dispatch
category: codex
canonical_source: recovered-agent-sources/from-hazmat-command/skills/codex-task-packet-dispatch/SKILL.md
source_repo: hazmat-skill
subsystem: snapshot-skills
recovery_label: DIRECTLY RECOVERED
bucket: canonical
---

# codex-task-packet-dispatch

**Category:** Codex Layer
**Canonical source:** `recovered-agent-sources/from-hazmat-command/skills/codex-task-packet-dispatch/SKILL.md`
**Source repo / subsystem:** `hazmat-skill` / `snapshot-skills`

## Description (verbatim frontmatter)

> Manual-only. Owner-triggered. Drafts and dispatches a Codex Task Packet per docs/templates/codex-task-package-template.md and docs/governance/17-codex-bounded-implementation-fabric.md. Wave 1 is contract-only — validates packet shape, confirms m...

## Recovery provenance

- Recovered by the AOS Recovery pass on branch `claude/aos-agent-recovery-hermes-jmocw` (2026-05-24).
- Frontmatter `name:` and `description:` extracted via awk from the canonical source.
- See `../../registry/AOS_AGENT_REGISTRY_COMPLETE.md` for the full canonical/alias/mentioned bucket structure.
- See `../../registry/AOS_DUPLICATE_AND_CONFLICT_REPORT.md` for any cross-source variant diffs.

## Activation

Loaded by the top-level `SKILL.md` when the request matches this category. Hermes runtime delegates here via `delegate_task` and persists artifacts under `memory` namespace `aos/council/<slug>/<category>`.
