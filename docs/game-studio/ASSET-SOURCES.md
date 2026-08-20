# Asset + tutorial sources (honest)

This is **not** a dumped 10M-mesh corpus. It is the lookup table the 9 seats
must follow. A LoRA cannot absorb Megascans. Density and beauty come from
licensed kits + engine (World Partition / PCG / Nanite), not from weights.

## Do not pirate

CGTrader / Fab paid packs / Quixel Megascans **meshes** are **not** SFT
material. Do not scrape them into jsonl. Use official APIs / CC0 / CC-BY
as labeled below. Megascans inside a licensed UE project via Fab is OK for
*placement*, not for training-weight redistribution.

## Research 3D corpora (meshes, not game-ready kits)

| Source | What | Format | License | Use here |
|---|---|---|---|---|
| [Objaverse-XL](https://github.com/allenai/objaverse-xl) | 10M+ objects, mixed quality | GLB | **per-object** (filter CC0/CC-BY) | Retrieval / few-shot refs only. Do not ingest 10M. |
| [ABO](https://amazon-berkeley-objects.s3.amazonaws.com/index.html) | 7,953 artist PBR products | glTF 2.0 / GLB | CC BY 4.0 (paper); AWS registry also lists **CC BY-NC 4.0** — treat **NC** as the conservative gate | Archviz props, not nordic kits |
| [Open Source 3D Assets](https://opensource3dassets.com/) | 991+ curated GLB | GLB | CC0 | Small, safe prop pool |
| ShapeNet / 3D-FUTURE | Academic furniture/objects | OBJ / proprietary | research licenses | Skip unless license re-checked |

Objaverse-XL is a **universe**, not a quality bar. Most items are not
Nanite-ready. Always filter license + inspect topology before import.

## Production-quality *materials* (the actual photoreal lever)

| Source | What | License | Use |
|---|---|---|---|
| [Poly Haven](https://polyhaven.com/) | 8K photoscanned PBR + HDRI + some hyperreal models | **CC0** | Terrain, stone, wood, sky. Blender add-on exists. |
| [ambientCG](https://ambientcg.com/) | Large CC0 PBR / HDRI / models | **CC0** | Same. Already in game-studio API toolkit. |
| ShareTextures | PBR + some models | claims copyright-free — **verify per file** | Secondary |

These beat “ultra realistic FBX dumps.” Photoreal in UE is Nanite + PBR +
Lumen, not a 10k unique mesh zip.

## Engine / marketplace (use, do not scrape)

| Source | What | Gate |
|---|---|---|
| [Fab free + Megascans](https://www.unrealengine.com/fabfreecontent) | Photogrammetry plants/rocks/surfaces | Fab / UE license. Place in-editor. Not training data. |
| Quixel Megascans on Fab | Scanned 3D + Megaplants | Same. Official course: [Mastering Megascans](https://dev.epicgames.com/community/learning/paths/yzG/unreal-engine-realityscan-mastering-megascans-a-guide-to-photogrammetry-and-asset-creation) |
| Kenney / Quaternius | Clean CC0 game kits | Good modular, not photoreal |

## Fantasy maps / open world

There is **no** public “Skyrim-quality 37 km² FBX.” Terrain is a heightmap
+ Landscape + PCG, not one mesh. Height sources: Gaea (paid), World Machine,
our `levels/terrain/height.png`, or UE Landmass.

Official UE landscape guide:
https://dev.epicgames.com/documentation/en-us/unreal-engine/landscape-technical-guide-in-unreal-engine

## Tutorial lookup protocol (seats must do this)

When a seat does not know a step, it **looks up** in this order, then cites
the URL in the artifact. It does not invent a pipeline.

1. **Official docs**
   - UE: `site:dev.epicgames.com/documentation <topic>`
   - Blender: `site:docs.blender.org <operator>`
2. **Official learning paths**
   - Megascans / RealityScan path above
   - UE PCG / World Partition docs
3. **Named high-signal tutorials (verify date ≥ 5.3 / Blender 4+)**
   - UE open world / heightmap import: Aziel Arts, [Creating Open World Landscapes](https://www.youtube.com/watch?v=B2f6EoOXRHg)
   - UE PCG + Landmass + Water + WP: Gorka Games, [How to Create an Open World](https://www.youtube.com/watch?v=Uvce5nRrzk8)
   - UE 5.7+ PCG Mode: Procedural Minds, [PCG Mode](https://www.youtube.com/watch?v=IPwVOhvQ2bo)
   - Blender fundamentals / lighting: Blender Guru (donut is lighting, not a world)
4. **web_search query templates**
   - `Unreal Engine 5.8 World Partition import heightmap 4033`
   - `Blender 5.2 export FBX Unreal Nanite grounded pivot`
   - `Poly Haven API download CC0 rock 4k`
   - `Megascans Fab license commercial game`

Stop after one official doc + one dated tutorial. Record both URLs in
`reports/<hold>/lookups.md`.

## What we will actually ingest into LoRA

Only **procedure rows**: license gates, lookup order, refuse piracy, kit-not-unique,
heightmap-not-10k-FBX. Not mesh bytes.

## CC0 2K actually on disk (2026-08-15)

Pulled via Poly Haven API (`https://api.polyhaven.com/files/<id>`), 2K JPG only:

| id | maps | local |
|---|---|---|
| forest_floor | diff / nor_gl / rough | `assets/pbr/forest_floor/` |
| pine_bark | diff / nor_gl / rough | `assets/pbr/pine_bark/` |
| wood_planks_grey | diff / nor_gl / rough | `assets/pbr/wood_planks_grey/` |
| rock_face_03 | diff / nor_gl / rough | `assets/pbr/rock_face_03/` |
| leafy_grass | diff / nor_gl / rough | `assets/pbr/leafy_grass/` |

License: **CC0**. Pages: `https://polyhaven.com/a/<id>`. Not Megascans. Not 8K (disk).

