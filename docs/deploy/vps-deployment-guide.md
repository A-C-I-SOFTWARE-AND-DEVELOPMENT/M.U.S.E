# Deploy M.U.S.E. 24/7 on a cloud VPS (one-click)

This guide takes you from a **bare Ubuntu/Debian VPS** to a M.U.S.E. instance
running around the clock — gateway online, model routing wired to every
provider you can reach, and the web dashboard reachable **securely** from your
laptop. Two tracks are covered; one command picks the right one for you.

> New to M.U.S.E.? Read [`../README.md`](../README.md) first for the
> plain-English overview. This page is specifically about *hosting it on a
> server*.

---

## What you're building

```
┌──────────────────────────────────────────────────────────────┐
│  Your laptop / phone                                          │
│    • Browser → dashboard (via SSH tunnel or authed proxy)     │
│    • Telegram / Discord / Slack DM → the gateway              │
└───────────────────────────┬──────────────────────────────────┘
                            │  SSH tunnel  /  authenticated reverse proxy
                            ▼
┌──────────────────────────────────────────────────────────────┐
│  Your VPS (24/7)                                              │
│    • muse gateway   — messaging bridge + cron + orchestration │
│    • muse dashboard — config / API-keys / sessions web UI     │
│                       (FastAPI, loopback 127.0.0.1:9119)      │
│    • ~/.hermes/     — config.yaml, .env (your keys), jobs/,    │
│                       logs/, memory  (back this up)           │
└───────────────────────────┬──────────────────────────────────┘
                            │  model routing (free-first)
                            ▼
   local OSS (Ollama/llama.cpp)  +  any provider whose key is in .env
   (OpenRouter, NIM, Gemini, Anthropic, OpenAI, Together, Fireworks, …)
```

Two things to be clear about up front, because a lot of circulating "M.U.S.E.
VPS guides" get them wrong:

- **The dashboard is a config/keys/sessions UI**, served by FastAPI on
  **port 9119**, bound to **127.0.0.1** by design. It is *not* a public
  task-graph visualizer, and there is no `--serve-dashboard` flag. It holds your
  API keys, so you never expose it directly on the internet.
- **"All models available" means every route the box can reach.** M.U.S.E.
  routes to model *providers*. Local open-weight models and any provider whose
  API key you've put in `~/.hermes/.env` go live automatically. Paid frontier
  models need *your* keys — there's no switch that conjures access without them.

---

## Pick a VPS

| Use | Sizing | Notes |
|---|---|---|
| **API-routing only** (route inference out to OpenRouter / NIM / Gemini / Anthropic) | 2 vCPU · 4 GB RAM · ~40 GB SSD | The common case. Any KVM VPS (Hetzner, DigitalOcean, Linode, …). ~$5–12/mo. |
| **Hybrid** (also run small local models on the box) | + an NVIDIA GPU (≥24 GB VRAM for ~14B models) | Optional. Install a local runtime (Ollama) yourself; M.U.S.E. detects it. |

This guide assumes **API-routing**. Hosting large local models is a separate
concern — see [`../README.md`](../README.md) and your runtime's docs (Ollama,
vLLM). M.U.S.E.'s `models bootstrap` auto-detects a local runtime if one is
present.

First, on a fresh box:

```bash
sudo apt update && sudo apt -y upgrade
sudo apt install -y git curl
```

Then choose a track. **If you're unsure, use the one-command quickstart**, which
auto-detects Docker and falls back to the native install:

```bash
git clone https://github.com/A-C-I-SOFTWARE-AND-DEVELOPMENT/M.U.S.E ~/M.U.S.E
cd ~/M.U.S.E
bash scripts/quickstart.sh        # auto: Docker if available, else native
```

Force a track with `bash scripts/quickstart.sh --docker` or `--native`.

---

## Track A — Docker (recommended)

Cleanest isolation; survives reboots via `restart: unless-stopped`.

**1. Install Docker (Engine + compose plugin):**

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker "$USER"   # log out/in so 'docker' works without sudo
```

**2. Bring it up** (the quickstart does this for you, or run it directly):

```bash
cd ~/M.U.S.E
HERMES_UID=$(id -u) HERMES_GID=$(id -g) docker compose up -d --build
```

This starts two services defined in [`../../docker-compose.yml`](../../docker-compose.yml):

- **`gateway`** — the messaging bridge / orchestrator. On first boot it wires
  every reachable model route into your model policy
  (`HERMES_BOOTSTRAP_MODELS=1`, run exactly once, guarded by a marker file).
- **`dashboard`** — `muse dashboard` on **127.0.0.1:9119** (loopback only).

Your data lives in `~/.hermes` on the host (bind-mounted to `/opt/data`).

**3. Watch it:**

```bash
docker compose logs -f gateway
docker compose ps
```

**Update later:**

```bash
cd ~/M.U.S.E && git pull && docker compose up -d --build
```

---

## Track B — Native (uv) + systemd

No Docker; runs directly on the host with systemd keeping it alive.

```bash
cd ~/M.U.S.E
bash scripts/quickstart.sh --native
```

Under the hood the quickstart runs the project installer with the launch
profile:

```bash
bash scripts/install.sh --jarvis-launch --bootstrap-models
```

which: installs `uv` + Python + Node + system deps, installs M.U.S.E. with all
extras, **installs the gateway as a systemd service and starts it**, and runs
`muse models bootstrap --free-first --jarvis` so every reachable route goes
live. The quickstart then installs a **loopback-only dashboard service** from
[`../../deploy/muse-dashboard.service`](../../deploy/muse-dashboard.service)
(skip it with `--no-dashboard`).

Manage the services:

```bash
muse gateway status          # gateway service
systemctl status muse-dashboard   # dashboard service (or: muse dashboard --status)
muse gateway restart
```

> The gateway has a built-in service manager (`muse gateway install/start/stop`).
> The dashboard does **not**, which is why the native track installs the small
> systemd unit above to keep it running 24/7.

### Establish it once — never set up the gateway by hand again

If you didn't go through the quickstart (or want a single, scriptable,
prompt-free command), run:

```bash
muse gateway ensure
```

`ensure` is **non-interactive and idempotent** — run it as many times as you
like:

- If a gateway is already running for the active profile, it does nothing.
- On systemd / launchd / Windows it **installs + enables + starts** the
  service, so the gateway also comes back automatically on every reboot.
- Inside an s6 container it brings up the pre-registered per-profile slot.
- On Termux / bare Docker / WSL-without-systemd it launches a detached
  background `muse gateway run` (logged to `$HERMES_HOME/logs/gateway.log`).

Because it asks no questions — even the pre-rename legacy-unit cleanup is
unattended — `ensure` is safe to drop into a provisioning script, a cron
`@reboot` line, or a boot hook.

### Opt in once with `gateway.auto_start`

To never run *anything* by hand, set the opt-in flag in `config.yaml`
(`~/.hermes/config.yaml`, or a profile's `config.yaml`):

```yaml
gateway:
  auto_start: true
```

With the flag set:

- **Containers** — the container-boot reconciler brings the gateway up on
  every boot from a fresh or cleanly-stopped state, not only when it was
  running before the last restart. A gateway that *failed at startup* still
  stays down (the crash-loop guard), so a misconfigured profile can't wedge
  the container into an endless restart loop.
- **Hosts** — the next time you launch MUSE (`muse`), it self-establishes the
  gateway (install + enable + start) if it isn't already up; after that first
  launch, systemd/launchd/Task Scheduler keeps it alive across every reboot.
- **`muse setup`** skips its "start now? / start on boot?" prompts and just
  establishes the service.

The flag is opt-in; with it unset, the default behaviour is unchanged
(containers restart only profiles that were `running`; hosts establish
nothing automatically). `muse doctor` will nudge you toward `muse gateway
ensure` whenever no gateway is established yet — and flags it as an issue if
`auto_start` is set but nothing is up.

---

## Make all models available

After either track, tell M.U.S.E. which providers you have keys for. **Keys live
in `~/.hermes/.env`** — the agent process itself never reads that file; only the
provider layer does.

```bash
nano ~/.hermes/.env
```

Add the keys you have (only the ones you have — leave the rest out):

```dotenv
OPENROUTER_API_KEY=sk-or-...
NVIDIA_NIM_API_KEY=nvapi-...
GEMINI_API_KEY=...
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
```

Then re-run the bootstrap so the new providers are picked up:

```bash
# native:
muse models bootstrap --free-first --jarvis
# docker:
docker compose exec gateway hermes models bootstrap --free-first --jarvis
```

See exactly **what's live vs. what still needs a key** without changing
anything (`--dry-run` plans only, writes nothing):

```bash
muse models bootstrap --free-first --jarvis --dry-run
```

`--free-first` orders **local OSS → free/hosted OSS → Claude/Codex workers →
paid API (explicit only)**, so you never accidentally spend on a paid provider
when a free route can do the job. To pull a local model for fully-offline use:

```bash
ollama pull deepseek-r1:8b      # then re-run models bootstrap to detect it
```

---

## Expose the dashboard securely

The dashboard binds `127.0.0.1` because it stores your API keys. **Never** make
it public directly.

> ⚠️ **Do NOT** run `muse dashboard --insecure --host 0.0.0.0`. The
> `--insecure` flag exists only for trusted private networks; on a public VPS it
> exposes your API keys on the open internet. The code itself warns:
> *"DANGEROUS: exposes API keys on the network."*

### Option 1 — SSH tunnel (simplest, nothing to install)

From your laptop:

```bash
ssh -L 9119:localhost:9119 user@your-vps
```

Then open <http://localhost:9119> in your browser. The traffic rides your
existing SSH session; nothing new is exposed on the VPS.

### Option 2 — Authenticated reverse proxy (for a real hostname + TLS)

Only do this **with authentication in front** — the proxy must reject
unauthenticated callers, because anyone who reaches the dashboard can read your
keys.

```bash
sudo apt install -y nginx certbot python3-certbot-nginx apache2-utils
sudo htpasswd -c /etc/nginx/muse.htpasswd youruser     # set a password
sudo ufw allow 'Nginx Full'
```

`/etc/nginx/sites-available/muse`:

```nginx
server {
    server_name muse.example.com;

    location / {
        auth_basic           "M.U.S.E.";
        auth_basic_user_file /etc/nginx/muse.htpasswd;

        proxy_pass http://127.0.0.1:9119;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;     # WebSocket (live updates)
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/muse /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d muse.example.com    # adds TLS
```

### Option 3 — Tailscale / Cloudflare Access

For identity-based access without managing TLS or basic-auth yourself, see
[`../remote/secure-tunnel-options.md`](../remote/secure-tunnel-options.md) — it
compares Tailscale, WireGuard, SSH reverse tunnels, and Cloudflare Access with
their security properties.

---

## Verify & operate

```bash
muse doctor                  # environment + install health
muse gateway status          # is the messaging bridge up?
muse dashboard --status      # is the dashboard process running?
muse dashboard --stop        # stop dashboard processes
```

Logs and data:

```bash
tail -f ~/.hermes/logs/gateway.log
ls ~/.hermes/logs/           # agent.log, errors.log, gateway.log
```

Back up everything (it's all plain files + SQLite):

```bash
rsync -a ~/.hermes/ backup-host:/backups/hermes/
```

Update:

```bash
# native:
muse update
# docker:
cd ~/M.U.S.E && git pull && docker compose up -d --build
```

---

## Myth-busting: corrections to circulating chatbot "M.U.S.E. VPS" guides

If you found a deployment walkthrough elsewhere, check it against reality:

| Claim seen in the wild | Reality |
|---|---|
| `muse --serve-dashboard --port 8080` | No such flag. It's `muse dashboard`, default port **9119**. |
| Dashboard runs on port 8080 | Default is **9119** (`muse dashboard --port` to change). |
| `git clone https://github.com muse-core` | Wrong. Repo is `https://github.com/A-C-I-SOFTWARE-AND-DEVELOPMENT/M.U.S.E`. |
| `pip install -r requirements.txt` in a hand-rolled venv | M.U.S.E. installs via `uv` through `scripts/install.sh` (or Docker). There is no top-level `requirements.txt` install path. |
| "Native task-graph visualization dashboard with a verify_chain() ledger viewer" | The dashboard is a config/keys/sessions UI. Ledgers are inspected via the CLI / job folders, not a built-in graph viewer. |
| Expose the dashboard on `0.0.0.0` behind a plain proxy | The dashboard stores API keys — only expose it via SSH tunnel or an **authenticated** proxy. Never `--insecure --host 0.0.0.0` on a public box. |
| "Anthropic shut down Fable 5 / Mythos 5; route around it" | Not a real event. Configure whichever providers you actually have keys for. |

---

## Keep it alive for the long horizon

Once it's running, harden it for **unattended 24/7 operation** — self-healing
autostart, crash recovery that never gives up, a liveness watchdog, log
rotation, and daily backups — with one opt-in, idempotent script:

```bash
bash scripts/vps-harden-longhorizon.sh            # apply everything
bash scripts/vps-harden-longhorizon.sh --dry-run  # preview the changes first
```

It's additive (it changes how the *host* keeps the agent alive, not how the
agent behaves) and reversible (`--uninstall`). Full details, what each piece
does, and how to verify: [`long-horizon-vps-runbook.md`](long-horizon-vps-runbook.md).

---

## See also

- [`long-horizon-vps-runbook.md`](long-horizon-vps-runbook.md) — keep it running unattended for weeks/months.
- [`../remote/secure-tunnel-options.md`](../remote/secure-tunnel-options.md) — secure remote-access transports.
- [`api-server.md`](../../website/docs/user-guide/features/api-server.md) — before exposing the OpenAI-compatible API server.
- [`../../docker-compose.yml`](../../docker-compose.yml) — the two-service compose this guide drives.
- [`../../scripts/quickstart.sh`](../../scripts/quickstart.sh) — the one-command dispatcher.
- [`../../scripts/install.sh`](../../scripts/install.sh) — the native installer it wraps.
