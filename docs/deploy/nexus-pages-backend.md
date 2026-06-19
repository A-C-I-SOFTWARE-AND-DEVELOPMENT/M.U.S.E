# Drive the live NEXUS PWA (GitHub Pages) from your MUSE backend

The NEXUS PWA (`apps/nexus`) is published to **GitHub Pages** on every push to
`main` (`.github/workflows/nexus-pages.yml`). That gives you a public,
installable front-end:

```
https://a-c-i-software-and-development.github.io/M.U.S.E/
```

But a PWA is only a **front-end** — it has no models, no agent loop, no
pipelines of its own. To "start a conversation and watch every pipeline
end-to-end," it must talk to a running **MUSE cockpit** (`/v1/cockpit/*`,
served by `muse cockpit serve`). This page explains the two ways to wire that
up, and the one gotcha that trips everyone.

## Easiest: one command

On the box that has your `~/.hermes/.env` keys:

```bash
bash scripts/nexus-up.sh                 # public HTTPS via a Cloudflare quick tunnel (no domain/DNS)
bash scripts/nexus-up.sh --domain muse.example.com   # stable HTTPS on your hostname (Caddy auto-TLS)
bash scripts/nexus-up.sh --local         # http://127.0.0.1:8765/nexus/ only
```

It builds the PWA if needed, starts `muse cockpit serve`, exposes it, and prints
the **`…/nexus/` URL + the pairing token** to paste into the ConnectWizard. Stop
it with `bash scripts/nexus-up.sh --stop`. The rest of this page explains what it
does and the manual equivalents.

## The gotcha: the cockpit is same-origin by design (no CORS)

`muse cockpit serve` binds `127.0.0.1:8765`, is gated by a Bearer pairing token,
and **emits no CORS headers** — it's built for the on-device app and the Termux
runtime, not cross-origin browser calls. Two consequences:

- A browser on the **public Pages origin** (`https://…github.io`) **cannot**
  call your cockpit cross-origin unless a proxy adds CORS — even over HTTPS, the
  preflight is rejected.
- An **HTTPS** Pages page can never call an **`http://localhost`** backend
  (browser mixed-content block). The PWA already detects and warns about this.

That's why the cockpit also **serves the identical NEXUS PWA same-origin** at
`/nexus/`. Pick the path that fits:

## Path A — same-origin (recommended, zero CORS) ✅

Use the copy of NEXUS the cockpit serves itself. Nothing cross-origin, nothing
to special-case.

**Locally (fastest test):**
```bash
muse cockpit serve            # cockpit API + PWA on http://127.0.0.1:8765
muse cockpit token            # copy the Bearer token
# open http://127.0.0.1:8765/nexus/  → ConnectWizard → base URL is auto (same origin) + token
```

**On the VPS (public + 24/7):** put the cockpit behind the HTTPS reverse proxy
in [`../../deploy/cockpit-https/Caddyfile`](../../deploy/cockpit-https/Caddyfile)
(auto-TLS), then open `https://your-host/nexus/`. Same origin → no CORS, no
mixed content. Here the public GitHub Pages site is just an installable
showcase; the functional control plane is `/nexus/` on your host.

## Path B — the public Pages PWA, pointed at your cockpit

If you specifically want `…github.io/M.U.S.E/` to drive MUSE, the proxy must
inject CORS for the Pages origin. The same
[`Caddyfile`](../../deploy/cockpit-https/Caddyfile) does this — it proxies
everything to the cockpit **and** adds `Access-Control-Allow-Origin` +
preflight handling for `__PAGES_ORIGIN__`.

1. On the VPS, run the cockpit and get a token:
   ```bash
   muse cockpit serve            # loopback :8765
   muse cockpit token
   ```
2. Install the proxy (DNS for your hostname must point at the VPS):
   ```bash
   sudo apt install -y caddy
   sudo cp deploy/cockpit-https/Caddyfile /etc/caddy/Caddyfile
   # replace __DOMAIN__ (e.g. muse.example.com) and
   #         __PAGES_ORIGIN__ (https://a-c-i-software-and-development.github.io)
   sudo systemctl restart caddy
   ```
3. Open the Pages URL → **ConnectWizard** → base URL `https://your-host`,
   paste the Bearer token → connect. Chat / Fusion / every pipeline lights up.

> CORS does not weaken security here — it only lets the browser *make* the
> request; the cockpit's Bearer token still gates every call. Keep the token
> secret and serve only over HTTPS.

### nginx variant

If you already run nginx (the [VPS guide](vps-deployment-guide.md) uses it for
the dashboard), add a server block that proxies to `127.0.0.1:8765` and, for the
Pages origin, sets `add_header Access-Control-Allow-Origin
https://a-c-i-software-and-development.github.io always;` plus an `if
($request_method = OPTIONS) { return 204; }` preflight branch with
`Access-Control-Allow-Headers "Authorization, Content-Type"`. Caddy is simpler
because it bundles auto-TLS — prefer it unless you're already invested in nginx.

## Keep it up 24/7

`muse cockpit serve` is a foreground process. To keep it (and the proxy) alive
across reboots on the VPS, fold them into the long-horizon hardening —
`gateway.auto_start` + the watchdog in
[`long-horizon-vps-runbook.md`](long-horizon-vps-runbook.md). Caddy installs its
own systemd unit and restarts automatically.

## See also

- [`vps-deployment-guide.md`](vps-deployment-guide.md) — get the box running first.
- [`long-horizon-vps-runbook.md`](long-horizon-vps-runbook.md) — keep it alive 24/7.
- [`../../deploy/cockpit-https/Caddyfile`](../../deploy/cockpit-https/Caddyfile) — the proxy template.
- [`../mobile/NEXUS_UNIFIED_APP_PLAN.md`](../mobile/NEXUS_UNIFIED_APP_PLAN.md) — why three front-ends collapse to one PWA over the cockpit.
