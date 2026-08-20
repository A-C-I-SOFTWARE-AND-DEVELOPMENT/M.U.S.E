# Guide ledger (allowlist)

Only these ranks may be used. If a search hit is not on this list or
does not match a `query` template + date gate, **refuse**.

Date gate: Unreal **≥ 5.3**, Blender **≥ 4.0**, or official current docs.
Prefer 2024–2026.

## Rank 0 — official (always first)

| id | task | title | url |
|---|---|---|---|
| blender-fbx | fbx-ue | Blender FBX exporter | https://docs.blender.org/manual/en/latest/addons/import_export/scene_fbx.html |
| blender-bevel | blender-kit | Bevel modifier | https://docs.blender.org/manual/en/latest/modeling/modifiers/generate/bevel.html |
| blender-extrude | blender-kit | Extrude | https://docs.blender.org/manual/en/latest/modeling/meshes/editing/mesh/extrude.html |
| blender-uv | blender-kit | UV unwrapping | https://docs.blender.org/manual/en/latest/modeling/meshes/uv/unwrapping.html |
| blender-shade | blender-kit | Auto Smooth / sharp | https://docs.blender.org/manual/en/latest/modeling/meshes/editing/face/shade_smooth.html |
| polyhaven-api | pbr | Poly Haven files API | https://polyhaven.com/our-api |
| ambientcg | pbr | ambientCG | https://ambientcg.com/ |
| ue-landscape | landscape | Landscape Technical Guide | https://dev.epicgames.com/documentation/en-us/unreal-engine/landscape-technical-guide-in-unreal-engine |
| ue-nanite | fbx-ue | Nanite virtualized geometry | https://dev.epicgames.com/documentation/en-us/unreal-engine/nanite-virtualized-geometry-in-unreal-engine |
| ue-pcg | pcg | Procedural Content Generation | https://dev.epicgames.com/documentation/en-us/unreal-engine/procedural-content-generation-overview |
| ue-wp | landscape | World Partition | https://dev.epicgames.com/documentation/en-us/unreal-engine/world-partition-in-unreal-engine |
| ue-megascans | pbr | Mastering Megascans (place, do not scrape) | https://dev.epicgames.com/community/learning/paths/yzG/unreal-engine-realityscan-mastering-megascans-a-guide-to-photogrammetry-and-asset-creation |

## Rank 1 — dated high-signal (one only)

| id | task | title | url | why |
|---|---|---|---|---|
| aziel-landscape | landscape | Aziel Arts — Open World Landscapes | https://www.youtube.com/watch?v=B2f6EoOXRHg | Heightmap + WP, named in prior pass |
| gorka-openworld | pcg | Gorka Games — Open World PCG+Landmass+Water+WP | https://www.youtube.com/watch?v=Uvce5nRrzk8 | Full stack, dated 5.x |
| pcg-mode | pcg | Procedural Minds — PCG Mode 5.7+ | https://www.youtube.com/watch?v=IPwVOhvQ2bo | Current PCG Mode |
| grant-game-assets | blender-kit | Grant Abbitt — Blender game assets (search latest ≥4.0) | https://www.youtube.com/@grantabbitt | Step-by-step game kits, not cinematic flex |
| default-cube-hard | blender-kit | Default Cube — hard-surface / bevels | https://www.youtube.com/@DefaultCube | Support loops, not boxy boolean sludge |
| blender-guru-pbr | pbr | Blender Guru — PBR / lighting (not a world) | https://www.youtube.com/@blenderguru | Material truth, not Skyrim |
| cgcookie-fund | blender-kit | CG Cookie fundamentals | https://www.youtube.com/@CGCookie | Numbered lessons |

## Rank 2 — refuse (never follow)

- "Blender in 60 seconds", "10 minute AAA asset", shorts with no date
- AI text-to-3D flex with no retopo / UV / PBR steps
- Purple/indigo/violet look-dev as a style guide
- 2.79 / 2.8 hotkey videos used as 5.2 truth
- Paid FlippedNormals / Gnomon *as scraped SFT* (may cite, may not dump)
- CGTrader / Fab mesh dumps into jsonl

## Query templates (if ledger miss)

```
site:docs.blender.org bevel modifier game asset
site:dev.epicgames.com/documentation Nanite Static Mesh import
Blender 4.2 unwrap texel density game asset 2025
Unreal Engine 5.5 FBX import Nanite grounded pivot
Poly Haven API download 2K diff nor rough
```

After one official + one tutorial, **stop searching**.
