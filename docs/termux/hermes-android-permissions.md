# Android permissions and constraints for M.U.S.E. on Termux

Android is not a general-purpose Linux. A process running inside
Termux is still bound by the platform's background-execution rules,
its battery optimizer, and its storage sandbox. This document calls
out the constraints that matter for the M.U.S.E. phone-first runtime,
and how the service script accommodates each one.

## Background execution limits

Starting with Android 8 (Oreo), the OS aggressively restricts what
background processes can do — short of holding a wake lock or running
inside a foreground service, a process loses CPU within a few minutes
of the screen turning off.

Termux ships its own foreground service that holds the notification
you see when Termux is running. While that notification is visible,
Termux itself is exempt from background restrictions. M.U.S.E. inherits
that exemption only as long as:

1. **The Termux notification is showing.** Do not swipe it away. On
   most launchers it lives under a "Silent notifications" section.
2. **A wake lock is held.** See [Wake lock](#wake-lock) below.
3. **The Termux app is not killed by the OOM killer.** See
   [Battery optimization](#battery-optimization).

If you need the runtime to survive overnight, all three conditions
must be met. The service script handles #2 for you; you handle #1 and
#3 in the system UI once per device.

## Foreground service / notification

Termux's foreground notification is what gives M.U.S.E. a stable home
on Android. The Termux team strongly recommends leaving it visible,
and so do we — there is no reliable way to keep a long-running Linux
process alive on modern Android without it.

Two things to verify on the device:

- The Termux notification is set to **show on the lock screen** (or
  at least not hidden entirely). Android may treat "hidden" the same
  as swiped away after a reboot.
- Notifications for Termux are not blocked at the channel level.
  Open **Settings → Apps → Termux → Notifications** and make sure
  the "Termux" channel is enabled. Disabling it lets the OS reclaim
  the foreground service almost immediately.

## Wake lock

`hermes-termux-service.sh start` calls `termux-wake-lock` before it
spawns the API or the gateway. This:

- Keeps the CPU governor from idling the device.
- Tells Android's Doze mode to leave the process alone when the
  screen turns off.
- Adds a "Wakelock held" line to the Termux notification so you can
  see the runtime is active.

`stop` calls `termux-wake-unlock`, which releases the lock and
removes the indicator. If you ever want to release the lock without
stopping the service (not recommended), tap the **Release Wakelock**
action on the Termux notification — `hermes-termux-service.sh
status` will report the lock as no longer held on the next call.

You can also opt out entirely with
`HERMES_TERMUX_NO_WAKELOCK=1`, but the service will then be subject
to Doze and will likely stop responding within minutes of the screen
turning off. Use this only when you are intentionally running a
short-lived, foreground-only command.

## Battery optimization

Android vendors layer their own battery optimizers on top of the
upstream Doze framework. Without an explicit allow-list entry,
aggressive vendors (Xiaomi, Huawei, OPPO, OnePlus, Samsung) may
unilaterally kill Termux even with a wake lock held. The path varies,
but the common ones are:

- **Stock / Pixel:** Settings → Apps → Termux → Battery → "Unrestricted".
- **Samsung:** Settings → Apps → Termux → Battery → "Unrestricted",
  *plus* Settings → Device care → Battery → Background usage limits →
  remove Termux from "Sleeping apps".
- **Xiaomi (MIUI):** Settings → Apps → Manage apps → Termux →
  Battery saver → "No restrictions"; also Autostart → enable for
  Termux and Termux:Boot.
- **OnePlus / OPPO / realme:** Settings → Battery → Background power
  consumption → Termux → "Allow background activity".

If you skip this step, you may see the runtime mysteriously die a few
hours after a successful start. The doctor script cannot detect this
from inside Termux — Android does not expose it — so it is on you to
configure once per device.

## Autostart

For [Termux:Boot](https://wiki.termux.com/wiki/Termux:Boot) to work
at all on most vendors, you also need to grant autostart permission:

- **Xiaomi:** Settings → Apps → Permissions → Autostart → enable for
  Termux and Termux:Boot.
- **Huawei / Honor:** Settings → Apps → App launch → Termux → manage
  manually → enable "Auto-launch".
- **Samsung:** generally no extra step beyond unrestricted battery.

Stock Android / Pixel devices do not require autostart configuration
beyond installing Termux:Boot and opening it once.

## File storage paths

Termux has two distinct filesystems, and M.U.S.E. uses both:

| Path                        | Owned by      | Notes                                          |
| --------------------------- | ------------- | ---------------------------------------------- |
| `$HOME` (Termux home)       | Termux only   | Private, full POSIX, no Android app can read it |
| `$PREFIX` (Termux packages) | Termux only   | Maps to `/data/data/com.termux/files/usr`      |
| `~/storage` (after setup)   | Shared        | Symlinks into shared Android storage           |
| `/sdcard`, `/storage/...`   | Shared        | Requires storage permission                    |

Run `termux-setup-storage` once after installing Termux to create the
`~/storage` symlinks. M.U.S.E. itself does not require shared storage —
`$HERMES_HOME` defaults to `$HOME/.hermes`, which lives entirely
inside the Termux-private sandbox. The doctor script will warn
if `~/storage` is missing but will not treat it as a failure.

### Why we default to private storage

- Private storage survives OS updates without re-prompting for
  permissions.
- Other apps cannot read it, so any local secrets, models, or
  conversation history stay inside Termux.
- Backup tools that target `/sdcard` will not accidentally pick up
  your `$HERMES_HOME`.

If you want to share artifacts with other apps (for example, exports
or screenshots), move just those files into `~/storage/shared/...`
explicitly rather than relocating the whole `$HERMES_HOME`.

## Storage permission status

The doctor script checks for the `~/storage` symlink as a proxy for
"has the user granted Termux the storage permission?". This is the
right signal in practice: `termux-setup-storage` creates the symlink
only after the Android dialog is accepted, so its presence implies
permission, and its absence implies the dialog was never accepted (or
the symlink was deleted).

If you re-deny the permission later in Android settings, the symlink
will still be there but reads will fail. That is a corner case the
doctor cannot detect without actually writing files, which it
deliberately does not do.

## Network constraints

- Termux can bind to any localhost port without root. The default
  `HERMES_TERMUX_API_PORT=8765` works out of the box.
- Binding below 1024 requires either root or the Linux capability
  set, neither of which is available on stock Android. Pick a port
  >=1024.
- Inbound connections from other devices on the same Wi-Fi work, but
  Android's Private DNS and per-app VPNs can block them silently.
- Mobile networks (LTE/5G) often run behind carrier NAT — exposing
  the API to the public internet requires a tunnel (Tailscale,
  Cloudflare Tunnel, etc.). M.U.S.E. does not require this and the
  default install does not configure it.

## Summary table

| Constraint                       | Mitigation                                              |
| -------------------------------- | ------------------------------------------------------- |
| Doze / background limits         | Wake lock + persistent Termux notification              |
| Vendor battery optimizer         | Whitelist Termux + Termux:Boot manually (once per device)|
| Boot autostart                   | Termux:Boot add-on + `~/.termux/boot/10-hermes`         |
| Shared storage access            | `termux-setup-storage` once; optional for M.U.S.E. itself |
| Privileged ports                 | Use a port >=1024 (`HERMES_TERMUX_API_PORT`)            |
| Public reachability              | Bring your own tunnel (out of scope)                    |

## Safety

This document deliberately contains no API keys, tokens, account
identifiers, or other secrets. The service script does not write any
secrets to disk and does not print them in its output. The doctor
script reports tool versions and presence flags only — it does not
echo environment variable values that might contain credentials.
