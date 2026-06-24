# Hosting the Neural Observatory 24/7 (web)

The Neural Observatory web viewer (`gateway/cockpit/static/observatory.*`) is a
pure client-side SPA (vendored three.js, no build step). It is published as an
always-on static page on the repo's existing GitHub Pages deploy, alongside the
NEXUS PWA and the 3D Atlas.

## Where it lives

- **Always-on demo:** `https://a-c-i-software-and-development.github.io/M.U.S.E/observatory/`
  — renders a **bundled, clearly-labeled static snapshot** (no backend needed),
  so the page is up 24/7 even with no gateway running. A prominent
  *"DEMO · static snapshot — not live MUSE telemetry"* badge makes the status
  unambiguous.
- **Live viewer:** `…/observatory/observatory.html` — the unmodified live page;
  point it at a running gateway (see below).

Published by [`.github/workflows/nexus-pages.yml`](../../.github/workflows/nexus-pages.yml)
on push to `main` that touches `apps/nexus/**` or
`gateway/cockpit/static/observatory*`, or via **workflow_dispatch** (Actions tab
→ "Deploy NEXUS to Pages" → Run). It copies the viewer into the Pages site under
`/observatory/`, using `observatory-demo.html` as the directory `index.html`.

## How demo mode works (opt-in, honest)

`observatory.js` enables demo mode only when the page sets
`window.OBSERVATORY_DEMO_URL` (which `observatory-demo.html` does) or is visited
with `?demo=1`. In demo mode the single `api()` helper returns slices of the
bundled `observatory-demo.json` instead of fetching a gateway, and the live SSE
streams are not started. **When the flag is absent the live code path is
unchanged** — the cockpit-served `observatory.html` behaves exactly as before.

The snapshot's *structure* is authentic — real M.U.S.E. area labels positioned
with the same `gateway.cockpit.observatory_layout_engine` the live page uses —
but the telemetry numbers are illustrative and frozen. Nothing is presented as
live measurement.

### Sacred-geometry layouts (in-browser)

The HUD **layout** select re-arranges the galaxy onto closed-form lattices,
computed client-side with the same golden angle + vertex math as the UE renderer
(`MuseSacredGeometry`):

- **Galaxy** (default) — the gateway-computed force / solar positions (unchanged).
- **Flower** — Vogel phyllotaxis disk.
- **Sphere** — spherical Fibonacci lattice.
- **Icosahedron** — Platonic-solid anchors (cycled in shells).
- **24-cell** — a projected, 4D-rotated regular 4-polytope.

This works on the hosted demo page too, so visitors can switch lattices live
with no backend. Only the geometry positions change; the honesty rules (null
heat → cool-gray, dormant dressing, no fabricated data) are untouched.

### Regenerating the demo snapshot

```bash
python3 scripts/build_observatory_demo.py   # writes gateway/cockpit/static/observatory-demo.json
```

Edit the `AREAS` / `LINKS` tables in that script to change the demo galaxy.

## Pointing the live viewer at a real gateway (optional)

To show *your* live MUSE on the hosted page, open the live viewer with a URL
fragment (it is stored in localStorage and stripped from the address bar):

```
…/observatory/observatory.html#base=https://your-gateway.example.com&token=<cockpit token>
```

Because the page is served from the Pages origin and your gateway is a different
origin, the gateway must send CORS headers for the Pages origin. The repo ships
a ready template:

- [`deploy/cockpit-https/Caddyfile`](../../deploy/cockpit-https/) — reverse proxy
  with auto-TLS that injects `Access-Control-Allow-Origin` for the Pages origin.
- [`scripts/nexus-up.sh`](../../scripts/nexus-up.sh) — one command to bring the
  cockpit up behind a tunnel or your domain.

The bearer token still gates every API call; CORS does not weaken it. The page
never asks for or stores the owner authorization phrase.

## Notes

- **No GPU / no backend** is needed to host the demo page — it is static files.
- Hosting your *live* gateway 24/7 (so the live viewer always has data) is a
  separate, owner-gated step: run the cockpit on an always-on host (see
  `deploy/longhorizon/` for the systemd watchdog/backups) behind the Caddy proxy.
- The viewer pins its three.js build by SHA-256 (vendored, no CDN); the Pages
  bundle copies `vendor/three.*.min.js` verbatim.
