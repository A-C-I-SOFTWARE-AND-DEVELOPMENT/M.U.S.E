# SYNAPSE — Unreal Engine 5.6 source project

This directory is the source-only Unreal companion for M.U.S.E. It now includes
the frozen universe projection contract, an Atlas Crown runtime projection, and
native stereo-cinematic queueing in addition to the existing core, networking,
observatory, and render modules.

No Unreal Engine binaries, cooked content, credentials, signing identities, or
Pixel Streaming infrastructure are bundled here. The project remains staged in
the monorepo for later migration to the private standalone SYNAPSE repository.

## Current layout

```text
Synapse.uproject                  UE 5.6 module and plugin declarations
Config/UniverseContract.lock.json
                                  Frozen schema hashes, major version, and routes
Source/SynapseCore/               Foundation and geometry utilities
Source/SynapseNet/                Authorized HTTP/SSE gateway boundary
Source/SynapseObservatory/        Typed observatory projection client
Source/SynapseObservatoryRender/  Existing observatory renderer
Source/SynapseUniverse/           Universe state, Atlas Crown, and vessel actors
Source/SynapseCinematic/          Physical stereo rig and deterministic MRQ jobs
Config/DefaultScalability.ini     Cinema through Accessible 2D profiles
docs/atlas-crown-runtime.md       Pairing, recovery, OpenXR, streaming, and QC
tools/universe-selfcheck/         Engine-independent C++ contract consumer
tools/universe_reference.py       Python reference used by specification tests
```

The imported OpenUSD and MaterialX masters live at
`../../assets/atlas-crown/`. Unreal-generated `.uasset` and `.umap` files stay
out of this repository unless the binary/LFS policy is separately approved.

## Security and runtime selection

- `SynapseNet` owns bearer-token access. Downstream modules ask it to create an
  authorized request and never read or serialize the token.
- Pixel Streaming is private, disabled by default, and selected through
  `MUSE_PIXEL_STREAMING_URL`; credentials and TLS termination remain external.
- OpenXR is an explicit local runtime choice. Accessible 2D remains the
  fail-safe path when XR, streaming, or high-fidelity rendering is unavailable.
- Universe schema major mismatches and cursor gaps fail closed into resnapshot;
  stale versions never overwrite a newer projection.

## Migration to the standalone repository

1. Copy this directory verbatim so `Synapse.uproject` becomes the repository
   root.
2. Install Git LFS and commit the existing `.gitattributes` before any future
   binary assets.
3. Register a private Windows runner with Unreal Engine 5.6 and Visual Studio
   2022 before enabling the staged workflow.
4. Pair against a private M.U.S.E. gateway and capture compile, automation,
   Pixel Streaming, OpenXR, and MRQ evidence before changing any gate to green.

## Verification status

The Tasks 1–6 deliverables were inspected as source only. In accordance with
the current assignment, no tests, Unreal commands, compilers, builds, linters,
type checks, scripts, gates, or servers were run. The exact open evidence gates
are recorded in
`../../docs/audits/2026-07-12-muse-atlas-universe-verification.md` and
`../../.superpowers/sdd/unreal-stream-report.md`.
