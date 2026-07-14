#!/data/data/com.termux/files/usr/bin/bash
# muse — one-paste Termux installer + launcher.
#
#   bash <(curl -fsSL https://raw.githubusercontent.com/A-C-I-SOFTWARE-AND-DEVELOPMENT/M.U.S.E/main/scripts/install-termux.sh)
#
# Idempotent: safe to re-run after a failure or an update. Handles the
# field-reported failure modes end to end: missing binutils (`ar`) breaking
# every cargo build script, a half-upgraded rust whose std rlibs the new
# compiler rejects ("crate `std` required to be available in rlib format,
# but was not found in this form" — the files exist but are stale, so the
# toolchain is verified by actually compiling a probe, never by counting
# files), and uv's cache holding onto a build attempt made with the broken
# toolchain. Rust deps (maturin, pydantic-core) compile from source
# on-device: 15-40 minutes on a typical phone is normal.

set -u

say() { printf '\n\033[1;36m[muse-install]\033[0m %s\n' "$*"; }
fail() { printf '\n\033[1;31m[muse-install] FAILED: %s\033[0m\n' "$*"; exit 1; }

case "${PREFIX:-}" in
  *com.termux*) : ;;
  *) fail "this installer is Termux-only (see SETUP.md for other platforms)" ;;
esac

command -v termux-wake-lock >/dev/null 2>&1 && termux-wake-lock || true

say "installing Termux packages"
pkg install -y git python uv rust clang make pkg-config openssl libffi binutils \
  || fail "pkg install did not complete"

# A broken rust upgrade kills every cargo build script with exit 101. The
# rlibs can be present on disk yet still be rejected by the compiler when
# they were built by the previous rust version, so the only trustworthy
# health check is compiling and running a real binary.
rust_smoke() {
  probe_dir="${TMPDIR:-$PREFIX/tmp}/muse-rust-probe.$$"
  mkdir -p "$probe_dir" || return 1
  printf 'fn main() {}\n' > "$probe_dir/probe.rs"
  rustc "$probe_dir/probe.rs" -o "$probe_dir/probe" >/dev/null 2>&1 \
    && "$probe_dir/probe" >/dev/null 2>&1
  probe_rc=$?
  rm -rf "$probe_dir"
  return "$probe_rc"
}

if ! rust_smoke; then
  say "rust toolchain is broken (std rejected by compiler) — wiping and reinstalling it"
  dpkg --configure -a >/dev/null 2>&1 || true
  pkg uninstall -y rust >/dev/null 2>&1 || true
  # Stale std rlibs from the old version survive a plain reinstall and the
  # new compiler refuses them — clear the whole sysroot library tree.
  rm -rf "$PREFIX/lib/rustlib"
  pkg install -y rust || fail "rust reinstall"
  rust_smoke || fail "rust still cannot compile after a clean reinstall; run 'pkg update && pkg upgrade rust' then re-run this installer"
fi
say "rust toolchain verified (compiled and ran a probe binary)"

cd "$HOME"
if [ ! -d M.U.S.E/.git ]; then
  say "cloning muse"
  git clone https://github.com/A-C-I-SOFTWARE-AND-DEVELOPMENT/M.U.S.E || fail "git clone"
fi
cd M.U.S.E
git pull --ff-only 2>/dev/null || true

if [ ! -f .venv/bin/activate ]; then
  say "creating venv with $(python --version 2>&1)"
  python -m venv .venv || fail "venv creation"
fi
# shellcheck disable=SC1091
. .venv/bin/activate

say "installing muse (.[termux]) — compiles Rust deps; expect 15-40 min on-device"
if ! uv pip install -e ".[termux]"; then
  say "first attempt failed — clearing uv's build cache and retrying once"
  uv cache clean >/dev/null 2>&1 || true
  uv pip install -e ".[termux]" || fail "install failed twice; scroll up for the first 'error:' line"
fi

# Every future Termux session gets muse on PATH automatically.
if ! grep -q 'M.U.S.E/.venv' "$HOME/.bashrc" 2>/dev/null; then
  printf '\n# muse — auto-activate\n[ -f "$HOME/M.U.S.E/.venv/bin/activate" ] && . "$HOME/M.U.S.E/.venv/bin/activate"\n' >> "$HOME/.bashrc"
  say "added venv auto-activate to ~/.bashrc"
fi

say "verifying with muse doctor"
muse doctor || say "doctor reported issues above — muse can still launch"

say "launching muse"
exec muse
