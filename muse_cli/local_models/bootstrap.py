"""Local model bootstrap — plan first, download only with explicit consent.

The cardinal rule (from the build mandate): **a normal install must not
download huge models.** This module always produces a *plan* from the detected
hardware + open-weight catalog + installed runtimes, and only executes
downloads when the caller passes ``accept_downloads=True`` (the CLI maps this
to the ``--accept-downloads`` flag). Without that flag it is a pure dry run.

    hermes models bootstrap --tier laptop|desktop|workstation|server --accept-downloads

Nothing here runs on import or on a normal `hermes` startup.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from typing import Optional

from muse_cli.local_models.catalog import OpenWeightCatalog, OpenWeightModel
from muse_cli.local_models.hardware_probe import HardwareProfile, probe
from muse_cli.local_models.server_adapters import LaunchPlan, get_adapter


@dataclass(frozen=True)
class BootstrapItem:
    model: OpenWeightModel
    runtime: str
    runtime_installed: bool
    fits_hardware: bool
    launch: LaunchPlan
    reason: str

    def to_dict(self) -> dict[str, object]:
        return {
            "model": self.model.name,
            "source": self.model.source,
            "license": self.model.license,
            "runtime": self.runtime,
            "runtime_installed": self.runtime_installed,
            "fits_hardware": self.fits_hardware,
            "launch": self.launch.to_dict(),
            "verify": self.model.verify,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class BootstrapPlan:
    tier: str
    hardware: HardwareProfile
    items: tuple[BootstrapItem, ...]
    downloads_accepted: bool
    skipped: tuple[str, ...] = ()

    @property
    def recommended(self) -> list[BootstrapItem]:
        return [i for i in self.items if i.fits_hardware]

    def to_dict(self) -> dict[str, object]:
        return {
            "tier": self.tier,
            "hardware": self.hardware.to_dict(),
            "downloads_accepted": self.downloads_accepted,
            "items": [i.to_dict() for i in self.items],
            "recommended": [i.model.name for i in self.recommended],
            "skipped": list(self.skipped),
        }

    def render(self) -> str:
        lines = [
            f"Bootstrap plan — tier={self.tier} (detected tier={self.hardware.tier})"
        ]
        lines.append(
            f"hardware: ram={self.hardware.ram_gb}GB vram={self.hardware.vram_gb}GB "
            f"disk_free={self.hardware.free_disk_gb}GB"
        )
        if not self.downloads_accepted:
            lines.append(
                "DRY RUN — no downloads (pass --accept-downloads to fetch weights)"
            )
        for i in self.items:
            mark = "✓" if i.fits_hardware else "✗"
            rt = "installed" if i.runtime_installed else "NOT installed"
            lines.append(f"  {mark} {i.model.name} [{i.runtime}/{rt}] — {i.reason}")
            if i.launch.pull_command:
                lines.append(f"      pull: {' '.join(i.launch.pull_command)}")
        return "\n".join(lines)


@dataclass
class DownloadOutcome:
    model: str
    attempted: bool
    ok: bool
    detail: str = ""
    command: tuple[str, ...] = ()


def plan_bootstrap(
    tier: str,
    *,
    catalog: Optional[OpenWeightCatalog] = None,
    hardware: Optional[HardwareProfile] = None,
    accept_downloads: bool = False,
) -> BootstrapPlan:
    """Build a bootstrap plan for ``tier``. Performs **no** downloads."""

    tier = tier.strip().lower()
    cat = catalog or OpenWeightCatalog.load()
    hw = hardware or probe()
    items: list[BootstrapItem] = []
    skipped: list[str] = []
    ram = hw.ram_gb or 0.0
    vram = hw.vram_gb or 0.0

    for model in cat.for_tier(tier):
        try:
            adapter = get_adapter(model.runtime)
        except KeyError:
            skipped.append(f"{model.name}: unknown runtime {model.runtime}")
            continue
        fits = model.fits(ram_gb=ram, vram_gb=vram)
        installed = adapter.is_installed()
        if fits and installed:
            reason = "fits hardware; runtime ready"
        elif fits and not installed:
            reason = f"fits hardware; install {model.runtime} first"
        else:
            reason = "exceeds detected memory budget — listed but not recommended"
        items.append(
            BootstrapItem(
                model=model,
                runtime=model.runtime,
                runtime_installed=installed,
                fits_hardware=fits,
                launch=adapter.launch_plan(model.source.split(":", 1)[-1]),
                reason=reason,
            )
        )
    return BootstrapPlan(
        tier=tier,
        hardware=hw,
        items=tuple(items),
        downloads_accepted=accept_downloads,
        skipped=tuple(skipped),
    )


def execute_bootstrap(
    plan: BootstrapPlan,
    *,
    accept_downloads: bool = False,
    runner=None,
) -> list[DownloadOutcome]:
    """Execute the download steps in ``plan`` — only if downloads are accepted.

    ``runner`` is injectable for tests (defaults to ``subprocess.run``). Without
    ``accept_downloads`` this is a guaranteed no-op that reports the refusal.
    """

    outcomes: list[DownloadOutcome] = []
    if not accept_downloads:
        for item in plan.recommended:
            outcomes.append(
                DownloadOutcome(
                    model=item.model.name,
                    attempted=False,
                    ok=False,
                    detail="downloads not accepted (dry run)",
                    command=item.launch.pull_command,
                )
            )
        return outcomes

    run = runner or _default_runner
    for item in plan.recommended:
        cmd = item.launch.pull_command
        if not cmd:
            outcomes.append(
                DownloadOutcome(
                    model=item.model.name,
                    attempted=False,
                    ok=True,
                    detail="no pull step for this runtime (bring-your-own weights)",
                )
            )
            continue
        if not item.runtime_installed:
            outcomes.append(
                DownloadOutcome(
                    model=item.model.name,
                    attempted=False,
                    ok=False,
                    detail=f"{item.runtime} not installed; cannot pull",
                    command=cmd,
                )
            )
            continue
        ok, detail = run(cmd)
        outcomes.append(
            DownloadOutcome(
                model=item.model.name, attempted=True, ok=ok, detail=detail, command=cmd
            )
        )
    return outcomes


def _default_runner(
    cmd,
) -> tuple[bool, str]:  # pragma: no cover - exercised only on real downloads
    try:
        proc = subprocess.run(list(cmd), capture_output=True, text=True, timeout=3600)
    except (OSError, subprocess.SubprocessError) as exc:
        return False, str(exc)
    return proc.returncode == 0, (proc.stderr or proc.stdout)[-500:]
