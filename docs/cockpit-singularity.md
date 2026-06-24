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
  logic + the inlined **dc-runtime** (the Claude Design renderer; parses the
  `<x-dc>`/`sc-if`/`sc-for` template and renders it with React).
- **React 18.3.1 UMD is vendored** at `gateway/cockpit/static/vendor/react*.js`
  (the same version the dc-runtime targets), loaded by plain `<script>` tags
  *before* the runtime — the runtime detects `window.React` and skips its own
  CDN loader. The runtime's CDN fallback constants (React, ReactDOM, Babel) are
  neutralised, so the file has **zero remote references** (verified by
  `tests/gateway/test_cockpit_dc_page.py`).
- The 3D Systems Atlas iframe degrades gracefully: it points at
  `window.__resources.atlas` when present, else a relative `atlas/…` path.

## Status

- **Additive / non-destructive.** This page is served *alongside* the existing
  cockpit (`/cockpit/`, the cinematic modular SPA from #551); it does **not**
  replace it. Promoting it to the default cockpit shell is an owner decision.
- **Verified:** `tests/gateway/test_cockpit_dc_page.py` (serving, content types,
  vendored-React resolution, React-before-runtime order, no remote references,
  packaging). JS syntax of the inlined runtime and `data-dc-script` checked with
  `node --check`. A live browser render was not run in CI (no headless Chrome in
  the container); the source design renders in Claude Design's own preview, and
  this page is byte-faithful to that template + script + runtime with React
  vendored locally.

## Provenance

Imported from Claude Design project `8d92036e-712c-431f-8d3b-ee9bda072456`,
file *muse Cockpit.dc.html*, via the owner's "send the file" hand-off (the
DesignSync MCP connector requires an interactive `/design-login` not available
in a headless web session).
