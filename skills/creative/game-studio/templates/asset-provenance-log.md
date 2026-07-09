# Asset Provenance & Licensing Log — <TITLE>

> Owned by `3d-asset-artist` / `audio-designer`. Backs the **asset-licensing
> owner gate**: any third-party or AI-generated asset requires owner sign-off
> recorded here before it ships in a build.

| Asset | Type | Source / tool | Prompt or origin | License | Owner-approved | Notes |
|---|---|---|---|---|---|---|
| `assets/prop.glb` | mesh | local placeholder | — | original / public-domain | n/a | slot for generated hero prop |
| | | `asset3d_generate` (meshy) | "<prompt>" | per Meshy ToS | ☐ | est_cost_usd: <x> |
| | | `comfyui` | "<prompt>" | model license | ☐ | |

## Rules
- AI-generated assets: confirm the backend's commercial-use terms; record the
  exact prompt and the model.
- Third-party/marketplace assets: store the license file path and seat count.
- Nothing in this table ships in a published build until **Owner-approved = ✔**.
