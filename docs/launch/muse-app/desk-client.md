# DESK — muse desktop client surfaces

Builder-grain snapshot for the muse App Grainler Parallel Swarm.

- **Grain:** DESK — the desktop client surfaces (Chat, Jobs, Approvals, Autonomy,
  Settings) built on the already-merged G0.2 Tauri scaffold.
- **Branch:** `claude/muse-app-desk-client`
- **Base commit:** `d4c66c0927ea904187b697135111b75d1e2ca77e` (`origin/main` at start).
- **Status:** built, validated (UI hard gate green, warning-clean), pushed. No PR
  opened (per grain contract).

## Intent

Turn the lean G0.2 desktop scaffold (a Tauri v2 shell around a Vite + React 19 +
TS UI with a *single* live Home route) into a **full Singularity desktop client**
with real, design-system-styled feature surfaces. Every surface is a new route
registered through the scaffold's **append-only route registry** (`src/routes.ts`),
so the shell (`App.tsx`) and the built-in Home route are untouched — adding these
routes was purely additive. The client speaks the exact same gateway protocol as
the browser cockpit (`gateway/cockpit/static/index.html`): bearer-token pairing,
SSE jobs over fetch + ReadableStream, NDJSON chat, and the owner-gated POSTs that
carry the owner phrase in the request. All work is confined to `apps/desktop/ui/**`
plus this snapshot; `src-tauri/`, `design-system/`, and `apps/android/` were not
touched.

## Views added (routes)

Registered from `src/views/register.ts` (a feature module imported once for its
side effect from `main.tsx` — the registry contract says grains register from
their own module, never by editing a shared switch). Nav order: Home (0,
scaffold) · Chat (10) · Jobs (20) · Approvals (30) · Autonomy (40) · Settings
(90, last).

1. **Chat** (`src/views/Chat.tsx`) — full-page NDJSON chat via `chat()`. User
   bubbles right (`--void-2`), assistant left with the one spectral accent (a
   ring-gradient left border, `.msg.asst`), streaming append, composer that sends
   on Enter and newlines on Shift+Enter. Unpaired devices are pointed at Settings.
2. **Jobs** (`src/views/Jobs.tsx`) — live SSE list via `subscribeJobs()`. Each job
   is a card with a **PhaseRail** (queued→running→approval→approved→publishing→
   published), a status pill, and the worker/branch line. Reconnect + poll fallback
   are already in the client; a live/reconnecting indicator reflects stream
   liveness.
3. **Approvals** (`src/views/Approvals.tsx`) — pending approvals with the proposed
   action. **Approve/Deny prompt for the owner phrase at action time**
   (`window.prompt` via `promptOwnerPhrase`, never stored) and send it per the
   cockpit; a 403 re-prompts exactly once. Refreshes on a 12s cadence.
4. **Autonomy** (`src/views/Autonomy.tsx`) — shows level + capabilities
   (auto-approved / requires-approval / always-deny). **Raising the level is
   owner-gated** (prompted phrase, owner-gate detected via the shared
   `isAutonomyRaise` ranking); **lowering and Revoke→Assisted are token-only**. A
   403 on a raise re-prompts once. The workspace-path field appears for
   High-Autonomy Coding.
5. **Settings** (`src/views/Settings.tsx`) — three cards: **Gateway** (view/change
   base URL, persisted to `muse.gateway.base`, with a reachability ping); **Device
   pairing** (the scaffold's owner-gated pair/start → pair/confirm flow, plus
   paste-a-token and clear-token); and an **Emergency stop** (owner-gated, danger
   styling) that confirms, prompts for the phrase, and re-prompts once on 403.

Shared additions:

- **PhaseRail** (`src/components/PhaseRail.tsx`) — the design-language PhaseRail
  component, driven by the shared `phaseStates()` vocabulary so it never drifts
  from the cockpit's rail.
- **Left nav + header + offline banner** — the scaffold already builds the nav
  from the route registry and renders the Glyph + "muse" wordmark + a status
  dot in the header. This grain adds an **offline banner** (`App.tsx`, the single
  8-line shell edit) shown when the health poll reports offline, pointing the user
  at the gateway URL in Settings.

## Gateway calls used

Extended `src/lib/gateway.ts` (additive — no existing export changed) with typed
wrappers + shared helpers, all mirroring the cockpit:

| Surface | Endpoint(s) | Owner-gated? |
|---|---|---|
| Chat | `POST /v1/jarvis/chat` (NDJSON, via existing `chat()`) | no |
| Jobs | `GET /v1/cockpit/jobs/stream` (SSE), `GET /v1/cockpit/jobs` (poll fallback) — via existing `subscribeJobs()` | no |
| Approvals | `GET /v1/cockpit/approvals`, `POST /v1/cockpit/approvals/{id}` | **approve** (phrase in body; 403 re-prompts) |
| Autonomy | `GET /v1/cockpit/autonomy`, `POST /v1/cockpit/autonomy` (set / `revoke:true`) | **raise** only (phrase in body; 403 re-prompts) |
| Emergency stop | `POST /v1/cockpit/emergency-stop` | **yes** (phrase in body; 403 re-prompts) |
| Pairing / health | `POST /v1/cockpit/pair/{start,confirm}`, `GET /v1/health` (existing) | confirm (owner phrase) |

New exports: `phaseStates` / `JOB_PHASES` / `JOB_PHASE_LABEL`, `getApprovals` /
`decideApproval`, `getAutonomy` / `setAutonomy` / `revokeAutonomy` /
`AUTONOMY_LEVELS` / `AUTONOMY_RANK` / `isAutonomyRaise`, `emergencyStop`, and
`promptOwnerPhrase`. All authenticated calls reuse the existing `api()` wrapper
(bearer token from localStorage `muse.cockpit.token`).

## Owner-gate handling (audit)

- **Phrase prompted at action time, never persisted.** `promptOwnerPhrase()` uses
  `window.prompt` and returns the trimmed phrase (or null on cancel); it is handed
  straight to the request body and discarded. No localStorage, no module-level
  state, no React state ever holds the phrase.
- **The three owner-gated actions — approve, autonomy-raise, emergency-stop —**
  each prompt before sending and **re-prompt exactly once** on a server `403`
  (surfaced as `forbidden` from the client). Deny and autonomy-lower/revoke send
  no phrase, but a 403 on Deny still re-prompts (cockpit parity).
- **Raise detection** uses the same ordinal ranking the cockpit uses
  (`AUTONOMY_RANK`); sending the phrase on a lower/equal change is harmless and is
  avoided anyway.
- **Bearer token stays in localStorage** (`muse.cockpit.token`), set only via
  pairing or explicit paste, and clearable from Settings. **No secrets in code.**
- **Service worker never caches `/v1/*`.** The scaffold's `vite.config.ts` keeps
  `globPatterns` shell-only and `navigateFallbackDenylist: [/^\/v1\//]`; this grain
  did not touch it. Verified post-build: `dist/sw.js` has **zero** `/v1/`
  references and the precache manifest lists only shell assets (html/svg/png/css/
  js/webmanifest). The API paths appear only as fetch URLs in the app bundle, as
  expected.

## Design language

Strict adherence to `docs/brand/muse-design-language.md`: void `#050507` field;
white core is the hero; the spectral ring (`--ring-1`→`--ring-2`) is a **matte**
accent only (phase-rail "done"/"current" nodes are flat tonal fills — no glow, no
neon, no drop-shadow); value-ladder hierarchy; status colors (`--ok`/`--warn`/
`--danger`) only for status (approve = ok-toned outline, deny/estop = danger,
banners = the cockpit's danger tint). All new CSS lives in `app.css` using the
`tokens.css` variables; the only literal hexes added (`#04060c`, `#1a0e10`,
`#ffd7d9`) are the exact values the scaffold/cockpit already use for "void text on
bright fill" and the danger banner. Motion reuses the scaffold's emphasized easing
(250–350ms). A focus-visible ring (2px `--ring-1`) was added to all controls (the
design-language rule "never remove the focus ring").

## Validation results

### UI production build — HARD GATE — PASS

```
cd apps/desktop/ui && npm install && npm run build
```

- `npm install` → 354 packages, **0 vulnerabilities**.
- `npm run build` (= `tsc -b && vite build`) → **green, warning-clean**. 45 modules
  transformed (was 38; +7 new source files). `dist/` emitted with `index.html`,
  hashed JS/CSS, `manifest.webmanifest`, and the PWA service worker (`sw.js`, 16
  precache entries). A clean rebuild (`rm -rf dist`) is also green.
- `npx tsc -b --noEmit` standalone typecheck passes (exit 0) under the scaffold's
  strict config (`strict`, `noUnusedLocals`, `noUnusedParameters`,
  `verbatimModuleSyntax`, `erasableSyntaxOnly`).
- **No lint script** exists in `package.json` (there is no `npm run lint`), so
  there is no lint gate to keep green; tsc strict is the type/quality gate and it
  passes.
- **SW `/v1/*` exclusion** re-verified on the build output (see audit above).

### Tauri Rust shell — not exercised

This grain touched **no** `src-tauri/**` files, so the Tauri build is unchanged
from G0.2 (whose snapshot records the Linux webkit2gtk system-lib caveat). The UI
`dist/` this grain produces is exactly what the shell loads.

## Residual risks

1. **Owner-gate enforcement is server-side; the client is a faithful courier.**
   The UI prompts and forwards the phrase but does not (and must not) validate it
   — the gateway is the authority. If the server's owner-gate contract changes
   (e.g. a different field name than `authorization`, or a status other than 403),
   these views need updating in lockstep with the cockpit. They currently mirror
   `gateway/cockpit/static/index.html` exactly.
2. **Two chat surfaces.** The scaffold's Home route still embeds a chat; this grain
   adds a dedicated full-page **Chat** route. Both work and share the same
   `chat()` client. Home was intentionally left untouched (it is the scaffold's
   landing/health demo); a future cleanup could slim Home to a dashboard and let
   Chat own conversation, but that would edit a scaffold file and was out of scope.
3. **`main.tsx` edit.** Wiring the feature routes required one side-effect import
   (`import "./views/register"`) in `main.tsx` — explicitly sanctioned by the
   scaffold ("a grain can add a single side-effect import here"). It is the only
   edit to a scaffold-authored file besides the 8-line offline banner in `App.tsx`;
   both are inside the owned `apps/desktop/ui/**` path.
4. **Polling cadences are fixed.** Approvals refresh every 12s and the header
   health pings every 10s (scaffold). These are deliberately gentle; if the gateway
   ever exposes an approvals SSE stream, Approvals should switch to it the way Jobs
   already streams.
5. **Inlined design tokens (inherited).** `src/styles/tokens.css` is still the
   scaffold's inline copy of the canonical tokens; new CSS consumes those variables,
   so when G0.1 `@muse/design-system` lands and the token sheet is swapped to an
   import, these surfaces inherit it for free.
6. **No collisions with sibling grains.** Work is confined to `apps/desktop/ui/**`
   (4 scaffold files modified, 7 new files) and this snapshot. `web/`,
   `apps/android/`, `design-system/`, `gateway/`, `src-tauri/`, and the central
   ledger were not touched.

## Reproduce

```bash
git checkout claude/muse-app-desk-client
cd apps/desktop/ui && npm install && npm run build   # hard gate (green, warning-clean)
npm run dev                                            # serve the UI on :1420
# Native shell (needs Rust + Tauri CLI + Linux webkit2gtk libs); unchanged from G0.2:
cd ../src-tauri && cargo tauri dev
```
