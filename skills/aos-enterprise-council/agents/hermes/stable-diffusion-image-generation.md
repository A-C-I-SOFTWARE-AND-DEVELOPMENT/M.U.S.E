---
name: stable-diffusion-image-generation
category: hermes
canonical_source: optional-skills/mlops/stable-diffusion/SKILL.md
source_repo: hermes-optional-skill
subsystem: live-optional-skills
recovery_label: DIRECTLY RECOVERED
bucket: canonical
---

# stable-diffusion-image-generation

**Category:** Hermes-Specific Skills Layer
**Canonical source:** `optional-skills/mlops/stable-diffusion/SKILL.md`
**Source repo / subsystem:** `hermes-optional-skill` / `live-optional-skills`

## Description (verbatim frontmatter)

> State-of-the-art text-to-image generation with Stable Diffusion models via HuggingFace Diffusers. Use when generating images from text prompts, performing image-to-image translation, inpainting, or building custom diffusion pipelines.

## Recovery provenance

- Recovered by the AOS Recovery pass on branch `claude/aos-agent-recovery-hermes-jmocw` (2026-05-24).
- Frontmatter `name:` and `description:` extracted via awk from the canonical source.
- See `../../registry/AOS_AGENT_REGISTRY_COMPLETE.md` for the full canonical/alias/mentioned bucket structure.
- See `../../registry/AOS_DUPLICATE_AND_CONFLICT_REPORT.md` for any cross-source variant diffs.

## Activation

Loaded by the top-level `SKILL.md` when the request matches this category. Hermes runtime delegates here via `delegate_task` and persists artifacts under `memory` namespace `aos/council/<slug>/<category>`.
