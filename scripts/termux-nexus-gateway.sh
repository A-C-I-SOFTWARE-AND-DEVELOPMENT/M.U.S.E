#!/usr/bin/env bash
# ============================================================================
# Auto-establish a MUSE gateway on THIS Android phone (Termux) and serve the
# NEXUS PWA same-origin — so the entire MUSE is reachable from the phone at
#
#     http://127.0.0.1:8765/nexus/
#
# Because the PWA and the API share one http loopback origin, there is no
# mixed-content barrier and no tunnel needed: cockpit, orchestration, memory,
# fleet — all of it — work from the phone browser. Add it to the home screen
# and it behaves like a native app.
#
# One-liner (paste into Termux):
#   curl -fsSL https://raw.githubusercontent.com/A-C-I-SOFTWARE-AND-DEVELOPMENT/M.U.S.E/main/scripts/termux-nexus-gateway.sh | bash
#
# Env overrides: MUSE_DIR, MUSE_REPO_URL, MUSE_BRANCH, MUSE_PORT, SKIP_BUILD=1
# ============================================================================
set -euo pipefail

MUSE_DIR="${MUSE_DIR:-$HOME/M.U.S.E}"
MUSE_REPO_URL="${MUSE_REPO_URL:-https://github.com/A-C-I-SOFTWARE-AND-DEVELOPMENT/M.U.S.E.git}"
MUSE_BRANCH="${MUSE_BRANCH:-main}"
MUSE_PORT="${MUSE_PORT:-8765}"

say() { printf '\033[0;36m▶ %s\033[0m\n' "$*"; }
ok() { printf '\033[0;32m✓ %s\033[0m\n' "$*"; }

is_termux() { [ -n "${TERMUX_VERSION:-}" ] || [[ "${PREFIX:-}" == *"com.termux/files/usr"* ]]; }

say "Installing prerequisites (git · python · nodejs · rust toolchain)…"
if is_termux; then
  pkg update -y >/dev/null 2>&1 || true
  pkg install -y git python nodejs-lts >/dev/null 2>&1 || pkg install -y git python nodejs
  # Termux uses bionic libc, so pip CANNOT use PyPI's prebuilt wheels and builds
  # from source. Two core deps (pydantic-core, cryptography) are Rust — without
  # the Rust toolchain + linker their build hangs/fails. clang builds the C deps
  # (pyyaml, …). Installing these up front is what keeps the pip step from
  # appearing frozen for 20+ minutes.
  pkg install -y rust binutils clang || pkg install -y rustc binutils clang || true
  # termux-api gives wake lock + notifications (optional but recommended)
  pkg install -y termux-api >/dev/null 2>&1 || true
  command -v rustc >/dev/null 2>&1 \
    && ok "Rust $(rustc --version 2>/dev/null | awk '{print $2}') ready" \
    || say "⚠ Rust not found — pydantic-core/cryptography may build slowly or fail. Try: pkg install rust"
else
  say "Not running under Termux — continuing anyway (desktop/dev)."
fi

say "Cloning / updating MUSE into $MUSE_DIR…"
if [ -d "$MUSE_DIR/.git" ]; then
  git -C "$MUSE_DIR" fetch --depth 1 origin "$MUSE_BRANCH" && git -C "$MUSE_DIR" checkout "$MUSE_BRANCH" && git -C "$MUSE_DIR" reset --hard "origin/$MUSE_BRANCH"
else
  git clone --depth 1 --branch "$MUSE_BRANCH" "$MUSE_REPO_URL" "$MUSE_DIR"
fi
cd "$MUSE_DIR"

say "Installing MUSE (Termux-aware). First run compiles the Rust deps —"
say "this can take 5–15 min on a phone and may show NO output mid-build. Not frozen."
if [ -f setup-hermes.sh ]; then
  bash setup-hermes.sh || pip install -e ".[termux]" -c constraints-termux.txt || pip install -e .
else
  pip install -e ".[termux]" -c constraints-termux.txt 2>/dev/null || pip install -e .
fi

if [ "${SKIP_BUILD:-0}" != "1" ]; then
  say "Building NEXUS (base = /nexus/, service worker skipped on Termux)…"
  # NEXUS_NO_PWA=1 skips the workbox/vite-plugin-pwa service-worker pass, which
  # fails on Termux/Android ("Unable to write the service worker file"). The SW is
  # an offline-shell nicety only — the gateway serves NEXUS, so it isn't needed.
  ( cd apps/nexus && (npm ci --no-audit --no-fund || npm install) && NEXUS_BASE=/nexus/ NEXUS_NO_PWA=1 npm run build )
  ok "NEXUS built → apps/nexus/dist"
else
  say "SKIP_BUILD=1 — using the existing apps/nexus/dist (if any)."
fi

# Keep the CPU awake so the gateway survives the screen turning off.
if is_termux; then termux-wake-lock 2>/dev/null || true; fi

# Resolve the CLI entry (console script after install, else module form).
MUSE_BIN="muse"
command -v muse >/dev/null 2>&1 || MUSE_BIN="hermes"
command -v "$MUSE_BIN" >/dev/null 2>&1 || MUSE_BIN="python -m hermes_cli"

ok "Gateway starting. Open this on the phone (add to home screen):"
printf '\n    \033[1;32mhttp://127.0.0.1:%s/nexus/\033[0m\n\n' "$MUSE_PORT"
echo "   First launch: NEXUS auto-detects this gateway (same origin) and pairs"
echo "   once you enter the owner phrase: Yes, with authorization."
echo
exec $MUSE_BIN cockpit serve --port "$MUSE_PORT"
