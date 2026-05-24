---
name: ocr-and-documents
category: hermes
canonical_source: skills/productivity/ocr-and-documents/SKILL.md
source_repo: hermes-skill
subsystem: live-skills
recovery_label: DIRECTLY RECOVERED
bucket: canonical
---

# ocr-and-documents

**Category:** Hermes-Specific Skills Layer
**Canonical source:** `skills/productivity/ocr-and-documents/SKILL.md`
**Source repo / subsystem:** `hermes-skill` / `live-skills`

## Description (verbatim frontmatter)

> Extract text from PDFs/scans (pymupdf, marker-pdf).

## Recovery provenance

- Recovered by the AOS Recovery pass on branch `claude/aos-agent-recovery-hermes-jmocw` (2026-05-24).
- Frontmatter `name:` and `description:` extracted via awk from the canonical source.
- See `../../registry/AOS_AGENT_REGISTRY_COMPLETE.md` for the full canonical/alias/mentioned bucket structure.
- See `../../registry/AOS_DUPLICATE_AND_CONFLICT_REPORT.md` for any cross-source variant diffs.

## Activation

Loaded by the top-level `SKILL.md` when the request matches this category. Hermes runtime delegates here via `delegate_task` and persists artifacts under `memory` namespace `aos/council/<slug>/<category>`.
