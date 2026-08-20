# Status — keep-going pass (verified vs remaining)

## Verified this pass
- 27B sequential curl **still live**: `base/Qwen3.8-27B-UD-Q3_K_XL.gguf` growing (one stream, HF token)
- Province height **4033² @ 1.5 m/px ≈ 36.6 km²** — `levels/terrain/height.png` + `layout.png` + `height.npy`
- **13,856** T_place rows (`levels/terrain/T_place.json`) — 30 heroes, rest instanced kits
- Hearthhold crop + 1813 placed in Blender; **0 missed ground rays**
- Contact still: `reports/r_hearth/contact.png` (1600×900). Brightness mid, edges present, no purple
- `SkyrimClass.uproject` EngineAssociation set to **5.8**; prefab height copied to `UnrealProjects/SkyrimClass/Saved/Heightmap_4033.png`
- `build_world.py` will use that prefab (skips hour-long in-editor fBm)

## Visual truth (not Skyrim)
The still is **greybox cones + boxes** on a flattened capital pad. Contact PASS. Beauty FAIL.
SkyrimClass has 6,865 **JSON** content objects and **zero** `.umap` landscapes.

## Remaining for Skyrim-class
1. 27B GGUF + mmproj complete + hole-check + hardlink
2. UE Landscape import + World Partition + PCG (editor job started)
3. Authored/Nanite kits, not cones
4. Cleared streets (buildings not buried in pines)
5. Packaged `.exe` loads a populated cell
6. Adapter seats still not reliable (smoke was junk)

A LoRA will never emit this world. Density is the engine.
