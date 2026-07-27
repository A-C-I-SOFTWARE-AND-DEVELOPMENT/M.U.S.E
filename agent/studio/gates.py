"""Cost, hardware, license, and commercial-use gates for AAA production."""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping, Sequence


@dataclass(frozen=True)
class CostGate:
    max_estimated_cost_usd: float
    current_cost_usd: float = 0.0

    def check(self, additional_cost: float = 0.0) -> tuple[bool, str]:
        total = self.current_cost_usd + additional_cost
        if total > self.max_estimated_cost_usd:
            return (
                False,
                f"cost gate blocked: ${total:.2f} exceeds budget ${self.max_estimated_cost_usd:.2f}",
            )
        return True, ""


@dataclass(frozen=True)
class HardwareGate:
    min_vram_gb: float
    min_system_ram_gb: float
    requires_gpu: bool
    requires_ue5: bool
    detected_vram_gb: float = 0.0
    detected_ram_gb: float = 0.0
    ue5_available: bool = False

    def check(self) -> tuple[bool, str]:
        failures: list[str] = []
        if self.requires_gpu and self.detected_vram_gb < self.min_vram_gb:
            failures.append(
                f"GPU VRAM {self.detected_vram_gb:.1f}GB < required {self.min_vram_gb:.1f}GB"
            )
        if self.detected_ram_gb < self.min_system_ram_gb:
            failures.append(
                f"System RAM {self.detected_ram_gb:.1f}GB < required {self.min_system_ram_gb:.1f}GB"
            )
        if self.requires_ue5 and not self.ue5_available:
            failures.append("Unreal Engine 5 not discovered on this machine")
        if failures:
            return False, "; ".join(failures)
        return True, ""


@dataclass(frozen=True)
class LicenseGate:
    required_licenses: tuple[str, ...]
    asset_licenses: Mapping[str, str]
    commercial_use_required: bool

    def check(self) -> tuple[bool, tuple[str, ...]]:
        failures: list[str] = []
        for asset_id, license_name in self.asset_licenses.items():
            if not license_name.strip():
                failures.append(f"{asset_id}:missing_license")
            elif license_name.startswith("stub-"):
                failures.append(f"{asset_id}:stub_license_non_authoritative")
            elif self.commercial_use_required and license_name in ("unknown", "editorial", ""):
                failures.append(f"{asset_id}:non_commercial_license")
        for req in self.required_licenses:
            if req not in self.asset_licenses.values():
                failures.append(f"missing_required_license:{req}")
        return (not failures, tuple(failures))


@dataclass(frozen=True)
class OwnerAuthorizationGate:
    required_for: tuple[str, ...]
    authorized_actions: frozenset[str]

    def check(self, action: str) -> tuple[bool, str]:
        if action in self.required_for and action not in self.authorized_actions:
            return (
                False,
                f"owner authorization required for {action!r}; "
                "reply exactly: Yes, with authorization.",
            )
        return True, ""


@dataclass(frozen=True)
class GateResult:
    passed: bool
    gate: str
    reason: str
    failures: tuple[str, ...] = ()


def evaluate_all_gates(
    *,
    cost: CostGate,
    hardware: HardwareGate,
    license_gate: LicenseGate,
    owner: OwnerAuthorizationGate,
    pending_action: str = "",
    additional_cost: float = 0.0,
) -> tuple[GateResult, ...]:
    results: list[GateResult] = []
    ok, reason = cost.check(additional_cost)
    results.append(GateResult(ok, "cost", reason))
    ok, reason = hardware.check()
    results.append(GateResult(ok, "hardware", reason))
    ok, failures = license_gate.check()
    results.append(GateResult(ok, "license", "; ".join(failures) if failures else "", failures))
    if pending_action:
        ok, reason = owner.check(pending_action)
        results.append(GateResult(ok, "owner_authorization", reason))
    return tuple(results)


def gates_passed(results: Sequence[GateResult]) -> bool:
    return all(r.passed for r in results)


def detect_hardware() -> tuple[float, float]:
    vram_gb = 0.0
    ram_gb = 0.0
    try:
        import psutil
        ram_gb = psutil.virtual_memory().total / (1024 ** 3)
    except ImportError:
        ram_gb = float(os.environ.get("HERMES_DETECTED_RAM_GB", "0"))
    vram_gb = float(os.environ.get("HERMES_DETECTED_VRAM_GB", "0"))
    return vram_gb, ram_gb


def build_gates_for_profile(
    profile_name: str,
    *,
    current_cost_usd: float = 0.0,
    asset_licenses: Mapping[str, str] | None = None,
    ue5_available: bool = False,
) -> tuple[CostGate, HardwareGate, LicenseGate, OwnerAuthorizationGate]:
    from agent.studio.quality_profiles import load_quality_profile

    profile = load_quality_profile(profile_name)
    max_cost = {
        "previz": 0.0,
        "high_fidelity": 500.0,
        "aaa_benchmark": 2000.0,
    }.get(profile.name, 100.0)
    vram_gb, ram_gb = detect_hardware()
    cost = CostGate(max_estimated_cost_usd=max_cost, current_cost_usd=current_cost_usd)
    hardware = HardwareGate(
        min_vram_gb=4.0 if profile.name == "previz" else 8.0,
        min_system_ram_gb=16.0 if profile.name == "previz" else 32.0,
        requires_gpu=profile.requires_ue_render_evidence,
        requires_ue5=profile.requires_ue_render_evidence,
        detected_vram_gb=vram_gb,
        detected_ram_gb=ram_gb,
        ue5_available=ue5_available,
    )
    license_gate = LicenseGate(
        required_licenses=("original",),
        asset_licenses=dict(asset_licenses or {}),
        commercial_use_required=profile.requires_ue_render_evidence,
    )
    owner = OwnerAuthorizationGate(
        required_for=("paid_api_spend", "engine_build", "commercial_publish"),
        authorized_actions=frozenset(
            item.strip()
            for item in os.environ.get("MUSE_AUTHORIZED_ACTIONS", "").split(",")
            if item.strip()
        ),
    )
    return cost, hardware, license_gate, owner


__all__ = [
    "CostGate",
    "GateResult",
    "HardwareGate",
    "LicenseGate",
    "OwnerAuthorizationGate",
    "build_gates_for_profile",
    "detect_hardware",
    "evaluate_all_gates",
    "gates_passed",
]
