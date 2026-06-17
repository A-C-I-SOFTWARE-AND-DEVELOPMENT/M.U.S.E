# Native-Rust UI rewrite — planning & design document

> **Status:** Exploration / decision document. **Not** an implementation, and
> **not** an approved direction. This document evaluates a *full native-Rust UI
> rewrite* of the M.U.S.E. desktop app, recommends a stack if we proceed, and —
> critically — argues about whether we should proceed at all.
>
> **Owner gate.** A native-Rust UI rewrite is architecturally significant and
> changes default runtime behavior of the desktop surface. Per `CLAUDE.md` and
> `docs/muse-system-contract.md`, starting it requires the owner's explicit
> `Yes, with authorization.` This document exists to *inform* that decision; it
> does not assume it.

---

## 1. Context & motivation

The owner wants a **cinematic, triple-A, 4K-quality** desktop experience for
M.U.S.E. — the "Observatory" cockpit and the brand's *Singularity* look
(a white core blazing in the void, wrapped by one matte spectral ring; see
[`docs/brand/muse-design-language.md`](../brand/muse-design-language.md)) should
feel like game-grade key-art rendered live, not a web page styled to look like
one.

The hypothesis behind a native-Rust rewrite is concrete:

- The current desktop app renders its UI in a **webview** (WebKitGTK on Linux,
  WebView2 on Windows, WKWebView on macOS) bundled by a Tauri v2 shell
  (`apps/desktop/src-tauri/`). A webview is excellent for documents and forms
  but is a constrained, sandboxed, per-OS-divergent path for *sustained
  game-grade rendering*: volumetric bloom, depth-composited 3D, HDR-ish tone
  curves, particle/field effects, and 4K-at-120fps motion are awkward to do
  *consistently across all three webviews* and impossible to fully control.
- A **native Rust UI on a GPU stack (wgpu)** gives us a single, owned render
  pipeline — the same shaders, the same frame loop, the same color management on
  every OS. That is the only path that can render the Observatory's
  "cinematic synthesis" lighting recipe (`muse-design-language.md` §5) *as a
  real-time scene* rather than as a clever CSS/SVG approximation.

**The goal, crisply:** evaluate whether replacing the React/webview UI with a
native-Rust GPU UI is the right way to reach a cinematic 4K cockpit — and if so,
how to do it without losing the protocol fidelity, the append-only extension
seam, the design-token discipline, and the dual-use (desktop + browser/PWA)
reach the current app already has.

This is **not** a mandate to rewrite. Section 8 gives the honest call.

---

## 2. What exists today

The desktop app is a **Tauri v2 (Rust shell) + React 19 (TypeScript, webview)**
split. The authoritative description is
[`apps/desktop/README.md`](../../apps/desktop/README.md); the relevant facts:

### 2.1 The two halves

- **Rust shell** — `apps/desktop/src-tauri/`:
  - `src/lib.rs` — the window, the native macOS-style menu (App / Edit / Help,
    with a "Copy Gateway URL" action), a system tray (Show / Hide / Quit),
    single-instance enforcement, window-state persistence, **hide-to-tray on
    close** (the window hides; the app keeps running), and an inert,
    owner-gated `tauri-plugin-updater` scaffold.
  - `src/brain.rs` — the **"one installable, the app starts the brain"** model:
    on launch it probes `GET /v1/health`; if the gateway is down and autostart
    is enabled (persisted in `app_config_dir/brain.json`, default on), it finds
    an installed `muse` binary (PATH + common install dirs) and spawns
    `muse cockpit serve` as a *managed child* via `tauri-plugin-shell`
    (Rust-side only — the webview gets **no** shell capability). It never
    double-serves (probe-then-check-then-spawn), never kills a gateway it
    didn't start, and reaps its child only on real exit (`RunEvent::Exit`), not
    on hide-to-tray.
  - The webview reaches the shell via five commands (`gateway_status`,
    `gateway_start`, `gateway_stop`, `autostart_get`, `autostart_set`) plus
    `gateway_url_hint_set`, exposed through `window.__TAURI__.core.invoke`
    (`withGlobalTauri`), wrapped in TypeScript by
    `apps/desktop/ui/src/lib/brain.ts`.

- **React webview UI** — `apps/desktop/ui/`:
  - `src/App.tsx` — the app shell: a header lockup (animated `Glyph` + "M.U.S.E."
    wordmark + a connection status dot driven by a 10s health poll), a nav
    rendered from the **route registry**, a minimal **hash router**, an offline
    banner with Retry, `Cmd/Ctrl+1..n` route shortcuts, and a persistent `Dock`
    overlay mounted once above all surfaces.
  - `src/routes.ts` — the **APPEND-ONLY route registry** (see §2.4). This is the
    extension seam and must be preserved conceptually in any rewrite.
  - `src/lib/gateway.ts` — the full gateway protocol client (see §2.3).
  - `src/views/` — the surfaces a rewrite must reach parity with:
    **Home** (pairing + live NDJSON chat), **Chat** (full-page NDJSON chat),
    **Jobs** (live SSE job list with a `PhaseRail`), **Approvals** (owner-gated
    approve/deny), **Autonomy** (owner-gated level raises + workspace scope),
    **Observatory** (the **3D/WebGL cockpit**, embedded as an `<iframe>` of the
    gateway-served `/cockpit/observatory.html`), and **Settings** (gateway URL,
    brain process control, pairing, emergency stop).

### 2.2 Dual-use: this is not only a Tauri payload

`apps/desktop/ui/vite.config.ts` builds the *same* React bundle two ways:

1. As the **webview payload** bundled inside the Tauri shell (loaded over
   Tauri's asset protocol; `base: "./"` for relative asset URLs).
2. As an **installable PWA / browser cockpit** — `vite-plugin-pwa` emits a
   `manifest.webmanifest` (name "M.U.S.E.", theme `#050507`) and a service
   worker that precaches the app shell while deliberately **never** caching
   `/v1/*` (the gateway API is always live). `ui/dist/` can be served from any
   static host and installed as a PWA.

This dual-use is load-bearing for reach: the browser cockpit is how the UI is
used on machines where installing a native app is undesirable or impossible.

### 2.3 The gateway protocol (what the UI depends on)

All in `apps/desktop/ui/src/lib/gateway.ts`. A rewrite **must reproduce every
one of these**, byte-for-byte on the wire:

| Concern | Endpoint(s) | Notes a rewrite must honor |
|---|---|---|
| Base URL | default `http://127.0.0.1:8765` | overridable; stored in `localStorage` `muse.gateway.base`; a Vite `VITE_GATEWAY_BASE` build default; reported to the shell via `gateway_url_hint_set`. |
| Auth | `Authorization: Bearer <token>` | per-device token in `localStorage` `muse.cockpit.token`. |
| Health | `GET /v1/health` | 10s poll drives the status dot. |
| Pairing | `POST /v1/cockpit/pair/start` → `POST /v1/cockpit/pair/confirm` | start is unauthenticated; confirm takes pairing code **+ owner authorization phrase**; a `403` means owner auth wrong/required; success mints + persists the token. |
| Chat | `POST /v1/jarvis/chat` | **NDJSON** stream — one JSON object per line; assistant `content` concatenated; consumed via `fetch` + `ReadableStream` reader. |
| Jobs | `GET /v1/cockpit/jobs/stream` (SSE) | bearer-authed, so **not** `EventSource` (can't set headers) — streamed via `fetch` + manual `text/event-stream` frame parsing; `job.upsert` / `job.removed` events; heartbeats; **capped-backoff reconnect**; falls back to a single `GET /v1/cockpit/jobs` poll when streaming primitives are unavailable. |
| Job phases | (client-side) | `JOB_PHASES` rail vocabulary + `phaseStates()` mapping over the server status vocabulary. |
| Approvals | `GET /v1/cockpit/approvals`, `POST /v1/cockpit/approvals/{id}` | approve is owner-gated (phrase at action time); `403` re-prompts once. |
| Autonomy | `GET`/`POST /v1/cockpit/autonomy` | a *raise* (per `AUTONOMY_RANK`) is owner-gated; lower/revoke is token-only; `workspace_path` scopes High-Autonomy Coding; `403` re-prompts. |
| Emergency stop | `POST /v1/cockpit/emergency-stop` | owner-gated; cancels all jobs + latches autonomy read-only; `403` re-prompts. |
| Owner phrase | (client-side) | `promptOwnerPhrase()` prompts at action time and **never persists** the phrase — handed straight to the request and discarded. |

### 2.4 The append-only route registry (the extension seam)

`apps/desktop/ui/src/routes.ts` is a **mutable registry** that feature grains
append to (`registerRoute({ id, label, render, order })`) from their **own**
modules — they must not edit a shared switch/enum, so parallel grains register
routes without touching the same lines (no merge conflicts on a central
dispatcher). `getRoutes()` returns a stable, order-sorted copy;
`registerRoute` is idempotent on `id`. `App.tsx` renders nav + the active view
purely from this registry and *never changes when a surface is added*. This is
the same single-writer / disjoint-ownership discipline the repo's parallel
follow-up contract encodes — it must survive the rewrite in spirit.

### 2.5 The design system

[`design-system/`](../../design-system/) is the `@muse/design-system` package:

- `tokens.json` — the canonical *Singularity* tokens (color, gradient, spacing
  4/8 grid, radius, type scale, tonal `elevation`, Material-3 `motion`, and
  `glyph` geometry ratios).
- `scripts/generate.mjs` — a **pure-Node, zero-dep generator** that emits
  `dist/tokens.css` (web) and `dist/Tokens.kt` (a Compose `object MuseTokens`
  for Android) from `tokens.json`. `dist/` is generated and committed; never
  hand-edited.
- The brand rubric in `docs/brand/muse-design-language.md` is the tie-breaker
  ("when the two disagree, the design-language doc wins"). Its non-negotiables:
  white core is the hero; **one** matte spectral ring; **≤ 3 color roles**;
  **no glow/neon on the ring**; **no drop shadows** (tonal/value elevation
  only); emphasized-easing motion; bloom on the white core only.

A native-Rust UI is simply **a third generator target**: `dist/Tokens.rs`
alongside `dist/Tokens.kt` and `dist/tokens.css` (see §5.3).

---

## 3. Candidate native-Rust UI stacks

We evaluate seven stacks against the criteria the goal demands. The hard
requirement that filters everything: **a wgpu-backed render surface we control,
on which we can run custom shaders, composited with normal UI** — because the
"cinematic 4K" goal *is* a custom-shader goal, and the Observatory cockpit is a
real 3D scene.

### 3.1 The stacks, in prose

- **egui** (`egui` + `eframe`/`egui-wgpu`) — immediate-mode GUI. Renders through
  wgpu; you can interleave your own `wgpu` render passes via the paint callback.
  Extremely fast to build with; mature; huge ecosystem. Text is good but not
  typographically world-class; accessibility exists (`accesskit`) but is
  basic. Immediate-mode means *you* own all state, which is great for a HUD/
  cockpit and less great for document-like flows. **Best "ship it" velocity of
  the GPU-native options.**

- **iced** — Elm-architecture retained-mode GUI, wgpu renderer (`wgpu` or
  `tiny-skia` fallback). Clean state model, good async (`iced::Task`/
  subscriptions), `accesskit` support, growing ecosystem (it's the System76
  COSMIC desktop toolkit). Custom wgpu primitives are supported via the
  `iced_wgpu` shader/`Primitive` API but are more ceremony than egui's
  callback. **Strong, principled, retained-mode option.**

- **Slint** — a declarative `.slint` markup + Rust/C++/JS logic toolkit with its
  own renderer (software or GPU via femtovg/skia; embedded-friendly). Excellent
  for clean product UI and animations; good tooling (live preview). But its
  rendering is *its* renderer — dropping arbitrary custom wgpu shader passes into
  the scene graph is not a first-class story, and its license (GPL / royalty /
  commercial) is a real consideration. **Great app UI, weak custom-GPU seam.**

- **Dioxus (native / Blitz)** — React-like RSX in Rust. The *native* path uses
  **Blitz**, an HTML/CSS layout+paint engine (Stylo + vello/wgpu). Very
  attractive for *us* because it's the closest conceptual port of the existing
  React component tree, and Blitz renders via vello (wgpu). But Blitz is
  **early** and not yet a stable, full CSS engine; betting the cockpit on it is
  betting on immature foundations. Dioxus's mature path is still a webview
  (Dioxus Desktop = Tauri-like), which defeats the purpose. **Tempting for
  migration shape; too immature for the GPU goal today.**

- **bevy + wgpu** — a full game engine. This is the only option that is *natively*
  a real-time 3D renderer with an ECS, PBR/material pipeline, post-processing
  (bloom, tonemapping), and an asset pipeline. UI exists (`bevy_ui`, plus
  `bevy_egui`-style integrations) but is the engine's weakest area for dense
  forms/tables. **Unmatched for the cinematic scene; heavy and awkward for the
  form-heavy surfaces (Settings, Approvals).**

- **Floem** — a fine-grained-reactive (signals) retained UI from the Lapce team,
  wgpu/vello rendering. Ergonomic reactive model, good performance. Younger and
  smaller ecosystem; accessibility and custom-shader-compositing stories are
  less proven. **Promising, but thinner than egui/iced.**

- **gpui** (Zed's) — the GPU-accelerated UI framework behind the Zed editor.
  Genuinely fast, genuinely beautiful, designed for exactly this "feels native
  and premium" bar. But it is **not a stable, separately-versioned, documented
  public crate** — it ships inside the Zed repo, its API churns, cross-platform
  Linux/Windows support has historically lagged macOS, and adopting it means
  tracking Zed's tree. **Aspirational; too much of a moving target to standardize
  a product on.**

### 3.2 Scoring

Scores are 1 (poor) – 5 (excellent) for *our* goal (cinematic 4K cockpit + the
seven existing surfaces + the gateway protocol + cross-platform + token
discipline). Weighted toward the two things this project actually needs:
**custom-GPU/cinematic capability** and **dev velocity to parity**.

| Criterion (weight) | egui | iced | Slint | Dioxus/Blitz | bevy+wgpu | Floem | gpui |
|---|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| **GPU / custom-shader / cinematic-4K (×3)** | 4 | 4 | 2 | 3 | 5 | 3 | 4 |
| **Dev velocity to 7-surface parity (×3)** | 5 | 4 | 4 | 4 | 2 | 3 | 3 |
| Rendering model fit (HUD + forms) | 4 | 4 | 4 | 4 | 3 | 4 | 4 |
| Text / i18n quality | 3 | 4 | 4 | 4 | 3 | 3 | 4 |
| Accessibility (AccessKit etc.) | 3 | 4 | 4 | 3 | 2 | 2 | 2 |
| Async / networking (tokio/reqwest) | 4 | 5 | 4 | 4 | 4 | 4 | 4 |
| Cross-platform (mac/win/linux) | 5 | 5 | 4 | 3 | 5 | 4 | 2 |
| Ecosystem maturity / stability | 5 | 4 | 4 | 2 | 5 | 3 | 2 |
| Tauri interop / packaging | 5 | 4 | 4 | 4 | 3 | 4 | 3 |
| **Weighted total (max 75)** | **62** | **61** | **52** | **51** | **57** | **49** | **49** |

Reading the table: **egui** and **iced** lead because they couple high dev
velocity with a *real* wgpu custom-render seam and mature cross-platform
packaging. **bevy** wins the pure-cinematic axis outright but loses heavily on
velocity-to-parity for the form-heavy surfaces. **gpui** and **Dioxus/Blitz**
are penalized for stability/maturity despite genuine appeal.

> Caveat: these are *judgment* scores for this goal as of the codebase's current
> date (2026-06-17), not benchmark numbers. They are meant to rank, not to be
> cited as measurements.

---

## 4. Recommendation (stack)

**If we proceed, build the shell in `egui` (eframe + egui-wgpu) and embed a
dedicated `wgpu` "cinematic layer" for the Observatory and the brand
hero.** Runner-up: **iced**.

Reasoning:

- **The custom-shader seam is first-class and cheap in egui.** `egui-wgpu`'s
  paint callback lets us run our *own* `wgpu` render passes (the white-core
  bloom, the spectral-ring scene, the Observatory 3D) *inside* the same frame as
  the normal UI, with the UI composited on top. That is precisely the
  "game-grade visuals behind a normal cockpit" shape the goal wants, and it
  avoids standing up a whole game engine.
- **Velocity to seven-surface parity is the highest of the GPU-native set.**
  Immediate mode maps naturally onto a live HUD whose state is the gateway's
  streamed truth (jobs, approvals, autonomy) — we already hold that state in
  TS the same way. The form surfaces (Settings, pairing) are trivial in egui.
- **It's the most boring, mature, cross-platform, well-packaged choice** — which
  for a *product* (not a tech demo) is a feature. It pairs cleanly with `tokio`/
  `reqwest` and slots into the existing Tauri packaging without inventing a new
  bundler.

**Why not the alternatives as the primary:**

- **bevy** is the runner-up *for the cinematic layer specifically*, and we use
  wgpu directly so we can lift bevy's post-processing techniques (bloom,
  tonemapping) as plain shaders without adopting the whole engine. Choosing bevy
  as the *whole UI* would make Settings/Approvals/Autonomy disproportionately
  expensive.
- **iced** is the genuine runner-up for the *whole app*: pick it instead of egui
  if, during a spike, we find the retained Elm model materially reduces bugs in
  the streaming surfaces and the `iced_wgpu` shader primitive proves ergonomic
  enough for the cinematic layer. It scores within one point of egui.
- **gpui / Dioxus-Blitz** — revisit in 6–12 months. If Blitz matures into a
  stable CSS engine, it becomes the lowest-friction *migration* target (it's the
  closest to the existing React tree) and should be re-scored.

---

## 5. Target architecture (if we proceed)

A native binary that **replaces the webview** but **keeps the Tauri shell's
proven responsibilities** (window, tray, menu, single-instance, brain
autostart). The cleanest framing: Tauri already *is* a good native shell; we are
swapping its *payload* from "a webview pointed at `ui/dist`" to "a wgpu surface
driven by our egui app," while reusing `brain.rs` essentially unchanged.

```
+-------------------------------------------------------------+
|  Native window (Tauri shell: tray, menu, single-instance,   |
|  window-state, hide-to-tray, brain autostart — brain.rs)    |
|                                                             |
|   +-----------------------------------------------------+   |
|   |  egui app (eframe + egui-wgpu)                       |   |
|   |   - app shell: header lockup, nav, router            |   |
|   |   - surfaces: Home/Chat/Jobs/Approvals/Autonomy/...  |   |
|   |   - reads design tokens from generated tokens.rs     |   |
|   |                                                       |   |
|   |   egui-wgpu paint callback ---> CINEMATIC LAYER (wgpu)|   |
|   |       core-bloom shader . matte spectral ring .       |   |
|   |       Observatory 3D scene . tonemap/post             |   |
|   +-----------------------------------------------------+   |
|                                                             |
|   gateway client  (tokio + reqwest, in-process)             |
|     REST . NDJSON chat . SSE jobs . bearer pairing .         |
|     owner-phrase prompts . emergency-stop                    |
+-------------------------------------------------------------+
                         |  HTTP (loopback)
                         v
        MUSE gateway  (muse cockpit serve, :8765)
```

### 5.1 Talking to the gateway (`tokio` + `reqwest`)

Port `lib/gateway.ts` to a Rust `gateway` module backed by `reqwest`
(async, `tokio` runtime) — **same wire protocol, no server changes**:

- **REST + auth** — a `reqwest::Client` with a default `Authorization: Bearer`
  header injected per request; base URL resolved exactly as today (override →
  env default → `http://127.0.0.1:8765`). The token persists to a small native
  config (the egui app's own config dir) standing in for `localStorage`.
- **Bearer pairing** — `pair/start` → `pair/confirm`, with the **owner
  authorization phrase** entered in a modal *at confirm time*. A `403` surfaces
  a re-prompt. The minted token is stored once on this device.
- **NDJSON chat** — `reqwest`'s streaming `bytes_stream()`; split on `\n`,
  `serde_json`-parse each line, accumulate assistant `content`, push deltas to
  the chat surface over an `mpsc` channel so the UI thread stays responsive.
- **SSE jobs** — the same fetch-not-EventSource pattern, in Rust trivially: a
  streaming GET to `/v1/cockpit/jobs/stream` with the bearer header, manual
  `text/event-stream` frame parsing (`event:` / `data:`, CRLF→LF), `job.upsert`/
  `job.removed`/heartbeat handling, **capped-backoff reconnect**, and the
  single-poll `/v1/cockpit/jobs` fallback. Stream tasks run on `tokio` and feed
  the UI via channels; `tokio_util::sync::CancellationToken` replaces
  `AbortController`.
- **Owner-gated actions** — approvals approve, autonomy *raise*, and
  emergency-stop all prompt for the owner phrase in a native modal at action
  time, send it in the body, and **discard it immediately** (no field, no log,
  no config — mirroring `promptOwnerPhrase`'s never-persist guarantee, which is
  also a `docs/jarvis-constitution.md` requirement). A `403` re-prompts once.
- **Brain control** — `gateway_start/stop/status` and `autostart_get/set` stay
  in `brain.rs` and are reached via Tauri `invoke` exactly as `lib/brain.ts`
  does today; the native UI calls them through the same command names. (If we
  ever drop Tauri entirely, this logic ports directly into the binary, but
  keeping the Tauri shell means **zero change to the brain layer** — a major
  de-risking choice.)

### 5.2 Re-creating the append-only route/surface registry in Rust

Preserve the **append-only, single-writer, no-central-dispatcher** property of
`routes.ts`. The idiomatic Rust port uses a registration registry populated at
startup:

- A `RouteDef { id, label, order, view: Box<dyn Fn(&mut Ctx) + ...> }` and a
  process-global registry (e.g. a `OnceCell<Mutex<Vec<RouteDef>>>` or the
  `inventory`/`linkme` crates' compile-time registration) so each surface
  *module* registers itself without editing a shared `match`. `inventory` is the
  closest Rust analog to "import a module for its side effect": a surface
  declares `inventory::submit!(RouteDef { … })` and is collected automatically.
- `get_routes()` returns a stable order-sorted copy; registration is idempotent
  on `id`. The shell renders nav + the active view from the registry and never
  changes to add a surface — identical contract to today, so the parallel-grain
  no-merge-conflict guarantee carries over.

### 5.3 Where the design tokens feed in

Add a **third generator target** to `design-system/scripts/generate.mjs`,
mirroring the existing `Tokens.kt` path exactly:

- Emit `design-system/dist/Tokens.rs` — a `pub mod muse_tokens` with the same
  shape as `MuseTokens` (Kotlin): colors as `egui::Color32` / `[f32; 4]`
  constants, spacing/radius as `f32`, the type scale, **tonal elevation
  surfaces** (not shadows), Material-3 motion durations + cubic-bezier easing
  control points, and the glyph geometry ratios. `tokens.json` stays the single
  source of truth; `dist/` stays generated-and-committed; the existing
  `test/tokens.test.mjs` gains assertions that the Rust artifact carries the
  exact Singularity hex too.
- The native UI imports `muse_tokens` and is *forbidden* from hand-picking a hex
  — same rule as web/Android. This is what keeps the native UI, the web cockpit,
  and the Android app pixel-consistent.

### 5.4 The cinematic layer (wgpu) and the Observatory

- **Brand hero (everywhere):** the white-core **bloom** is a small wgpu pass
  (stacked cool-white radial halos + a tight core punch, per
  `muse-design-language.md` §5) rendered behind/around the egui content; the
  **spectral ring stays matte** (a saturated cyan→violet gradient, never
  bloomed). This is the one place we exceed what CSS/SVG do comfortably, and it
  is deterministic — no per-OS webview divergence.
- **Observatory:** today it's an `<iframe>` of the gateway-served
  `/cockpit/observatory.html` (a WebGL/3D scene), token-passed via a URL
  fragment (see `apps/desktop/ui/src/views/Observatory.tsx`). In the native app
  there is **no iframe**: the Observatory becomes a *first-class wgpu scene*
  rendered in-process (the egui-wgpu paint callback), fed live by the same
  gateway streams. This is the single biggest *upside* of the rewrite — and the
  single biggest *new build* (see §7), because we'd be reimplementing a 3D
  cockpit that currently lives as web code.
  - **Interim option:** keep the iframe story alive during migration by *not*
    porting Observatory first — render the native cinematic hero on the simpler
    surfaces, and keep Observatory as a web view (even launched in a child
    webview window) until the native scene reaches parity.
- All cinematic work obeys the brand **Don'ts**: no lens flare, no chromatic
  aberration, no ring glow, no drop shadows; value/tone for hierarchy; bloom on
  the core only. The GPU makes these *easier* to do correctly and consistently,
  not an excuse to violate them.

---

## 6. Migration strategy (strangler-fig)

Never a big-bang rewrite. A **strangler-fig**: stand the native UI up beside the
webview, port surfaces one at a time behind a flag, and keep both shippable
until parity is proven. The repo's parallel-follow-up contract (single-writer
ledger, disjoint file ownership, branch+worktree per task, validate-before-PR,
owner-gated merges) governs the work.

### Phase 0 — Spike & decision (1–2 weeks)
- Build a throwaway egui+wgpu spike: the header lockup with the **real core-bloom
  shader**, one live surface (Jobs over SSE), and the `Tokens.rs` generator.
- **Gate to proceed:** the bloom visibly meets the brand rubric at 4K; SSE jobs
  stream and reconnect correctly; tokens are generated, not hand-coded. If the
  spike doesn't clearly beat the web path's cinematic ceiling, **stop here** (see
  §8). This is the cheapest place to kill the project.

### Phase 1 — Native shell + protocol core (2–4 weeks)
- Tauri shell swapped to host the egui app (or a second native binary alongside
  the webview, selected by a build feature / env flag). `brain.rs` unchanged.
- Port `gateway.rs` (REST, bearer pairing, NDJSON chat, SSE jobs, owner-phrase
  modal, emergency-stop) with parity tests against a running gateway.
- Port the route registry + app shell (nav, router, health dot, offline banner,
  `Cmd/Ctrl+1..n`).
- **Parity gate:** Home (pairing + chat) and Jobs reach functional parity; the
  owner-phrase never-persist guarantee is verified; the webview build still
  ships unchanged.

### Phase 2 — Form & control surfaces (2–3 weeks)
- Port Chat, Approvals, Autonomy, Settings (incl. the brain card + emergency
  stop). These are form-heavy and fast in egui.
- **Parity gate:** every owner-gated path (approve, autonomy raise, emergency
  stop) re-prompts on `403` exactly once and matches the web behavior; Settings
  controls the brain identically.

### Phase 3 — The cinematic layer & Observatory (4–8+ weeks)
- Promote the core-bloom hero across surfaces; build the **native Observatory
  3D scene** in wgpu, fed by live gateway streams (replacing the iframe). This is
  the long pole.
- **Parity gate:** Observatory reaches *visual + functional* parity with the web
  cockpit (or better) at 4K; offline fallback ("start the brain") preserved.

### Phase 4 — Cutover & cleanup (1–2 weeks)
- Default the desktop installer to the native UI; keep the webview build as a
  fallback flag for one release.
- **Crucially, keep the Vite/PWA browser-cockpit build alive and primary for the
  *web* surface** (see §7) — the native UI does **not** replace it.

### Coexistence & rollback
- During Phases 1–3, the webview build remains the shipped desktop default; the
  native build is opt-in (flag). Rollback at any phase = ship the webview build;
  nothing about the gateway changed, so there is no server-side rollback.
- Two codebases (TS + Rust UI) coexist for the migration window — an accepted,
  bounded cost, ledgered like any parallel work.

---

## 7. Tradeoffs & risks (the honest part)

**The single biggest cost: a native UI breaks the PWA / browser-cockpit
parity.** Today `apps/desktop/ui/vite.config.ts` builds *one* artifact that is
both the Tauri payload **and** the installable web cockpit (manifest + service
worker, served from any static host). A native-Rust UI is, by definition, **not
a web app** — it cannot be installed as a PWA, cannot be served to a browser,
and cannot be opened on a locked-down machine where only a browser is allowed. A
rewrite therefore **either**:
- keeps the React/Vite UI alive *anyway* for the web/PWA surface (so we now
  maintain **two** full UIs — Rust + React — forever, not just during
  migration), **or**
- abandons the browser cockpit entirely (a real capability regression).

Neither is free. This alone is the strongest argument against the rewrite, and
it does not go away after migration.

Other risks, roughly in order:

- **Loss of web-ecosystem reuse.** The React UI leans on the browser for free:
  text input/IME, selection, clipboard, accessibility tree, hyperlinks,
  copy/paste, dev-tools, the entire npm component ecosystem. A native UI
  re-implements or re-wires all of it. egui's HUD strengths don't fully cover
  rich-text editing, complex IME, or screen-reader-grade a11y.
- **Accessibility regression.** The webview gives us a mature accessibility tree
  for free (WCAG-ish, screen readers, OS high-contrast). Native Rust UIs rely on
  `AccessKit`, which is real but younger and less complete than a browser's a11y.
  For an *operating partner* used hands-free/voice-first
  (`docs/voice/`), an a11y regression is not cosmetic — it's a capability loss.
- **Text & i18n regression.** Webviews render text and bidi/complex scripts
  superbly. egui's text is good but not browser-grade for complex layout, RTL,
  and font fallback. The brand wordmark is bespoke vector anyway, but *body*
  text (chat transcripts, multilingual content) is exactly where webviews shine.
- **Effort is large and the long pole is the Observatory.** The 3D cockpit is
  currently web code; reimplementing it natively in wgpu is a genuine graphics
  project, not a port. Underestimating Phase 3 is the most likely way this slips.
- **Two codebases during (and possibly after) migration.** Bug-for-bug protocol
  parity across two clients, two design-token consumers, two test suites.
- **Hiring/maintenance surface.** Far more contributors can edit React/CSS than
  can edit wgpu shaders + egui. A native UI narrows the bus factor.
- **The gateway protocol is a *moving* target.** Every future `/v1/*` change
  must now land in the Rust client too, not just the TS one. The append-only
  registry helps with *surfaces*, not with *protocol*.

**Effort / timeline (single capable engineer, rough):**

| Phase | Estimate |
|---|---|
| 0 — Spike & decision | 1–2 weeks |
| 1 — Shell + protocol core | 2–4 weeks |
| 2 — Form & control surfaces | 2–3 weeks |
| 3 — Cinematic layer + native Observatory | 4–8+ weeks (high variance) |
| 4 — Cutover & cleanup | 1–2 weeks |
| **Total to parity** | **~3–5 months**, Observatory-dominated, **plus indefinite dual-UI maintenance** if the web cockpit is retained. |

---

## 8. Recommendation: should we proceed?

**Honest call: do not start a full native-Rust UI rewrite now. Instead, first
exhaust elevating the existing web UI with WebGL/WebGPU.**

The cinematic-4K goal is real and worth chasing, but a *full rewrite* is a
disproportionate, partly-irreversible bet whose largest cost — **losing
PWA/browser-cockpit parity and incurring a second permanent UI codebase** — is
unrelated to the visual goal and persists forever. The cinematic upside is
concentrated in essentially one surface (the Observatory) plus the brand hero,
and most of that upside is reachable *inside the webview*:

- **WebGPU is shipping in modern webviews.** A `<canvas>` WebGPU/WebGL scene in
  the existing React app can run real shaders for the core-bloom and the
  Observatory — the same techniques (bloom, tonemapping) we'd write in wgpu —
  without abandoning the web platform. The Observatory is *already* a WebGL
  scene; the lever is to make it cinematic and embed it first-class (replace the
  iframe with an in-app `<canvas>`), not to leave the platform.
- This keeps the PWA, the accessibility tree, text/i18n quality, the npm
  ecosystem, and the single-artifact dual-use **all intact**, and is a fraction
  of the effort.

**The conditions under which a native rewrite *would* be worth it:**

1. **The web GPU ceiling is provably hit.** A focused WebGPU spike inside the
   current app demonstrably *cannot* reach the target look/perf at 4K across the
   three OS webviews (e.g. WebKitGTK lacks the WebGPU support we need, or
   per-webview divergence is unfixable). Prove this before rewriting — it is the
   actual decision criterion.
2. **The browser cockpit is being deprioritized anyway** (a product decision,
   owner-made) so the PWA-parity loss stops being a loss. If the owner decides
   the desktop app is the only blessed surface, the strongest counter-argument
   evaporates.
3. **There is sustained capacity** for a graphics-capable maintainer and for the
   indefinite second codebase, ledgered and owned per the parallel-work contract.
4. **The Phase-0 spike clears its gate** — the native core-bloom visibly beats
   the best achievable web result at 4K *and* the protocol core (SSE/NDJSON/
   owner-gates) ports cleanly.

If and only if those hold, proceed with the **egui + dedicated-wgpu** plan in
§§4–6, starting at Phase 0 and treating Phase 0's gate as a real stop/go — and
treating the whole effort as **owner-gated** (`Yes, with authorization.`),
because it changes the default desktop runtime and is architecturally
significant.

**Net:** the right next step is a **WebGPU-in-the-current-app spike**, not a
rewrite. The rewrite is a Plan B that only earns its cost once the web path is
proven insufficient and the browser-cockpit surface is no longer a requirement.
