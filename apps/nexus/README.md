# NEXUS — Unified Agent Command Console

A mobile-first **PWA** that unifies **Antigravity**, **Google AI Studio**, and
**M.U.S.E.** into one command center — with an interactive **Agent Optimization
Control** octagon for real-time inference steering, an **Axiom Gate** fusion +
verification stage, and a live **Neural Observatory** "mirror" dashboard.

> M.U.S.E. is the only backend the user fully controls, so it gets the deepest
> integration (embedded panel + live steering). Antigravity and AI Studio are
> **link-out** surfaces — they refuse iframe embedding and expose no SDK.

## The MUSE command center (everything, accessible)

The **Console** tab is a full command center over the MUSE README/architecture:
a **capability registry** (`src/lib/capabilities.ts`) of **32 capabilities**
grouped by plane — Operating Layer · Cognition · Orchestration · Governance ·
Intelligence · Federation · Surfaces — each wired to the real cockpit gateway
surface (`src/adapters/cockpit.ts`, the full `/v1/cockpit/*` API). Tapping a
capability either jumps to its tab, opens its **interactive drawer**, or links to
its doc:

| Plane | Reachable from the PWA |
|---|---|
| **Operating Layer** | Six Modes · **Emergency Stop** (`/emergency-stop`) · Autonomy bands (`/autonomy`) · Runtime & monitors (`/runtime/status`) |
| **Cognition** | Memory Tree (`/memory/tree`) · Natural-language coder → packet (`/coding/plan`) · Evidence engine (`/evidence/search`) · Research Vault (`/research`) · GraphRAG query (`/graph/query`) · Neural Observatory · TokenJuice |
| **Orchestration** | Goal→PR orchestration (`/orchestrate`) · Jobs & task graph (`/jobs`) · AOS Council |
| **Governance** | Eight verification gates (Axiom tab) · **Owner Approvals** with the exact "Yes, with authorization." phrase (`/approvals`) · Evidence ledger `verify_chain` (`/audit`) · Constitution |
| **Intelligence** | Free-first model routing (`/model-routes`) · Learning loop (`/learning`) · SIA + autoresearch proposals (`/proposals`) · Open data sources |
| **Federation** | Sovereign nodes / quorum / Forge · Architecture map |
| **Surfaces** | Octagon · Skills (`/skills`) · Command palette · Voice · Activity · Android companion · MCP · Cron |

A top banner shows live **runtime status** and a one-tap **Emergency Stop**.
Every gateway-backed panel degrades to an honest "requires gateway" state when
`VITE_MUSE_BASE_URL` is unset — never fabricated data.

---

## Stack

React 18 · TypeScript · Vite · Tailwind · Zustand · React Router ·
`vite-plugin-pwa` (Workbox) · Framer Motion · SVG octagon · Supabase (auth +
persistence) · deploy to Vercel.

## Quick start

```bash
cd apps/nexus
cp .env.example .env        # fill in VITE_MUSE_BASE_URL etc. (optional for UI)
npm install
npm run dev                 # http://localhost:5173
npm test                    # 30 unit tests (steering + Axiom-Gate fusion math)
npm run build && npm run preview
```

The app runs fully **without** a backend — unconfigured integrations render
honest empty states (no fabricated metrics).

## Deploy

- **Web (Vercel):** `apps/nexus` → framework "Vite", build `npm run build`,
  output `dist`. `vercel.json` is included (SPA rewrites + SW headers).
- **Edge/DNS (Cloudflare):** point your domain at the Vercel deployment.
- Set env vars (`VITE_MUSE_BASE_URL`, Supabase keys, `VITE_VAPID_PUBLIC_KEY`) in
  the Vercel project.

## The octagon → inference mapping

The draggable central node yields a normalized 8-weight vector. Two pure,
unit-tested functions translate it:

- **`deriveGlowState(weights, vertices)`** → the live glow color + pulse + label.
  Balanced ⇒ harmony green `#3DD68C`; one vertex dominant ⇒ its accent
  (contemplation ⇒ warm orange `#FF8A3D`); two close leaders ⇒ OKLCH blend; any
  weight > 0.7 ⇒ pulsing "maxed" state. The color rides on the
  `--octa-glow` CSS variable (animated ~400ms).
- **`weightsToInference(weights)`** → `{ temperature, topP, maxThinkingTokens,
  groundingStrength, systemStyleHint }`. Documented **tunable** curves — e.g.
  `temperature = 0.2 + creativity*1.1 − coding*0.3` (clamped 0..2).

Vertex sets are swappable via `VERTEX_PRESETS` (`src/lib/vertices.ts`): ship
`default` (reasoning, creativity, logic, contemplation, coding, synthesis,
empathy, factuality) and `ops` (coding, reasoning, factuality, safety, speed,
tone, contemplation, creativity).

The emitted `SteeringVector` POSTs to M.U.S.E.'s `/api/agents/:id/steer`
(see [`ADAPTERS.md`](./ADAPTERS.md)).

## The Axiom Gate (fusion + verification)

AXIOM is MUSE's verified-intelligence kernel — *"Intelligence proposes; the
verifier disposes."* The **Axiom Gate** tab is where **fusion** happens: multiple
steering sources (the live octagon vector, saved profiles, a grounding baseline)
are fused into one vector, then run through MUSE's **8 verification gates**
(Planning · Build · Review · Test · Security · Release · Owner Approval ·
Rollback). Only an **attested** vector (all enforced gates green) gets a
content-address and can be applied to the router.

Customizable: four fusion strategies (`Blend` / `Union` / `Priority` /
`Consensus`), per-source contribution sliders, per-gate enforce toggles, and the
challenge-bound **"Yes, with authorization"** owner gate for high-risk vectors.
The fusion engine (`fuseVectors` / `runAxiomGates` / `runFusion` /
`attestationHash`) is pure and unit-tested (13 of the 30 tests).

## The Neural Observatory (the live "mirror" dashboard)

The **Observatory** tab is the live system mirror — the web/PWA renderer of MUSE's
cross-device "live neural-network wallpaper" program (the UE5 and Android
renderers share the exact same gateway contract). It consumes the read-only
`/v1/observatory/*` route family and renders the **Nero Solar System** dressing:

- **Nero Core** (the sun) at the reserved origin — pulse ∝ queue depth.
- **Planets** = GraphRAG clusters at gateway-computed `pos`, size ∝ `radius`,
  tint by dominant `type_mix`, glow by `heat` (**grey when `heat` is null** —
  "no measured activations", never a guessed glow).
- **Orbit rings** derived from planet positions; **cluster edges** weighted by heat.
- **Pipeline** — the station graph Job → Navigator → Worker → Gate → Ledger, with
  live packets and a red gate flare on a `gate.verdict` fail.
- **Brain Ladder** — routing share per tier (local / hosted / paired).
- It **pulses on every real system action** via the SSE `/stream` feed
  (`node.activate`, `job.stage`, `gate.verdict`, `route.decision`).

**Honesty (binding):** when the graph is unavailable (no gateway / no GraphRAG
cache), it renders the **dormant dressing** — dim core, **zero planets**, empty
pipeline — never fabricated activity. A separate, clearly-badged **`SAMPLE`**
demo topology lets the design be previewed without passing demo data off as
telemetry.

**Wallpaper mode** (`?wallpaper=1` or the in-app button) renders the galaxy
full-bleed with all chrome hidden — the PWA "mirror."

## App shell — 7 tabs

| Tab | What |
|---|---|
| **Console** | Launcher tiles (M.U.S.E. embedded, Antigravity/AI Studio link-out) + AOS roster with live status dots |
| **Steer** | The Agent Optimization Control octagon + profiles + fine sliders + mapped inference readout |
| **Axiom** | The Axiom Gate — fuse steering sources, verify through 8 gates, attest, apply |
| **Observatory** | The live Neural Observatory galaxy ("mirror") + pipeline + Brain Ladder + wallpaper mode |
| **Agents** | All agents across surfaces; full control for M.U.S.E., open-out for the rest; embedded M.U.S.E. panel |
| **Activity** | Unified event feed (SSE from M.U.S.E.) |
| **Settings** | Connections, install prompt, push notifications, daemon pairing, **live voice bridge (mic STT + TTS)** |

The shell is tuned to Apple/Google-grade feel: springy sliding tab indicator,
emphasized-easing page transitions, tactile press feedback, on-brand focus rings,
and full `prefers-reduced-motion` support.

## Supabase + voice (wired, optional)

- **Supabase** (`src/lib/supabase.ts`) — a thin REST client (no SDK) that
  persists Web Push subscriptions and probes the session; no-ops gracefully when
  `VITE_SUPABASE_URL` / `VITE_SUPABASE_ANON_KEY` are unset.
- **Voice bridge** (`src/lib/voice.ts`) — Web Speech API STT + TTS with a real
  microphone-permission flow; final transcripts POST to the existing M.U.S.E.
  voice bridge (`/api/voice/stt`). Driven from Settings; the bridge itself is not
  reimplemented.

## PWA

Installable (manifest + maskable icons), offline app shell, network-first
runtime caching for `/api/*`, Web Push (VAPID) for completions / errors /
owner-gated approvals, custom install button in Settings.

## Companion daemon (Phase 6)

[`companion-android/`](./companion-android) — a thin Kotlin/Compose daemon:
persistent foreground service holding the M.U.S.E. connection, home-screen
widget, Quick Settings tile, share-sheet target, and an Approve/Deny
authorization relay. It does **not** reimplement the UI; it shares this
backend contract. See [`companion-android/CONTRACT.md`](./companion-android/CONTRACT.md).

## Why not iframe Antigravity / AI Studio?

They send `X-Frame-Options` / restrictive `frame-ancestors` CSP and have no
embeddable SDK. NEXUS deep-links out (new tab / Android Custom Tab). This is
deliberate — see the comment in `src/adapters/index.ts`.
