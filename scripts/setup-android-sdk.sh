#!/usr/bin/env bash
# Install the Android SDK needed to build the Jarvis Prime app
# (apps/android) — compile, unit-test, and assemble the debug APK.
#
# Why: Claude Code on the web / CI containers ship a JDK but no Android
# SDK, so `./gradlew assembleDebug` and the JVM/Robolectric unit tests
# can't run. Point your environment's *setup script* at this file (see
# apps/android/docs/LOCAL_SDK_SETUP.md) so every session can build.
#
# Idempotent: re-running is a no-op once the packages are present.
# Needs outbound HTTPS to dl.google.com. A hardware-accelerated emulator
# is NOT installed (it needs /dev/kvm, absent in most cloud containers) —
# this enables compile + unit tests, which is what verification needs.
#
# Honors:
#   ANDROID_HOME   install location (default: $HOME/android-sdk)
#   ANDROID_API    platform level    (default: 35, matches compileSdk)
#   ANDROID_BUILD_TOOLS build-tools  (default: 35.0.0)
set -euo pipefail

ANDROID_HOME="${ANDROID_HOME:-$HOME/android-sdk}"
ANDROID_API="${ANDROID_API:-35}"
ANDROID_BUILD_TOOLS="${ANDROID_BUILD_TOOLS:-35.0.0}"
SDKMANAGER="$ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager"

echo "==> Android SDK target: $ANDROID_HOME (api $ANDROID_API, build-tools $ANDROID_BUILD_TOOLS)"

# 1. Command-line tools (sdkmanager) — discover the current build, since the
#    version in the filename changes over time.
if [ ! -x "$SDKMANAGER" ]; then
  echo "==> Installing command-line tools"
  tmp="$(mktemp -d)"
  curl -sS -L -o "$tmp/repo.xml" "https://dl.google.com/android/repository/repository2-1.xml"
  latest="$(grep -oE 'commandlinetools-linux-[0-9]+_latest\.zip' "$tmp/repo.xml" | sort -t- -k3 -n | tail -1)"
  if [ -z "$latest" ]; then
    echo "!! could not discover commandlinetools filename (network/policy?)" >&2
    exit 1
  fi
  echo "    -> $latest"
  curl -sS -L -o "$tmp/cmdtools.zip" "https://dl.google.com/android/repository/$latest"
  mkdir -p "$ANDROID_HOME/cmdline-tools"
  rm -rf "$ANDROID_HOME/cmdline-tools/latest"
  unzip -q "$tmp/cmdtools.zip" -d "$ANDROID_HOME/cmdline-tools"
  mv "$ANDROID_HOME/cmdline-tools/cmdline-tools" "$ANDROID_HOME/cmdline-tools/latest"
  rm -rf "$tmp"
else
  echo "==> command-line tools already present"
fi

# 2. Accept licenses (idempotent) + install the build packages.
yes | "$SDKMANAGER" --licenses >/dev/null 2>&1 || true
echo "==> Installing platform-tools, platforms;android-$ANDROID_API, build-tools;$ANDROID_BUILD_TOOLS"
"$SDKMANAGER" \
  "platform-tools" \
  "platforms;android-$ANDROID_API" \
  "build-tools;$ANDROID_BUILD_TOOLS" >/dev/null

echo "==> Done. Export these (or add to your shell profile):"
echo "      export ANDROID_HOME=\"$ANDROID_HOME\""
echo "      export PATH=\"\$ANDROID_HOME/cmdline-tools/latest/bin:\$ANDROID_HOME/platform-tools:\$PATH\""
echo "==> Verify:  (cd apps/android && ANDROID_HOME=$ANDROID_HOME ./gradlew :app:assembleDebug :app:testDebugUnitTest)"
