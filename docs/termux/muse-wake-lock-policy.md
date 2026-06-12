# M.U.S.E. wake lock policy

The M.U.S.E. phone-first runtime holds a **Termux wake lock** for as
long as the service is running, and releases it as soon as the
service stops. This document explains why, what kind of wake lock
that is, when we acquire and release it, and how to opt out when
you know what you are doing.

Companion docs:

- [`muse-phone-runtime.md`](./muse-phone-runtime.md) — service lifecycle
- [`muse-background-limits.md`](./muse-background-limits.md) — Android background rules
- [`muse-termux-boot.md`](./muse-termux-boot.md) — autostart at device boot

## What a Termux wake lock actually is

`termux-wake-lock` calls into the Termux Android app, which in
turn acquires a `PARTIAL_WAKE_LOCK` from
`android.os.PowerManager` and pins the Termux foreground service
into a "do not throttle" state. A partial wake lock:

- Keeps the CPU running, even when the screen is off.
- Does **not** keep the screen on.
- Does **not** affect Wi-Fi or modem state directly, though it
  reduces Doze's ability to defer their work.
- Adds a "Wakelock held" line to the Termux notification so you
  can see at a glance that something is intentionally keeping the
  CPU awake.

The wake lock is **process-scoped to the Termux Android service**,
not to any individual Linux process. Releasing it does not kill
the M.U.S.E. API; the API just becomes subject to normal Doze
throttling.

## Why the runtime needs it

On Android 8 and later, a background app loses CPU within minutes
of the screen turning off. The M.U.S.E. API is a long-lived Python
process listening on `127.0.0.1:8765`. Without a wake lock:

- Network reads block indefinitely and time out.
- Sleep/poll loops fire only during Doze maintenance windows
  (every 15 minutes at first, then every hour, then every several
  hours).
- The gateway's outbound WebSockets to Discord, Telegram, etc.
  get torn down by their respective servers as "client not
  responding".

The symptoms look like a crash but the process is still alive —
it has just been frozen by the OS. A wake lock prevents this
class of pseudo-crash.

## When we acquire and release it

```
                                 wake lock state
                                 ───────────────
start                            acquired
  ├─ start API
  ├─ start gateway (optional)
  └─ write wake-lock marker      held

(running normally)               held

status                           reported as "held"

stop                             held → released
  ├─ SIGTERM API (and gateway)
  ├─ wait up to 12s for exit
  ├─ termux-wake-unlock
  └─ delete wake-lock marker     not held

restart                          held → released → held
```

Concretely:

- **`start`** calls `termux-wake-lock` first, *before* spawning
  the API. Spawning under the wake lock gives the API a brief
  window of guaranteed CPU to bind its port and finish startup.
- **`stop`** calls `termux-wake-unlock` only **after** all
  processes managed by the script have exited. If a process
  refuses to die (the script never escalates to `SIGKILL`), the
  wake lock is still released — better to leave a stuck process
  visible without a wake lock than to lock up the device for an
  unresponsive worker.
- **`restart`** is `stop` then `start`, which means there is a
  small window (typically <1s) where the wake lock is released
  and re-acquired. The Termux notification will briefly drop the
  "Wakelock held" indicator.

## The wake-lock marker file

The service writes an empty marker file at
`~/.hermes/termux/wake-lock.acquired` whenever it successfully
acquires a wake lock, and deletes it on release. This marker:

- Lets the `status` subcommand report whether the script *thinks*
  it holds a wake lock without shelling out to Termux.
- Is intentionally **advisory**. It is not used as a lock — the
  real authority is the Android wake-lock subsystem, which
  refcounts requests inside Termux's process. Multiple `start`s
  in a row are safe; the OS just refcounts.
- Is empty. It contains no secrets, no PIDs, no timestamps.

If you ever see `status` reporting `wake lock : held` but the
Termux notification disagrees, the OS won. (Or you pressed
"Release Wakelock" on the notification.) Re-run `start` and the
script will re-acquire and re-create the marker.

## Opting out

Two escape hatches exist:

### `HERMES_TERMUX_NO_WAKELOCK=1`

Setting this in the environment skips both the `termux-wake-lock`
call and the marker file:

```bash
HERMES_TERMUX_NO_WAKELOCK=1 bash scripts/hermes-termux-service.sh start
```

Use this when:

- You are running the API briefly, in the foreground, to test a
  change. There is no need to lock the CPU awake for a 30-second
  test.
- You are running on a non-Termux Linux environment (CI, a
  generic Debian VM) where `termux-wake-lock` is missing
  entirely. The script warns and continues, so the opt-out is
  purely cosmetic in that case.

Do **not** use this on a phone you expect to leave running
unattended. The runtime will appear to work and then fail in
mysterious ways the moment the screen turns off.

### The Termux notification "Release Wakelock" button

You can also release the wake lock from outside the service by
tapping **Release Wakelock** on the Termux notification. The
service is not informed and will continue to think the wake lock
is held; `status` will report it as `held` until the next `stop`.

This is fine to do in a pinch (for example, you forgot to stop
the service before going to bed and you want to save battery).
The next `start` re-acquires the wake lock and resyncs the marker.

## How the wake lock interacts with Termux:Boot

The boot script template in
[`muse-termux-boot.md`](./muse-termux-boot.md) calls
`termux-wake-lock` once at the top, before invoking the service
script:

```sh
#!/data/data/com.termux/files/usr/bin/sh
termux-wake-lock
export HERMES_REPO_DIR="$HOME/.hermes/hermes-agent"
exec bash "$HERMES_REPO_DIR/scripts/hermes-termux-service.sh" start
```

The explicit call at the top is cheap insurance against the very
early-boot race where Termux:Boot fires before the Termux app's
notification service is fully wired up. Both calls are
idempotent — they bump the same refcount inside Termux.

## Battery cost

A held partial wake lock prevents the CPU from entering deep idle
when the screen is off. On a typical Pixel-class phone running an
idle M.U.S.E. API, that costs roughly 1–3% of battery per hour —
noticeable over a full day, negligible over a few hours.

If battery cost matters more than always-on availability:

- Stop the service when you are not using it
  (`hermes-termux-service.sh stop` releases the wake lock).
- Run the service only when the phone is on a charger. The wake
  lock cost is irrelevant in that case.
- Use `HERMES_TERMUX_NO_WAKELOCK=1` for short foreground sessions
  where you do not need overnight reliability.

## What the wake lock does **not** do

The wake lock is a partial mitigation, not a guarantee:

- **It does not exempt Termux from the vendor battery optimizer.**
  Xiaomi, Huawei, OPPO and friends will still kill Termux if you
  have not whitelisted it. See
  [`muse-background-limits.md#vendor-battery-optimizers`](./muse-background-limits.md#vendor-battery-optimizers).
- **It does not prevent the OOM killer from reclaiming Termux.**
  Foreground-service classification helps; wake lock does not.
- **It does not keep network sockets alive on its own.** Gateway
  clients still need to handle reconnects.
- **It does not bring Termux back after Android force-stops it.**
  You will need to open Termux again (or rely on Termux:Boot at
  the next reboot).

The wake lock buys you "the runtime keeps getting CPU while the
screen is off". It does not buy you "the runtime is immortal".

## Safety

- The wake lock does not grant any new permission. It is purely
  a power-management hint.
- Releasing the wake lock never deletes data or kills processes;
  it only allows the CPU to idle.
- The marker file is empty and contains no secrets.
- No part of the wake-lock policy depends on, or interacts with,
  user credentials or model API keys.
