# M.U.S.E. phone-first runtime on Termux

M.U.S.E. runs as a real local development backend on an Android phone
through [Termux](https://termux.dev/). The phone is the primary host: it
owns the venv, the working directories, and the service lifecycle. No
desktop machine is required, and no traffic leaves the device unless you
explicitly configure a gateway.

This document is the entry point for that "phone-first" setup. Two
companion guides cover the OS-level pieces:

- [`hermes-termux-boot.md`](./hermes-termux-boot.md) — autostart on device boot
- [`hermes-android-permissions.md`](./hermes-android-permissions.md) — Android constraints

## Why phone-first

Termux gives you a real POSIX userland (`bash`, `python`, `git`, `node`,
`ssh`, `pkg`) inside a normal Android app sandbox. M.U.S.E. treats this as
a first-class deployment target rather than a curiosity:

- **No round trips.** Tools, models, and state live on the device.
- **Battery-aware.** The service script acquires a Termux wake lock so
  the runtime is not paused the moment the screen turns off.
- **No secrets in cloud.** Credentials stay in `$HERMES_HOME` on the
  device's private storage.
- **Self-diagnosing.** A doctor script verifies the environment before
  you spend time debugging service failures.

## Quick start

```bash
# 1. Confirm the environment is healthy.
bash scripts/hermes-termux-doctor.sh

# 2. Start the local API (and the gateway, if you opt in).
bash scripts/hermes-termux-service.sh start

# 3. Inspect status / tail logs.
bash scripts/hermes-termux-service.sh status
bash scripts/hermes-termux-service.sh logs api
```

`hermes-termux-service.sh` is intentionally minimal — no systemd, no
launchd, no service manager binaries. Termux does not run any of those.
Instead, the script supervises with a PID file plus `nohup`, and
acquires a [wake lock](./hermes-android-permissions.md#wake-lock) so
Android's Doze mode does not freeze the process when the screen turns
off.

## Service commands

| Command   | Effect                                                         |
| --------- | -------------------------------------------------------------- |
| `start`   | Acquire wake lock, start the local API, optionally the gateway |
| `stop`    | Graceful SIGTERM, then SIGINT after 10s; release wake lock     |
| `restart` | `stop` + short pause + `start`                                 |
| `status`  | PID + uptime + wake lock state                                 |
| `logs`    | `tail -F` the most recent service log (`api` or `gateway`)     |
| `doctor`  | Delegate to `hermes-termux-doctor.sh`                          |

The script never uses `kill -9`, never deletes data, and never reads or
prints secrets. Stop will report (not force-kill) any process that
refuses SIGINT after 12 seconds, so you can investigate before
escalating.

## Doctor checks

`scripts/hermes-termux-doctor.sh` is a read-only diagnostic. It produces
human-readable output by default and machine-readable JSON with
`--json`. It exits non-zero only on hard failures, so it is safe to
chain into a `SessionStart` hook.

What it checks, grouped:

1. **Termux detection** — `TERMUX_VERSION`, `PREFIX`, `termux-info`.
2. **Package manager + storage** — `pkg`, `apt`, `~/storage` symlink,
   Termux:API availability.
3. **Wake lock support** — `termux-wake-lock` / `termux-wake-unlock`.
4. **Core tooling** — `git`, `python`/`python3`, `pip`, `node`.
5. **Optional CLI agents** — `gh`, `codex`, `claude`, `aider`, `goose`.
6. **M.U.S.E. install state** — `HERMES_HOME`, `hermes-agent` checkout,
   venv discovery, `hermes` command on PATH.

Sample output (abridged):

```
── Termux detection ──
[OK  ] Running inside Termux (TERMUX_VERSION=0.118.0)
[OK  ] PREFIX environment variable set (<PREFIX>)
[OK  ] termux-info available (aarch64 on Android 14)

── Wake lock ──
[OK  ] termux-wake-lock / termux-wake-unlock available
[INFO] Wake lock keeps the CPU awake while the gateway runs in the background

── Core tooling ──
[OK  ] git available (git version 2.x)
[OK  ] python available (Python 3.12.x)
[WARN] node missing (pkg install nodejs — optional; needed for browser tools)
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
service script reads them on every invocation, so changes take effect
on the next `start`/`restart`.

## Where to go next

- Wire the service into device boot — [`hermes-termux-boot.md`](./hermes-termux-boot.md).
- Understand what Android allows in the background —
  [`hermes-android-permissions.md`](./hermes-android-permissions.md).
- For the broader installer story (Termux packages, the
  `.[termux-all]` extras profile, etc.), see `scripts/install.sh` and
  `hermes_cli/doctor.py`.

## Safety notes

- The service script never prints secrets, never writes to `.env`
  files, and never modifies your shell startup files.
- The doctor script is read-only — it issues no `pkg install`, no
  `mkdir` beyond what the service script already creates, and no
  network calls.
- The wake lock can be released at any time with `bash
  scripts/hermes-termux-service.sh stop` or by tapping "Release
  Wakelock" in the Termux notification.
