# NVIDIA Deep Learning Software (MUSE provenance registry)

> A curated, license-aware capture of NVIDIA's
> [Deep Learning Software](https://developer.nvidia.com/deep-learning-software)
> catalog — frameworks, inference, libraries, and developer/devops tools —
> recorded as **citeable provenance cards**, not binaries. Companion to
> [`nvidia-deep-learning-software.yaml`](nvidia-deep-learning-software.yaml)
> (the machine-readable registry behind this doc). The registry is loaded by
> [`hermes_cli/jarvis_prime/nvidia_dl_software.py`](../../hermes_cli/jarvis_prime/nvidia_dl_software.py)
> and surfaced via `python -m hermes_cli.jarvis_prime nvidia-dl-software`.

As of 2026-06-15.

## Why this inventory exists

MUSE is **hardware-agnostic and local-first** — it runs on a $5 VPS, a laptop,
a GPU cluster, or Termux on a phone. It does not bundle or run NVIDIA's GUI
profilers, and most of these tools are proprietary NVIDIA binaries under the
NVIDIA Software License / EULA. So "download all to MUSE" means **capturing the
catalog as source-backed knowledge**, not fetching installers.

Each entry feeds the **Research Vault**
([`research_vault.py`](../../hermes_cli/jarvis_prime/research_vault.py)) as a
provenance card carrying the canonical source URI, an evidence strength, and the
license posture, so the learning/evidence pipeline can cite NVIDIA's
deep-learning stack via `learning_ingest.from_research_artifact`. This
*supplements* — never replaces — the existing
[open-data registry](top-open-data-sources-for-training.md).

## Capture caveat (evidence strength)

The live page `https://developer.nvidia.com/deep-learning-software` returned
**HTTP 403** to every available fetcher on 2026-06-15, so entries were
**reconstructed** from NVIDIA's official sub-pages plus web search. Every entry
is therefore `evidence_strength: vendor_reported` (its `.trust` maps to
`SourceTrust.UNVERIFIED`), and each `license_notes` asks the reader to re-verify
the URI and details at ingest. Two known wrinkles are recorded rather than
silently "fixed": **DLProf is NVIDIA-deprecated** in favor of Nsight, and
**Feature Map Explorer's standalone URL is unconfirmed** (it ships within Nsight
DL Designer).

## The catalog

### Frameworks

| Rank | Tool (`key`) | Category | License | Purpose |
|---|---|---|---|---|
| 1 | PyTorch (`pytorch`) | framework | open-source | GPU-accelerated PyTorch, tuned NGC containers for multi-GPU training/inference |
| 2 | TensorFlow (`tensorflow`) | framework | open-source | GPU-accelerated TensorFlow, tuned NGC containers |
| 3 | JAX (`jax`) | framework | open-source | GPU-accelerated, XLA-compiled JAX, tuned NGC containers |

### Inference

| Rank | Tool (`key`) | Category | License | Purpose |
|---|---|---|---|---|
| 4 | NVIDIA TensorRT (`tensorrt`) | inference-sdk | proprietary | Compiler + runtime for low-latency, high-throughput inference |
| 5 | TensorRT-LLM (`tensorrt-llm`) | inference-sdk | open-source | Compiles/optimizes LLMs for efficient GPU inference |
| 6 | Triton Inference Server (`triton-inference-server`) | inference-server | open-source | Standardized multi-backend model serving on GPU/CPU |
| 7 | TensorRT Model Optimizer (`tensorrt-model-optimizer`) | inference-sdk | mixed | Quantization/sparsity/distillation to compress models |
| 8 | TensorFlow-TensorRT (`tf-trt`) | inference-integration | mixed | Integrates TensorRT into TensorFlow for optimized inference |

### Libraries

| Rank | Tool (`key`) | Category | License | Purpose |
|---|---|---|---|---|
| 9 | cuDNN (`cudnn`) | library | proprietary | Tuned DNN primitives (conv, pooling, norm, activation) |
| 10 | NCCL (`nccl`) | library | open-source | Topology-aware multi-GPU/multi-node collective communication |
| 11 | DALI (`dali`) | library | open-source | GPU-accelerated data loading/preprocessing (ETL) |

### Developer and DevOps Tools

These are the five tools from the page section that prompted this capture.

| Rank | Tool (`key`) | Category | License | Purpose |
|---|---|---|---|---|
| 12 | Nsight Systems (`nsight-systems`) | profiler | proprietary | System-wide CPU+GPU performance analysis; find/tune optimization opportunities |
| 13 | DLProf (`dlprof`) | profiler | proprietary | Visualize GPU utilization + Tensor Core op usage (NVIDIA-deprecated) |
| 14 | Kubernetes on NVIDIA GPUs (`kubernetes-on-nvidia-gpus`) | orchestration | mixed | Scale training/inference to multi-cloud GPU clusters via Kubernetes |
| 15 | Nsight Compute (`nsight-compute`) | profiler | proprietary | Interactive CUDA kernel profiler; metrics + API debugging (GUI/CLI) |
| 16 | Feature Map Explorer (`feature-map-explorer`) | visualization | proprietary | Visualize 4D feature-map tensors and per-channel slices |

## Licensing & provenance posture

- **License field** is one of `open-source` / `proprietary` / `mixed`. Even the
  open-source frameworks/libraries are *GPU-accelerated via the proprietary CUDA
  stack*; NVIDIA's optimized container builds add the NVIDIA Deep Learning
  Container license. The Research Vault tag is `license:<value>`.
- **Nothing is downloaded or executed.** `register-vault` records provenance
  cards only (title, source URI, evidence strength, license notes, tags).
- Tools are stored as `OFFICIAL_DOC` artifacts, except those whose canonical
  source is a GitHub repo (e.g. TensorRT-LLM), stored as `REPO`.

## CLI usage

```bash
# List everything, or filter by section / category
python -m hermes_cli.jarvis_prime nvidia-dl-software list
python -m hermes_cli.jarvis_prime nvidia-dl-software list --section "Developer and DevOps Tools"
python -m hermes_cli.jarvis_prime nvidia-dl-software list --category profiler

# Inspect one tool
python -m hermes_cli.jarvis_prime nvidia-dl-software show nsight-compute

# Preview the Research Vault bridge, then persist to an isolated vault
python -m hermes_cli.jarvis_prime nvidia-dl-software register-vault --dry-run --json
python -m hermes_cli.jarvis_prime nvidia-dl-software register-vault --store /tmp/nv_vault.jsonl --json
```

The default vault lives at `~/.hermes/jarvis_prime/research_vault.jsonl`
(honoring `HERMES_HOME`), written with `0600` permissions. Override the registry
path with `--registry` or `HERMES_NVIDIA_DL_SOFTWARE_REGISTRY`.
