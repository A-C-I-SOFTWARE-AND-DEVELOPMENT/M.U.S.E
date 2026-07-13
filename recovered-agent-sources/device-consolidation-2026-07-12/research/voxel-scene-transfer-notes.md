# Voxel Scene Transfer Notes

## Source reviewed

A Claude temporary workspace for the deleted Google AI Studio build contained 289 PNG captures, three archives, and assorted scratch output. Most of the large visual set came from `patrix32.zip` (`SHA-256 31A495C2E7041751D6B836B08714FB1253779337626AC369A84EF6AAE2FD8D70`), whose 36,114 archive entries include an `assets/minecraft/` tree.

The captures showed voxel meadows, cliffs, reefs, ice basins, tree settlements, bridges, floating structures, and biome-scale vistas. They were inspected as references but are not retained or activated.

## Why the raw assets were rejected

- The visual language is block-based and stylized, while Atlas Crown requires photoreal, physically scaled, cinematic geometry.
- The archive contains Minecraft-named assets and no verified license suitable for redistribution in M.U.S.E.
- Many captures are iterative debug views with clipping, overdraw, missing surfaces, or extreme exposure.
- Retaining 700 MB of redundant PNG iterations would work against the consolidation goal without improving the production asset library.

## Transferable design lessons

1. **Macro silhouettes first.** A civilization reads from orbit when mountains, megastructures, canopies, and transit lines create a distinct skyline before fine detail appears.
2. **Biome transitions create navigation memory.** Ice, reef, forest, mineral, and settlement zones should have distinct lighting, material response, sound, and landmark grammar.
3. **Vertical traversal makes worlds feel inhabited.** Bridges, elevators, docking spines, canopy routes, and deep shafts should connect visible destinations rather than decorate an inaccessible backdrop.
4. **Landmarks should reveal function.** Ports, energy collectors, archives, habitats, and civic centers need recognizable silhouettes at long range and believable detail up close.
5. **Density needs hierarchy.** Broad terrain masses, medium architectural clusters, and small props must remain legible instead of becoming uniform visual noise.
6. **Atmosphere must preserve depth.** Fog, volumetrics, bloom, and emissive materials should reinforce scale while keeping stereo separation and silhouettes readable.

## Atlas Crown translation

These lessons are translated into original, license-clean PBR environments: metric-scale station sectors, physically plausible transit and docking, civilization-specific material systems, orbital-to-interior continuity, and native stereo depth. No Minecraft or PatriX source asset is part of the active build.
