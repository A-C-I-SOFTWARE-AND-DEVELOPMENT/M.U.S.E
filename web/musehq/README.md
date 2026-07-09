# musehq.io — OpenCode chat shell (secondary surface)

This is the **OpenCode-layout chat shell** dressed in the MUSE "Singularity"
look. On the public site it ships under **`/chat/`**. The canonical Muse Omni
operations UI (Connect, jobs, approvals, providers, atlas) is the Singularity
cockpit at site root — see [`docs/cockpit-singularity.md`](../../docs/cockpit-singularity.md).

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
  Rail.tsx           # sessions + destinations (Muse Omni / Atlas / Studio / Observatory)
  Thread.tsx         # renders the store through OpenCode's <Part>
  Composer.tsx       # the message composer
  messages.ts        # i18n strings the vendored renderer consumes (MUSE-branded)
```

## Develop

```bash
# Terminal 1 — the muse admin API (optional; for /api proxy during local chat):
muse dashboard --no-open                   # http://127.0.0.1:9119
# or: python -m hermes_cli.main dashboard --no-open

# Terminal 2 — the Vite dev server (proxies /api → the API above):
cd web/musehq
npm install
npm run dev                                # http://127.0.0.1:9200
```

Set `MUSE_API_ORIGIN` to point the dev proxy at a different API origin.

## Build / deploy

`npm run build` emits `dist/`. The Vercel/cockpit deploy is assembled by
[`scripts/deploy/build_cockpit_vercel.sh`](../../scripts/deploy/build_cockpit_vercel.sh),
which puts the **Singularity cockpit at site root** and this OpenCode chat
shell under `/chat/` (built with `MUSEHQ_BASE=/chat/`), plus Atlas, Studio,
Observatory, legal pages, and PWA assets.

Day-to-day local ops: `muse omni` (full-agent Singularity cockpit).
