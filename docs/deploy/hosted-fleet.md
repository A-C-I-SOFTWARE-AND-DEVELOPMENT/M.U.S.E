# Hosted muse gateway fleet

This is the always-on compute behind **musehq.io**'s signed-in, full-agent
chat. A single VPS runs **one isolated cockpit container per Pro user**; the
public cockpit reaches each user's container through the Vercel relay, which
attaches that account's gateway bearer server-side. No user ever shares a
container, and the per-user gateway token never reaches the browser after the
one-time bind.

```
Browser (musehq.io)
  └─ Supabase session ─▶ /api/gateway/<path>  (Vercel Edge relay)
                           └─ attaches this account's bearer (server-side)
                              ─https──▶ Caddy (VPS)  gw.musehq.io/u/<slug>/*
                                          └─▶ 127.0.0.1:<pub_port> (container)
                                                └─ socat ─▶ 127.0.0.1:8765
                                                             muse cockpit --agent full
```

## Why this shape

- **The container is the sandbox.** The full agent executes arbitrary code, so
  each user gets their own container: `cap_drop: ALL`, `no-new-privileges`, a
  PID limit, mem/CPU caps, a dedicated `~/.hermes` volume, and **no Docker
  socket**. See `docker-compose.hosted.yml`.
- **Loopback bind is load-bearing.** `gateway/cockpit/handlers.py` disables the
  agentic execute lanes whenever the cockpit binds a non-loopback host. So the
  cockpit always binds `127.0.0.1:8765` *inside* the container (execute lanes
  on) and `docker/start-cockpit.sh` runs a `socat` hop to the container's
  published port. Binding `0.0.0.0` directly would silently kill code execution.
- **Owner gates stay in force.** Owner-gated actions still require the exact
  owner authorization through the Approvals UI — hosting does not weaken any
  gate or publish the authorization value as a hint.

## One-time host setup

```bash
# On the VPS (Docker + Caddy installed):
sudo cp deploy/hosted/Caddyfile /etc/caddy/Caddyfile
sudo sed -i 's/__GW_DOMAIN__/gw.musehq.io/' /etc/caddy/Caddyfile   # your DNS
# Set the same high-entropy MUSE_GATEWAY_RELAY_TOKEN in Caddy's service
# environment and Vercel's server-only environment before the first reload.
sudo systemctl reload caddy
```

Point DNS `gw.musehq.io` → the VPS. Export the fleet secrets (service-role key,
never the anon key) in the shell you provision from:

```bash
export SUPABASE_URL=https://<project>.supabase.co
export SUPABASE_SERVICE_ROLE_KEY=<service-role-key>
export GW_DOMAIN=gw.musehq.io
```

## Provision a Pro user (owner-gated)

Each provision spends compute and creates a credential + a Supabase row, so it
is an **owner action** — run it by hand per signup while the fleet is small:

```bash
scripts/fleet/provision_user.sh up <slug> <supabase_user_id> [pub_port]
```

It builds/starts the user's container, waits for `"agent":"full"` health, reads
the container's cockpit token, and upserts the `account_gateways` binding via
the service role. It then points to the hardened `handle_path` template in
`deploy/hosted/Caddyfile`; copy it without removing the relay-token or
route/method matchers, reload Caddy, and set a provider key in the container's
`~/.hermes/.env` (a free Groq/Gemini key works):

```bash
docker compose -p muse-<slug> -f docker-compose.hosted.yml exec cockpit \
  sh -c 'echo "GROQ_API_KEY=..." >> /opt/data/.env'
```

Deprovision:

```bash
scripts/fleet/provision_user.sh down <slug>
# then remove the /u/<slug>/ route from the Caddyfile, reload Caddy,
# and delete the user's account_gateways row.
```

## Verify a user end-to-end

```bash
# Direct proxy checks require the server-only relay proof.
RELAY_PROOF='Bearer <relay-token>'
curl -s -H "X-Muse-Relay-Authorization: ${RELAY_PROOF}" \
  https://gw.musehq.io/u/<slug>/v1/health
# execute lanes survived containerization (the critical check)
curl -s -H "X-Muse-Relay-Authorization: ${RELAY_PROOF}" \
  -H "Authorization: Bearer <owner-token>" \
  https://gw.musehq.io/u/<slug>/v1/cockpit/capabilities    # execute_allowed: true
# streaming works through every hop (no proxy buffering)
curl -N -H "X-Muse-Relay-Authorization: ${RELAY_PROOF}" \
  -H "Authorization: Bearer <owner-token>" \
  -d '{"prompt":"run: python -c \"print(6*7)\""}' \
  https://gw.musehq.io/u/<slug>/v1/agent/chat              # tool_call + body(42)
```

Then sign in on musehq.io, confirm the Account panel shows **Full agent ready**,
and send a message that runs code and pauses on an approval.

### Block-Buzz through musehq.io

Buzz keeps a short-lived service token, while the browser/owner session keeps
using the account's stored gateway token. To relay Buzz, authenticate the
request with the normal musehq.io account session and send the scoped token in
`X-Muse-Service-Authorization: Bearer muse_svc_...`. For POST controls, also
send a unique `X-Muse-Request-Id`. The relay and cockpit each apply independent
route+method allowlists; the cockpit attributes accepted and denied calls to
the token's `block-buzz` identity and credential id.

Never put a service token in a URL, browser storage, Vite variable, Caddyfile,
or log. Do not reuse the account's owner gateway token for Buzz.

## Operations

- **Backups:** the state that matters is the per-user volumes `muse-data-<slug>`
  (config, token, memory, keys). Snapshot them on the host's backup schedule.
- **Emergency stop:** `docker compose -p muse-<slug> -f docker-compose.hosted.yml stop`
  halts a single user's agent; the Approvals UI + `/v1/cockpit/emergency-stop`
  handle in-session halts.
- **Limits & silent caps:** `MUSE_MEM_LIMIT` / `MUSE_CPUS` bound each container.
  Daily agent-chat quota is enforced at the relay (`api/_entitlements.ts`,
  `AGENT_CHAT_DAILY_FREE` / `_PRO`), not here.

## Alternatives

- **Owner's own always-on PC** (zero hosting cost): run
  `muse cockpit serve --agent full` locally and expose it with a Cloudflare
  named tunnel to a stable `https://` hostname; bind that URL to your account in
  the cockpit's **Account** panel. The site loses agent features whenever the PC
  is off.
- **Azure AKS** (fleets beyond ~50 users): reuse `deploy/aks/*` + KEDA — one
  namespace per user, an ingress path per user, `secretproviderclass` for
  provider keys. More moving parts than a single VPS; pick it only at scale.
