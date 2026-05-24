---
name: multi-plan-council-run
category: executive
canonical_source: recovered-agent-sources/from-hazmat-command/skills/multi-plan-council-run/SKILL.md
source_repo: hazmat-skill
subsystem: snapshot-skills
recovery_label: DIRECTLY RECOVERED
bucket: canonical
---

# multi-plan-council-run

**Category:** Executive / Operator Layer
**Canonical source:** `recovered-agent-sources/from-hazmat-command/skills/multi-plan-council-run/SKILL.md`
**Source repo / subsystem:** `hazmat-skill` / `snapshot-skills`

## Description (verbatim frontmatter)

> Manual-only. Owner-triggered. Dispatches N parallel plan-generation passes for Council Mode (Lite 3 / Standard 4–6 / RC3-strategy 6+) each under a distinct lens — Market Domination, Enterprise Trust, Product Experience, Engineering Reality, Mi...

## Recovery provenance

- Recovered by the AOS Recovery pass on branch `claude/aos-agent-recovery-hermes-jmocw` (2026-05-24).
- Frontmatter `name:` and `description:` extracted via awk from the canonical source.
- See `../../registry/AOS_AGENT_REGISTRY_COMPLETE.md` for the full canonical/alias/mentioned bucket structure.
- See `../../registry/AOS_DUPLICATE_AND_CONFLICT_REPORT.md` for any cross-source variant diffs.

## Activation

Loaded by the top-level `SKILL.md` when the request matches this category. Hermes runtime delegates here via `delegate_task` and persists artifacts under `memory` namespace `aos/council/<slug>/<category>`.
