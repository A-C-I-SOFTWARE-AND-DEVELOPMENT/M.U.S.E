# musehq.io go-live runbook

Everything to take musehq.io from "wired in the repo" to "live, full-agent, and
paid" is code-complete on this branch. What remains is a sequence of
**owner-gated** actions — creating cloud accounts, setting secrets, DNS, and
turning Stripe on. This runbook is the checklist; each step notes where the
code already meets it.

> Owner gate: deploys to production, account/credential creation, spend, and
> DNS are owner actions. Per the muse constitution, do them yourself (or reply
> `Yes, with authorization.` to authorize a specific one).

## What's already true (no action)

- The public cockpit builds and deploys on Vercel; the deploy hook now fires on
  release (`.github/workflows/deploy-site.yml`, repo-name gate fixed).
- The site chat has three lanes: anonymous demo (`/api/chat`), device-paired
  gateway, and — for signed-in users — the **full agent** streamed through the
  relay (`/api/gateway/v1/agent/chat`), with tool calls, code execution,
  sub-agents, and inline owner approvals.
- The full-agent endpoint (`muse cockpit serve --agent full`) and the hosted
  fleet assets (`docker-compose.hosted.yml`, `deploy/hosted/Caddyfile`,
  `scripts/fleet/provision_user.sh`) exist and are validated.
- The billing endpoints (`api/billing/*`) and the pricing UI are built; they sit
  dormant and return 501 until Stripe env is set.

## Step 1 — Supabase project (auth + relay tables)

1. Create a Supabase project.
2. Apply the migrations (via the Supabase MCP `apply_migration`, the SQL editor,
   or `supabase db push`):
   - `supabase/migrations/0001_core.sql` — profiles, account_gateways,
     subscriptions, usage_events, push_subscriptions (+ RLS).
   - `supabase/migrations/0002_billing.sql` — stripe_events.
3. In Auth settings, enable email/password (and Google/GitHub if you want the
   OAuth buttons). Set the site URL to `https://musehq.io`.
4. Note the **Project URL**, **anon key**, **service-role key**, and **JWT
   secret**.

Verify: `get_advisors` is clean; an anon-key REST read of another user's row
returns nothing (RLS holds).

## Step 2 — Vercel env (auth + relay + demo chat)

Set on the Vercel project (server-only unless noted):

| Var | Value |
|---|---|
| `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET` | from Step 1 |
| `SUPABASE_ANON_KEY` | from Step 1 (surfaced publicly via `/api/config`) |
| one provider key, e.g. `GROQ_API_KEY` / `GEMINI_API_KEY` | powers the anonymous demo lane |
| `UPSTASH_REDIS_REST_URL` / `_TOKEN` (optional) | global rate limit for `/api/chat` |
| `AGENT_CHAT_DAILY_FREE` / `_PRO` (optional) | agent quota, default 20 / 400 |

Redeploy. Verify: `GET /api/config` shows `auth` populated and `relay: true`;
sign-up works on the Account panel.

## Step 3 — Hosted gateway (the always-on full-agent compute)

Follow `docs/deploy/hosted-fleet.md`:

1. Stand up a VPS with Docker + Caddy; point DNS `gw.musehq.io` at it.
2. `scripts/fleet/provision_user.sh up <slug> <supabase_user_id>` per Pro user;
   add the printed `handle_path` route to `deploy/hosted/Caddyfile`, reload
   Caddy, and drop a provider key into the container's `~/.hermes/.env`.

Verify: `curl https://gw.musehq.io/u/<slug>/v1/health` → `"agent":"full"`, and
`/v1/cockpit/capabilities` shows `execute_allowed: true` (the loopback check).
Then sign in on musehq.io → Account shows **Full agent ready** → a chat message
runs code and pauses on an approval.

> Alternative (zero hosting cost): run `muse cockpit serve --agent full` on your
> own always-on machine behind a Cloudflare named tunnel and bind that https URL
> in the Account panel. Off when your machine is off.

## Step 4 — Stripe (turn commerce on)

1. Create a Stripe account and a **Pro** product with a monthly price (and a
   yearly price if you want the "Pay yearly" button).
2. Add a webhook endpoint → `https://musehq.io/api/billing/webhook`, subscribing
   to `checkout.session.completed`, `customer.subscription.created|updated|
   deleted`, and `invoice.payment_failed`. Copy its signing secret.
3. Set on Vercel: `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`,
   `STRIPE_PRICE_PRO_MONTHLY` (and `_YEARLY`). Redeploy.
4. Decide the access model: leave `RELAY_AGENT_REQUIRES_PRO` unset for
   "signed-in users get the agent, quota'd" (default), or set it to `1` to gate
   the agent lane behind an active subscription.

Verify (test mode first): `stripe trigger checkout.session.completed` flips a
`subscriptions` row to `pro/active`; the Account panel shows **Pro** and a
**Manage subscription** button; portal cancel downgrades on the webhook.

## Step 5 — Production cutover

- Promote the Vercel deployment to production for `musehq.io`.
- Graduate the CSP in `vercel.json` from `Content-Security-Policy-Report-Only`
  to enforcing after a clean report window.
- Add uptime checks on `GET /api/chat` (expects 200/501, not 5xx) and
  `https://gw.musehq.io/u/<owner>/v1/health`.

## Acceptance (maps to the original request)

- **Actually function** — anonymous chat streams a real reply; a signed-in
  user's chat executes code, spawns sub-agents, pauses on an approval, and
  resumes — the same `AIAgent`/toolsets as the muse TUI.
- **Everything on the website live and wired** — sections render live gateway
  data when connected or carry an explicit demo badge; downloads point at real
  GitHub releases; emergency stop hits the real endpoint.
- **Commercially available and ready** — sign up → Stripe Checkout → webhook →
  Pro entitlement → provisioned hosted gateway → quota'd usage; portal cancel
  downgrades; terms/privacy/support are live.
