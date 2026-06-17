# M.U.S.E. phone-first runtime (Termux backend service)

This is the operator manual for running M.U.S.E. as a real
**backend service** on an Android phone via [Termux](https://termux.dev/).
The phone is the host: it owns the venv, the working directories,
the local API, and the service lifecycle. No desktop machine is
required, and no traffic leaves the device unless you explicitly
configure a gateway.

For deeper Android-specific topics, see the companion docs:

- [`hermes-termux-boot.md`](./hermes-termux-boot.md) — autostart on device boot
- [`hermes-background-limits.md`](./hermes-background-limits.md) — what Android allows in the background
- [`hermes-wake-lock-policy.md`](./hermes-wake-lock-policy.md) — when the runtime holds a wake lock
- [`hermes-android-permissions.md`](./hermes-android-permissions.md) — system permissions and battery whitelists

## TL;DR

```bash
# Verify environment.
bash scripts/hermes-termux-service.sh doctor

# Start the local API (and optionally the gateway).
bash scripts/hermes-termux-service.sh start

# Inspect / observe.
bash scripts/hermes-termux-service.sh status
bash scripts/hermes-termux-service.sh logs api

# Stop cleanly.
bash scripts/hermes-termux-service.sh stop
```

That is the entire interface. There is no daemon to install, no
systemd unit to write, and no Termux-specific package required
beyond the `pkg install` set documented below.

## Why phone-first

Termux gives you a real POSIX userland (`bash`, `python`, `git`,
`node`, `ssh`, `pkg`) inside the normal Android app sandbox. M.U.S.E.
treats this as a first-class deployment target rather than a
curiosity:

- **No round trips.** Tools, models, and state all live on the
  device. Latency between the agent and the model is dominated by
  whatever the model itself takes.
- **Battery-aware.** The service script acquires a Termux wake lock
  so the runtime is not silently frozen the moment the screen turns
  off. See [`hermes-wake-lock-policy.md`](./hermes-wake-lock-policy.md).
- **Background-aware.** The service plays inside Android's
  background-execution rules, not around them. See
  [`hermes-background-limits.md`](./hermes-background-limits.md).
- **No secrets in cloud.** Credentials live in `$HERMES_HOME`
  on the device's private storage.
- **Self-diagnosing.** The doctor script verifies tooling, wake lock
  support, the local API port, and gateway state before you spend
  time debugging service failures.

## Service commands

`scripts/hermes-termux-service.sh` is intentionally minimal — no
systemd, no launchd, no service-manager binaries. Termux runs none
of those. Instead it supervises with a PID file plus `nohup`, and
acquires a wake lock so Android's Doze mode does not freeze the
process when the screen turns off.

| Command            | Effect                                                                       |
| ------------------ | ---------------------------------------------------------------------------- |
| `start`            | Acquire wake lock, start the local API, optionally start the gateway         |
| `stop`             | Graceful SIGTERM → SIGINT after 10s; release wake lock; **never** `kill -9`  |
| `restart`          | `stop` + short pause + `start`                                               |
| `status`           | PID + uptime + wake lock state                                               |
| `logs [api\|gateway]` | `tail -F` the named service log (default: `api`)                          |
| `doctor`           | Delegate to `hermes-termux-doctor.sh` for environment checks                 |

The script never deletes data, never reads or prints secrets, and
never escalates beyond `SIGINT`. If a process refuses to exit, the
script will leave the PID file alone so you can investigate
manually with `ps -p <pid> -o pid,etime,cmd`.

## Doctor checks

`scripts/hermes-termux-doctor.sh` is a read-only diagnostic. It
produces human-readable output by default and machine-readable
JSON with `--json`. It exits non-zero only on hard failures, so it
is safe to chain into a `SessionStart` hook.

What it covers, grouped:

1. **Termux detection** — `TERMUX_VERSION`, `PREFIX`, `termux-info`.
2. **Package manager + storage** — `pkg`, `apt`, `~/storage` symlink,
   Termux:API availability.
3. **Wake lock support** — `termux-wake-lock` / `termux-wake-unlock`.
4. **Core tooling** — `git`, `python` / `python3`, `pip`, `node`,
   plus the package managers (`npm` or `pnpm`) and `uv`.
5. **Optional CLI agents** — `gh`, `codex`, `claude`, `aider`, `goose`.
6. **M.U.S.E. install state** — `HERMES_HOME`, `hermes-agent`
   checkout, venv discovery, `hermes` command on PATH.
7. **Network sanity** — `resolv.conf` only; no outbound probes.
8. **Local API reachability** — verifies the PID file matches a
   live process and probes `http://127.0.0.1:${HERMES_TERMUX_API_PORT}/`
   via `curl` (or `nc -z` when curl is unavailable).
9. **Gateway status** — checks the gateway PID file against
   `kill -0`; reports `running`, `stale`, or `not running`.

Sample abridged output:

```
── Termux detection ──
[OK  ] Running inside Termux (TERMUX_VERSION=0.118.0)
[OK  ] termux-info available (aarch64 on Android 14)

── Wake lock ──
[OK  ] termux-wake-lock / termux-wake-unlock available

── Core tooling ──
[OK  ] git available (git version 2.x)
[OK  ] python available (Python 3.12.x)
[OK  ] npm available (10.x)
[OK  ] uv available (uv 0.4.x)

── Local API reachability ──
[OK  ] API process alive (pid 12345)
[OK  ] Local API reachable on 127.0.0.1:8765

── Gateway status ──
[INFO] Gateway not running (opt in with HERMES_TERMUX_GATEWAY=1)
```

## Environment variables

The phone-first runtime is configured entirely through environment
variables — no separate config file, no secrets in version control.

| Variable                    | Purpose                                          | Default      |
| --------------------------- | ------------------------------------------------ | ------------ |
| `HERMES_HOME`               | M.U.S.E. data directory                            | `~/.hermes`  |
| `HERMES_REPO_DIR`           | Path to the `hermes-agent` checkout              | auto-detect  |
| `HERMES_TERMUX_API_PORT`    | Local API port                                   | `8765`       |
| `HERMES_TERMUX_GATEWAY`     | Set to `1` to also start the gateway             | unset        |
| `HERMES_TERMUX_NO_WAKELOCK` | Set to `1` to skip wake lock acquisition         | unset        |
| `HERMES_TERMUX_API_CMD`     | Override the command used to launch the API      | unset        |

Set these once in `~/.bashrc` or `~/.profile` inside Termux. The
service script reads them on every invocation, so changes take
effect on the next `start` / `restart`.

## Local API: starting and stopping

The local API is what `hermes` commands talk to when they need
the long-running agent state. On phone-first installs, it binds
to `127.0.0.1:${HERMES_TERMUX_API_PORT}` (default `8765`) and is
**not** reachable from outside the device unless you explicitly
expose it (which M.U.S.E. does not do for you).

Lifecycle:

```bash
# Start (acquires wake lock, writes PID + log under ~/.hermes/termux/).
bash scripts/hermes-termux-service.sh start

# Probe (the doctor reuses the same check).
curl --max-time 2 --silent --fail http://127.0.0.1:8765/ \
    && echo "API responding"

# Restart (stop + start; preserves PID-file machinery).
bash scripts/hermes-termux-service.sh restart

# Stop cleanly. Releases the wake lock; does not delete data.
bash scripts/hermes-termux-service.sh stop
```

State and logs live under:

```
~/.hermes/termux/api.pid
~/.hermes/termux/gateway.pid
~/.hermes/termux/wake-lock.acquired
~/.hermes/logs/termux-api.log
~/.hermes/logs/termux-gateway.log
```

Nothing under `~/.hermes/termux/` contains secrets; PID files hold
PIDs, the wake-lock marker is empty, and logs come straight from
the API process (which itself does not echo credentials).

## Safe shutdown

Stop is always graceful:

1. The service script sends `SIGTERM` to the API (and the gateway
   if it was started).
2. It waits up to **10 seconds** for the process to exit.
3. If the process is still alive it sends `SIGINT` and waits **2
   more seconds**.
4. If still alive after that, the script reports the PID and the
   command line and exits non-zero. It **does not** escalate to
   `SIGKILL`. That is intentional — `kill -9` on Python can leak
   the SQLite WAL or corrupt in-flight model output, and we would
   rather fail loud than corrupt silent.

If you ever need to force-kill a hung process, do it explicitly
yourself and only after capturing the state you care about:

```bash
# Look at the process.
ps -p "$(cat ~/.hermes/termux/api.pid)" -o pid,etime,cmd

# Capture a Python stack trace before killing.
kill -USR1 "$(cat ~/.hermes/termux/api.pid)"   # if the process supports it
tail -n 80 ~/.hermes/logs/termux-api.log
```

The wake lock is always released on `stop`, even if one of the
processes refused to exit. You will not be left with a wake lock
you cannot get rid of.

## Crash recovery

Phones are not servers. The runtime can disappear for reasons that
have nothing to do with M.U.S.E. itself — the OOM killer reclaims
RAM, the vendor's battery optimizer terminates Termux, a forced
reboot interrupts work, or Android pushes a system update.

The service is designed to recover from any of these without
manual intervention beyond a single `start`:

- **PID file is stale, no process alive.** `status` reports
  `stopped` with a `(stale PID file: …)` annotation. The next
  `start` overwrites the file and brings the API back up.
- **PID file is present, process alive.** `start` is a no-op and
  reports the running PID. You cannot accidentally end up with
  two API processes fighting over the same port.
- **Wake lock marker is present, no wake lock actually held.**
  Android can release the wake lock when the Termux app is killed
  outright. The next `start` calls `termux-wake-lock` again and
  re-creates the marker. `stop` is idempotent on the marker too.
- **Logs lost on reboot.** Logs live under `$HERMES_HOME/logs/`,
  which is on the Termux-private partition and survives reboots.
  If `$HERMES_HOME` is on shared storage and shared storage was
  unmounted, the next `start` re-creates the directory.

If you want the runtime to come back automatically after a reboot,
see [`hermes-termux-boot.md`](./hermes-termux-boot.md). Termux:Boot
plus `~/.termux/boot/10-hermes` is enough; you do not need
anything more sophisticated.

## Required Termux packages

The doctor script will flag anything missing, but here is the
minimum set for a working phone-first runtime:

```bash
# Termux essentials.
pkg install termux-tools termux-api git python nodejs

# Build toolchain — REQUIRED. Termux uses bionic libc, so pip cannot use
# PyPI's prebuilt wheels and builds from source. Two core deps
# (pydantic-core, cryptography) are Rust, and others (pyyaml, …) are C —
# without rust + a linker + clang their build hangs/fails and the install
# looks frozen for 20+ minutes.
pkg install rust binutils clang

# Granted-via-dialog permission for shared storage (only needed if
# you want to share files with other Android apps).
termux-setup-storage

# Recommended: uv replaces pip + venv with a much faster installer.
curl -LsSf https://astral.sh/uv/install.sh | sh
```

`termux-tools` provides `termux-wake-lock` / `termux-wake-unlock`.
`termux-api` is the on-device helper for the Termux:API add-on
app; the doctor reports it as a warning rather than a failure
because the runtime works without it (you just lose nice extras
like `termux-battery-status`).

## Safety notes

- The service script never prints secrets, never writes to `.env`
  files, and never modifies your shell startup files.
- The doctor script is read-only — it issues no `pkg install`, no
  `mkdir` beyond what the service script already creates, and no
  outbound network calls. Its only probe is on `127.0.0.1`.
- The wake lock is released by `stop`, by tapping "Release
  Wakelock" on the Termux notification, or by killing Termux
  outright. None of those leave the system in an unsafe state.

## Cross-references

- Phone-first installer entry points: `scripts/install.sh`,
  `hermes_cli/doctor.py`.
- Background-execution rules: [`hermes-background-limits.md`](./hermes-background-limits.md).
- Wake lock policy: [`hermes-wake-lock-policy.md`](./hermes-wake-lock-policy.md).
- Boot autostart: [`hermes-termux-boot.md`](./hermes-termux-boot.md).
- Android permissions table: [`hermes-android-permissions.md`](./hermes-android-permissions.md).
