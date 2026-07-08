# musehq.io on OpenCode — the chat shell (`/chat/`)

> **TL;DR** — The **OpenCode chat shell** lives in [`web/musehq/`](../web/musehq/)
> and ships on musehq.io under **`/chat/`**. Site root is the Singularity
> cockpit (Muse Omni) — see [`cockpit-singularity.md`](cockpit-singularity.md).
> This app vendors OpenCode's chat renderer (MIT), keeps **their chat layout**,
> and applies the MUSE "Singularity" look.

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

1. Puts the **Singularity cockpit** (`cockpit.dc.html`) at the site **root**
   (`index.html`) — Muse Omni with Connect, jobs, approvals, providers.
2. Builds `web/musehq` into **`/chat/`** (OpenCode chat shell; `MUSEHQ_BASE=/chat/`).
3. Keeps `/legacy.html` as an alias of the Singularity cockpit for old bookmarks.
4. Carries over every cockpit static surface: the 3D **Atlas** (`/atlas/`),
   **Studio** (`/studio.html`), **Observatory** (`/observatory.html`), legal
   pages, PWA icons + manifest, `robots.txt`, `sitemap.xml`, `og.png`.

Day-to-day local ops: `muse omni` (full-agent Singularity). Optional admin:
`muse omni --with-admin` or `muse dashboard`.

### Service-worker migration

The Singularity cockpit may install a service worker at `/sw.js`. Returning
visitors who previously cached the OpenCode-at-root shell should hard-refresh
once after deploy; `/chat/` is the OpenCode surface going forward.

## Feature parity

| Singularity root (Muse Omni) | OpenCode shell (`/chat/`) |
|---|---|
| Connect / pairing, jobs, approvals | Message/part chat thread |
| OMNI providers, autonomy, memory | Streaming markdown + syntax highlight |
| Atlas / Studio / Observatory (inline + links) | Reasoning ("thinking") cards |
| Local Admin link → `:9119` | Tool cards (when gateway transport is wired) |
| Legal pages, PWA install | Copy-link-to-message, show-more/less |

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
endpoint) is a **follow-up** here because the Singularity cockpit, Studio, and
Observatory are inline-script-heavy and would break under a blanket enforcing
policy — they need a path-scoped policy, which is out of scope for this PR. The
OpenCode app itself already carries **no inline script** (SW registration lives in
`main.tsx`), so it is ready for a `'self'`-only `script-src` under `/chat/`.

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
- **Connect UI on `/chat/`:** pairing remains on Singularity root; optional
  BYOK/Connect dialog for the OpenCode shell is still a follow-up.

## Owner gate

Changing what musehq.io serves by default is **owner-gated**. Restoring
Singularity as the public root (and demoting the incomplete OpenCode shell to
`/chat/`) is the intentional Muse Omni fix; merge still waits for the owner's
explicit `Yes, with authorization.` when required by release policy.
