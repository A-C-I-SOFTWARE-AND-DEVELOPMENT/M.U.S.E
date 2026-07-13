# M.U.S.E. → n8n integration: Stage 1 install

This is the foundational piece of the "cheaper StackAI alternative" rollout:
self-hosted n8n as M.U.S.E.'s external app-connector layer, called from the
Delegate stage after AXIOM's Gate has approved an action.

Everything in this package has been tested end-to-end in a sandbox (npm-run
n8n, not Docker, since Docker wasn't available there) — the workflow JSON and
`muse_n8n_bridge.py` are the exact files that produced a working round trip.
Two real bugs got caught and fixed in the process: the workflow JSON was
missing a required `id` field, and the Webhook node's `responseMode` had to
be `responseNode` (not the default `lastNode`) to work with an explicit
Respond node. Docker itself is not testable in that sandbox, so step 2 below
is the one thing to confirm on your actual machine — everything after it is
proven to work.

## 0. Prerequisites

Docker Desktop with the WSL2 backend, running. If you don't have it:
https://docs.docker.com/desktop/setup/install/windows-install/

## 1. Generate secrets

In WSL2:

```bash
openssl rand -hex 24   # run twice — one output for each secret below
```

## 2. Set up the stack

```bash
mkdir -p ~/muse-n8n && cd ~/muse-n8n
# copy docker-compose.yml, .env.example, muse_echo_workflow.json, muse_n8n_bridge.py here
cp .env.example .env
```

Edit `.env`: set `POSTGRES_PASSWORD`, `N8N_ENCRYPTION_KEY`, and
`N8N_USER_MANAGEMENT_JWT_SECRET` to the values you just generated. Back up
`N8N_ENCRYPTION_KEY` somewhere outside the repo — if it's lost after n8n has
saved credentials, those credentials become permanently unreadable.

```bash
docker compose up -d
docker compose ps    # both containers should show "healthy" / "running"
```

## 3. Create your owner account

Open http://localhost:5678 and create the admin account (this is a one-time,
interactive step — n8n requires it, there's no way around it for a fresh
instance).

## 4. Import and activate the test workflow

In the n8n UI: **Workflows → Import from File** → select
`muse_echo_workflow.json`. Open it, and flip the **Active** toggle in the
top-right corner. (n8n's CLI import always leaves workflows inactive
regardless of what the JSON says — this toggle is the real activation step,
confirmed in testing.)

## 5. Confirm the round trip

```bash
pip install --break-system-packages -U pip   # if needed
python muse_n8n_bridge.py http://localhost:5678
```

Expected output:

```
Pinging n8n at http://localhost:5678 ...
OK (200, ~150-300ms): {'ok': True, 'received': {...}, 'source': 'n8n'}
```

If you get a 404, the workflow isn't active — recheck step 4. If you get a
connection error, check `docker compose logs n8n`.

## 6. Wire it into the real pipeline

`muse_n8n_bridge.py` is dependency-free (stdlib only) and drop-in ready.
In whatever module implements the Delegate stage:

```python
from muse_n8n_bridge import N8nBridge

n8n = N8nBridge(
    base_url="http://localhost:5678",
    ledger_writer=axiom_ledger.append,  # your actual hash-chained ledger append fn
)
```

Then call `n8n.trigger_workflow(...)` only after the Gate stage has approved
the action — see the docstring at the top of the file for the exact contract
(idempotency handling, retry behavior, what gets logged). Build one real n8n
workflow (e.g. a Gmail-send or Slack-post) behind its own webhook path, point
Delegate at it the same way this echo test does, and you have the first real
StackAI-alternative connector live.

## What this doesn't cover yet

This is Stage 1 only — MUSE calling out to n8n. Exposing MUSE itself as a
callable node inside n8n/Zapier/Make (so others can trigger MUSE agents from
their own workflows), and the MCP-connector angle for Zapier/Make/Taskade,
are separate follow-on pieces — say the word if you want those built out next.
