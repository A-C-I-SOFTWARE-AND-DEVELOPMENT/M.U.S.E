# Building the Android app in a headless / cloud session

The MUSE app (`apps/android`) needs the **Android SDK** to compile,
run its JVM/Robolectric unit tests, and assemble the debug APK. Claude Code
on the web and most CI containers ship a JDK but **no SDK**, so a fresh
session can't build until the SDK is installed.

## TL;DR

```bash
bash scripts/setup-android-sdk.sh
export ANDROID_HOME="$HOME/android-sdk"
export PATH="$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools:$PATH"
cd apps/android
./gradlew :app:testDebugUnitTest :app:assembleDebug   # compile + tests + APK
```

`scripts/setup-android-sdk.sh` is idempotent, discovers the current
command-line-tools build automatically, and installs `platform-tools`,
`platforms;android-35`, and `build-tools;35.0.0` (matching `compileSdk` and
the `android-build.yml` CI workflow). It needs outbound HTTPS to
`dl.google.com`.

## Making it persistent across web sessions

The container is ephemeral — the SDK is gone when it recycles. Pick one:

1. **Environment setup script (recommended).** In your Claude Code on the
   web environment config, set the *setup script* to run
   `bash scripts/setup-android-sdk.sh`. It runs at container start so every
   session can build. Ensure the environment's **network policy allows
   `dl.google.com`**. See
   <https://code.claude.com/docs/en/claude-code-on-the-web>.
2. **Custom environment image.** Bake the SDK into a custom base image —
   fastest (no per-session download), more setup on your side.

First install downloads ~0.5 GB (cmdline-tools + platform/build-tools) plus
the Gradle distribution and AndroidX/Compose deps on the first build; budget
a few minutes on a cold container.

## What this does NOT give you: a running emulator

A hardware-accelerated emulator needs `/dev/kvm` (nested virtualization),
which cloud containers generally **don't** expose — so the *live UI* can't
be booted here, and instrumented (`androidTest`) tests can't run. That's
fine for verification: **compile + unit tests + `assembleDebug` are what
catch real defects**, and they run without an emulator.

To actually *see* the app run:

- **Sideload the CI APK:** tag `android-v*` to trigger the signed-release
  workflow (`android-release.yml`), then install the published APK on a
  phone. Or grab the debug APK artifact from `android-build.yml`.
- **Local emulator/device:** on your own machine,
  `./gradlew installDebug` against an attached device or a local AVD.
