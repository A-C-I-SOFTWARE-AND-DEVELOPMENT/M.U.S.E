# muse Cockpit — the "Singularity" design (`cockpit.dc.html`)

This is the imported **Claude Design** project *muse Cockpit* (`muse Cockpit.dc.html`),
landed in the repo as a first-class, offline-capable cockpit page.

- **Served at:** `/cockpit/cockpit.dc.html` (the gateway cockpit static mount;
  `gateway/cockpit/static/cockpit.dc.html`).
- **Design language:** the "Singularity / Cinematic synthesis" system — one white
  core in the void, a single matte spectral ring, tonal (never drop-shadow)
  elevation, hierarchy by value. The token block at the top of the page is
  aligned to [`design-system/tokens.json`](../design-system/tokens.json) and is
  the canonical palette for the browser cockpit.
- **Surfaces:** boot/ignition sequence, sticky header lockup + live status, a
  left nav rail, and view sections (jobs, chat composer, approvals, providers,
  toolsets, the 3D Systems Atlas embed, pairing, emergency-stop). It runs in a
  self-contained **demo mode** with no backend and **lights up live** when paired
  to a gateway (`/v1/cockpit/pair/start`, `/v1/cockpit/runtime/status`,
  `/v1/health`) — the same honest "works-offline, lights-up-when-connected"
  contract as the Neural Observatory.

## How it's built (un-bundled, offline)

Claude Design exports a *standalone* HTML that base64-bundles its modules and
pulls React from a CDN at runtime. That is unwrapped here so the cockpit is
readable, reviewable, and **fully offline** — matching the repo's local-first
rule and the Observatory's "no remote references" guarantee:

- The page is the design's own **`<x-dc>` template** + its **`data-dc-script`**
  logic, rendered by the **dc-runtime** (the Claude Design renderer; parses the
  `<x-dc>`/`sc-if`/`sc-for` template and renders it with React).
- **React 18.3.1 UMD is vendored** at `gateway/cockpit/static/vendor/react*.js`
  (the same version the dc-runtime targets), loaded by plain `<script>` tags
  *before* the runtime — the runtime detects `window.React` and skips its own
  CDN loader. The runtime's CDN fallback constants (React, ReactDOM, Babel) are
  neutralised, so the page has **zero remote references**.
- The **dc-runtime is loaded externally** as
  `gateway/cockpit/static/vendor/dc-runtime.js`, *not* inlined. This is
  load-bearing: `boot()` renders the template from the DOM first, then re-fetches
  `location.href` and re-parses the raw HTML with a regex (`parseDcText`, for
  live-edit). The runtime's source contains its own `/<x-dc…>/` regex literal, so
  **inlining it would make that re-parse match the runtime's own source instead
  of the real template, corrupting the render.** Externalising keeps the page
  HTML free of stray `<x-dc` literals. (Caught by the live render check below.)
- The **3D Systems Atlas** is vendored under `gateway/cockpit/static/atlas/`
  (synced from `docs/3d-model/`), and `window.__resources.atlas` points the
  design's atlas iframe at `atlas/index.html`. The atlas reuses the cockpit's
  vendored three.js (its `app.js` imports `../vendor/three.module.min.js`), so
  there is **no 712 KB three.js duplication**. It still degrades gracefully if
  the resource is absent.

## Status

- **Default cockpit / Muse Omni.** `/cockpit/` (and the gateway root `/`) serve
  this design — the full operations UI (Connect, jobs, approvals, OMNI
  providers, atlas, studio). Day-to-day local launch: `muse omni` (full-agent
  mode). The prior cinematic modular SPA from #551 stays reachable at
  `/cockpit/index.html`, and the flagship Observatory at
  `/cockpit/observatory.html`. `/nexus` is unaffected. (Promotion routing lives
  in `gateway/cockpit/server.py::_serve_static`.)
- **Public face (Vercel).** The public deployment serves **this Singularity
  cockpit at the site root**. `scripts/deploy/build_cockpit_vercel.sh` assembles
  it (page + vendored runtime + atlas) as `index.html`; the OpenCode chat shell
  (`web/musehq`) ships under `/chat/`; `/legacy.html` is an alias of this same
  cockpit for old bookmarks. The System rail links **OpenCode chat** and
  **Local Admin** (`http://127.0.0.1:9119` when `muse dashboard` / `muse omni
  --with-admin` is running).
- **Segregated nav.** The left rail groups its destinations into sections —
  **Command / Build / Intelligence / Govern / System** — rendered from
  `navMeta` (each entry carries a `group`; the rail emits a `.nav-section`
  heading whenever the group changes).
- **Live chat, honest fallback.** The chat composer is wired to the repo-root
  Edge function `/api/chat`: on the public deployment it streams a real reply
  from the server-held provider key; paired to a gateway it dispatches a real
  job; on a static host with no `/api` it shows an honest "pair a gateway"
  message and never fabricates a reply. Chat opens to a single greeting (no
  seeded demo conversation); the other panels keep their designed demo shell.
- **Verified — live render.** Booted in headless Chrome against the cockpit
  server: React + ReactDOM load locally, the `<x-dc>` template renders (app
  shell + nav items: Chat / Tasks / Agents / Studio / 3D Atlas / Approvals
  …), and the 3D Atlas loads inside its panel. Plus
  `tests/gateway/test_cockpit_dc_page.py` (serving, content types, vendored-React
  resolution, React-before-runtime order, no remote references across page +
  runtime + atlas, default-promotion routing, atlas wiring + three.js sharing,
  packaging) and `node --check` on the runtime + `data-dc-script`.

## Provenance

Imported from Claude Design project `8d92036e-712c-431f-8d3b-ee9bda072456`,
file *muse Cockpit.dc.html*, via the owner's "send the file" hand-off (the
DesignSync MCP connector requires an interactive `/design-login` not available
in a headless web session). The live file in-repo is
`gateway/cockpit/static/cockpit.dc.html` — do not edit a root-level bundler
export if one appears locally; it is not what the gateway or Vercel serve.
