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


@dataclass(frozen=True)
class HardwareProfile:
    os_name: str
    arch: str
    cpu_cores: Optional[int]
    ram_gb: Optional[float]
    vram_gb: Optional[float]
    free_disk_gb: Optional[float]
    gpu_name: Optional[str] = None

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

    def to_dict(self) -> dict[str, object]:
        return {
            "os": self.os_name,
            "arch": self.arch,
            "cpu_cores": self.cpu_cores,
            "ram_gb": self.ram_gb,
            "vram_gb": self.vram_gb,
            "gpu_name": self.gpu_name,
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


def _gpu_name() -> Optional[str]:
    out = _run(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"])
    if not out:
        return None
    first = out.splitlines()[0].strip() if out.strip() else ""
    return first or None


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
