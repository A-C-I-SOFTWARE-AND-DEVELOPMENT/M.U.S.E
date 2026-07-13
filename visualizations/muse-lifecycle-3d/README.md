# MUSE · Workflow Lifecycle — 3D

Interactive 3D visualization of the complete Muse Desktop workflow lifecycle map:
the master prompt→completion pipeline, all 16 catalog workflows (Creative, Research,
Engineering, Design, Planning, Meta), and the 4 universal patterns — **20 flows, 160 nodes**.

## Interactive app
Open **`muse-lifecycle-3d.html`** in any modern browser (double-click — no server needed).

- **Drag** to orbit · **scroll** to zoom · **shift-drag** to pan
- Left menu switches flows (grouped by family); **◀/▶** or arrow keys step through
- **Auto-orbit**, **Flow** (particles), and **Fit view** toggles top-right
- Hover any node for its agent + type
- Glowing billboarded cards, animated flow particles along typed edges, starfield + nebula

Needs internet on first load (Three.js from CDN). The posters below are fully offline.

## Static posters  (`posters/`)
High-res 3D-extruded renders (SVG + 2× PNG) of the hero flows: the master lifecycle,
one per family, and all four patterns.

## Data
`flows.json` — the structured flow-graph model (nodes, edges, families, branches, loops)
extracted from the lifecycle map. The app and posters are both generated from it, so
editing it updates both.

Node types: entry · classify · plan · agent · research · review · gate · tool · output · done · fail · compensate
Edge kinds: flow · branch · loop · compensate
