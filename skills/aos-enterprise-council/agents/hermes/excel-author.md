---
name: excel-author
category: hermes
canonical_source: optional-skills/finance/excel-author/SKILL.md
source_repo: hermes-optional-skill
subsystem: live-optional-skills
recovery_label: DIRECTLY RECOVERED
bucket: canonical
---

# excel-author

**Category:** Hermes-Specific Skills Layer
**Canonical source:** `optional-skills/finance/excel-author/SKILL.md`
**Source repo / subsystem:** `hermes-optional-skill` / `live-optional-skills`

## Description (verbatim frontmatter)

> Build auditable Excel workbooks headless with openpyxl — blue/black/green cell conventions, formulas over hardcodes, named ranges, balance checks, sensitivity tables. Use for financial models, audit outputs, reconciliations.

## Recovery provenance

- Recovered by the AOS Recovery pass on branch `claude/aos-agent-recovery-hermes-jmocw` (2026-05-24).
- Frontmatter `name:` and `description:` extracted via awk from the canonical source.
- See `../../registry/AOS_AGENT_REGISTRY_COMPLETE.md` for the full canonical/alias/mentioned bucket structure.
- See `../../registry/AOS_DUPLICATE_AND_CONFLICT_REPORT.md` for any cross-source variant diffs.

## Activation

Loaded by the top-level `SKILL.md` when the request matches this category. Hermes runtime delegates here via `delegate_task` and persists artifacts under `memory` namespace `aos/council/<slug>/<category>`.
