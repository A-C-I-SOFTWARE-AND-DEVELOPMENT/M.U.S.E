---
name: enterprise-finance
category: hermes
canonical_source: recovered-agent-sources/from-hermes-agent/enterprise-council/finance/SKILL.md
source_repo: recovered-hermes-skill
subsystem: snapshot-skills
recovery_label: DIRECTLY RECOVERED
bucket: canonical
---

# enterprise-finance

**Category:** Hermes-Specific Skills Layer
**Canonical source:** `recovered-agent-sources/from-hermes-agent/enterprise-council/finance/SKILL.md`
**Source repo / subsystem:** `recovered-hermes-skill` / `snapshot-skills`

## Description (verbatim frontmatter)

> Finance leaf: invoicing, budgeting, reporting against Stripe/NetSuite/QuickBooks.

## Aliases (other sources defining the same `name:`)

- `skills/enterprise-council/finance/SKILL.md` — `hermes-skill` / `live-skills`

## Recovery provenance

- Recovered by the AOS Recovery pass on branch `claude/aos-agent-recovery-hermes-jmocw` (2026-05-24).
- Frontmatter `name:` and `description:` extracted via awk from the canonical source.
- See `../../registry/AOS_AGENT_REGISTRY_COMPLETE.md` for the full canonical/alias/mentioned bucket structure.
- See `../../registry/AOS_DUPLICATE_AND_CONFLICT_REPORT.md` for any cross-source variant diffs.

## Activation

Loaded by the top-level `SKILL.md` when the request matches this category. Hermes runtime delegates here via `delegate_task` and persists artifacts under `memory` namespace `aos/council/<slug>/<category>`.
