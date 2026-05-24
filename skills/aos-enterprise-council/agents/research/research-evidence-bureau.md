---
name: research-evidence-bureau
category: research
canonical_source: recovered-agent-sources/from-hazmat-command/agents/research-evidence-bureau.md
source_repo: hazmat-agent
subsystem: snapshot-agents
recovery_label: DIRECTLY RECOVERED
bucket: canonical
---

# research-evidence-bureau

**Category:** Research / Evidence Layer
**Canonical source:** `recovered-agent-sources/from-hazmat-command/agents/research-evidence-bureau.md`
**Source repo / subsystem:** `hazmat-agent` / `snapshot-agents`

## Description (verbatim frontmatter)

> Read-only research and evidence agent. Use whenever a task requires verifying an external standard (49 CFR, TDG, NIST SP, OWASP, ISO 27001, vendor documentation), comparing claims to sources, building a research dossier, or detecting source contra...

## Recovery provenance

- Recovered by the AOS Recovery pass on branch `claude/aos-agent-recovery-hermes-jmocw` (2026-05-24).
- Frontmatter `name:` and `description:` extracted via awk from the canonical source.
- See `../../registry/AOS_AGENT_REGISTRY_COMPLETE.md` for the full canonical/alias/mentioned bucket structure.
- See `../../registry/AOS_DUPLICATE_AND_CONFLICT_REPORT.md` for any cross-source variant diffs.

## Activation

Loaded by the top-level `SKILL.md` when the request matches this category. Hermes runtime delegates here via `delegate_task` and persists artifacts under `memory` namespace `aos/council/<slug>/<category>`.
