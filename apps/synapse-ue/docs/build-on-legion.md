# Build SYNAPSE on the Legion (owner's Windows machine)

The whole flow is scripted in [`tools/`](../tools). Source is **staged** — it has
**not** been compiled in the authoring container (no UE/GPU there); these scripts
are validated by review and meant to **run on your machine**.

## One-time prerequisites

- **Visual Studio 2022** with the *"Game development with C++"* workload.
- **Unreal Engine 5.6** (Epic Games Launcher), default `C:\Program Files\Epic Games\UE_5.6`.
  The project pins `EngineAssociation: 5.6`. If you installed elsewhere, set
  `UE_ROOT` before running any script (`set "UE_ROOT=D:\Epic\UE_5.6"`).
- **Git + Git LFS** (`git lfs install`) and **Python 3** on `PATH` (for the stub).

## Full build — one double-click

```bat
apps\synapse-ue\tools\build-legion.bat
```

It does everything:

1. **Compiles** `SynapseEditor Win64 Development` (warnings-as-errors) — builds
   `SynapseCore` (incl. `MuseSacredGeometry`), `SynapseNet`, `SynapseObservatory`,
   and the new **`SynapseObservatoryRender`**.
2. **Runs** the headless `Synapse.Geometry` automation suite (no GPU) and writes a
   report to `Saved\Automation\index.html`.

Expect four green tests: `Synapse.Geometry.Constants / VertexCounts / Rotation4D /
NormalizedShell` (golden angle 137.50776405°, 600-cell = 120 vertices,
120-cell = 600, rotation/projection invariants).

> Re-run just the tests after a build with
> [`tools\run-geometry-tests.bat`](../tools/run-geometry-tests.bat) (pass
> `Synapse.` to run the whole suite).

> **Want CI to compile it automatically on the Legion?** Register the Legion as a
> self-hosted GitHub Actions runner — see
> [`self-hosted-runner-setup.md`](self-hosted-runner-setup.md). Then
> [`.github/workflows/synapse-ue-build.yml`](../../../.github/workflows/synapse-ue-build.yml)
> compiles + runs `Synapse.Geometry` on every push and the PR's UE check goes
> green with no manual step.

## See it in the editor (PIE)

1. Start the offline gateway + pair the client (writes `Saved\muse_token.txt`):
   ```bat
   apps\synapse-ue\tools\run-stub.bat
   ```
2. Open `Synapse.uproject` in UE 5.6. Make a level, drop an
   **`AObservatoryGalaxyActor`**, and assign a sphere to its **`NodeMesh`**
   (no mesh ⇒ nothing renders, by design — never a placeholder).
3. Pick a layout: Project Settings → Plugins → *MUSE Observatory Render*, or the
   console:
   ```
   muse.Observatory.LayoutMode 4      // 0 Gateway 1 Phyllotaxis 2 FibonacciSphere 3 Platonic 4 Polytope4D
   muse.Observatory.Polytope 4        // 4 = 600-cell
   muse.Observatory.GeometryBlend 1
   ```
4. Press **Play**. The actor auto-fetches the snapshot (or call `Refresh`). Filter
   the Output Log on `LogSynapseObservatoryRender`.

Against a **real** gateway: point Project Settings → MUSE Gateway `GatewayBaseUrl`
at it, drop a valid bearer into `Saved\muse_token.txt`, and run
`POST /v1/cockpit/graph/build` once so the snapshot isn't the dormant
"unavailable" shape.

## Manual equivalents (if you prefer)

```bat
:: compile
"%UE_ROOT%\Engine\Build\BatchFiles\Build.bat" SynapseEditor Win64 Development -Project="<path>\Synapse.uproject" -WaitMutex

:: test (headless)
"%UE_ROOT%\Engine\Binaries\Win64\UnrealEditor-Cmd.exe" "<path>\Synapse.uproject" -ExecCmds="Automation RunTests Synapse.Geometry; Quit" -TestExit="Automation Test Queue Empty" -unattended -nopause -nullrhi -nosplash -log
```

## Optional: stream it 24/7 (Pixel Streaming)

See [`deploy/pixelstreaming/README.md`](../../../deploy/pixelstreaming/README.md)
(owner-gated). The render visuals (Niagara flow particles, the gate-flare material
parameter collection) are owner-authored `.uasset`s — the C++ no-ops gracefully
until you assign them, so build + tests + a basic PIE work with no art.
