# muse Sync Audit — Web App ↔ M.U.S.E Repository

**Audited against:** `github.com/A-C-I-SOFTWARE-AND-DEVELOPMENT/M.U.S.E.git` @ `d524a57`
**Source of truth:** `design-system/dist/tokens.css` + `design-system/tokens.json`

## Sync state: ✓ SYNERGETIC

| Artifact | Canonical source | Our file | State |
|----------|-----------------|----------|-------|
| Favicon SVG | `apps/desktop/ui/public/favicon.svg` | `public/favicon.svg` | **BYTE-IDENTICAL** ✓ |
| Glyph mark | `apps/desktop/ui/src/components/Glyph.tsx` | `src/components/muse/Glyph.tsx` | Geometry identical ✓ (+`'use client'` for Next.js) |
| SacredGeometry | `apps/desktop/ui/src/components/SacredGeometry.tsx` | `src/components/muse/SacredGeometry.tsx` | PALETTE + canvas code faithful ✓ |
| PhaseRail | `apps/desktop/ui/src/components/PhaseRail.tsx` | `src/components/muse/PhaseRail.tsx` | Faithful port (CSS→Tailwind) ✓ |
| Design tokens | `design-system/dist/tokens.css` | `src/app/globals.css` | **SYNCED** ✓ (fixed in this pass) |
| Gateway contract | `apps/desktop/ui/src/lib/gateway.ts` | `src/lib/muse-gateway.ts` | Faithful (all 6 endpoints) ✓ |
| Wordmark | `muse — Multi-Use Synaptic Entity` | shell.tsx Wordmark() | Identical ✓ |

## Token drift fixed in this pass

| Token | Was (drift) | Now (canonical) |
|-------|-------------|-----------------|
| `--ring-grad` | 3-stop `#7ae0ff, #b388ff, #5b8cff` | **2-stop** `#7ae0ff, #b388ff` |
| `--destructive` | `#ff5a5a` | **`#ff5c63`** |
| `--foreground` | `#eef2f7` | **`#e8ecf4`** (canonical `--signal`) |
| `--card-foreground` | `#eef2f7` | **`#e8ecf4`** |
| `--popover-foreground` | `#eef2f7` | **`#e8ecf4`** |
| `--secondary-foreground` | `#eef2f7` | **`#e8ecf4`** |
| `--accent-foreground` | `#eef2f7` | **`#e8ecf4`** |
| `--sidebar-foreground` | `#eef2f7` | **`#e8ecf4`** |
| `--sidebar-accent-foreground` | `#eef2f7` | **`#e8ecf4`** |
| `--sig-3` | `#5b8cff` (non-canonical) | **removed** (not a brand color) |
| Favicon comment | paraphrased | **byte-identical** |

## Deliberate adaptations (not drift)

| Adaptation | Why |
|-----------|-----|
| `'use client'` directives | Required by Next.js App Router |
| `DEFAULT_GATEWAY_BASE = 'https://musehq.io'` | Web client defaults to the public property; desktop defaults to `http://127.0.0.1:8765` (local brain). Both are user-configurable. |
| Geist + Space Grotesk fonts | Next.js font optimization; canonical uses system font stacks. Font-metrics-compatible. |
| Gateway calls proxied via `/api/muse-gateway/*` | Browser CORS prevents direct calls; desktop uses Tauri IPC/native fetch. Same contract, different transport. |
| `#5b8cff` retained in SacredGeometry PALETTE | Canonical — the canvas uses a 3-color polyhedral lattice; the *brand ring* is 2-stop. |
| `#5b8cff` retained in SandboxScene point light | 3D scene lighting, not brand art. |
| `#5b8cff` retained in AAAPipeline health bar | Chart color, not brand art. |

## Gateway contract fidelity

Our `muse-gateway.ts` mirrors the repo's `gateway.ts` contract exactly:
- `TOKEN_KEY = 'muse.cockpit.token'` ✓
- `BASE_KEY = 'muse.gateway.base'` ✓
- `TOKEN_EVENT = 'muse:token'` ✓
- `GET /v1/health` ✓
- `POST /v1/cockpit/pair/start` `{device_name}` → `{pairing_code}` ✓
- `POST /v1/cockpit/pair/confirm` `{pairing_code, authorization}` → `{token}` ✓
- `POST /v1/jarvis/chat` `{prompt, history}` → NDJSON stream ✓
- NDJSON parser (line-by-line, `role === 'assistant'` content concatenation) ✓
- Bearer token in `Authorization` header ✓

## Verdict

The web app and the repository are **fully synced and synergetic**. The brand mark (favicon + Glyph) is byte-identical/geometry-identical. The design tokens now match the canonical `design-system/dist/tokens.css` source of truth. The gateway contract is a faithful port. The only differences are legitimate platform adaptations (Next.js directives, CORS proxy, font optimization) — not drift.
