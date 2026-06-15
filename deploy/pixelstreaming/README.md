# Pixel Streaming deployment — Nero cockpit (owner‑gated)

Render the UE5 `SynapseObservatory` (Nero theme) on a high‑power **host render node**
(Legion RTX 5070 / ASUS ROG Zephyrus / Skytech rig) and stream the interactive cockpit to
Android/desktop thin clients over WebRTC. The MUSE gateway (the brain) is unchanged and keeps
talking to the UE app over the frozen HTTP/SSE cockpit contract.

> **Owner gate.** Standing up a render node and a signalling server is an outward‑facing,
> resource‑spending action and a change to the master plan's locked delivery model. Treat the
> scripts here as templates: do not run them in production until the pivot PR is approved with
> `Yes, with authorization.` (see `docs/plans/2026-06-14-nero-fleet-streaming-pivot-addendum.md`).

## Prerequisites (host render node)
- Windows 10/11 + a recent NVIDIA GPU (NVENC) — the master plan's dev machine qualifies.
- Unreal Engine **5.6** with the **PixelStreaming2** plugin available.
- Epic's Pixel Streaming **Infrastructure** (SignallingWebServer + optional TURN), from the
  `EpicGames/PixelStreamingInfrastructure` distribution matched to UE 5.6.
- The MUSE gateway reachable from the host (default cockpit `127.0.0.1:8765`); the UE app reads
  its bearer from the settings token file exactly as today (no token in the stream).

## Step 1 — enable streaming in the UE app (reviewable patch; apply in‑editor)
These are **documented, not auto‑applied** (UE builds aren't validated in this repo's CI).
Apply in the editor or by hand on the host, then commit from the host build.

`apps/synapse-ue/Synapse.uproject` — add a `Plugins` block enabling Pixel Streaming:
```jsonc
"Plugins": [
  { "Name": "PixelStreaming2", "Enabled": true },
  { "Name": "PixelStreaming2HMD", "Enabled": false }
]
```

`apps/synapse-ue/Config/DefaultEngine.ini` — append a streaming‑input section (rendering
settings already target Lumen/Nanite + SM6):
```ini
[/Script/PixelStreaming2.PixelStreaming2Settings]
PixelStreaming2DefaultStreamerID=Nero
; encoder/bitrate tuned on the host; offscreen render keeps the editor headless
```
Launch the cooked app (or editor) with: `-PixelStreaming2URL=ws://<host>:8888 -RenderOffscreen`.

## Step 2 — run the signalling server (host)
```bash
deploy/pixelstreaming/run-signalling.sh        # wraps Epic's SignallingWebServer
```
Defaults to `:80` (player/web) and `:8888` (streamer). Put a TURN server in front for clients
that aren't on the LAN.

## Step 3 — launch the render node (host, owner‑gated)
```bash
MUSE_PS_ALLOW_SPAWN=1 deploy/pixelstreaming/run-render-node.sh /path/to/Synapse.exe ws://<host>:8888
```
The script refuses to launch unless `MUSE_PS_ALLOW_SPAWN=1` is set — an explicit, auditable
owner gate that mirrors `MUSE_UE5_ALLOW_SPAWN` for the offscreen‑render path.

## Step 4 — thin clients
- **Desktop:** open `http://<host>/` (Epic's bundled player frontend) — no install.
- **Android:** the opt‑in WebRTC receiver screen (separate, feature‑flagged phase). Until it
  ships, the Android browser can use the web player; the REST thin client remains the default
  app experience.

## No‑mock invariant (end‑to‑end)
The stream shows whatever the gateway reports. With no collector, the Observatory renders its
dormant dressing — never fabricated planets or ships. `?layout=solar` only re‑arranges **real**
clusters; positions are deterministic placement, not telemetry.
