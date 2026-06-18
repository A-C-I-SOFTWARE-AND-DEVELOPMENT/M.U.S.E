# `deploy/longhorizon/` — 24/7 long-horizon hardening templates

These are the systemd / logrotate templates that
[`scripts/vps-harden-longhorizon.sh`](../../scripts/vps-harden-longhorizon.sh)
installs to turn a running M.U.S.E. deployment into one that survives weeks or
months of unattended operation. They are **opt-in and additive** — the gateway
runs fine without them; this layer only changes how the host keeps it alive.

Read the [long-horizon VPS runbook](../../docs/deploy/long-horizon-vps-runbook.md)
for the why and the operating notes. Don't install these by hand — run the
script; it detects your systemd scope (system vs user) and substitutes the
`__PLACEHOLDERS__`.

| File | Installed as | Purpose |
|---|---|---|
| `gateway-hardening.conf` | `…/hermes-gateway.service.d/10-longhorizon.conf` | Drop-in: `StartLimitIntervalSec=0` + `Restart=always` + OOM deprioritization so crashes always self-heal. |
| `muse-watchdog.service` + `.timer` | scope unit dir | Runs `muse gateway ensure` every 5 min — idempotent liveness backstop. |
| `muse-backup.service` + `.timer` | scope unit dir | Daily `muse backup` into the backup dir, prunes old archives. |
| `muse-logrotate.conf` | `/etc/logrotate.d/muse-hermes` | Rotates `~/.hermes/logs/*.log` (weekly, 8 kept, `copytruncate`). |

Placeholders the script substitutes: `__MUSE_BIN__`, `__RUN_USER__`,
`__HERMES_HOME__`, `__BACKUP_DIR__`, `__KEEP_DAYS__`, `__USER_LINE__` (a
`User=` line for system scope, empty for user scope).
