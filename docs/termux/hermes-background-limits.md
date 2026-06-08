# Android background limits and M.U.S.E.

Android is not a general-purpose Linux. A process living inside
Termux is still bound by the platform's background-execution rules,
its battery optimizer, the OOM killer, and the foreground-service
contract. This document is the field guide for those constraints
as they apply to the M.U.S.E. phone-first runtime.

Companion docs:

- [`hermes-phone-runtime.md`](./hermes-phone-runtime.md) — service lifecycle
- [`hermes-wake-lock-policy.md`](./hermes-wake-lock-policy.md) — when we hold a wake lock
- [`hermes-android-permissions.md`](./hermes-android-permissions.md) — full permission table

## What "background" means on Android

Android tracks every app as one of:

| State                 | What it means                                                       | Allowed CPU |
| --------------------- | ------------------------------------------------------------------- | ----------- |
| **Foreground**        | An activity is visible, OR a foreground service is running.        | Full        |
| **Background**        | Process exists but is not visible and no foreground service.       | Heavily throttled |
| **Cached**            | Process held in RAM but nothing is happening.                       | None        |
| **Killed**            | Process terminated; pages reclaimed.                                | N/A         |

Termux runs as a normal Android app. The Termux notification you
see when you launch the terminal is **the** foreground service —
it is what keeps the Linux runtime alive on the platform's terms.
M.U.S.E. inherits Termux's foreground status; it does not run its
own foreground service.

## The three things that must be true overnight

For the M.U.S.E. runtime to survive a screen-off period longer than
a few minutes, all three of these must hold simultaneously:

1. **The Termux notification is showing.** Swiping it away revokes
   Termux's foreground-service status and pushes it into the
   background bucket. On most launchers the notification lives
   under a "Silent notifications" section.
2. **A Termux wake lock is held.** Without it the process keeps
   its memory but stops getting CPU time within minutes of the
   screen turning off, and any network listener will go
   unresponsive. The service script handles this for you — see
   [`hermes-wake-lock-policy.md`](./hermes-wake-lock-policy.md).
3. **The Termux app is not killed by the OOM killer or by the
   vendor battery optimizer.** This is the one M.U.S.E. cannot
   control from inside Termux; it is on you to configure the
   battery whitelist once per device.

If you need the runtime to survive overnight, all three conditions
must be met. The service script handles #2 for you; you handle #1
and #3 in the Android system UI.

## Doze and App Standby

Android 6 (Marshmallow) introduced **Doze mode**: when the device
is unplugged and motionless, the OS progressively shuts down
background work. Wake locks are partially ignored, network access
gets batched into "maintenance windows", alarms are deferred, and
job-scheduler jobs are suspended.

Android 9 (Pie) added **App Standby Buckets**: every app is sorted
into `active`, `working_set`, `frequent`, `rare`, or `restricted`
based on how often you use it. Apps in lower buckets get
progressively less background CPU. Termux that you only open once
a week may end up in `rare` even with battery whitelisting.

What this means for M.U.S.E.:

- A wake lock is necessary but **not sufficient**. Doze can still
  throttle network access during deep sleep.
- Opening Termux periodically (or relying on Termux:Boot to bring
  it up at every reboot) keeps the app in a higher standby bucket.
- Long-lived TCP connections (gateway WebSockets to Discord,
  Telegram, etc.) may be silently torn down during Doze
  maintenance windows. Gateways should reconnect on backoff; the
  M.U.S.E. gateway does.

## Background execution limits since Oreo

Starting with Android 8 (Oreo), the OS aggressively restricts what
background processes can do — short of running inside a foreground
service or holding a wake lock, a process loses CPU within a few
minutes of the screen turning off.

The M.U.S.E. phone-first runtime stays alive because:

- Termux's foreground service keeps the whole Termux app in the
  foreground bucket. The Linux processes spawned under it
  (including `muse serve`) inherit that classification.
- The wake lock acquired by `hermes-termux-service.sh start`
  prevents the CPU governor from idling the device while the API
  is doing work.
- The local API binds to `127.0.0.1` only, so it never gets
  classified as a network-listener app that the OS might suspend
  separately.

Without the wake lock the runtime is **not** killed — it is
**throttled**. The Python process is still there, file handles
are still open, but the scheduler stops giving it meaningful
slices of CPU. Network reads time out. The symptoms look like a
crash, but `status` will still show the process as running.

## Vendor battery optimizers

Android vendors layer their own optimizers on top of Doze. They
are aggressive, undocumented, and sometimes override the
"unrestricted" battery setting from system Settings. Without an
explicit allow-list entry, vendors like Xiaomi, Huawei, OPPO,
OnePlus, and (less aggressively) Samsung may unilaterally kill
Termux even with a wake lock held.

The settings paths change with every major OS version. The common
ones, as of 2025:

- **Stock / Pixel:** Settings → Apps → Termux → Battery →
  "Unrestricted".
- **Samsung One UI:** Settings → Apps → Termux → Battery →
  "Unrestricted", **plus** Settings → Device care → Battery →
  Background usage limits → remove Termux from "Sleeping apps".
- **Xiaomi (MIUI / HyperOS):** Settings → Apps → Manage apps →
  Termux → Battery saver → "No restrictions"; also Autostart →
  enable for Termux and Termux:Boot.
- **OnePlus / OPPO / realme (ColorOS):** Settings → Battery →
  Background power consumption → Termux → "Allow background
  activity".
- **Huawei / Honor (EMUI / HarmonyOS):** Settings → Apps → App
  launch → Termux → manage manually → enable "Auto-launch",
  "Secondary launch", and "Run in background".

If you skip this step, the runtime may mysteriously die a few
hours after a successful start. The doctor script cannot detect
this from inside Termux — Android does not expose it through any
API — so it is on you to configure once per device.

## Foreground service notification

Termux's foreground notification is what gives M.U.S.E. a stable
home on Android. The Termux team strongly recommends leaving it
visible, and so do we — there is no reliable way to keep a
long-running Linux process alive on modern Android without it.

Two things to verify on the device:

- The Termux notification is set to **show on the lock screen**
  (or at least not be hidden entirely). Android may treat
  "hidden" the same as "swiped away" after a reboot.
- Notifications for Termux are not blocked at the channel level.
  Open **Settings → Apps → Termux → Notifications** and confirm
  the "Termux" channel is enabled. Disabling the channel lets the
  OS reclaim the foreground service almost immediately.

The Termux notification also exposes two action buttons that are
relevant to M.U.S.E.:

- **EXIT** — kills the entire Termux session. Use this only when
  you actually want to terminate everything; it is equivalent to
  force-stopping the app.
- **Acquire Wakelock / Release Wakelock** — manually toggles the
  same wake lock the service script manipulates. Tapping
  "Release Wakelock" while M.U.S.E. is running will leave the
  runtime in the background-throttled state described above.

## The OOM killer

Even with a wake lock and battery whitelist, Android can still
kill Termux if the device is under memory pressure. Modern phones
ship with plenty of RAM, but games, video apps, and Chrome can
consume enough to force the OOM killer to start reclaiming.

Termux is usually high on the "OK to keep" list because of its
foreground service, but it is not immune. The defence is process
priority, not exemption:

- The Termux notification's foreground-service classification
  gives it a much lower `oom_score_adj` than typical background
  apps.
- The wake lock further nudges Android toward keeping the process.
- A vendor battery whitelist tells the OEM layer not to volunteer
  Termux for reclamation.

If the OOM killer does take Termux, Termux:Boot will *not* bring
it back — Termux:Boot only fires at device boot. You will need to
re-open Termux manually, after which a single
`hermes-termux-service.sh start` restores the runtime.

## Network constraints

Background-execution rules also touch the network stack:

- Termux can bind to any localhost port without root. The default
  `HERMES_TERMUX_API_PORT=8765` works out of the box.
- Binding below 1024 requires either root or the Linux capability
  set, neither of which is available on stock Android. Pick a
  port ≥ 1024.
- Inbound connections from other devices on the same Wi-Fi work,
  but Android's Private DNS and per-app VPNs can block them
  silently.
- Mobile networks (LTE/5G) often run behind carrier NAT — exposing
  the API to the public internet requires a tunnel (Tailscale,
  Cloudflare Tunnel, etc.). M.U.S.E. does not require this and the
  default install does not configure it.
- During Doze maintenance windows, even foreground services with
  wake locks can see network requests batched. Your gateway will
  reconnect; do not write code that assumes a connection cannot
  drop for 5 minutes.

## Storage constraints

Termux has two distinct filesystems, and the runtime uses both:

| Path                        | Owned by      | Notes                                          |
| --------------------------- | ------------- | ---------------------------------------------- |
| `$HOME` (Termux home)       | Termux only   | Private, full POSIX, no Android app can read it |
| `$PREFIX` (Termux packages) | Termux only   | Maps to `/data/data/com.termux/files/usr`      |
| `~/storage` (after setup)   | Shared        | Symlinks into shared Android storage            |
| `/sdcard`, `/storage/...`   | Shared        | Requires storage permission                    |

Run `termux-setup-storage` once after installing Termux to create
the `~/storage` symlinks. M.U.S.E. itself does not require shared
storage — `$HERMES_HOME` defaults to `$HOME/.hermes`, which lives
entirely inside the Termux-private sandbox. The doctor script
warns if `~/storage` is missing but does not treat it as a
failure.

## Summary table

| Constraint                       | Mitigation                                              |
| -------------------------------- | ------------------------------------------------------- |
| Doze / background limits         | Wake lock + persistent Termux notification              |
| App Standby buckets              | Use Termux periodically, or autostart at boot           |
| Vendor battery optimizer         | Whitelist Termux + Termux:Boot manually (once per device)|
| OOM killer                       | Foreground service + wake lock + whitelist              |
| Boot autostart                   | Termux:Boot add-on + `~/.termux/boot/10-hermes`         |
| Privileged ports                 | Use a port ≥ 1024 (`HERMES_TERMUX_API_PORT`)            |
| Public reachability              | Bring your own tunnel (out of scope)                    |

## Safety

This document deliberately contains no API keys, tokens, account
identifiers, or other secrets. The service and doctor scripts do
not write or print secrets. The runtime stays inside the
Termux-private sandbox by default; shared-storage access is
opt-in.
