# Atlas Crown UE 5.6 runtime

This is a source-complete, source-only runtime contract for the original
M.U.S.E. Atlas Crown and agent flagship. It does not contain generated Unreal
assets, a packaged executable, credentials, Pixel Streaming infrastructure, or
evidence that UE 5.6 compiled this revision.

## Runtime modes

| Mode | Selection | Authority and fallback |
|---|---|---|
| Local native | default | Primary when the executable and supported GPU exist. Universe state still comes from authenticated plugin routes. |
| OpenXR | explicit user selection plus platform OpenXR runtime | Standard runtime selection; snap turn and comfort vignette defaults are configurable. Failure falls back to accessible 2D when enabled. |
| Pixel Streaming 2 | explicit launch plus `MUSE_PIXEL_STREAMING_URL` | No automatic public endpoint. Loopback may use WS; external signaling requires WSS/TLS. Viewer input never receives the gateway bearer. |
| Cinema | explicit MRQ job | Separate physical L/R cameras, path-traced OpenEXR intent, ACES metadata, deterministic settings and QC records. |
| Accessible 2D | explicit or fail-safe | All operational controls remain available without spatial navigation or continuous motion. |

OpenXR and Pixel Streaming are delivery modes, not authority sources. Client
movement and cosmetics may be predicted, but only `/v1/plugins/muse-universe`
events and projections update capabilities, inventory, memberships, missions,
or command results.

## Local build and source import

1. Install Unreal Engine 5.6 and Visual Studio 2022 with the Unreal C++
   workload. Do not regenerate the project against 5.5 or 5.7.
2. Open `Synapse.uproject` and confirm `OpenXR`, `MovieRenderPipeline`,
   `USDImporter`, and `PixelStreaming2` resolve in this exact engine install.
3. Build `SynapseEditor Win64 Development` with warnings as errors.
4. Import or stage `assets/atlas-crown/atlas-crown.usda` and
   `agent-flagship.usda`; retain authored meters and convert to centimeters once
   through `MuseUniverseMath::MetersToCentimeters`.
5. Translate local MaterialX IDs to reviewed native materials. Do not add
   untracked texture URLs during import.
6. Run `Synapse.Universe`, `Synapse.Cinematic`, and existing
   `Synapse.Geometry` automation suites, then package and profile a development
   build. These commands are required future evidence; they were not run in the
   constrained source-authoring stream.

The USDA `source`, `interactive`, and `proxy` variants define authoring budgets.
Proxy-purpose prims belong to collision/navigation/HLOD, not beauty output.

## Gateway pairing and frozen contract

- Pair through the existing SynapseNet token-file convention. Connect the
  projection with both realm ID and authoritative actor ID; `/snapshot`
  requires both. The token is read inside SynapseNet for each request and is
  never stored by SynapseUniverse.
- `Config/UniverseContract.lock.json` pins schema major 1, route paths, and
  checked-in schema hashes. A higher schema major stops projection application.
- Snapshot boot is followed by bounded event polling at
  `LastAcknowledgedCursor`. Since event sequence is global while pages are
  realm-filtered, legal numeric sequence gaps are distinguished from missing
  realm events with `realm_version`. A real gap triggers snapshot resync and replay from zero;
  history already represented by the fresh snapshot is suppressed so it cannot
  create false equal-version conflicts or duplicate projection events. Stale
  entity versions are ignored; live equal-version conflicting bodies are
  retained for review.
- Commands keep the same idempotency ID and expected version on retry. Owner
  phrases, API keys, access tokens, raw headers, and credential pools are
  rejected from payloads. Sensitive operations use an existing approval ID.

## Pixel Streaming security

Enabling the plugin does not start a stream. Supply the signaling endpoint at
launch from `MUSE_PIXEL_STREAMING_URL`; do not commit it to `.ini` files. The
runtime accepts endpoint shapes without user info, query strings, or fragments,
uses loopback/private operation by default, and requires `wss://` off-loopback.
TLS termination, TURN/STUN policy, authentication, rate limiting, and viewer
authorization belong to the separately deployed signaling infrastructure.

Never expose the M.U.S.E. gateway bearer, owner approval material, request
headers, or backend URLs containing credentials to the viewer page or WebRTC
data channel.

## OpenXR comfort

The platform runtime selects the OpenXR device. The source default is no
continuous camera drift, 30-degree snap turn, and a 0.35 comfort vignette.
Applications must expose seated/standing recentering, depth strength, captions,
reduced motion, and a direct 2D return path. Pixel-streamed VR is not treated as
equivalent evidence to local OpenXR and is not required for core operation.

## Fidelity and failure recovery

- Cinema keeps source LOD, native stereo, path tracing, and highest volumetric
  intent for offline MRQ.
- Ultra/High keep the full silhouette and reduce samples before geometry
  identity.
- Balanced keeps the silhouette with HLOD, probes, reduced shadows, and no
  volumetric fog at the lowest effects group.
- Accessible 2D mounts no required 3D scene and preserves every command/control.

The runtime records selected tier and reason. Unsupported ray/path-tracing
features fall back to Lumen, probes, Balanced, or Accessible 2D without claiming
the higher tier. Missing USD/MRQ/XR/Pixel Streaming plugins are surfaced as
environment gates; the local projection client and 2D path remain usable.
GPU context loss, network loss, and cursor gaps preserve the last acknowledged
snapshot, show stale/degraded state, and resync rather than inventing success.

## Cinematic truth

MRQ jobs use separate left/right level sequences whose camera-cut tracks bind
the physical `LeftEyeCamera` and `RightEyeCamera` components on the same stereo
rig. Symmetric toe-in is the verified source policy. Off-axis output fails
closed until its projection-matrix extension is compiled and validated against
UE 5.6. Jobs preserve separate L/R eye names, identical scene revision,
deterministic seed, timing, exposure, resolution, sample counts, motion blur,
depth of field, volumetric, reflection/refraction, and color metadata. Expected
output is OpenEXR with ACES 2 intent. Missing frames, frame-number mismatch, temporal
misalignment, missing checksums, vertical mismatch over 0.5 px, or a
post-converted depth card blocks QC. Both 1.90:1 and 1.43:1 guides are preserved.

M.U.S.E. provides an IMAX-targeted workflow only. It does not claim IMAX
certification, trademark permission, partnership, screen testing, or mastering
approval.
