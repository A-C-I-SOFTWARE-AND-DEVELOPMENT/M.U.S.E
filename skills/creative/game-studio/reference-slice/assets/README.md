# Assets — the generated-asset slot

`prop.glb` is a **placeholder** hero prop (a minimal valid glТF triangle,
generated locally — no third-party content, no license obligations). It marks
the slot that the Game Studio `3d-asset-artist` role fills via the
`asset3d_generate` tool (Meshy / Hunyuan3D backend).

## How it's wired

`scripts/player.gd` → `_try_load_generated_prop()` loads `res://assets/prop.glb`
at runtime and parents it under the `HeroProp` node, **defensively**: if the file
is missing or not importable, the built-in placeholder box stays, so the slice
always runs. This keeps the headless export dependency-free while still
demonstrating the asset-generation integration point.

## Replacing it with a generated asset

1. `3d-asset-artist` calls `asset3d_generate` with a prompt (e.g. "weathered
   sci-fi supply crate, PBR, game-ready").
2. The tool returns `{ "mesh": "<path>.glb", "textures": [...], "est_cost_usd": ... }`.
3. Surface `est_cost_usd` to the owner before bulk generation (owner gate).
4. Copy the returned `.glb` over `assets/prop.glb` and record provenance below.

## Provenance / licensing

| File | Source | License |
|---|---|---|
| `prop.glb` | Generated locally by `scripts`-equivalent (placeholder triangle) | Original / public-domain placeholder |

Any third-party or AI-generated asset added here requires owner licensing
sign-off; record it in this table.
