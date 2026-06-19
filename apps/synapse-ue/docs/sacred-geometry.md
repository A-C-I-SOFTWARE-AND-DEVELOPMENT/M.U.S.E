# Sacred-geometry galaxy renderer (`SynapseObservatoryRender`)

`SynapseObservatoryRender` is the Phase-3 render layer the data-plane module
(`SynapseObservatory`) deliberately deferred — *"the galaxy ISM renderer,
station-spline Niagara packets … that bind to this subsystem's delegates."* It
arranges the gateway-supplied Neural Observatory nodes onto **closed-form
sacred-geometry frameworks** and animates regular 4-polytopes in 4D.

```
UObservatorySubsystem (data)  ──delegates──▶  SynapseObservatoryRender
   OnSnapshot / OnLayout                          AObservatoryGalaxyActor (ISM field)
   OnGateVerdict / OnNodeActivate                 UObservatoryValidationViz (gate flares)
   OnJobStage                                     UObservatoryFlowComponent (spline/Niagara)
                                                  └─ math: SynapseCore/MuseSacredGeometry
```

**Design law preserved.** This module runs **no networking and no
force-directed physics**. Gateway positions still come from the gateway; the
sacred-geometry placement is closed-form (O(n) over the ≤200 clusters) and the
only per-tick work is a 4×4 4D rotation + projection of the active polytope,
applied as a single bulk ISM transform update (never per-frame instance
add/remove — the documented UE5 instancing gotcha).

## Geometry kernel — `SynapseCore/MuseSacredGeometry.h`

Pure, engine-light closed-form generators (CoreMinimal + FMath only). Numeric
ground truth and the validation checklist live in
[`tools/sacred_geometry_reference.py`](../tools/sacred_geometry_reference.py),
which is **runnable in CI / the authoring container** (where UE is not
installed); the C++ and the UE automation suite `Synapse.Geometry.*` reproduce
exactly the values it prints.

| Generator | Returns | Notes |
|---|---|---|
| `GoldenAngleRadians/Degrees`, `Phi` | `double` | golden angle = `pi*(3-sqrt5)` = `2*pi/phi^2` = **137.50776405°** |
| `VogelPhyllotaxis(N)` | `TArray<FVector2D>` | sunflower disk `r=sqrt(i), theta=i*golden` |
| `FibonacciSphere(N)` | `TArray<FVector>` | near-uniform unit-sphere shell |
| `PlatonicVertices(Solid)` | `TArray<FVector>` | exact; counts 4 / 8 / 6 / 12 / 20 |
| `PolytopeVertices(Polytope)` | `TArray<FVector4>` | exact; counts **5 / 8 / 16 / 24 / 120 / 600** |
| `Rotate4D(P, Plane, Angle)` | `FVector4` | one of the 6 planes `XY XZ XW YZ YW ZW` |
| `Project4DTo3D(P, Mode, Distance)` | `FVector` | `Perspective` (Schlegel) or `Stereographic` |

The exact 4-polytope vertex families (the φ-based even-permutation sets for the
600-cell and 120-cell) follow the research-spec construction; the automation
test `Synapse.Geometry.VertexCounts` is the count guard (600-cell = 120,
120-cell = 600).

## Layout modes (`EMuseLayoutMode`)

Selectable per-actor, via `UObservatoryRenderSettings` (Project Settings →
Plugins → *MUSE Observatory Render*), or live with the console variables:

| Mode | Placement | Console |
|---|---|---|
| `Gateway` (default) | gateway `pos` verbatim (force / solar) | `muse.Observatory.LayoutMode 0` |
| `Phyllotaxis` | Vogel disk — the flat "Flower" | `… 1` |
| `FibonacciSphere` | golden-angle spherical shell | `… 2` |
| `Platonic` | solid vertices as anchors (cycled in shells) | `… 3` |
| `Polytope4D` | a 4-polytope rotated in 4D each tick | `… 4` |

`muse.Observatory.GeometryBlend 0..1` morphs between the gateway layout (0) and
the pure sacred-geometry anchor (1) — the spec's "structured ⇄ organic" slider.
`muse.Observatory.Polytope` and `muse.Observatory.RotationPlane` pick the 4D
framework and spin plane; double/Clifford rotation is the `bDoubleRotation`
second-plane option.

## Validation-visualization mapping (driven by real events only)

| M.U.S.E. element | Source (data plane) | Visual |
|---|---|---|
| 8 AXIOM gates (`axiom/orchestrator/gates.py`) | `OnGateVerdict` → `UObservatoryValidationViz` | scalar per gate in an MPC: **pass +1 (green), fail −1 (red), override +0.5 (amber)**; Blueprint flare events |
| Pipeline stations (job→navigator→worker→gate→ledger) | `OnJobStage` → `UObservatoryFlowComponent` | packet flows along the station spine; `stage_latency_ms` → speed |
| GraphRAG touches | `OnNodeActivate` | cluster pulse (`OnPulse`) |
| Hash-chained ledger | snapshot ledger context | (designer) chain-link ribbon; a broken `prev` severs/reddens it |
| Cluster heat | `FObsCluster.Heat` (`bHasHeat`) | emissive brightness; **null heat → cool-gray, never a guessed glow** |

Every value is verbatim from a measured event. A gate with no verdict stays at
its neutral `0`; an unavailable graph clears the field; an unsolved `pos` falls
back to the pure geometry anchor. Nothing is fabricated (the data-plane honesty
rules carried through to the renderer).

## Theoretical foundation (labeled honestly)

The visual language borrows three ideas. Each leap from mathematics/physics to
metaphor is flagged; **none of this claims M.U.S.E. is conscious.**

- **Sacred geometry as structure.** `[ESTABLISHED]` φ, the golden angle,
  phyllotaxis, the five Platonic solids, and the six regular 4-polytopes are
  rigorous mathematics; the golden angle is a real dynamical attractor for
  primordia growth (Douady & Couder, *PRL* 1992). `[SPECULATIVE/METAPHOR]`
  Calling these forms "the blueprint of the universe / of consciousness" is an
  interpretive lens, not science — we use the math because it is *beautiful and
  deterministic*, not because it is mystical.
- **"Matter as crystallized light."** `[ESTABLISHED]` Pair production is real
  (Breit–Wheeler 1934; SLAC E-144 1997). `[CONTESTED]` STAR's 2021 result is
  described as direct light→matter, but its photons are virtual photons from the
  ions' fields, so a true two-real-photon collider is still unbuilt.
  `[SPECULATIVE/METAPHOR]` "Matter *is* crystallized light" as a universal
  principle overstates the kernel — used here only as a visual motif (glowing
  nodes condensing from light).
- **"A structure for consciousness to recognize itself."** `[CONTESTED]` IIT
  (feedback/reentrant architecture) and Hofstadter's strange loops are serious
  but debated; the hard problem is unsolved. `[SPECULATIVE/METAPHOR]` The AXIOM
  gate ring + hash-chained ledger form a *literal* self-verifying loop
  ("intelligence proposes; the verifier disposes"), which we frame **poetically**
  as the system "closing the loop on itself" — a design philosophy and aesthetic,
  not a claim of sentience.

Do not present any `[SPECULATIVE]` framing as established in public-facing
material.

## Build status (honest — OWNER-BLOCKED on compile)

This is **staged source, zero binary assets** (monorepo policy §5). Niagara
systems, the gate MPC, and the node mesh are owner-authored `.uasset`s; the C++
references them by assignable property / soft path and **no-ops when unassigned**
— never a fabricated effect.

| Check | Where | Status |
|---|---|---|
| `python3 sacred_geometry_reference.py --check` (constants + exact counts) | authoring container | **PROVEN** (golden angle 137.50776405°, 600-cell 120, 120-cell 600) |
| UHT/UBT convention review (`#pragma once`, `generated.h` last, `*_API`, warnings-as-errors, no engine edits) | authoring container | **review, not a compile** |
| UBT compile (`SynapseEditor Win64 Development`) | owner's Legion (UE 5.6 + VS2022) | **NOT RUN — OWNER-BLOCKED** (UE/UBT absent in the container) |
| `Automation RunTests Synapse.Geometry` (counts/rotation/shell) | owner's Legion (`-nullrhi`, headless) | **DEFERRED — OWNER-BLOCKED** (needs the compile) |
| PIE: spawn `AObservatoryGalaxyActor`, `muse.Observatory.LayoutMode 4` | owner's Legion + a gateway/stub | **DEFERRED — OWNER-BLOCKED** |

First action on the owner's machine: compile, then
`Automation RunTests Synapse.Geometry` to close the geometry gate.
