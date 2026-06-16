#!/usr/bin/env bash
# install-cuda.sh — install the NVIDIA CUDA toolkit on (almost) any device.
#
# MUSE is hardware-agnostic; the NVIDIA dev tools it catalogs
# (docs/ai-intelligence/nvidia-deep-learning-software.md) need the CUDA toolkit
# to build/run. This script detects your OS/arch/GPU and picks the right install
# path so the same command works across machines. See the full cross-device
# guide at docs/gpu/using-nvidia-tools-anywhere.md.
#
# Paths (auto-selected, or force with --mode):
#   apt          Ubuntu/Debian distro package `nvidia-cuda-toolkit` (CUDA 12.0).
#                Simplest; no third-party repo; installs nvcc + libs. CPU-OK.
#   nvidia-repo  NVIDIA's official CUDA apt repo (latest, e.g. cuda-toolkit-12-6).
#                Adds the NVIDIA repo + keyring. Best for a real GPU box.
#   wsl          NVIDIA's WSL-Ubuntu repo (toolkit only; the GPU driver comes
#                from the Windows host).
#   pip          Redistributable CUDA wheels into the active venv (nvcc + runtime)
#                — cross-distro, no root. Fallback when apt isn't available.
#
# Usage:
#   scripts/install-cuda.sh [--mode auto|apt|nvidia-repo|wsl|pip]
#                           [--cuda-version 12-6] [--dry-run] [--yes] [--force]
#
# Notes:
#   * Installing the toolkit does NOT require a GPU — you can compile CUDA on a
#     CPU-only host. Running kernels needs a physical NVIDIA GPU + driver.
#   * --dry-run prints the exact commands and changes nothing (safe in CI).
set -uo pipefail

MODE="auto"
CUDA_VERSION="12-6"   # used by nvidia-repo / wsl meta-package: cuda-toolkit-<X-Y>
DRY_RUN=0
ASSUME_YES=0
FORCE=0

c_bold() { printf '\033[1m%s\033[0m\n' "$*"; }
step()   { printf '\n\033[1m── %s ──\033[0m\n' "$*"; }
info()   { printf '   %s\n' "$*"; }
warn()   { printf '\033[1;33m   ! %s\033[0m\n' "$*"; }
die()    { printf '\033[1;31mERROR: %s\033[0m\n' "$*" >&2; exit 2; }

usage() {
  sed -n '2,33p' "$0" | sed 's/^# \{0,1\}//'
  exit 0
}

# Run a command, or just print it under --dry-run. Use for every mutating step.
run() {
  if [ "$DRY_RUN" -eq 1 ]; then
    printf '   + %s\n' "$*"
  else
    printf '   + %s\n' "$*"
    "$@"
  fi
}

# sudo only when not already root (and only if sudo exists).
SUDO=""
need_sudo() {
  if [ "$(id -u)" -ne 0 ]; then
    if command -v sudo >/dev/null 2>&1; then
      SUDO="sudo"
    elif [ "$DRY_RUN" -eq 1 ]; then
      SUDO="sudo"   # display only — dry run executes nothing
    else
      die "need root or sudo for $MODE install"
    fi
  fi
}

while [ $# -gt 0 ]; do
  case "$1" in
    --mode) MODE="${2:-}"; shift 2 ;;
    --mode=*) MODE="${1#*=}"; shift ;;
    --cuda-version) CUDA_VERSION="${2:-}"; shift 2 ;;
    --cuda-version=*) CUDA_VERSION="${1#*=}"; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    --yes|-y) ASSUME_YES=1; shift ;;
    --force) FORCE=1; shift ;;
    -h|--help) usage ;;
    *) die "unknown argument: $1 (try --help)" ;;
  esac
done

case "$MODE" in
  auto|apt|nvidia-repo|wsl|pip) ;;
  *) die "invalid --mode: $MODE" ;;
esac

# --- detect environment -----------------------------------------------------
OS="$(uname -s)"
ARCH="$(uname -m)"
DISTRO_ID=""
DISTRO_VER=""
if [ -r /etc/os-release ]; then
  # shellcheck disable=SC1091
  . /etc/os-release
  DISTRO_ID="${ID:-}"
  DISTRO_VER="${VERSION_ID:-}"
fi
IS_WSL=0
if grep -qiE "microsoft|wsl" /proc/version 2>/dev/null; then IS_WSL=1; fi
HAS_GPU=0
if command -v nvidia-smi >/dev/null 2>&1; then HAS_GPU=1
elif command -v lspci >/dev/null 2>&1 && lspci 2>/dev/null | grep -qi nvidia; then HAS_GPU=1; fi
HAS_NVCC=0
command -v nvcc >/dev/null 2>&1 && HAS_NVCC=1

step "Environment"
info "os=$OS arch=$ARCH distro=${DISTRO_ID:-?} ${DISTRO_VER:-} wsl=$IS_WSL gpu=$HAS_GPU nvcc=$HAS_NVCC"

# macOS has no NVIDIA CUDA support — there is nothing to install.
if [ "$OS" = "Darwin" ]; then
  die "CUDA is not available on macOS. Use a remote/cloud NVIDIA GPU — see docs/gpu/using-nvidia-tools-anywhere.md"
fi

# Idempotent: if nvcc is already here and we're not forcing, we're done.
# (Skipped under --dry-run so the planned commands are always shown.)
if [ "$HAS_NVCC" -eq 1 ] && [ "$FORCE" -eq 0 ] && [ "$DRY_RUN" -eq 0 ]; then
  c_bold "CUDA toolkit already installed:"
  nvcc --version | sed 's/^/   /'
  info "Re-run with --force to reinstall."
  exit 0
fi
[ "$HAS_NVCC" -eq 1 ] && warn "nvcc already present — will proceed because --force/--dry-run was given."

# --- resolve auto mode ------------------------------------------------------
if [ "$MODE" = "auto" ]; then
  if [ "$IS_WSL" -eq 1 ]; then MODE="wsl"
  elif command -v apt-get >/dev/null 2>&1; then MODE="apt"
  else MODE="pip"; warn "no apt-get found — falling back to pip wheels"; fi
  info "auto-selected mode: $MODE"
fi

# Map arch to NVIDIA's repo path component.
nvidia_arch() {
  case "$ARCH" in
    x86_64) echo "x86_64" ;;
    aarch64|arm64) echo "sbsa" ;;  # server arm; Jetson uses JetPack instead
    *) die "unsupported arch for NVIDIA repo: $ARCH" ;;
  esac
}

APT_YES="-y"; [ "$ASSUME_YES" -eq 0 ] && [ -t 0 ] && APT_YES=""  # interactive if a TTY

# --- install ----------------------------------------------------------------
case "$MODE" in
  apt)
    step "Install via Ubuntu/Debian package (nvidia-cuda-toolkit)"
    command -v apt-get >/dev/null 2>&1 || die "apt-get not found (use --mode pip)"
    need_sudo
    run $SUDO apt-get update
    # shellcheck disable=SC2086
    run $SUDO env DEBIAN_FRONTEND=noninteractive apt-get install $APT_YES --no-install-recommends nvidia-cuda-toolkit \
      || die "apt install failed"
    CUDA_HOME_HINT="/usr/lib/cuda"
    ;;

  nvidia-repo)
    step "Install via NVIDIA CUDA apt repo (cuda-toolkit-$CUDA_VERSION, latest)"
    [ "$DISTRO_ID" = "ubuntu" ] || [ "$DISTRO_ID" = "debian" ] || \
      warn "nvidia-repo is tuned for Ubuntu/Debian; '$DISTRO_ID' may differ"
    need_sudo
    local_distro="${DISTRO_ID}$(echo "${DISTRO_VER}" | tr -d '.')"   # e.g. ubuntu2404
    a="$(nvidia_arch)"
    keyring="cuda-keyring_1.1-1_all.deb"
    base="https://developer.download.nvidia.com/compute/cuda/repos/${local_distro}/${a}"
    run wget -qO "/tmp/${keyring}" "${base}/${keyring}" || die "could not download keyring from ${base}"
    run $SUDO dpkg -i "/tmp/${keyring}" || die "dpkg keyring install failed"
    run $SUDO apt-get update
    # shellcheck disable=SC2086
    run $SUDO env DEBIAN_FRONTEND=noninteractive apt-get install $APT_YES "cuda-toolkit-${CUDA_VERSION}" \
      || die "cuda-toolkit-${CUDA_VERSION} install failed"
    CUDA_HOME_HINT="/usr/local/cuda"
    ;;

  wsl)
    step "Install via NVIDIA WSL-Ubuntu repo (toolkit only; driver from Windows)"
    need_sudo
    a="$(nvidia_arch)"
    keyring="cuda-keyring_1.1-1_all.deb"
    base="https://developer.download.nvidia.com/compute/cuda/repos/wsl-ubuntu/${a}"
    run wget -qO "/tmp/${keyring}" "${base}/${keyring}" || die "could not download keyring from ${base}"
    run $SUDO dpkg -i "/tmp/${keyring}" || die "dpkg keyring install failed"
    run $SUDO apt-get update
    # shellcheck disable=SC2086
    run $SUDO env DEBIAN_FRONTEND=noninteractive apt-get install $APT_YES "cuda-toolkit-${CUDA_VERSION}" \
      || die "cuda-toolkit-${CUDA_VERSION} install failed"
    warn "Do NOT install a Linux GPU driver under WSL — the Windows driver provides it."
    CUDA_HOME_HINT="/usr/local/cuda"
    ;;

  pip)
    step "Install redistributable CUDA wheels (nvcc + runtime) into the active venv"
    PIP="pip"
    command -v uv >/dev/null 2>&1 && PIP="uv pip"
    # shellcheck disable=SC2086
    run $PIP install nvidia-cuda-nvcc-cu12 nvidia-cuda-runtime-cu12 nvidia-cuda-cccl-cu12 nvidia-cublas-cu12 \
      || die "pip wheel install failed"
    warn "Wheel nvcc lives under <site-packages>/nvidia/cuda_nvcc/bin — add it to PATH."
    CUDA_HOME_HINT="<site-packages>/nvidia"
    ;;
esac

# --- verify + guidance ------------------------------------------------------
step "Verify"
if [ "$DRY_RUN" -eq 1 ]; then
  c_bold "Dry run complete — no changes made."
  info "Re-run without --dry-run to execute the steps above."
  exit 0
fi

if command -v nvcc >/dev/null 2>&1; then
  nvcc --version | sed 's/^/   /'
  c_bold "CUDA toolkit installed ✓"
else
  warn "nvcc not on PATH yet. Add it for this session:"
  info "export CUDA_HOME=${CUDA_HOME_HINT}"
  info 'export PATH="$CUDA_HOME/bin:$PATH"'
fi

if [ "$HAS_GPU" -eq 0 ]; then
  warn "No NVIDIA GPU detected here — you can COMPILE CUDA but not RUN kernels."
  info "To run on a GPU from this device, see the remote-GPU section of"
  info "docs/gpu/using-nvidia-tools-anywhere.md"
fi
