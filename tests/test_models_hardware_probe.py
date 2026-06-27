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


# ---------------------------------------------------------------------------
# gpu_available — distinguishes "nvidia-smi worked" from "VRAM > 0".
# ---------------------------------------------------------------------------
def test_gpu_available_defaults_false():
    # Backward-compat positional construction (no gpu_available arg) is CPU-only.
    p = HardwareProfile("Linux", "x86_64", 8, 32.0, None, 100.0)
    assert p.gpu_available is False
    assert p.to_dict()["gpu_available"] is False


def test_gpu_available_true_even_when_vram_unreadable():
    # Driver is up (nvidia-smi ran) but VRAM read failed -> gpu_available True,
    # vram_gb None. This is the "driver-down momentarily" case that vram_gb
    # alone would conflate with "no GPU".
    p = HardwareProfile(
        "Linux", "x86_64", 24, 31.0, None, 500.0, "RTX 5070", gpu_available=True
    )
    assert p.gpu_available is True
    assert p.vram_gb is None


def test_gpu_available_independent_of_vram_amount():
    present = HardwareProfile(
        "Linux", "x86_64", 24, 31.0, 8.0, 500.0, "RTX 5070", gpu_available=True
    )
    assert present.gpu_available is True
    absent = HardwareProfile("Linux", "x86_64", 24, 31.0, None, 500.0)
    assert absent.gpu_available is False


# ---------------------------------------------------------------------------
# vram_safe_context_limit — KV-cache-driven, rounded to 2048, clamped 4K-32K.
# ---------------------------------------------------------------------------
def _gpu(vram_gb: float, ram_gb: float = 31.0) -> HardwareProfile:
    return HardwareProfile(
        "Linux", "x86_64", 24, ram_gb, vram_gb, 500.0, "GPU", gpu_available=True
    )


def test_ctx_limit_is_stepped_and_clamped():
    # Every result is a multiple of 2048 inside [4096, 32768].
    for vram, size in ((8.0, 5.5), (8.0, 18.5), (24.0, 5.5), (16.0, 18.5)):
        ctx = _gpu(vram).vram_safe_context_limit(size)
        assert 4096 <= ctx <= 32768
        assert ctx % 2048 == 0


def test_ctx_limit_8gb_9b_lands_16k_to_24k():
    # 8GB card + ~9B q4_k_m (~5.5GB on disk) should give a generous-but-capped
    # window in the 16-24K band (per the verified capability matrix).
    ctx = _gpu(8.0).vram_safe_context_limit(5.5)
    assert 16384 <= ctx <= 24576


def test_ctx_limit_8gb_12b_within_band():
    # ~12B q4_k_m (~7.3GB) on 8GB stays in the same 16-24K envelope.
    ctx = _gpu(8.0).vram_safe_context_limit(7.3)
    assert 14336 <= ctx <= 24576


def test_ctx_limit_8gb_30b_lands_6k_to_8k():
    # 8GB card + ~30B q4_k_m (~18.5GB on disk, partial offload) -> ~6-8K.
    ctx = _gpu(8.0).vram_safe_context_limit(18.5)
    assert 6144 <= ctx <= 8192


def test_ctx_limit_24gb_not_aggressively_capped():
    # A 24GB card running a 9B should not be aggressively capped — it hits the
    # 32768 ceiling.
    assert _gpu(24.0).vram_safe_context_limit(5.5) == 32768


def test_ctx_limit_larger_model_gets_less_context():
    card = _gpu(8.0)
    assert card.vram_safe_context_limit(5.5) > card.vram_safe_context_limit(18.5)


def test_ctx_limit_cheaper_kv_quant_buys_more_context():
    card = _gpu(8.0)
    q8 = card.vram_safe_context_limit(18.5, kv_quant="q8_0")
    q4 = card.vram_safe_context_limit(18.5, kv_quant="q4_0")
    # q4 KV is ~half the bytes/token, so it should fit more (or equal at clamp).
    assert q4 >= q8


def test_ctx_limit_cpu_only_is_ram_bounded():
    # gpu_available False -> ignore (absent) VRAM, bound by RAM instead.
    cpu = HardwareProfile("Linux", "x86_64", 24, 31.0, None, 500.0)
    assert cpu.gpu_available is False
    ctx = cpu.vram_safe_context_limit(5.5)
    assert 4096 <= ctx <= 32768
    assert ctx % 2048 == 0
    # More RAM -> at least as much context (monotonic, both clamped).
    small = HardwareProfile("Linux", "x86_64", 8, 8.0, None, 100.0)
    big = HardwareProfile("Linux", "x86_64", 64, 128.0, None, 2000.0)
    assert big.vram_safe_context_limit(5.5) >= small.vram_safe_context_limit(5.5)


def test_ctx_limit_cpu_only_low_ram_hits_floor():
    tiny = HardwareProfile("Android", "aarch64", 8, 4.0, None, 16.0)
    assert tiny.vram_safe_context_limit(5.5) == 4096


def test_ctx_limit_zero_vram_with_gpu_flag_falls_to_floor():
    # Pathological: gpu_available True but accelerator budget below overhead.
    starved = HardwareProfile(
        "Linux", "x86_64", 24, 0.0, 1.0, 500.0, "GPU", gpu_available=True
    )
    assert starved.vram_safe_context_limit(5.5) == 4096
