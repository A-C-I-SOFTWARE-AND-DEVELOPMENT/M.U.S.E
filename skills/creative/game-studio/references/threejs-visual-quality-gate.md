# Three.js web game — visual quality gate (FAIL/PASS)

When the brief says **hyper-fidelity**, **3D**, **super visuals**, or **Three.js / 3js**,
this gate is **mandatory**. A Vite build that exits 0 is **not** success.

## Instant FAIL (reject and rebuild — do not ship)

1. Obstacles / enemies rendered as `CircleGeometry` / flat discs / color blobs
2. `MeshBasicMaterial` as the primary look (no lights, no PBR)
3. Camera sitting on +Z looking at XY like a 2D canvas (`position.set(0,0,10)`)
4. Empty `assets/` folders with no meshes/textures while claiming "sprites and assets"
5. Comic Sans / default system UI for a branded game HUD
6. Missing: shadows, fog, ACES/tone mapping, hemisphere + sun lights
7. Named characters (tractor, teacher, stairs…) that are indistinguishable colored primitives
8. **Runtime crash / blank canvas** — any uncaught `ReferenceError` / `TypeError` in boot, or WebGL canvas with no drawable scene
9. **Class field without `this.`** — e.g. `laneWidth` inside a method when the field is `this.laneWidth` (ships as white screen)
10. **Uncapped first-frame `deltaTime`** — `lastTime = 0` then `(time - 0) / 1000` → gravity yeets the player / instant game-over
11. Claiming **PASS** without loading the page and confirming **zero console errors**

## PASS requirements (Three.js endless Frogger-class)

1. **Perspective camera** above the playfield looking down/forward (classic 3D Frogger angle), not orthographic XY
2. **MeshStandardMaterial / MeshPhysicalMaterial** + real lights (`HemisphereLight` + `DirectionalLight` with `castShadow`)
3. Renderer: `antialias`, `shadowMap.enabled`, `SRGBColorSpace`, `ACESFilmicToneMapping`
4. Player wheelchair = **composed 3D group** (seat, back, torus/cylinder wheels, caster) — not flat circles
5. Each obstacle type = **distinct 3D silhouette** (boxes/capsules/cones/cylinders grouped), readable at distance
6. Lemons = yellow **ellipsoid / sphere with slight squash**, emissive hint OK
7. World = ground plane + alternating road/grass **lanes along depth (Z)** — `BoxGeometry(laneWidth, height, laneLength)` with length on **Z**, not swapped axes
8. UI: intentional web fonts (not Comic Sans), HUD readable on dark/light
9. Game loop: `lastTime = performance.now()` before first frame; **cap** `deltaTime` (e.g. `<= 0.05`); ground clamp so player does not fall through
10. Ship only after **all** of:
    - `npm run build` exit 0
    - `npm run dev` page loads
    - browser console has **no** errors
    - self-critique against every FAIL item above

## Shell (Windows Hermes)

- Terminal is **bash**. Never `cd /d`. Use `cd "C:/Users/..."` 
- Prefer small module files (<80 lines) for `write_file` / Set-Content to avoid truncated tool JSON

## Routing

For "hyper-fidelity 3js game": do **not** collapse to Godot stub pipeline. Ship a playable Three.js vertical slice that passes this gate.
