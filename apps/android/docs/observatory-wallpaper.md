# Neural Observatory live wallpaper (Android)

A **native on-device** live wallpaper that renders MUSE's neural network and
pulses on every real system action — synced from the paired gateway, **not** a
remote-streamed view. Part of the cross-device "live neural-network wallpaper"
program (gateway side: `gateway/cockpit/action_fusion.py` →
`GET /v1/observatory/actions`).

## Pieces (this drop)

| File | Role |
|---|---|
| `data/observatory/ObservatoryStreamClient.kt` | Self-contained `HttpURLConnection` client (mirrors `HttpJarvisChatGateway`): `snapshotClusters()` (boot graph) + `actions()` SSE flow of `ActionEvent`s. Bearer + endpoint from the same paired connection facts every cockpit surface uses. |
| `service/ObservatoryWallpaperService.kt` | `WallpaperService` + `Engine` with a Canvas render loop (~30 fps when visible): starfield + real cluster nodes (from server-computed `pos`) + an expanding ripple/energy bump per action. |
| `AndroidManifest.xml` | `<service … android:permission="android.permission.BIND_WALLPAPER">` + `android.service.wallpaper` meta-data. |
| `res/xml/observatory_wallpaper.xml` | Live-wallpaper metadata (thumbnail + description). |

## Data contract (shared with every renderer)

- **Boot:** `GET /v1/observatory/snapshot` → `graph.clusters[]` each with `id`,
  `pos:[x,y,z]` (gateway-computed in `[-100,100]³`), `radius`, `heat` (nullable).
  The service projects `(x,y)` across the short screen axis; the GLES upgrade
  uses the full 3D.
- **Live:** `GET /v1/observatory/actions` (SSE) → the fused `ActionEvent`
  vocabulary (`cluster.spark`/`pipeline.packet`/`gate.flare`/`ladder.streak`/
  `owner.pulse`/`agent.pulse`/`skill.pulse`/`system.pulse`/`audit.flare`). The
  `id:` line is the opaque resume cursor.

## Honesty (binding)

The wallpaper renders **only** real gateway data. Unpaired (no token), gateway
unreachable, or collector opt-out (snapshot empty / actions `503`) ⇒ a quiet
starfield — never fabricated nodes or activity. No mutation calls; display-only.

## Battery

Rendering is gated on `Engine.onVisibilityChanged` (no drawing while the
launcher is hidden / screen off). The SSE reconnects with capped backoff and is
cancelled when the engine is destroyed. Tunables: `FRAME_MS`, `DECAY`,
`MAX_RIPPLES`, `STAR_COUNT`.

## Build + iterate (on device)

This cloud repo cannot build the APK (no Android SDK/NDK/GPU). On a dev machine:

1. `./gradlew :app:assembleDebug` from `apps/android/`.
2. Install, then **Settings → Wallpaper → Live → MUSE Neural Observatory** (or
   long-press home → Wallpapers). Pair the gateway first (Settings → Connection).
3. With `MUSE_OBSERVATORY=1` on the gateway, run an orchestrated job / use a
   skill and watch nodes spark and ripples travel; confirm the quiet starfield
   when the gateway is unpaired.
4. `./gradlew :app:testDebugUnitTest` for the JVM unit tier.

## "Ultimate quality" upgrade path (GLES)

The Canvas renderer is the correct baseline that matches the app's existing
Canvas drawing. The high-fidelity upgrade keeps the **same data contract** and
swaps only the `Engine`'s draw path for a GLES2 renderer:

- An EGL context on the wallpaper `Surface` + a dedicated GL thread.
- Instanced point sprites for clusters (additive blending), a bloom post pass,
  and Bezier "ship" trails for `pipeline.packet` along the station graph.
- The full 3D `pos` with a slow orbital camera (the web reference does this via
  `?wallpaper=1`).

Slot it behind `ObservatoryStreamClient` (unchanged) so the data plane is reused.

## Owner-gate posture

`BIND_WALLPAPER` is a new user-facing surface (a system live wallpaper). Treat
it like the prior owner-reviewed permission/posture additions in
`docs/launch/`: surface it in the posture docs and keep it opt-in (the user
chooses it as their wallpaper) before shipping in a release.
