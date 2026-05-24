---
name: commercial-strategy-growth-office
category: business
canonical_source: recovered-agent-sources/from-hazmat-command/agents/commercial-strategy-growth-office.md
source_repo: hazmat-agent
subsystem: snapshot-agents
recovery_label: DIRECTLY RECOVERED
bucket: canonical
---

# commercial-strategy-growth-office

**Category:** Business / Commercial / Legal Layer
**Canonical source:** `recovered-agent-sources/from-hazmat-command/agents/commercial-strategy-growth-office.md`
**Source repo / subsystem:** `hazmat-agent` / `snapshot-agents`

## Description (verbatim frontmatter)

> Use only for pricing, packaging, positioning, claims, GTM messaging, competitor positioning, RFP answer drafting. Does NOT write product code. Activated whenever externally-visible commercial copy or pricing changes. Every claim it produces must b...

## Recovery provenance

- Recovered by the AOS Recovery pass on branch `claude/aos-agent-recovery-hermes-jmocw` (2026-05-24).
- Frontmatter `name:` and `description:` extracted via awk from the canonical source.
- See `../../registry/AOS_AGENT_REGISTRY_COMPLETE.md` for the full canonical/alias/mentioned bucket structure.
- See `../../registry/AOS_DUPLICATE_AND_CONFLICT_REPORT.md` for any cross-source variant diffs.

## Activation

Loaded by the top-level `SKILL.md` when the request matches this category. Hermes runtime delegates here via `delegate_task` and persists artifacts under `memory` namespace `aos/council/<slug>/<category>`.
