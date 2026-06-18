# Long-horizon 24/7 VPS runbook

You've deployed M.U.S.E. on a VPS (see
[`vps-deployment-guide.md`](vps-deployment-guide.md)). It runs. This page is
about the next thing: keeping it running **unattended for weeks or months** —
the "long-horizon agentic running" case, where the gateway and its in-process
cron scheduler must survive crashes, reboots, log growth, and the occasional
bad night without you babysitting them.

A plain install already restarts on reboot (Docker `restart: unless-stopped`,
or the systemd unit `muse gateway install` writes). This runbook layers on what
a plain install does **not** give you, and ships one opt-in script that applies
all of it:

```bash
bash scripts/vps-harden-longhorizon.sh            # apply everything
bash scripts/vps-harden-longhorizon.sh --dry-run  # show every change first
bash scripts/vps-harden-longhorizon.sh --uninstall
```

It is **opt-in, idempotent, and additive** — it changes how the *host* keeps
the agent alive, never how the agent itself behaves. Re-run it freely.

> Run `scripts/quickstart.sh` **first**. This script hardens an existing
> deployment; it does not install M.U.S.E. from scratch.

---

## What "long horizon" actually needs

The autonomous engine for long-horizon work is the **cron scheduler that ticks
inside the gateway process** (`cron/scheduler.py`, started as a background
thread by the gateway). So "keep the agent working over a long horizon" reduces
to "keep the gateway process alive and healthy, indefinitely." Five concerns,
and how the hardening layer addresses each:

| Concern | Plain install | Hardening layer adds |
|---|---|---|
| **Self-healing autostart** | Restarts only if it was running before reboot | `gateway.auto_start=true` + `gateway ensure` + systemd linger → comes back from *any* state, no login needed |
| **Crash recovery** | systemd parks the unit in `failed` after a few rapid restarts | `StartLimitIntervalSec=0` + `Restart=always` → transient crashes always self-heal |
| **Liveness backstop** | none | a watchdog timer runs `muse gateway ensure` every 5 min |
| **Disk over months** | logs grow unbounded | logrotate on `~/.hermes/logs` (weekly, 8 kept, `copytruncate`) |
| **Disaster recovery** | none | a daily timer zips `~/.hermes` and prunes old archives |

---

## What it installs

Everything is rendered from the committed templates in
[`../../deploy/longhorizon/`](../../deploy/longhorizon/) into the same systemd
**scope** as your gateway (system scope under `/etc/systemd/system`, or user
scope under `~/.config/systemd/user`). The script detects which.

1. **Autostart** — `muse config set gateway.auto_start true`, then
   `muse gateway ensure`. For a *user-scope* gateway it also runs
   `loginctl enable-linger`, so the service starts at boot even when you never
   log in. (Why `auto_start` matters is spelled out in the
   [deployment guide](vps-deployment-guide.md#opt-in-once-with-gatewayauto_start).)

2. **Restart-hardening drop-in** —
   `…/hermes-gateway.service.d/10-longhorizon.conf`
   ([`gateway-hardening.conf`](../../deploy/longhorizon/gateway-hardening.conf)).
   A drop-in *adds to* the gateway's own unit; it never replaces it. The key
   line is `StartLimitIntervalSec=0`: systemd's default rate-limiter would, over
   a long horizon, eventually leave a flapping gateway dead in `failed`. We
   disable it so it always keeps trying (with `RestartSec=15`, so a genuine
   crash loop backs off rather than spins). It also sets `OOMScoreAdjust=-200`
   so the kernel reaps something else first under memory pressure.

3. **Watchdog timer** — `muse-watchdog.timer` fires `muse gateway ensure` every
   5 minutes. `ensure` is idempotent (a no-op when the gateway is already up),
   so this is a cheap, safe backstop that also recovers the gateway after a
   *clean stop* — which `Restart=` alone does not.

4. **Daily backup timer** — `muse-backup.timer` runs `muse backup` into
   `~/.hermes/backups/` (override with `--backup-dir`) and deletes archives
   older than 14 days (`--backup-keep N`). Restore any of them with
   `muse import <zip>`.

5. **Log rotation** — `/etc/logrotate.d/muse-hermes` rotates
   `~/.hermes/logs/*.log` weekly, keeping 8 compressed generations, using
   `copytruncate` because the gateway holds its log files open.

### Docker deployments

If you deployed with `docker compose`, restart/autostart is already handled by
`restart: unless-stopped`, so the script **skips** autostart, the drop-in, and
the watchdog. It still installs the host-level **backup** and **logrotate**
pieces (they operate on the bind-mounted `~/.hermes` on the host).

---

## Selective use

```bash
# Just self-healing + watchdog, no backups or logrotate:
bash scripts/vps-harden-longhorizon.sh --no-backup --no-logrotate

# Keep 30 days of backups in a dedicated volume:
bash scripts/vps-harden-longhorizon.sh --backup-dir /mnt/backups/muse --backup-keep 30

# A non-default profile's gateway (unit is hermes-gateway-<profile>):
bash scripts/vps-harden-longhorizon.sh --service hermes-gateway-coder
```

Flags: `--no-autostart`, `--no-hardening`, `--no-watchdog`, `--no-backup`,
`--no-logrotate`, `--dry-run`, `--uninstall`.

---

## Verify

```bash
# Gateway is up, and the hardening drop-in is loaded:
systemctl status hermes-gateway.service          # add --user for a user-scope install
systemctl show hermes-gateway.service -p Restart -p StartLimitIntervalSec

# Timers are scheduled:
systemctl list-timers 'muse-*'

# Health + routes:
muse gateway status
muse doctor

# A backup landed:
ls -lh ~/.hermes/backups/
```

Watch it work:

```bash
tail -f ~/.hermes/logs/gateway.log
journalctl -u muse-watchdog.service -f          # add --user for a user-scope install
```

---

## Roll back

```bash
bash scripts/vps-harden-longhorizon.sh --uninstall
```

Removes the watchdog/backup timers, the logrotate config, and the
restart-hardening drop-in, then reloads systemd. It deliberately **leaves
`gateway.auto_start` as-is** (flip it off with `muse config set
gateway.auto_start false` if you want). The gateway service itself is never
touched.

---

## Operating notes for a long-horizon box

- **Back up off-box too.** The daily timer protects against `~/.hermes`
  corruption, not against losing the VPS. Mirror it elsewhere periodically:
  `rsync -a ~/.hermes/backups/ backup-host:/backups/muse/`.
- **Watch disk and memory.** `df -h` and `free -m` over time; the OOM score and
  logrotate buy headroom but aren't a substitute for right-sizing the box (see
  the sizing table in the [deployment guide](vps-deployment-guide.md#pick-a-vps)).
- **Updates still need a nudge.** This layer keeps the *current* version alive;
  it does not auto-update. Run `muse update` (native) or
  `git pull && docker compose up -d --build` (Docker) on your own cadence.
- **Keep the dashboard loopback-only.** Nothing here changes that — reach it
  via SSH tunnel or an authenticated proxy, never `--insecure --host 0.0.0.0`.

---

## See also

- [`vps-deployment-guide.md`](vps-deployment-guide.md) — get to a running box first.
- [`../../deploy/longhorizon/`](../../deploy/longhorizon/) — the unit / drop-in / logrotate templates this installs.
- [`../remote/secure-tunnel-options.md`](../remote/secure-tunnel-options.md) — secure remote access to the dashboard.
