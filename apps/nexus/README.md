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

## Zero-server use (no terminal, ever)

The fastest path needs **no local server and no terminal**: install the PWA, open
the first-run wizard, paste **one OpenRouter key**, and **Chat + Fusion work
instantly** — straight from the browser via OpenRouter (Claude, GPT, Gemini & 300+
models through one key). The key is stored encrypted on-device.

- **Chat / Fusion** auto-select a transport: `direct` (browser → OpenRouter) when
  an OpenRouter key is present, else the optional local `gateway`. No process to run.
- The **MUSE cockpit gateway** (orchestration, memory, fleet, observatory) is the
  only thing that still needs a backend — it's optional and gated behind
  "Advanced" in the wizard.

## One-click install (autonomous bring-up)

```bash
cd apps/nexus && ./install.sh        # Linux / macOS / WSL2 / Termux
#   apps\nexus\install.ps1           # Windows (PowerShell)
```

The installer checks Node, installs deps, **generates a VAPID keypair**, writes
`.env` (seeding the gateway URL), builds the PWA, and serves it — then opens to a
first-run **"Install & Connect"** wizard that establishes *everything*
autonomously:

1. **Discovers** the MUSE gateway (tries your URL, the page origin, and
   `127.0.0.1:8765`, probing the open `/v1/health` route).
2. **Pairs** this device through the cockpit handshake (`pair/start` →
   `pair/confirm`) — the one owner-gated step, so it asks for the owner phrase
   once and stores the returned per-device Bearer token.
3. **Verifies** capabilities, then wires the **Observatory**, **runtime**,
   **push**, **Supabase**, and **voice** — each reporting its own honest status
   (optional/unsupported connections are skipped, never faked).

Env flags: `START_GATEWAY=1` also boots the local cockpit gateway;
`MUSE_GATEWAY_URL=…` and `NEXUS_PORT=…` override defaults. Runtime config is
stored in `localStorage`, so the wizard reconfigures the live app **without a
rebuild** — re-open it anytime from Settings → "Install & connect everything".

## Manual / dev

```bash
cd apps/nexus
cp .env.example .env        # optional — the wizard can set these at runtime
npm install
npm run dev                 # http://localhost:5173
npm test                    # 30 unit tests (steering + Axiom-Gate fusion math)
npm run build && npm run preview
```

The app runs fully **without** a backend — unconfigured integrations render
honest empty states (no fabricated metrics).

## Deploy to Vercel (one click / one command)

[![Deploy with Vercel](https://vercel.com/button)](https://vercel.com/new/clone?repository-url=https%3A%2F%2Fgithub.com%2FA-C-I-SOFTWARE-AND-DEVELOPMENT%2FM.U.S.E&root-directory=apps%2Fnexus&project-name=nexus&framework=vite)

- **One-click:** the button above clones + deploys with **Root Directory =
  `apps/nexus`**, framework **Vite**, output `dist` (auto-detected). `vercel.json`
  is included (SPA rewrites + SW headers).
- **One-command:** `VERCEL_TOKEN=xxxxx ./deploy.sh` (token from
  <https://vercel.com/account/tokens>, or paste it in Settings → Connections &
  Credentials → Vercel). First run auto-creates the project.
- **Git integration:** import the repo in Vercel once with Root Directory
  `apps/nexus`; every push then auto-deploys.
- **Edge/DNS (Cloudflare):** point your domain at the Vercel deployment.
- Runtime config (gateway URL, keys) is entered **in the app** (connect wizard +
  credentials manager) — no Vercel env vars required, though
  `VITE_MUSE_BASE_URL` / `VITE_VAPID_PUBLIC_KEY` can pre-seed them.

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

## Connections & credentials (enter anything through the app)

Settings → **Connections & Credentials** is an in-app manager for every
third-party connection that needs a username / password / API key / token —
`src/lib/credentials.ts` registers them by category (Backend · Model Providers ·
Messaging Bridges · Dev Integrations · Push & MCP) with the **canonical MUSE env
var names**:

- **App credentials** (gateway URL + device token, Supabase URL/anon key, VAPID
  public key) apply immediately to the live runtime config — no rebuild.
- **Gateway credentials** (Anthropic / OpenAI / Google / OpenRouter / Novita /
  NIM keys; Telegram / Discord / Slack / WhatsApp / Signal / Email; GitHub /
  Vercel / Cloudflare; MCP) are collected and exported as a ready-to-apply
  **`.env` snippet** (Copy) to paste into `~/.hermes/.env` on the gateway host —
  because MUSE keeps provider/messaging keys server-side by design (there is no
  remote secrets endpoint to push them to).

Secret fields are masked with a reveal toggle and stored only in this device's
`localStorage`; "Forget all credentials" clears them.

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
