# Using the NVIDIA tools on any device

> How to actually *use* the CUDA toolkit and the NVIDIA dev tools MUSE catalogs
> ([nvidia-deep-learning-software.md](../ai-intelligence/nvidia-deep-learning-software.md))
> across all your devices — laptop, desktop, Windows/WSL2, phone, or cloud.
> Three opt-in helpers ship with this guide:
> [`scripts/install-cuda.sh`](../../scripts/install-cuda.sh),
> [`Dockerfile.cuda`](../../Dockerfile.cuda) +
> [`scripts/muse-gpu.sh`](../../scripts/muse-gpu.sh).

## The one rule

CUDA and the NVIDIA dev tools (Nsight, cuDNN, TensorRT, Triton, DALI…) **need an
NVIDIA GPU + driver to actually run.** Without one you can still *compile* and
*inspect*, but not *execute* kernels. So "any device" is really two cases:

1. **Devices with an NVIDIA GPU** → install/run directly (paths A & B below).
2. **Devices without one** (phone, Mac, CPU laptop) → drive a *remote* GPU
   (path C) — which is exactly what MUSE is built to orchestrate.

## Device matrix

| Your device | Run them? | How |
|---|---|---|
| Linux PC/laptop w/ NVIDIA GPU | ✅ Fully | `scripts/install-cuda.sh` (apt or `--mode nvidia-repo`) |
| Windows w/ NVIDIA GPU | ✅ Fully | WSL2 + `scripts/install-cuda.sh --mode wsl` (driver from Windows) |
| Mac (Intel/Apple Silicon) | ❌ No CUDA on macOS | Remote GPU (path C) |
| CPU-only Linux (e.g. a cheap VPS) | ⚠️ Compile only | `install-cuda.sh` to build; remote GPU to run |
| Android / Termux | ❌ No NVIDIA GPU | MUSE handoff to a remote GPU (path C) |
| NVIDIA Jetson (edge, arm64) | ✅ Yes | JetPack SDK (CUDA-for-Tegra), not this script |
| Cloud GPU (Lambda/RunPod/AWS/GCP) | ✅ Yes | Provider image has drivers; path A or B |

## Path A — install the toolkit directly

The installer detects OS/arch/GPU/WSL and picks the right method; it is
idempotent (no-ops if `nvcc` is already present) and `--dry-run` changes nothing.

```bash
scripts/install-cuda.sh                      # auto-detect (apt on Ubuntu/Debian)
scripts/install-cuda.sh --mode nvidia-repo   # latest CUDA from NVIDIA's apt repo
scripts/install-cuda.sh --mode wsl           # Windows + WSL2
scripts/install-cuda.sh --mode pip           # nvcc/runtime wheels into a venv (no root)
scripts/install-cuda.sh --dry-run            # preview the exact commands
```

After install:
```bash
export CUDA_HOME=/usr/lib/cuda        # /usr/local/cuda for the nvidia-repo path
export PATH="$CUDA_HOME/bin:$PATH"
nvcc --version
```

> Installing the toolkit works even on a CPU-only box (verified) — you just need
> a real GPU to *run* kernels.

## Path B — the portable container (recommended for "any device")

One image, identical on every Linux host that has an NVIDIA GPU + driver + the
[NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html).
No per-machine CUDA install.

```bash
scripts/muse-gpu.sh build                                   # build from Dockerfile.cuda
scripts/muse-gpu.sh smoke                                   # nvidia-smi + nvcc + MUSE CLI
scripts/muse-gpu.sh run python -m hermes_cli.jarvis_prime nvidia-dl-software list
scripts/muse-gpu.sh --print run nvidia-smi                  # print the docker cmd only
```

Pin a different CUDA/cuDNN/OS by overriding the base image:
```bash
CUDA_IMAGE=nvidia/cuda:12.4.1-cudnn-devel-ubuntu22.04 scripts/muse-gpu.sh build
```

NVIDIA's prebuilt NGC images already bundle the tools, if you'd rather not build:
```bash
docker run --gpus all nvcr.io/nvidia/pytorch:24.05-py3        # framework + CUDA + cuDNN + Nsight
docker run --gpus all nvcr.io/nvidia/tritonserver:24.05-py3   # Triton inference server
```

## Path C — no local GPU? drive a remote one (the MUSE way)

Your phone/Mac/CPU-laptop can't run CUDA, but **MUSE runs on every device** and
orchestrates the GPU work elsewhere:

1. Keep **one** GPU machine — your desktop, a Jetson, or a rented cloud GPU —
   set up via path A or B.
2. From whatever device you're on, MUSE dispatches the GPU job to it and brings
   results back. See:
   - [docs/remote/windows-claude-code-bridge-guide.md](../remote/windows-claude-code-bridge-guide.md) — drive a GPU Windows box.
   - [docs/hermes-local-orchestrator.md](../hermes-local-orchestrator.md) — phone-first handoff.
   - [docs/architecture/](../architecture/) — the remote-worker / work-packet model.
3. On the GPU box, run the tools via path A/B; on your phone you trigger,
   monitor, and read the output.

## See also

- [Catalog of the NVIDIA tools themselves](../ai-intelligence/nvidia-deep-learning-software.md)
  (`python -m hermes_cli.jarvis_prime nvidia-dl-software list`).
- NVIDIA CUDA install docs: <https://docs.nvidia.com/cuda/cuda-installation-guide-linux/>
