# Atlas Crown source assets

This directory contains the original, renderer-neutral source contract for the
M.U.S.E. Atlas Crown and the multi-role agent flagship. The design is authored
in metric OpenUSD (`metersPerUnit = 1`) with local MaterialX 1.38 looks. No
binary mesh, external texture URL, franchise geometry, trademarked silhouette,
or third-party model is included. The visual contract is photoreal,
non-cartoony aerospace construction: restrained coatings, pressure-vessel
logic, service hardware, scale cues, wear, and repair marks carry the design.

## Canonical dimensions

| Assembly | Source dimension |
|---|---:|
| Neural Core stationary sphere | 210 m diameter |
| Non-rotating axial spine | 1,800 m length |
| Crown Ring A | 1,200 m diameter, +0.25 deg/s |
| Crown Ring B | 1,200 m diameter, -0.25 deg/s |
| Dock/navigation keep-out | 12 m minimum local clearance |
| Agent flagship | 148 m length, 42 m beam, 28 m height |

The station rings are equal and counter-rotating. Docking collars, the axial
spine, the Neural Core, radiators, and approach corridors remain stationary.
Transfer uses sealed bearings and radial lifts. Exterior and interior flagship
airlock transforms are identical by contract.

## Fidelity and depth tiers

The USD `lod` variants describe source, interactive, and proxy budgets. They
are renderer-neutral declarations, not claims that an importer has met a frame
budget.

| Tier | Geometry source | Depth/lighting intent | Target evidence |
|---|---|---|---|
| Cinema | `source` | path-traced solar key, planetary bounce, native stereo | UE MRQ render + stereo QC |
| Ultra/High | `interactive` | full silhouette, Lumen/ray features when supported | packaged UE benchmark |
| Balanced | `interactive` plus HLOD | simplified volumetrics, full station identity | packaged UE benchmark |
| Accessible 2D | cached derivative | no forced motion or spatial navigation | Desktop keyboard/2D acceptance |
| Collision/navigation | `proxy` | non-rendered simple proxies | UE collision/nav validation |

Suggested budgets are 2.4 M source triangles / 480 k interactive / 18 k proxy
for Atlas Crown and 900 k / 180 k / 12 k for the flagship. These are authoring
ceilings. Measured frame time, draw calls, triangles, load time, and memory stay
open until a UE 5.6 packaged build is profiled on target hardware.

## Material intent

`materials/atlas-hull.mtlx` defines restrained brushed alloy, layered composite,
thermal blanket, repair marking, and procedural micrometeor-wear concepts.
`materials/optical-core.mtlx` defines optical glass, the Neural Core shell, and
bounded navigation emission. Values stay in physically plausible metalness,
roughness, IOR, transmission, and emission ranges. Importers may translate the
graphs to native UE materials while retaining the material IDs and provenance.

## Import and validation

- Open the USDA through an OpenUSD stage/importer with Z-up and authored meters.
- Convert meters to Unreal centimeters exactly once at the runtime boundary.
- Bind the MaterialX IDs or reviewed native equivalents; do not invent external
  texture dependencies during import.
- Keep proxy-purpose prims out of beauty renders and use them for collision,
  HLOD, navigation, and streaming bounds.
- Run `python assets/atlas-crown/validate_assets.py --check` after any source
  edit. The command is a future verification instruction; it was not executed
  during the source-only authoring stream.

`provenance.json` is the machine-readable license and hash manifest. Public use
must preserve that file and re-run rights/performance verification for any
derivative. M.U.S.E. does not claim IMAX certification or third-party approval.
