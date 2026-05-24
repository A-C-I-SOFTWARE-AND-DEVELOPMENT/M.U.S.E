---
name: plan-comparison-scorecard
category: executive
canonical_source: recovered-agent-sources/from-hazmat-command/skills/plan-comparison-scorecard/SKILL.md
source_repo: hazmat-skill
subsystem: snapshot-skills
recovery_label: DIRECTLY RECOVERED
bucket: canonical
---

# plan-comparison-scorecard

**Category:** Executive / Operator Layer
**Canonical source:** `recovered-agent-sources/from-hazmat-command/skills/plan-comparison-scorecard/SKILL.md`
**Source repo / subsystem:** `hazmat-skill` / `snapshot-skills`

## Description (verbatim frontmatter)

> Use after multi-plan-council-run produces N materially-distinct plans. Scores each plan 1–10 across the 10-criterion rubric in governance/16, extracts surviving ideas, rejected ideas, assumptions needing proof, contradictions with repo reality, ...

## Recovery provenance

- Recovered by the AOS Recovery pass on branch `claude/aos-agent-recovery-hermes-jmocw` (2026-05-24).
- Frontmatter `name:` and `description:` extracted via awk from the canonical source.
- See `../../registry/AOS_AGENT_REGISTRY_COMPLETE.md` for the full canonical/alias/mentioned bucket structure.
- See `../../registry/AOS_DUPLICATE_AND_CONFLICT_REPORT.md` for any cross-source variant diffs.

## Activation

Loaded by the top-level `SKILL.md` when the request matches this category. Hermes runtime delegates here via `delegate_task` and persists artifacts under `memory` namespace `aos/council/<slug>/<category>`.
