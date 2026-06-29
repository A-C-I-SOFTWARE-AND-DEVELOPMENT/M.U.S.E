# Going public: the muse cockpit production checklist

A short, honest checklist for running the public cockpit (e.g. musehq.io) as a
real product. Items are ordered by impact; the first two are the only ones that
*must* happen for the public chat to work and be safe.

## 1. Turn the chat on — set ONE provider key (required)

The public chat runs through the server-held provider key in `/api/chat`. Until
one is set, the cockpit honestly shows **"set a provider key"** and never
fabricates a reply. It does **not** have to be OpenRouter — any one of the
supported providers works, and a free-tier key costs nothing:

| Provider | Env var | Cost |
|----------|---------|------|
| Groq | `GROQ_API_KEY` | free tier |
| Google Gemini | `GEMINI_API_KEY` | free tier |
| Cerebras | `CEREBRAS_API_KEY` | free tier |
| NVIDIA NIM | `NIM_API_KEY` | free tier |
| OpenRouter | `OPENROUTER_API_KEY` | free `:free` models + paid |
| Anthropic / OpenAI / … | `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / … | paid |

Set it on the **Production** environment of the Vercel project, then redeploy.
The server prefers a free-tier key automatically (free-first routing).

## 2. Meter the chat — rate-limit `/api/chat` (strongly recommended)

A public, no-auth endpoint that spends your key needs a meter. The limiter is
on by default with sane values; tune or harden via env:

| Var | Default | Meaning |
|-----|---------|---------|
| `CHAT_RATE_RPM` | 20 | requests / minute / IP |
| `CHAT_RATE_DAILY` | 500 | requests / day / IP |
| `UPSTASH_REDIS_REST_URL` + `UPSTASH_REDIS_REST_TOKEN` | — | **global** hard limit across regions |

Without Upstash the limit is in-memory per Edge isolate (best-effort — resets on
cold start, not shared across regions). For a real public launch, provision a
free Upstash Redis and set the two `UPSTASH_*` vars so the cap is global.

## 3. A stable one-click connect link (optional)

The hands-off link `…/cockpit/#gateway=<url>&token=<t>` lets you (or a teammate)
drop straight into a live session against a terminal gateway. To make it durable:

- Run a **named** tunnel so the hostname doesn't change each restart
  (`cloudflared tunnel` with a configured hostname, or a reserved ngrok domain).
- Add that hostname to the gateway's CORS allowlist once:
  `muse cockpit serve --cors-origin https://<your-stable-host>` (or
  `HERMES_COCKPIT_CORS_ORIGINS=https://<your-stable-host>`).
- **Authenticate the tunnel** (Cloudflare Access / ngrok auth / tailnet ACL) —
  the link carries a bearer token and the gateway is now publicly reachable.

See [`../remote/connect-cockpit-to-terminal.md`](../remote/connect-cockpit-to-terminal.md).

## 4. Install + branding

- The cockpit is an installable PWA — the in-app **Install app** button adds it
  to the device home screen (manifest + service worker ship in the build).
- **App icon:** the manifest currently uses an SVG icon (`icon.svg`), which keeps
  the repo source-only (no binary assets). Modern Chrome/Android accept it; if
  you want maximally crisp icons on iOS and older Android, add raster
  `192×192` + `512×512` PNGs (incl. a maskable variant) and reference them in
  `manifest.webmanifest`. Deferred here to respect the zero-binary-asset policy.

## 5. Verify on the real site

From a normal browser on the live URL, confirm:

- Chat replies (header shows **online**, not "set a provider key").
- The **Install app** button appears and installs.
- **Connect → Pair this device** reaches a locally-running gateway (Chrome can
  hit `http://localhost` directly; other browsers/devices use the tunnel).
- A burst of rapid requests eventually returns **429** (the meter works).

If anything is off, capture a screenshot — the sandbox that builds this can't
reach the public URL, so owner eyes are the ground truth for the live render.
