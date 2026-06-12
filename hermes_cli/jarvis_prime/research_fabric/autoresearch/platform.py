"""Device shim for the vendored autoresearch engine — honest MFU off-H100.

The vendored ``train.py`` hardcodes ``H100_BF16_PEAK_FLOPS = 989.5e12`` (line
463) as its MFU normalizer and stays byte-identical, so on any other GPU its
reported MFU is H100-normalized fiction. This shim detects the device (lazy
torch import — never at module import time) and re-normalizes the reported
number against a per-device dense-BF16 peak table, plus derives a default
VRAM budget for the feasibility gate.

Figures are vendor dense-BF16 (FP32-accumulate) peaks; unknown devices map to
``None`` and ``honest_mfu`` returns ``None`` rather than guessing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

# Mirrors the constant baked into vendored train.py:463 — the normalizer its
# printed mfu_percent is implicitly divided by.
H100_BF16_PEAK_FLOPS = 989.5e12

# name-substring -> dense BF16 peak FLOPS (FP32 accumulate, no sparsity).
# Ordered: first substring match wins, so more specific names come first.
PEAK_BF16_FLOPS_TABLE: tuple[tuple[str, float], ...] = (
    ("B200", 2250e12),
    ("H200", 989.5e12),
    ("H100", 989.5e12),
    ("A100", 312e12),
    ("RTX 5090", 209.5e12),
    ("RTX 5080", 112.6e12),
    ("RTX 5070 Ti", 87.9e12),
    ("RTX 5070", 61.7e12),
    ("RTX 4090", 165.2e12),
    ("RTX 4080", 97.4e12),
    ("RTX 3090", 71e12),
)


@dataclass(frozen=True)
class DeviceProfile:
    name: str
    capability: tuple[int, int]
    total_vram_mb: float
    peak_bf16_flops: Optional[float]  # None = unknown device, no honest MFU
    fa3_repo: str  # which FA3 kernel repo vendored train.py will pick


def _peak_for(name: str) -> Optional[float]:
    for substring, peak in PEAK_BF16_FLOPS_TABLE:
        if substring.lower() in name.lower():
            return peak
    return None


def detect(index: int = 0) -> Optional[DeviceProfile]:
    """Profile CUDA device ``index``; None when torch/CUDA is unavailable."""

    try:
        import torch  # ty: ignore[unresolved-import]  (lazy — owner GPU hardware only)
    except ImportError:
        return None
    try:
        if not torch.cuda.is_available():
            return None
        props: Any = torch.cuda.get_device_properties(index)
        capability = (int(props.major), int(props.minor))
    except Exception:
        return None
    name = str(props.name)
    # Mirrors vendored train.py:21-24: varunneal FA3 is Hopper-only.
    fa3_repo = (
        "varunneal/flash-attention-3"
        if capability == (9, 0)
        else "kernels-community/flash-attn3"
    )
    return DeviceProfile(
        name=name,
        capability=capability,
        total_vram_mb=float(props.total_memory) / (1024 * 1024),
        peak_bf16_flops=_peak_for(name),
        fa3_repo=fa3_repo,
    )


def honest_mfu(
    reported_mfu_percent: float, profile: Optional[DeviceProfile]
) -> Optional[float]:
    """Re-normalize train.py's H100-normalized MFU to the actual device.

    ``None`` when the device (or its peak) is unknown — no guessed numbers.
    """

    if profile is None or not profile.peak_bf16_flops:
        return None
    return reported_mfu_percent * H100_BF16_PEAK_FLOPS / profile.peak_bf16_flops


def default_vram_budget_mb(
    profile: Optional[DeviceProfile], headroom: float = 0.9
) -> float:
    """Feasibility budget: ``headroom`` of detected VRAM; 0.0 when unknown."""

    if profile is None or profile.total_vram_mb <= 0:
        return 0.0
    return profile.total_vram_mb * headroom


__all__ = [
    "H100_BF16_PEAK_FLOPS",
    "PEAK_BF16_FLOPS_TABLE",
    "DeviceProfile",
    "detect",
    "honest_mfu",
    "default_vram_budget_mb",
]
