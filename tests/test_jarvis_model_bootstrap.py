"""Tests for the unified free-first model bootstrap
(hermes_cli.jarvis_prime.model_bootstrap).

Hermetic: no network, no real ``shutil.which``, no model downloads, no
real hardware probe. The runtime detector (``which``), environment,
hardware profile, and download runner are all injected so the tests are
deterministic on any host. The bootstrap unifies provider routing with
the local model layer (``hermes_cli.local_models``).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hermes_cli.jarvis_prime import model_bootstrap as mb
from hermes_cli.local_models.hardware_probe import HardwareProfile


@pytest.fixture()
def hermes_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    return tmp_path


@pytest.fixture()
def fake_hw() -> HardwareProfile:
    # A deterministic mid-range box so the local plan is reproducible.
    return HardwareProfile(
        os_name="Linux",
        arch="x86_64",
        cpu_cores=8,
        ram_gb=16.0,
        vram_gb=0.0,
        free_disk_gb=200.0,
        gpu_name=None,
    )


def _which_none(_binary: str):
    return None


def _which_only(*available: str):
    def which(binary: str):
        return f"/usr/bin/{binary}" if binary in available else None

    return which


# ---------------------------------------------------------------------------
# dry-run writes nothing
# ---------------------------------------------------------------------------


def test_dry_run_produces_no_writes(hermes_home: Path, fake_hw: HardwareProfile) -> None:
    result = mb.bootstrap(
        dry_run=True, which=_which_none, env={}, hardware=fake_hw, record_memory=False
    )
    assert result.ok is True
    assert result.config_written is False
    assert not mb.config_path().exists()


def test_apply_writes_policy_with_routes_and_local(
    hermes_home: Path, fake_hw: HardwareProfile
) -> None:
    result = mb.bootstrap(
        dry_run=False, which=_which_none, env={}, hardware=fake_hw, record_memory=False
    )
    assert result.config_written is True
    policy = mb.load_policy()
    assert policy is not None
    assert policy["free_first"] is True
    assert policy["route_order"][0] == "local_oss"
    # Unified: the local model layer is folded into the policy.
    assert "local" in policy
    assert policy["local"]["hardware"]["tier"]  # hardware profile present
    assert policy["local"]["plan"] is not None  # hardware-aware plan present


# ---------------------------------------------------------------------------
# downloads are consent-gated (the load-bearing safety guarantee)
# ---------------------------------------------------------------------------


def test_no_pull_does_not_call_download_runner(
    hermes_home: Path, fake_hw: HardwareProfile
) -> None:
    calls: list = []

    def runner(cmd):
        calls.append(cmd)
        return True, "pulled"

    result = mb.bootstrap(
        dry_run=False,
        no_pull=True,
        force=True,  # even with force, --no-pull wins
        which=_which_only("ollama"),
        env={},
        hardware=fake_hw,
        pull_runner=runner,
        record_memory=False,
    )
    assert calls == []
    assert result.config["local"]["downloads_accepted"] is False


def test_dry_run_does_not_call_download_runner(
    hermes_home: Path, fake_hw: HardwareProfile
) -> None:
    calls: list = []

    def runner(cmd):
        calls.append(cmd)
        return True, "pulled"

    result = mb.bootstrap(
        dry_run=True,
        force=True,
        which=_which_only("ollama"),
        env={},
        hardware=fake_hw,
        pull_runner=runner,
        record_memory=False,
    )
    assert calls == []
    assert result.config["local"]["downloads_accepted"] is False


def test_force_marks_downloads_accepted(
    hermes_home: Path, fake_hw: HardwareProfile
) -> None:
    # force + not dry-run + not no-pull => downloads are consented to.
    result = mb.bootstrap(
        dry_run=False,
        force=True,
        which=_which_none,
        env={},
        hardware=fake_hw,
        record_memory=False,
    )
    assert result.config["local"]["downloads_accepted"] is True
    # No real runtime here, so nothing is actually pulled — that's fine.
    assert all(not o.get("attempted") for o in result.download_outcomes)


# ---------------------------------------------------------------------------
# missing Ollama is a warning, not a failure
# ---------------------------------------------------------------------------


def test_missing_runtime_is_warning_not_failure(
    hermes_home: Path, fake_hw: HardwareProfile
) -> None:
    result = mb.bootstrap(
        which=_which_none, env={}, hardware=fake_hw, record_memory=False
    )
    assert result.ok is True
    assert any("local model runtime" in w.lower() for w in result.warnings)
    assert result.config["routes"]["local_oss"]["enabled"] is False


# ---------------------------------------------------------------------------
# detected Ollama produces a local_oss route
# ---------------------------------------------------------------------------


def test_detected_ollama_enables_local_oss_route(
    hermes_home: Path, fake_hw: HardwareProfile
) -> None:
    result = mb.bootstrap(
        which=_which_only("ollama"), env={}, hardware=fake_hw, record_memory=False
    )
    route = result.config["routes"]["local_oss"]
    assert route["enabled"] is True
    assert "ollama" in route["runtimes"]


def test_local_oss_route_lists_recommended_local_models(
    hermes_home: Path, fake_hw: HardwareProfile
) -> None:
    # Unification: the local_oss route surfaces concrete hardware-fit models
    # from the local model layer (not just a runtime list).
    result = mb.bootstrap(
        which=_which_only("ollama"), env={}, hardware=fake_hw, record_memory=False
    )
    route = result.config["routes"]["local_oss"]
    assert "recommended_local_models" in route
    assert isinstance(route["recommended_local_models"], list)
    assert route["recommended_local_models"], "expected hardware-fit local models"


# ---------------------------------------------------------------------------
# paid routes disabled unless explicitly configured
# ---------------------------------------------------------------------------


def test_paid_route_disabled_even_with_paid_key_present(
    hermes_home: Path, fake_hw: HardwareProfile
) -> None:
    env = {"ANTHROPIC_API_KEY": "sk-ant-doesnotmatter"}
    result = mb.bootstrap(
        which=_which_none, env=env, hardware=fake_hw, record_memory=False
    )
    paid = result.config["routes"]["paid_api_explicit_only"]
    assert paid["enabled"] is False
    assert "anthropic" in result.config["paid"]["providers_detected"]


def test_paid_route_enabled_only_with_explicit_opt_in(
    hermes_home: Path, fake_hw: HardwareProfile
) -> None:
    env = {"ANTHROPIC_API_KEY": "sk-ant-x", mb.PAID_OPT_IN_ENV: "1"}
    result = mb.bootstrap(
        which=_which_none, env=env, hardware=fake_hw, record_memory=False
    )
    assert result.config["routes"]["paid_api_explicit_only"]["enabled"] is True


def test_hosted_oss_detected_only_when_key_present(
    hermes_home: Path, fake_hw: HardwareProfile
) -> None:
    env = {"OPENROUTER_API_KEY": "or-xxx"}
    result = mb.bootstrap(
        which=_which_none, env=env, hardware=fake_hw, record_memory=False
    )
    hosted = result.config["routes"]["hosted_free_or_user_configured_oss"]
    assert hosted["enabled"] is True
    assert "openrouter" in hosted["providers"]


# ---------------------------------------------------------------------------
# no secrets ever land in the written config
# ---------------------------------------------------------------------------


def test_secret_values_never_written_to_config(
    hermes_home: Path, fake_hw: HardwareProfile
) -> None:
    secret = "sk-or-v1-THISISASECRETVALUE1234567890"
    env = {"OPENROUTER_API_KEY": secret}
    result = mb.bootstrap(
        which=_which_none, env=env, hardware=fake_hw, record_memory=False
    )
    raw = mb.config_path().read_text(encoding="utf-8")
    assert secret not in raw
    assert secret not in repr(result.to_dict())


# ---------------------------------------------------------------------------
# free-first ordering invariant
# ---------------------------------------------------------------------------


def test_route_order_is_free_first() -> None:
    assert mb.ROUTE_ORDER == (
        "local_oss",
        "hosted_free_or_user_configured_oss",
        "claude_code_worker",
        "codex_worker",
        "paid_api_explicit_only",
    )


def test_local_only_disables_non_local_routes(
    hermes_home: Path, fake_hw: HardwareProfile
) -> None:
    env = {"OPENROUTER_API_KEY": "or-xxx", mb.PAID_OPT_IN_ENV: "1"}
    result = mb.bootstrap(
        which=_which_only("ollama"),
        env=env,
        local_only=True,
        hardware=fake_hw,
        record_memory=False,
    )
    routes = result.config["routes"]
    assert routes["local_oss"]["enabled"] is True
    assert routes["hosted_free_or_user_configured_oss"]["enabled"] is False
    assert routes["claude_code_worker"]["enabled"] is False
    assert routes["paid_api_explicit_only"]["enabled"] is False


# ---------------------------------------------------------------------------
# local defaults come from the catalog (route preferences)
# ---------------------------------------------------------------------------


def test_local_defaults_cover_reasoning_coding_embeddings() -> None:
    purposes = {d.purpose for d in mb.compute_local_defaults()}
    assert {"local_reasoning", "local_coding", "embeddings"} <= purposes


# ---------------------------------------------------------------------------
# local model layer integration (hardware-aware plan)
# ---------------------------------------------------------------------------


def test_hardware_plan_present_in_policy(
    hermes_home: Path, fake_hw: HardwareProfile
) -> None:
    result = mb.bootstrap(
        which=_which_none, env={}, hardware=fake_hw, record_memory=False
    )
    local = result.config["local"]
    assert local["hardware"]["tier"]  # tier derived from injected hardware
    assert local["plan"] is not None
    assert "items" in local["plan"]


def test_probe_hardware_accepts_injected_profile(fake_hw: HardwareProfile) -> None:
    assert mb.probe_hardware(fake_hw) is fake_hw


# ---------------------------------------------------------------------------
# bootstrap records the durable launch-policy memory
# ---------------------------------------------------------------------------


def test_bootstrap_records_launch_policy_memory(
    hermes_home: Path, fake_hw: HardwareProfile
) -> None:
    from hermes_cli.jarvis_prime.memory import MemoryStore

    mb.bootstrap(which=_which_none, env={}, hardware=fake_hw, record_memory=True)
    store = MemoryStore()
    hits = store.recollect("jarvis_launch_model_policy", limit=5)
    matches = [r for r in hits if r.key == "jarvis_launch_model_policy"]
    assert matches, "expected a durable launch-policy memory record"
    assert matches[0].durability == "durable"
    assert "free-first" in matches[0].value
