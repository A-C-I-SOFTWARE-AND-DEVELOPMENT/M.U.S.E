# Connect the cockpit to the muse in your terminal

This guide gets the **cockpit** (the browser app — local or the public
[musehq.io](https://musehq.io)) talking to the **muse gateway running in your
terminal**, so the chat drives your real agents, jobs, orchestration, memory,
evidence, and ledger — all your data — not just the stateless public chat.

There are three ways to do it. Pick by where you want to open the cockpit.

---

## TL;DR

```bash
muse cockpit serve
# muse cockpit API listening on http://127.0.0.1:8765
# Open the browser cockpit: http://127.0.0.1:8765/cockpit/
```

- **On the same machine?** Open the local URL it prints. Done — full power, zero
  setup, nothing leaves your machine.
- **Want to use the public musehq.io page?** musehq.io is allowed to reach your
  gateway **by default** (CORS). In Chrome it can talk to `http://localhost`
  directly; from another browser or another device, expose the gateway over an
  **HTTPS tunnel** and point the cockpit's **Connect** dialog at the tunnel URL.

Pairing is **friction-free** — no owner phrase — for a loopback gateway. The
device gets its own token, stored only in that browser.

---

## 1. Local cockpit (same machine) — works now, zero setup

```bash
muse cockpit serve
```

Open `http://127.0.0.1:8765/cockpit/`. The page is served *same-origin* by the
gateway, so there is no CORS or mixed-content barrier at all. Click **Connect →
Get code → Pair this device**. You now have the full cockpit wired to your real
gateway.

This is the simplest path and the one to use day-to-day.

## 2. Public cockpit (musehq.io) → your terminal

The public page is HTTPS; your terminal gateway is HTTP on loopback. Two things
make the bridge work, and the first is already the default:

1. **CORS** — the gateway allows the first-party muse origins
   (`https://musehq.io`, `https://www.musehq.io`) to call it **by default**. No
   flag needed. (Extend or disable below.)
2. **Reachability** — the browser still has to *reach* the gateway:
   - **Chrome / Edge:** treat `http://localhost` / `http://127.0.0.1` as a
     secure context and honour the gateway's Private Network Access consent, so
     musehq.io can talk to `http://127.0.0.1:8765` **directly** — just run
     `muse cockpit serve`, open musehq.io, **Connect**, set the gateway URL to
     `http://127.0.0.1:8765`, and pair.
   - **Firefox / Safari / a phone / another machine:** put the gateway behind an
     **HTTPS tunnel** and point Connect at the tunnel URL (next section).

### Expose the gateway over an HTTPS tunnel

Run the gateway as usual (it stays bound to loopback), then run a tunnel that
forwards to it. Examples:

```bash
# Cloudflare Tunnel (recommended — add Cloudflare Access for auth)
cloudflared tunnel --url http://127.0.0.1:8765

# ngrok
ngrok http 8765

# Tailscale Funnel (within your tailnet / public)
tailscale funnel 8765
```

Each prints an HTTPS URL (e.g. `https://abc-123.trycloudflare.com`). If the
tunnel hostname is fixed, allow it explicitly:

```bash
muse cockpit serve --cors-origin https://abc-123.trycloudflare.com
```

Then in the cockpit **Connect** dialog, set the **gateway URL** to that HTTPS
tunnel URL and pair. The public page now drives your terminal from anywhere.

> **Security — read this.** Pairing a loopback gateway is intentionally
> phrase-free. A tunnel turns your loopback gateway into a public hostname, so
> **put authentication on the tunnel** (Cloudflare Access, an ngrok auth/OIDC
> rule, or your tailnet ACL). Without it, anyone who learns the tunnel URL can
> pair and reach your agent. The bearer token still guards every data route, but
> pairing *issues* that token, so the tunnel is your front door — lock it.

## 3. Phone / another device on your home Wi-Fi (LAN)

Bind the gateway to your LAN IP and allowlist it (fail-closed):

```bash
muse cockpit serve \
  --host 192.168.1.50 --allow-external --allow-external-host 192.168.1.50 \
  --cors-origin https://musehq.io
```

A **non-loopback bind exposes the agent to your network**, so this path keeps
the owner-phrase gate: pairing asks for `Yes, with authorization.` exactly
(the cockpit reveals the field only when the gateway demands it). Only do this
on a trusted LAN (you control the Wi-Fi, no untrusted devices) — and prefer a
tunnel (§2) over a raw LAN bind when you can.

---

## CORS configuration reference

| What | How |
|------|-----|
| Default allowlist | `https://musehq.io`, `https://www.musehq.io` |
| Add an origin (one-off) | `muse cockpit serve --cors-origin https://my.tunnel` (repeatable) |
| Add origins (env) | `HERMES_COCKPIT_CORS_ORIGINS="https://a,https://b"` (CSV; extends defaults) |
| Disable CORS entirely | `HERMES_COCKPIT_CORS_ORIGINS=off` |

CORS only decides which **browser origins** may read responses; it never
weakens the bearer-token requirement on the API routes, and it never opens a
network port (the bind host does that — loopback by default).

## What you get once connected

The same cockpit, now live against your gateway: streaming agent chat, the job
graph + orchestration, owner approvals, the Memory Tree, evidence engine, the
decision ledger, autonomy controls, the GraphRAG knowledge graph, and the
emergency stop. The device token lives only in that browser; **Disconnect**
clears it.

## Troubleshooting

- **"Connect" spins / network error from musehq.io.** Your browser can't reach
  the gateway. In Firefox/Safari/another device, use a tunnel (§2). Confirm the
  gateway is up: `curl http://127.0.0.1:8765/v1/health`.
- **CORS error in the console.** The browser Origin isn't allowlisted. Add it
  with `--cors-origin <origin>` (must match exactly, scheme + host + port).
- **Pairing asks for the owner phrase unexpectedly.** The gateway was started
  `--allow-external` (a network bind). Enter `Yes, with authorization.` exactly,
  or run loopback + a tunnel instead.
- **Mixed-content block (https → http).** You pointed Connect at an `http://`
  non-localhost gateway from the HTTPS page. Use the gateway's HTTPS tunnel URL.

See also: [`secure-tunnel-options.md`](secure-tunnel-options.md) for the
tunnel-transport comparison and hardening notes.
