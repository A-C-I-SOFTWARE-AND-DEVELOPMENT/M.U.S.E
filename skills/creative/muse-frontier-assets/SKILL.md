---
name: muse-frontier-assets
description: Frontier biome and creature asset specs for open worlds.
version: "1.0"
author: MUSE Studio
license: MIT
metadata:
  hermes:
    category: creative
    tags: [game, assets, creatures, biomes, frontier]
---

# MUSE Frontier Assets Skill

Defines frontier open-world biome, creature, terrain, foliage, and mission asset specifications for high-fidelity production.

## When to Use

- Specifying creature-hunting open-world asset requirements
- Building creature manifests with skeletal animation requirements
- Configuring terrain, foliage, water, atmosphere, and VFX per zone

## Prerequisites

- Quality profile selected (`high_fidelity` or `aaa_benchmark`)
- Original IP only — no third-party franchise assets

## How to Run

Use via the AAA pipeline with frontier biomes and creatures:

```python
from agent.studio.aaa_pipeline import run_creature_hunting_pipeline
result = run_creature_hunting_pipeline(Path("output"), offline=True)
```

## Quick Reference

| Spec | Module |
|------|--------|
| Creatures + animations | `agent/studio/creature_specs.py` |
| Terrain/foliage/water/VFX | `agent/studio/world_specs.py` |
| Quality budgets | `agent/studio/quality_profiles.py` |
| World zones + biomes | `agent/studio/manifests.py` |

## Procedure

1. Define creatures and biomes in `AAAPipelineBrief`.
2. Pipeline generates `WorldSystemsManifest` with missions, AI, audio, cinematics.
3. Each creature gets 15 required animation clips.
4. Each zone gets terrain, foliage, water, and atmosphere specs.

## Pitfalls

- Creature manifests missing required animations fail validation.
- Benchmark references describe quality targets, not asset copies.

## Verification

Inspect `manifests/world_systems.json` and `manifests/creatures/` after pipeline run.
