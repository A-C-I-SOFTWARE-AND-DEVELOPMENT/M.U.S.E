# Autostarting muse with Termux:Boot

`hermes-termux-service.sh` is designed to be invoked by [Termux:Boot](https://wiki.termux.com/wiki/Termux:Boot)
so the muse runtime is up before you unlock the phone in the morning.
This document covers the boot script location, the required wake lock,
and how to optionally bring the gateway up at boot.

## Prerequisites

1. **Install the Termux:Boot add-on** from F-Droid (the Google Play
   version is not maintained). Open it once after installation — until
   you do, Android does not register the boot receiver.
2. **Allow autostart** for both Termux and Termux:Boot in your device's
   battery / autostart settings. The exact path varies by vendor; see
   [`hermes-android-permissions.md`](./hermes-android-permissions.md#autostart)
   for the common ones.
3. **Confirm the wake lock works** by running:

   ```bash
   bash scripts/hermes-termux-service.sh start
   bash scripts/hermes-termux-service.sh status
   ```

   The `wake lock` line should read `held`.

## Boot script location

Termux:Boot executes every executable file inside `~/.termux/boot/` in
alphabetical order at device startup. Create that directory if it does
not already exist, then drop in a thin wrapper that calls the muse
service script:

```bash
mkdir -p ~/.termux/boot
cat > ~/.termux/boot/10-hermes <<'BOOT'
#!/data/data/com.termux/files/usr/bin/sh
# Wake the device long enough to bring muse up reliably.
termux-wake-lock

# Adjust HERMES_REPO_DIR if your checkout lives elsewhere.
export HERMES_REPO_DIR="$HOME/.hermes/hermes-agent"
# Uncomment to also start the gateway at boot:
# export HERMES_TERMUX_GATEWAY=1

exec bash "$HERMES_REPO_DIR/scripts/hermes-termux-service.sh" start
BOOT
chmod +x ~/.termux/boot/10-hermes
```

Notes:

- The shebang must point at the Termux sh binary. `/bin/sh` does not
  exist on Android.
- The `10-` prefix gives you headroom to layer other boot scripts in a
  predictable order (`20-foo`, `30-bar`, …).
- `termux-wake-lock` is called twice: once explicitly at the top of the
  boot script (cheap insurance against very early boot races) and once
  inside `hermes-termux-service.sh start`. Both calls are idempotent.

## Verifying the boot path

Reboot the device, wait roughly thirty seconds, then re-open Termux and
run:

```bash
bash scripts/hermes-termux-service.sh status
```

You should see the API running with an uptime close to "since boot",
and `wake lock : held`. If not, check the log directory:

```bash
ls -la ~/.hermes/logs/
tail -n 80 ~/.hermes/logs/termux-api.log
```

You can also run the doctor for an at-a-glance environment health check:

```bash
bash scripts/hermes-termux-service.sh doctor
```

## Starting the gateway at boot

The local API is enough for most phone-first usage — it is the runtime
that backs `hermes` commands invoked from another Termux session. The
gateway is a separate, opt-in service that bridges muse to external
messaging platforms.

To start the gateway at boot, set `HERMES_TERMUX_GATEWAY=1` in your
boot script (commented example above). The service script will then
launch `muse gateway run` after the API is up, using the same wake
lock and PID-file machinery.

If you only want the gateway some of the time, leave it out of the
boot script and start it on demand:

```bash
HERMES_TERMUX_GATEWAY=1 bash scripts/hermes-termux-service.sh restart
```

## Wake lock and battery

The wake lock is essential for any background service on modern
Android. Without it, the Linux process keeps its memory but stops
getting CPU time within minutes of the screen turning off, and any
network listener will go unresponsive.

`hermes-termux-service.sh start` acquires the wake lock for you and
`stop` releases it. The Termux notification will show a "Wakelock held"
indicator while the service is running — that is normal and indicates
the service is allowed to keep working in the background.

For the trade-off with battery life and how to whitelist Termux against
your vendor's battery optimizer, see
[`hermes-android-permissions.md`](./hermes-android-permissions.md).

## Disabling autostart

To stop muse from coming up at boot:

```bash
rm ~/.termux/boot/10-hermes
```

The next reboot will skip muse entirely. The boot script is the only
thing you need to remove; the service script and its data are
untouched.

## Safety

- No secrets are written into `~/.termux/boot/`. Everything sensitive
  belongs in `$HERMES_HOME` and is read by the service at runtime.
- The boot script does not run anything destructive. It only acquires a
  wake lock and execs the service script.
- If `~/.termux/boot/10-hermes` errors out, Termux:Boot just logs and
  moves on; it will not retry in a loop or otherwise disrupt the boot
  sequence.
