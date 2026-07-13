# Atlas Crown Desktop Visual Acceptance

Date: 2026-07-12
Owner: Desktop UI stream
Status: implementation inspected; runtime visual acceptance deferred by explicit owner constraint

## Acceptance boundary

This record covers the Atlas desktop implementation under `apps/desktop/ui`. The owner explicitly prohibited tests, linters, typecheckers, builds, gates, dev servers, and browser automation. Accordingly:

- No dev server was started.
- No route was rendered in a browser or desktop webview.
- No screenshots were captured.
- The 1440 x 900 and 390 x 844 viewport passes were not run.
- Keyboard-only, reduced-motion, forced-offline, denied, empty, conflict, and WebGL-disabled browser passes were not run.
- No runtime claim below should be interpreted as browser-verified.

The acceptance method for this stream was source inspection, route/catalog comparison, static spec-test authoring without execution, and a final `git diff --check` only.

## Source-inspection acceptance

| Area | Inspection result | Runtime status |
|---|---|---|
| Navigation | Atlas Crown, Stations, Shipyard, Fleet, Agents, Civilizations, Fabrication, Game Foundry, Cinema Stage, Release Dock, Observatory, and all legacy interiors are registered; primary destinations are present in desktop and mobile navigation. | Not rendered |
| Truth state | Universe state is bearer-authenticated, credential-omitting, cursor-resuming, abortable, and represented as idle, loading, online, empty, offline, denied, conflict, degraded, or error. No local sample entities are seeded. | Not connected to a live gateway |
| Atlas Crown | Original procedural command spine, luminous Neural Core, counter-rotating habitats, five sector arcs, docking assemblies, radiators, windows, and antenna structures are implemented. | Not visually reviewed |
| Celestial field | Deterministic stars, dust, volumetric nebulae, and comets use fidelity budgets; reduced motion removes drift, dust, and comets. | Performance not measured |
| Station interiors | Selected station routes resolve to their functional room instead of a generic station shell. | Not visually reviewed |
| Neural Core | 3D and semantic DOM use the same authenticated Universe snapshot and explicit edge list. Spatial proximity never creates an edge. | Not visually reviewed |
| Vessels | Nine class silhouettes, reported agent bindings, exterior/interior scenes, airlock boarding, player modes, cosmetic-only customization, and simulation-labelled test flights are represented. Unreported rooms remain unavailable. | Not visually reviewed |
| Production | Fabrication, 28-lane Game Foundry, physical native-stereo Cinema Stage, and Release Dock expose evidence rather than synthetic progress. Missing backend records remain unavailable. | No production provider exercised |
| Accessibility | Canvas is presentation-only; route summaries, station buttons, graph tree, vessel controls, focus indicators, safe areas, forced colors, contrast, reduced motion, text scale, color-safe cues, and 2D-only mode are present in source. | Assistive technology not exercised |
| Resilience | WebGL loss dispatches a 2D-only fallback; stale snapshots retain timestamps; denied state hides operational content; conflict refresh preserves the draft path. | Failure injection not run |
| Diagnostics | Fidelity tier, DPR, moving frame time, draw calls, triangles, texture estimate, graph count, cursor, and degraded reasons are exposed. | Values not measured |

## Route interior matrix

| Route group | Implemented interior or surface |
|---|---|
| `/atlas`, `/`, `/chat` | Atlas Crown command bridge and Neural Core context |
| `/stations`, `/stations/:stationId` | Celestial directory plus functional station room resolution |
| `/shipyard`, `/fleet`, `/agents` | Shipyard, vessel exterior, and boardable vessel interior |
| `/observatory`, `/models`, `/second-brain`, `/activity` | Shared Neural Core graph, sensor laboratory, memory vault, and evidence surfaces |
| `/civilizations`, `/federation`, `/council`, `/championship` | Relay Embassy, governance chamber, and crew observation |
| `/fabrication`, `/game-foundry`, `/cinema`, `/release`, `/studio`, `/forge` | Fabrication bay, Game Foundry, Cinema Array, Release Dock, and Production Command |
| `/console`, `/steer`, `/axiom`, `/fusion`, `/repo`, `/share`, `/settings`, `/signin` | Command bridge, neural chamber, security airlock, blueprint exchange, relay, engineering, and identity boundaries |

## Operational truth findings

- A configured URL, saved provider key, stored credential, or configured add-on is not labelled as connected.
- Gateway-only actions are disabled until the health monitor reports `gateway`.
- Chat routes remain unverified until a gateway probe or completion succeeds.
- Game packages are not labelled playable without both backend `playable=true` and passed engine validation.
- Cinema masters require passed QC, exactly two camera identifiers, a settings hash, and deliverable checksums.
- Release state reads directly from the reported release record; failed publication never becomes live in the UI.
- The current backend does not expose a Shipyard `/validate` route or dedicated Fabrication, Game, Cinema, and Release production APIs. Their controls remain unavailable or evidence-only rather than simulating success.

## Deferred runtime acceptance

The following remain open until the owner authorizes runtime verification:

1. Capture 1440 x 900 and 390 x 844 screenshots for every route.
2. Verify keyboard order, visible focus, screen-reader names, and zoom/text scaling.
3. Inject offline, 401/403, 409, 429, 5xx, empty snapshot, stale snapshot, and WebGL-loss conditions.
4. Measure frame time, draw calls, triangle count, GPU memory behavior, thermal behavior, and tier transitions.
5. Inspect real aerospace materials, exposure, nebula density, room framing, overflow, and safe-area behavior in the desktop webview.
6. Run the authored static specs, TypeScript validation, and production build when the prohibition is lifted.

## Verification log

| Check | Result |
|---|---|
| Source inspection | Completed |
| Static specification files authored | Completed, not executed |
| `git diff --check` | Passed for scoped tracked files and no-index untracked files |
| Tests / lint / typecheck / build / gates | Not run by owner instruction |
| Dev server / browser / screenshots | Not run by owner instruction |
