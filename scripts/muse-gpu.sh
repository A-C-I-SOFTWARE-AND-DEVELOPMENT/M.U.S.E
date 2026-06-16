#!/usr/bin/env bash
# muse-gpu.sh — run MUSE (or any command) inside the CUDA container, with the
# host GPU passed through. The portable "use NVIDIA tools on any device" path:
# one image, any Linux host with an NVIDIA GPU + driver + NVIDIA Container Toolkit.
#
# Wire it up as `muse gpu` if you like:
#   alias muse-gpu="$PWD/scripts/muse-gpu.sh"
#
# Usage:
#   scripts/muse-gpu.sh build                 # build the image from Dockerfile.cuda
#   scripts/muse-gpu.sh run <cmd> [args...]   # run <cmd> in the container (--gpus all)
#   scripts/muse-gpu.sh shell                 # interactive shell in the container
#   scripts/muse-gpu.sh smoke                 # nvidia-smi + nvcc + MUSE CLI smoke
#   scripts/muse-gpu.sh --print run <cmd>     # print the docker command, run nothing
#
# Env overrides:
#   IMAGE        image tag           (default: muse-cuda:local)
#   CUDA_IMAGE   base image          (passed to docker build --build-arg)
#   DOCKERFILE   dockerfile path     (default: Dockerfile.cuda)
set -uo pipefail

cd "$(dirname "$0")/.." || exit 2

IMAGE="${IMAGE:-muse-cuda:local}"
DOCKERFILE="${DOCKERFILE:-Dockerfile.cuda}"
PRINT_ONLY=0

step() { printf '\n\033[1m── %s ──\033[0m\n' "$*"; }
die()  { printf '\033[1;31mERROR: %s\033[0m\n' "$*" >&2; exit 2; }

usage() { sed -n '2,27p' "$0" | sed 's/^# \{0,1\}//'; exit 0; }

# Print or execute a docker command (so this is testable without Docker).
docker_do() {
  printf '   + %s\n' "$*"
  [ "$PRINT_ONLY" -eq 1 ] && return 0
  command -v docker >/dev/null 2>&1 || die "docker not found. Install Docker + the NVIDIA Container Toolkit: https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html"
  "$@"
}

# Leading flags.
while [ $# -gt 0 ]; do
  case "$1" in
    --print|--dry-run) PRINT_ONLY=1; shift ;;
    -h|--help) usage ;;
    build|run|shell|smoke) break ;;
    *) die "unknown argument: $1 (try --help)" ;;
  esac
done

[ $# -gt 0 ] || usage
SUBCMD="$1"; shift

BUILD_ARGS=()
[ -n "${CUDA_IMAGE:-}" ] && BUILD_ARGS=(--build-arg "CUDA_IMAGE=${CUDA_IMAGE}")
GPU_RUN=(docker run --rm --gpus all -v "$PWD":/work -w /work "$IMAGE")

case "$SUBCMD" in
  build)
    step "Build $IMAGE from $DOCKERFILE"
    docker_do docker build -f "$DOCKERFILE" "${BUILD_ARGS[@]}" -t "$IMAGE" .
    ;;
  run)
    [ $# -gt 0 ] || die "run needs a command, e.g. run python -m hermes_cli.jarvis_prime nvidia-dl-software list"
    step "Run in $IMAGE (GPU passthrough)"
    docker_do "${GPU_RUN[@]}" "$@"
    ;;
  shell)
    step "Interactive shell in $IMAGE (GPU passthrough)"
    docker_do docker run --rm -it --gpus all -v "$PWD":/work -w /work "$IMAGE" bash
    ;;
  smoke)
    step "GPU + toolkit smoke in $IMAGE"
    docker_do "${GPU_RUN[@]}" bash -lc 'nvidia-smi && nvcc --version && python -m hermes_cli.jarvis_prime nvidia-dl-software list'
    ;;
  *)
    die "unknown subcommand: $SUBCMD (try --help)"
    ;;
esac
