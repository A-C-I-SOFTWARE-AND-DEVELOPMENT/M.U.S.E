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

from hermes_cli.local_models.catalog import OpenWeightCatalog, OpenWeightModel
from hermes_cli.local_models.hardware_probe import HardwareProfile, probe
from hermes_cli.local_models.server_adapters import LaunchPlan, get_adapter


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
    # Post-download health: did the pulled tag appear in ``ollama list``?
    # ``None`` ⇒ not checked (non-Ollama runtime, or check unavailable).
    health_verified: Optional[bool] = None
    health_detail: str = ""


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
    verify_health: bool = False,
    ollama_list_runner=None,
) -> list[DownloadOutcome]:
    """Execute the download steps in ``plan`` — only if downloads are accepted.

    ``runner`` is injectable for tests (defaults to ``subprocess.run``). Without
    ``accept_downloads`` this is a guaranteed no-op that reports the refusal.

    When ``verify_health`` is set, each successful Ollama pull is confirmed with
    a post-download health check (``ollama list`` must show the pulled tag); the
    verdict is appended to the outcome's ``health_verified`` / ``health_detail``
    fields. The check is best-effort and never flips ``ok`` — it is advisory.
    ``ollama_list_runner`` is injectable so this stays hermetic in tests.
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
        outcome = DownloadOutcome(
            model=item.model.name, attempted=True, ok=ok, detail=detail, command=cmd
        )
        # Post-download health: confirm the pulled tag actually landed.
        if verify_health and ok and item.runtime == "ollama":
            tag = _pull_tag(cmd)
            if tag:
                post_download_health_check(
                    outcome, tag, ollama_list_runner=ollama_list_runner
                )
        outcomes.append(outcome)
    return outcomes


def _pull_tag(pull_command: tuple[str, ...]) -> Optional[str]:
    """Extract the model tag from an ``ollama pull <tag>`` command, if present."""
    if len(pull_command) >= 3 and pull_command[:2] == ("ollama", "pull"):
        return pull_command[2]
    return pull_command[-1] if pull_command else None


def post_download_health_check(
    outcome: DownloadOutcome,
    tag: str,
    *,
    ollama_list_runner=None,
) -> DownloadOutcome:
    """Confirm a freshly pulled Ollama ``tag`` appears in ``ollama list``.

    Mutates and returns ``outcome`` with its ``health_verified`` /
    ``health_detail`` fields set. Best-effort and advisory: a missing/unreadable
    ``ollama list`` leaves ``health_verified=None`` (not checked) rather than
    marking a successful download as failed. ``ollama_list_runner`` is injectable
    (returns ``ollama list`` stdout) so tests never shell out.
    """
    run = ollama_list_runner or _default_ollama_list_runner
    try:
        listing = run() or ""
    except Exception as exc:  # pragma: no cover - defensive
        outcome.health_verified = None
        outcome.health_detail = f"health check unavailable: {exc}"
        return outcome
    if not listing.strip():
        outcome.health_verified = None
        outcome.health_detail = "ollama list returned nothing — health not verified"
        return outcome
    if _tag_in_listing(tag, listing):
        outcome.health_verified = True
        outcome.health_detail = f"{tag} present in `ollama list`"
    else:
        outcome.health_verified = False
        outcome.health_detail = (
            f"{tag} pulled but NOT shown by `ollama list` — verify with: ollama list"
        )
    return outcome


def _tag_in_listing(tag: str, listing: str) -> bool:
    """True if ``tag`` matches a model name in ``ollama list`` output.

    Ollama defaults a bare ``name`` to ``name:latest`` in its listing, so a
    pull of ``gemma4`` is matched against ``gemma4:latest`` too. Matching is on
    the NAME column (first whitespace-delimited token of each row).
    """
    candidates = {tag.strip()}
    if ":" not in tag:
        candidates.add(f"{tag.strip()}:latest")
    listed: set[str] = set()
    for line in listing.splitlines():
        line = line.strip()
        if not line or line.upper().startswith("NAME"):
            continue
        first = line.split()[0] if line.split() else ""
        if first:
            listed.add(first)
    return bool(candidates & listed)


def _default_ollama_list_runner() -> str:  # pragma: no cover - real shell-out
    """Run ``ollama list`` once (read-only) and return stdout, or ``""``."""
    import shutil

    if shutil.which("ollama") is None:
        return ""
    try:
        proc = subprocess.run(
            ["ollama", "list"], capture_output=True, text=True, timeout=6.0
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    if proc.returncode != 0:
        return ""
    return proc.stdout or ""


def _default_runner(
    cmd,
) -> tuple[bool, str]:  # pragma: no cover - exercised only on real downloads
    try:
        proc = subprocess.run(list(cmd), capture_output=True, text=True, timeout=3600)
    except (OSError, subprocess.SubprocessError) as exc:
        return False, str(exc)
    return proc.returncode == 0, (proc.stderr or proc.stdout)[-500:]
