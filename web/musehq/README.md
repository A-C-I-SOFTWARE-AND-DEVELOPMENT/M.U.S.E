# musehq.io — the OpenCode-layout cockpit, in the MUSE look

This is the front-end served at **musehq.io**. It is built **on top of
OpenCode's own chat layout** (vendored, MIT — see
[`vendor/opencode/VENDOR.md`](vendor/opencode/VENDOR.md)) and dressed in the
MUSE "Singularity" look. Their layout, our look — with both feature sets kept.

## Stack

- **SolidJS + Vite** (so we can compose OpenCode's SolidJS chat renderer directly).
- OpenCode's vendored **Share-viewer** chat components under `vendor/opencode/`.
- The MUSE reskin + cockpit shell under `src/`.

## What's where

```
vendor/opencode/     # OpenCode's chat renderer, vendored verbatim (MIT)
src/
  theme.css          # THE RESKIN: maps OpenCode's CSS vars → MUSE tokens + shell layout
  tokens.css         # canonical MUSE "Singularity" design tokens (copy of the cockpit's)
  api.ts             # /api/chat SSE client (OpenAI delta frames)
  store.ts           # session store → OpenCode MessageV2 message/part shapes
  Shell.tsx          # cockpit shell: rail | topbar + thread + composer
  Rail.tsx           # sessions + cockpit destinations (Atlas / Studio / Observatory / Classic cockpit)
  Thread.tsx         # renders the store through OpenCode's <Part>
  Composer.tsx       # the message composer
  messages.ts        # i18n strings the vendored renderer consumes (MUSE-branded)
```

## Develop

```bash
# Terminal 1 — the muse web/gateway API (serves /api/chat):
python -m hermes_cli.main web --no-open        # http://127.0.0.1:9119

# Terminal 2 — the Vite dev server (proxies /api → the API above):
cd web/musehq
npm install
npm run dev                                    # http://127.0.0.1:9200
```

Set `MUSE_API_ORIGIN` to point the dev proxy at a different API origin.

## Build / deploy

`npm run build` emits `dist/`. The Vercel/cockpit deploy is assembled by
[`scripts/deploy/build_cockpit_vercel.sh`](../../scripts/deploy/build_cockpit_vercel.sh),
which builds this app to the site root, preserves the previous single-file
cockpit at `/legacy.html`, and carries over every cockpit static surface
(Atlas, Studio, Observatory, legal pages, PWA assets).

## The `/api/chat` contract

`POST /api/chat { model?, messages:[{role,content}] }` → SSE of OpenAI delta
frames (`data: {"choices":[{"delta":{"content"}}]}` … `data: [DONE]`).
`501` when no server key and no BYOK key is present — the UI shows an honest
"add a key / pair a gateway" banner rather than inventing output. This is a
**text** stream; the renderer's tool-card UI lights up on the richer
paired-gateway transport.

See [`docs/musehq-opencode-cockpit.md`](../../docs/musehq-opencode-cockpit.md)
for the full design.
