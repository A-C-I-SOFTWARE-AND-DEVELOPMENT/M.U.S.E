# musehq.io on OpenCode — the chat cockpit

> **TL;DR** — musehq.io is rebuilt **on top of OpenCode's actual chat code**.
> We vendor OpenCode's own chat renderer (MIT) and compose it into a MUSE
> Solid+Vite app, keeping **their chat layout** and applying **the MUSE
> "Singularity" look**, while preserving every existing cockpit feature. The
> new app lives in [`web/musehq/`](../web/musehq/).

## Why this shape

The request was: *build musehq.io on top of the OpenCode code, keep all
features of both, keep their chat layout, wear the MUSE look.*

OpenCode ships several UIs:

| OpenCode surface | What it is | Fit for musehq.io |
|---|---|---|
| `packages/tui` | Go/Bubbletea terminal UI | Not a website |
| `packages/app` | Full SolidJS IDE client | Bound to a live OpenCode **server** (SDK v2, tabs, file trees, worktrees) — not deployable against musehq's stateless `/api/chat` |
| `packages/session-ui` | Rich chat renderer | Drags in all 87 `@opencode-ai/ui` components (kobalte/pierre/shiki/motion) + the server data context |
| **`packages/web` Share viewer** | **Self-contained** session/chat renderer (`opencode.ai/s/<id>`) | ✅ Renders OpenCode's exact chat layout from a plain message store, **no live server** — the deployable seam |

We therefore vendor the **Share-viewer chat renderer** and drive it from a
message store we control. This is genuinely "on top of the OpenCode code": the
message/part components, tool cards, diffs, markdown streaming, and icons are
OpenCode's, verbatim.

## Architecture

```
                 web/musehq  (SolidJS + Vite)
 ┌───────────────────────────────────────────────────────────────┐
 │  Shell.tsx      rail │ topbar + Thread + Composer               │
 │                                                                 │
 │  Composer ──send──▶ store.ts ──▶ MessageV2 message/part store   │
 │                        │                                        │
 │                        ├─▶ api.ts  POST /api/chat  (SSE deltas) │
 │                        │      └── OpenAI delta frames ──────────┼─▶ /api/chat (Edge)
 │                        ▼                                        │
 │  Thread.tsx ──renders──▶  vendor/opencode/share/part.tsx  ◀─────┤  (OpenCode's layout)
 │                                                                 │
 │  theme.css  ── redefines OpenCode's --sl-color-* etc. ──▶ MUSE  │  (the reskin)
 └───────────────────────────────────────────────────────────────┘
```

### Their layout, our look

OpenCode's vendored components are styled **entirely through CSS custom
properties** (mostly Starlight `--sl-color-*`, because upstream renders inside
Astro Starlight). The reskin (`src/theme.css`) keeps the markup and layout
byte-for-byte and simply **redefines those variables** in terms of the MUSE
Singularity tokens (`src/tokens.css`):

| OpenCode variable | MUSE token |
|---|---|
| `--sl-color-bg` | `--void` (`#050507`) |
| `--sl-color-bg-surface` | `--void-2` |
| `--sl-color-text` | `--signal` |
| `--sl-color-text-secondary` | `--signal-dim` |
| `--sl-color-divider` / `-border` / `-hairline` | `--edge` |
| `--sl-color-green` / `-red` / `-orange` | `--ok` / `--danger` / `--warn` |
| `--sl-color-blue` / `-accent` | `--ring-1` / `--ring-2` (the spectral ring) |

The cockpit shell (rail, orb, composer, glass topbar) is MUSE-original CSS in
the same file. Net effect: **OpenCode's chat, MUSE's face.**

### Data flow

`store.ts` holds sessions as OpenCode `MessageV2` messages-with-parts, so the
vendored `<Part>` renders them directly. On send it appends a user text part
and a streaming assistant text part, then `api.ts` POSTs to `/api/chat` and
folds each OpenAI `delta.content` into the assistant part — Solid's fine-grained
reactivity streams it into OpenCode's renderer live.

`/api/chat` (repo-root Edge function) is a **text** stream, so the public path
shows streamed assistant text; the renderer's full tool-card UI (bash/edit/diff
cards) is retained for the richer paired-gateway transport.

## Deploy

[`scripts/deploy/build_cockpit_vercel.sh`](../scripts/deploy/build_cockpit_vercel.sh)
(invoked by `vercel.json`) now:

1. Builds `web/musehq` → the site **root** (`index.html` + `assets/` + `sw.js`).
2. Preserves the previous single-file cockpit **verbatim** at `/legacy.html`
   (reachable from the rail as "Classic cockpit").
3. Carries over every cockpit static surface: the 3D **Atlas** (`/atlas/`),
   **Studio** (`/studio.html`), **Observatory** (`/observatory.html`), legal
   pages, PWA icons + manifest, `robots.txt`, `sitemap.xml`, `og.png`.

### Service-worker migration

The old cockpit installed a service worker at `/sw.js` that cached its shell.
The new app ships a **kill-switch** `/sw.js` (`web/musehq/public/sw.js`) that
deletes old caches, unregisters, and reloads controlled clients — so returning
PWA visitors migrate to the new app instead of being stuck on the cached shell.

## Feature parity

| Kept from the cockpit ("my look") | Kept from OpenCode ("their layout") |
|---|---|
| Singularity palette, orb, glass | Message/part chat thread |
| Atlas / Studio / Observatory | Streaming markdown + syntax highlight |
| Legal pages, PWA install | Reasoning ("thinking") cards |
| BYOK + `/api/chat` lanes, honest offline banner | Tool cards (bash/edit/read/grep/… + diffs) |
| Classic cockpit at `/legacy.html` | Copy-link-to-message, show-more/less |

## Security

LLM output is rendered on the first-party origin, so the markdown renderer is
hardened (`vendor/opencode/share/content-markdown.tsx`): rendered HTML is passed
through **DOMPurify**, and the link renderer escapes `href`/`title` and
allowlists the URL scheme. The shiki code/bash paths HTML-escape by construction.

**Required before this handles real BYOK keys / before merge-to-prod:** the
repo-wide CSP in `vercel.json` is currently `Content-Security-Policy-Report-Only`
with `script-src 'unsafe-inline' 'unsafe-eval'` and `connect-src https:`. That is
a weak backstop for an origin that can hold a provider key in memory. Promoting
it to an enforcing `Content-Security-Policy` (nonce/hash instead of
`'unsafe-inline'`, `connect-src` narrowed to the provider hosts, a `report-to`
endpoint) is a **follow-up** here because the legacy cockpit, Studio, and
Observatory are inline-script-heavy and would break under a blanket enforcing
policy — they need a path-scoped policy, which is out of scope for this PR. The
new app itself already carries **no inline script** (SW registration lives in
`main.tsx`), so it is ready for a `'self'`-only `script-src`.

## Known follow-ups

- **CSP enforcement** (see Security above) — path-scoped enforcing policy.
- **Bundle:** shiki ships every language grammar as a lazy chunk (~10 MB on
  disk, loaded on demand). Curate a language set to shrink the deploy.
- **Tool cards live:** wire the paired-gateway transport (structured
  `tool.start/complete` events) into the store so tool cards render live, not
  only text.
- **User-bubble width:** OpenCode collapses long user text; tune the
  `--*-tool-width` / user-part widths for MUSE.
- **Multi-session persistence:** the rail lists in-memory sessions; persist to
  the gateway.

## Owner gate

Changing what musehq.io serves by default is **owner-gated**. This lands as a
**draft PR**; merge to `main` waits for the owner's explicit
`Yes, with authorization.`
