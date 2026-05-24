---
name: product-pilot-experience-studio
category: ux
canonical_source: recovered-agent-sources/from-hazmat-command/agents/product-pilot-experience-studio.md
source_repo: hazmat-agent
subsystem: snapshot-agents
recovery_label: DIRECTLY RECOVERED
bucket: canonical
---

# product-pilot-experience-studio

**Category:** UX Layer (Product & Pilot Studio)
**Canonical source:** `recovered-agent-sources/from-hazmat-command/agents/product-pilot-experience-studio.md`
**Source repo / subsystem:** `hazmat-agent` / `snapshot-agents`

## Description (verbatim frontmatter)

> Use when a request is about user experience, founder demo, pilot/customer walkthrough, onboarding clarity, or visual presentation flow. Reviews PRDs, demo scripts, pilot readiness reports, and onboarding artifacts. Optimizes for clarity in front o...

## Recovery provenance

- Recovered by the AOS Recovery pass on branch `claude/aos-agent-recovery-hermes-jmocw` (2026-05-24).
- Frontmatter `name:` and `description:` extracted via awk from the canonical source.
- See `../../registry/AOS_AGENT_REGISTRY_COMPLETE.md` for the full canonical/alias/mentioned bucket structure.
- See `../../registry/AOS_DUPLICATE_AND_CONFLICT_REPORT.md` for any cross-source variant diffs.

## Activation

Loaded by the top-level `SKILL.md` when the request matches this category. Hermes runtime delegates here via `delegate_task` and persists artifacts under `memory` namespace `aos/council/<slug>/<category>`.
