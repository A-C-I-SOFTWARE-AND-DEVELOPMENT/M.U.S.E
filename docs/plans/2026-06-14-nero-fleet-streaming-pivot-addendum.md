# Addendum — Pixel Streaming delivery pivot (Nero‑Fleet)

**Date:** 2026-06-14 · **Owner:** Jeremiah Echerd · **Amends:**
`docs/plans/2026-06-10-project-synapse-master-plan.md` · **Status:** OWNER‑GATED — draft
PR only; merge to `main` requires the exact phrase `Yes, with authorization.`

## Why this addendum exists

The master plan locks (Decision 2 + the "one law" Coupling Rule) that *UE5 is a native C++
client over the frozen wire contract*, with a native scaled Android renderer (Decision 5;
tech‑design §242) — **not** Pixel Streaming. The Nero‑Fleet vision instead delivers the
cockpit by **rendering on a high‑power host (ROG/Skytech/Legion) and streaming the
interactive UI** to Android/desktop thin clients. After the conflict was surfaced, the owner
chose to **pivot to Pixel Streaming** as the primary delivery model and to apply the Nero
theme to the native `SynapseObservatory` map.

This is an **architecturally significant** change to the owner's own design authority, so it
is owner‑gated: implemented on the feature branch, opened as a **draft PR**, and **not merged**
until the owner replies `Yes, with authorization.`

## What changes (and what does NOT)

- **Master plan Decisions 2 & 5 are amended:** Pixel Streaming becomes an accepted delivery
  tier. The native PC path is **retained** (the UE app still renders natively on the host);
  Pixel Streaming is added as the *transport to thin clients*, reached sooner than the
  Phase‑7 native mobile renderer.
- **The Coupling Rule still holds:** nothing in `hermes_cli/jarvis_prime/`, GraphRAG, the
  orchestrator, the gates, or the ledgers is ported to C++. The UE app keeps consuming the
  gateway over HTTP/SSE per the frozen contract. Pixel Streaming changes only *how pixels
  reach the user*, not where the brain lives.
- **No default behavior changes** in the gateway, the Android REST thin client, or the
  default UE native run. Streaming is a separate build config + opt‑in deployment.

## Topology

```
  [Host render node: Legion/ROG/Skytech, RTX]              [Thin clients]
   UE5 SynapseObservatory (Nero theme)                      Android / desktop browser
        │  renders frames (Lumen/Nanite)                         │  WebRTC receiver
        │  PixelStreaming2 plugin → WebRTC                       │
        ▼                                                        ▼
   Signalling/Web server (Epic) ───────── WebRTC (video+input) ──┘
        ▲
        │ HTTP/SSE (unchanged, frozen contract)
   MUSE gateway (the brain)
```

## Workstreams (all owner‑gated for merge)

1. **Enable streaming in the UE app** — `apps/synapse-ue`: PixelStreaming2 plugin + a
   `Streaming` build/run config. Documented as a reviewable patch in
   `deploy/pixelstreaming/README.md` (not blind‑applied here: UE builds cannot be validated
   in a GPU‑less CI container; the owner applies it in‑editor).
2. **Deployment scaffolding** — `deploy/pixelstreaming/` (signalling launch, render‑node
   launch, TURN/STUN notes). Render‑node/process spawn is owner‑gated, mirroring the
   `MUSE_UE5_ALLOW_SPAWN` doctrine.
3. **Nero theme on the UE map** — `apps/synapse-ue/docs/nero-theme.md`; binds to the gateway's
   new `layout_algo == "solar-orbital"` (already shipped gateway‑side; see the static analysis).
4. **Android WebRTC receiver** — its own phase; opt‑in, feature‑flagged; the REST thin client
   stays the default.

## Acceptance (on the owner's rig, gated)

- The UE app builds in the `Streaming` config and launches against a local signalling server.
- A browser/Android receiver shows the **Nero‑themed** Observatory; real `job.stage` events
  animate ships; `?layout=solar` arranges clusters as orbiting planets around the Nero Core.
- Pointing at a gateway with no collector → dormant dressing, no fabricated bodies (no‑mock
  invariant preserved end‑to‑end).
