---
name: codex-return-envelope-verify
category: codex
canonical_source: recovered-agent-sources/from-hazmat-command/skills/codex-return-envelope-verify/SKILL.md
source_repo: hazmat-skill
subsystem: snapshot-skills
recovery_label: DIRECTLY RECOVERED
bucket: canonical
---

# codex-return-envelope-verify

**Category:** Codex Layer
**Canonical source:** `recovered-agent-sources/from-hazmat-command/skills/codex-return-envelope-verify/SKILL.md`
**Source repo / subsystem:** `hazmat-skill` / `snapshot-skills`

## Description (verbatim frontmatter)

> Use after a Codex Task Packet execution returns. Parses the return envelope, asserts schema validity, asserts allow-list adherence, asserts forbidden-list adherence, re-runs the claimed test commands locally, cross-checks against the owner-only-wa...

## Recovery provenance

- Recovered by the AOS Recovery pass on branch `claude/aos-agent-recovery-hermes-jmocw` (2026-05-24).
- Frontmatter `name:` and `description:` extracted via awk from the canonical source.
- See `../../registry/AOS_AGENT_REGISTRY_COMPLETE.md` for the full canonical/alias/mentioned bucket structure.
- See `../../registry/AOS_DUPLICATE_AND_CONFLICT_REPORT.md` for any cross-source variant diffs.

## Activation

Loaded by the top-level `SKILL.md` when the request matches this category. Hermes runtime delegates here via `delegate_task` and persists artifacts under `memory` namespace `aos/council/<slug>/<category>`.
