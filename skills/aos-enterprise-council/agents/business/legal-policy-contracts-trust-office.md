---
name: legal-policy-contracts-trust-office
category: business
canonical_source: recovered-agent-sources/from-hazmat-command/agents/legal-policy-contracts-trust-office.md
source_repo: hazmat-agent
subsystem: snapshot-agents
recovery_label: DIRECTLY RECOVERED
bucket: canonical
---

# legal-policy-contracts-trust-office

**Category:** Business / Commercial / Legal Layer
**Canonical source:** `recovered-agent-sources/from-hazmat-command/agents/legal-policy-contracts-trust-office.md`
**Source repo / subsystem:** `hazmat-agent` / `snapshot-agents`

## Description (verbatim frontmatter)

> Use only for legal, policy, trust, and contractual artifacts (ToS, Privacy, NDA, MSA, SOW, DPA, Pilot Agreement, Security Addendum, sub-processor list, retention policy, store disclosures, trust portal copy). Every output is a counsel-review draft...

## Recovery provenance

- Recovered by the AOS Recovery pass on branch `claude/aos-agent-recovery-hermes-jmocw` (2026-05-24).
- Frontmatter `name:` and `description:` extracted via awk from the canonical source.
- See `../../registry/AOS_AGENT_REGISTRY_COMPLETE.md` for the full canonical/alias/mentioned bucket structure.
- See `../../registry/AOS_DUPLICATE_AND_CONFLICT_REPORT.md` for any cross-source variant diffs.

## Activation

Loaded by the top-level `SKILL.md` when the request matches this category. Hermes runtime delegates here via `delegate_task` and persists artifacts under `memory` namespace `aos/council/<slug>/<category>`.
