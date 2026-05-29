"""Tests for the stdlib hardware probe + server adapters."""

from __future__ import annotations

from hermes_cli.local_models.hardware_probe import HardwareProfile, probe
from hermes_cli.local_models.server_adapters import (
    SUPPORTED_RUNTIMES,
    get_adapter,
    installed_runtimes,
)


def test_probe_returns_profile_without_crashing():
    profile = probe()
    assert isinstance(profile, HardwareProfile)
    assert profile.os_name
    assert profile.tier in {"laptop", "desktop", "workstation", "server"}
    d = profile.to_dict()
    assert "tier" in d and "accelerator_gb" in d


def test_tier_thresholds():
    laptop = HardwareProfile("Linux", "x86_64", 4, 8.0, None, 100.0)
    assert laptop.tier == "laptop"
    workstation = HardwareProfile("Linux", "x86_64", 16, 64.0, 24.0, 500.0)
    assert workstation.tier == "workstation"
    server = HardwareProfile("Linux", "x86_64", 64, 256.0, 80.0, 2000.0)
    assert server.tier == "server"


def test_accelerator_prefers_vram():
    p = HardwareProfile("Linux", "x86_64", 8, 32.0, 16.0, 100.0)
    assert p.accelerator_gb == 16.0
    cpu_only = HardwareProfile("Linux", "x86_64", 8, 32.0, None, 100.0)
    assert cpu_only.accelerator_gb == 32.0


def test_server_adapters_build_launch_plans():
    for runtime in SUPPORTED_RUNTIMES:
        adapter = get_adapter(runtime)
        plan = adapter.launch_plan("some-model")
        assert plan.runtime == runtime
        assert plan.base_url.startswith("http")


def test_ollama_plan_has_pull_step():
    plan = get_adapter("ollama").launch_plan("qwen2.5-coder:7b")
    assert plan.pull_command == ("ollama", "pull", "qwen2.5-coder:7b")


def test_unknown_runtime_raises():
    import pytest

    with pytest.raises(KeyError):
        get_adapter("not-a-runtime")


def test_installed_runtimes_returns_list():
    # openai-compatible is always "installed" (bring-your-own endpoint).
    assert "openai-compatible" in installed_runtimes()
