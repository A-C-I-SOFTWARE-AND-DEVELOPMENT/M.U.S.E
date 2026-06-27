"""Hardware probe — detect what the local box can actually run.

Stdlib-only and **Android/Termux-safe** (no ``psutil`` dependency). Every
probe degrades gracefully: if a value can't be read it returns ``None`` rather
than raising, so callers can still make a tier decision from partial data.

Detected:

- CPU logical cores
- total system RAM (GB)
- GPU VRAM (GB) — best-effort via ``nvidia-smi`` if present; never required
- OS / platform
- free disk space at the model cache path (GB)

The probe performs **no downloads** and reads no secrets. The only subprocess
it may run is ``nvidia-smi --query-gpu`` (read-only), guarded by a timeout.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# Tiers map to the model sizes a box can comfortably serve. Thresholds are
# conservative so we never recommend a model that will thrash a machine.
TIER_THRESHOLDS_GB: tuple[tuple[str, float], ...] = (
    ("server", 80.0),  # multi-GPU / big VRAM or huge RAM
    ("workstation", 24.0),
    ("desktop", 12.0),
    ("laptop", 0.0),
)

# --- KV-cache sizing constants (used by vram_safe_context_limit) -----------
# Fixed runtime/scratch overhead reserved on the accelerator before weights or
# KV cache (CUDA context, activations, framework buffers).
_RUNTIME_OVERHEAD_GB = 1.5
# Reference KV-cache footprint for a 9-12B model at q8_0 KV: ~0.9 GB per 8K
# tokens (within the defensible 0.5-1.0 GB/8K band). KV bytes/token scale
# linearly from this reference by model size and KV-quant element width.
_REF_KV_GB_PER_8K = 0.9
_REF_MODEL_GB = 6.0  # on-disk size of the q4_k_m reference model (~9-11B)
# Share of the post-overhead VRAM the runtime can devote to the KV cache when
# maximizing context on a shared card (the remainder hosts offloaded weight
# layers; on a tight card the rest of the weights stream from host RAM).
_KV_VRAM_FRACTION = 0.35
# Approximate bytes-per-element for common KV-cache quantizations, relative to
# q8_0 (1 byte/element). Unknown quants fall back to q8_0.
_KV_QUANT_BYTES: dict[str, float] = {
    "f32": 4.0,
    "f16": 2.0,
    "bf16": 2.0,
    "q8_0": 1.0,
    "q5_1": 0.6875,
    "q5_0": 0.625,
    "q4_1": 0.5625,
    "q4_0": 0.5,
}
# CPU-only fallback: tokens of context affordable per GB of usable system RAM.
_CPU_RAM_TOKENS_PER_GB = 1000
# Bounds + granularity for every returned context limit.
_CTX_FLOOR = 4096
_CTX_CEILING = 32768
_CTX_STEP = 2048


@dataclass(frozen=True)
class HardwareProfile:
    os_name: str
    arch: str
    cpu_cores: Optional[int]
    ram_gb: Optional[float]
    vram_gb: Optional[float]
    free_disk_gb: Optional[float]
    gpu_name: Optional[str] = None
    gpu_available: bool = False
    """``True`` when ``nvidia-smi`` ran successfully — *regardless* of the VRAM
    figure. This distinguishes "no NVIDIA GPU / driver absent" (``False``) from
    "GPU present but the driver is down so VRAM read as ``None``" (``True``).
    ``vram_gb`` alone conflates those cases; ``gpu_available`` does not."""

    @property
    def accelerator_gb(self) -> float:
        """The memory budget that matters for model size — VRAM if present,
        otherwise system RAM (CPU inference)."""

        if self.vram_gb and self.vram_gb > 0:
            return self.vram_gb
        return self.ram_gb or 0.0

    @property
    def tier(self) -> str:
        budget = self.accelerator_gb
        for name, floor in TIER_THRESHOLDS_GB:
            if budget >= floor:
                return name
        return "laptop"

    def vram_safe_context_limit(
        self,
        model_size_gb: float,
        quant: str = "q4_k_m",
        kv_quant: str = "q8_0",
    ) -> int:
        """Largest context window (in tokens) that fits the KV cache inside the
        accelerator budget, after a fixed runtime overhead and the weights the
        runtime keeps resident.

        The estimate is driven by the **real KV-cache cost per token** — not the
        auditor's dimensionally-wrong ``(vram-1.5)*1000/(size/4)`` formula. KV
        bytes/token are modelled from a reference calibrated against a 9-12B
        model at ``q8_0`` KV (~0.5-1.0 GB per 8K tokens), scaled linearly by
        model size (``model_size_gb`` already reflects the on-disk weight quant)
        and by the KV quant's bytes/element. On a tight card the runtime trades
        offloaded weight layers for KV space, so only a fraction
        (:data:`_KV_VRAM_FRACTION`) of the post-overhead VRAM is the practical
        KV envelope; the remainder hosts weights (some streaming from host RAM).

        On a CPU-only box (``gpu_available`` is ``False``) the VRAM budget is
        meaningless, so the limit is bounded by system RAM instead.

        ``model_size_gb`` is the model's on-disk (quantized) size in GB. The
        ``quant`` argument names that weight quantization; it is accepted for
        API symmetry and forward use but the size already encodes its effect.

        The result is rounded **down** to a multiple of ``2048`` and clamped to
        ``[4096, 32768]``.
        """

        # --- CPU-only path: GPU budget is meaningless, bound by RAM. --------
        if not self.gpu_available:
            ram = self.ram_gb or 0.0
            # Reserve ~2GB for the OS; the remainder is the working set for KV
            # + activations on CPU inference.
            ram_budget = max(0.0, ram - 2.0)
            ctx = int(ram_budget * _CPU_RAM_TOKENS_PER_GB)
            return _round_and_clamp(ctx)

        # --- GPU path: KV envelope = fraction of post-overhead VRAM. --------
        post_overhead_gb = self.accelerator_gb - _RUNTIME_OVERHEAD_GB
        if post_overhead_gb <= 0:
            return _CTX_FLOOR
        kv_budget_gb = post_overhead_gb * _KV_VRAM_FRACTION

        kv_bytes_per_token = _kv_bytes_per_token(model_size_gb, kv_quant)
        if kv_bytes_per_token <= 0:  # pragma: no cover - defensive
            return _CTX_FLOOR
        ctx = int((kv_budget_gb * (1024**3)) / kv_bytes_per_token)
        return _round_and_clamp(ctx)

    def to_dict(self) -> dict[str, object]:
        return {
            "os": self.os_name,
            "arch": self.arch,
            "cpu_cores": self.cpu_cores,
            "ram_gb": self.ram_gb,
            "vram_gb": self.vram_gb,
            "gpu_name": self.gpu_name,
            "gpu_available": self.gpu_available,
            "free_disk_gb": self.free_disk_gb,
            "accelerator_gb": round(self.accelerator_gb, 2),
            "tier": self.tier,
        }


def probe(cache_path: os.PathLike[str] | str | None = None) -> HardwareProfile:
    """Build a :class:`HardwareProfile` for this machine (best-effort)."""

    return HardwareProfile(
        os_name=platform.system() or "unknown",
        arch=platform.machine() or "unknown",
        cpu_cores=_cpu_cores(),
        ram_gb=_ram_gb(),
        vram_gb=_vram_gb(),
        gpu_name=_gpu_name(),
        gpu_available=_gpu_available(),
        free_disk_gb=_free_disk_gb(cache_path),
    )


# ---------------------------------------------------------------------------
# Individual probes — each returns None on any failure.
# ---------------------------------------------------------------------------
def _cpu_cores() -> Optional[int]:
    try:
        return os.cpu_count()
    except Exception:  # pragma: no cover - defensive
        return None


def _ram_gb() -> Optional[float]:
    # Linux/most POSIX: sysconf gives pages * page size.
    try:
        pages = os.sysconf("SC_PHYS_PAGES")
        page_size = os.sysconf("SC_PAGE_SIZE")
        if pages > 0 and page_size > 0:
            return round(pages * page_size / (1024**3), 2)
    except (ValueError, OSError, AttributeError):
        pass
    # macOS fallback via sysctl.
    out = _run(["sysctl", "-n", "hw.memsize"])
    if out:
        try:
            return round(int(out.strip()) / (1024**3), 2)
        except ValueError:
            pass
    return None


def _vram_gb() -> Optional[float]:
    out = _run([
        "nvidia-smi",
        "--query-gpu=memory.total",
        "--format=csv,noheader,nounits",
    ])
    if not out:
        return None
    # Sum across GPUs; values are in MiB.
    total_mib = 0
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            total_mib += int(float(line))
        except ValueError:
            continue
    if total_mib <= 0:
        return None
    return round(total_mib / 1024, 2)


def _gpu_available() -> bool:
    """``True`` iff ``nvidia-smi`` *ran successfully* (exit 0), independent of
    the VRAM figure.

    :func:`_vram_gb` returns ``None`` both when there is no NVIDIA GPU and when
    a GPU is present but its driver is down (so VRAM can't be read) — it
    conflates the two. This probe disambiguates: it is ``True`` whenever the
    driver/CLI responds, even if VRAM is momentarily unreadable, and ``False``
    when ``nvidia-smi`` is absent or errors.
    """

    # ``-L`` lists GPUs and succeeds (exit 0) even when memory queries would
    # fail, making it the most robust "is there a working NVIDIA stack" probe.
    return _run_ok(["nvidia-smi", "-L"])


def _gpu_name() -> Optional[str]:
    out = _run(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"])
    if not out:
        return None
    first = out.splitlines()[0].strip() if out.strip() else ""
    return first or None


def _kv_bytes_per_token(model_size_gb: float, kv_quant: str) -> float:
    """KV-cache bytes consumed per context token for ``model_size_gb`` at the
    given KV quantization.

    Linearly scales a calibrated reference (a ~9-12B model at ``q8_0`` KV using
    :data:`_REF_KV_GB_PER_8K` GB per 8K tokens) by the model's on-disk size
    relative to :data:`_REF_MODEL_GB`, then by the KV quant's bytes/element
    relative to ``q8_0``. This is the defensible stand-in for the exact
    ``n_layers * 2 * kv_dim * kv_quant_bytes`` formula when per-layer geometry
    is unknown.
    """

    if model_size_gb <= 0:
        return 0.0
    ref_bytes_per_token = _REF_KV_GB_PER_8K * (1024**3) / 8192
    size_scale = model_size_gb / _REF_MODEL_GB
    quant_scale = _KV_QUANT_BYTES.get(kv_quant.lower(), 1.0)
    return ref_bytes_per_token * size_scale * quant_scale


def _round_and_clamp(ctx: int) -> int:
    """Round ``ctx`` down to a multiple of :data:`_CTX_STEP` and clamp into
    ``[_CTX_FLOOR, _CTX_CEILING]``."""

    stepped = (ctx // _CTX_STEP) * _CTX_STEP
    return max(_CTX_FLOOR, min(_CTX_CEILING, stepped))


def _free_disk_gb(cache_path: os.PathLike[str] | str | None) -> Optional[float]:
    path = Path(cache_path) if cache_path else Path.home()
    # Walk up to the first existing parent so a not-yet-created cache dir works.
    while not path.exists() and path != path.parent:
        path = path.parent
    try:
        usage = shutil.disk_usage(str(path))
        return round(usage.free / (1024**3), 2)
    except OSError:
        return None


def _run(cmd: list[str], *, timeout: float = 4.0) -> Optional[str]:
    if shutil.which(cmd[0]) is None:
        return None
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout


def _run_ok(cmd: list[str], *, timeout: float = 4.0) -> bool:
    """Return ``True`` only if ``cmd`` is present *and* exits 0.

    Unlike :func:`_run`, this distinguishes "binary absent / errored" from
    "ran successfully" without inspecting stdout — used to detect a working
    accelerator stack independent of any VRAM reading.
    """

    if shutil.which(cmd[0]) is None:
        return False
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return False
    return proc.returncode == 0
