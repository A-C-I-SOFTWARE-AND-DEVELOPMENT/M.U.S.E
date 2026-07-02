# M.U.S.E — Interactive 3D Systems Atlas

An **interactive, ultra-HD 3D model of M.U.S.E and all its systems**, plus an
animated **"first prompt → fully built product"** pipeline you can play and watch.

It renders the whole architecture as a luminous *synaptic tower*: twelve stacked
plane-rings (surfaces, command center, the governance safety spine, orchestration,
cognition, model routing, the capability layer, self-improvement, the AXIOM
verification kernel, federation, supporting fabric and the execution substrate),
each carrying its component nodes around a central spine, with the MUSE core at
the apex and the shipped product at the base.

## Use it

It is a static page — **no build step, no server required** (Three.js is vendored
locally, no CDN).

- **Open directly:** open `index.html` in any modern browser, or
- **Serve the folder** (recommended, avoids `file://` module quirks):

  ```bash
  npx http-server docs/3d-model -p 8123 -c-1
  # then visit http://127.0.0.1:8123/
  ```

When published to GitHub Pages alongside the rest of the site it lives at
`…/M.U.S.E/atlas/`.

## Interactions

| Action | Result |
|---|---|
| **Drag** | orbit the camera around the tower |
| **Scroll / pinch** | zoom |
| **Right-drag** | pan |
| **Hover a node** | name tooltip + highlight |
| **Click a node** | detail panel (description, tags, owner-gated badge) + fly-in |
| **Click a plane** in the legend | focus that plane |
| **▶ Play the build** (or **Space**) | animate a prompt becoming a finished product |
| **⟲ Reset / ⤢ Overview** (or **R**) | frame the whole model |
| **↻ Auto-rotate · 🏷 Labels** | toggles |

Owner-gated components wear a crimson halo, matching the architecture PDF.

## How it stays in sync

Both this model and the architecture PDF are generated from **one source**:
[`scripts/diagrams/build_muse_flowchart.py`](../../scripts/diagrams/build_muse_flowchart.py).
Running it (re)writes `architecture_data.js` / `architecture_data.json` here from
the same plane/component model the PDF uses, so the 3D atlas reflects repository
changes whenever the generator runs:

```bash
python3 scripts/diagrams/build_muse_flowchart.py
```

A CI check (`.github/workflows/muse-3d-atlas.yml`) regenerates the data and fails
if the committed files have drifted, so the model can never silently fall out of
sync with the documented architecture.

## One portable file (open by double-click)

To get the whole atlas as a single self-contained `.html` (three.js, app, styles
and data all inlined — no server, no network):

```bash
python3 scripts/diagrams/build_muse_flowchart.py        # refresh the data
node   scripts/diagrams/bundle_atlas_singlefile.mjs      # -> docs/_generated/flowchart/MUSE_3D_Systems_Atlas.html
```

The output opens in any browser by double-clicking. (Uses the esbuild already
vendored under `apps/nexus/node_modules`.)

## Files

- `index.html` — page shell + cockpit HUD
- `app.js` — the Three.js scene, orbit rig, interactions and the build animation
- `style.css` — the dark cockpit UI
- `architecture_data.js` / `.json` — **generated** component + pipeline data
- `vendor/` — three.js, vendored locally (MIT, copied from the cockpit Observatory)

> Conceptual only — like the PDF, the atlas shows *what each system does*, with no
> filenames and no source code.
