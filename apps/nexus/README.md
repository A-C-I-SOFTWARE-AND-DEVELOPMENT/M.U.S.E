# NEXUS — Unified Agent Command Console

A mobile-first **PWA** that unifies **Antigravity**, **Google AI Studio**, and
**M.U.S.E.** into one command center, fronted by an interactive **Agent
Optimization Control** octagon for real-time inference steering.

> M.U.S.E. is the only backend the user fully controls, so it gets the deepest
> integration (embedded panel + live steering). Antigravity and AI Studio are
> **link-out** surfaces — they refuse iframe embedding and expose no SDK.

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
npm test                    # 17 unit tests for the steering math
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

## App shell — 6 tabs

| Tab | What |
|---|---|
| **Console** | Launcher tiles (M.U.S.E. embedded, Antigravity/AI Studio link-out) + AOS roster with live status dots |
| **Steer** | The Agent Optimization Control octagon + profiles + fine sliders + mapped inference readout |
| **Axiom** | The Axiom Gate — fuse steering sources, verify through 8 gates, attest, apply |
| **Agents** | All agents across surfaces; full control for M.U.S.E., open-out for the rest; embedded M.U.S.E. panel |
| **Activity** | Unified event feed (SSE from M.U.S.E.) |
| **Settings** | Connections, install prompt, push notifications, daemon pairing, voice bridge |

The shell is tuned to Apple/Google-grade feel: springy sliding tab indicator,
emphasized-easing page transitions, tactile press feedback, on-brand focus rings,
and full `prefers-reduced-motion` support.

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
