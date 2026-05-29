"""Tests for the free-first model bootstrap (hermes_cli.jarvis_prime.model_bootstrap).

Hermetic: no network, no real ``shutil.which``, no model pulls. The
detector (``which``), environment, and pull runner are all injected so
the tests are deterministic on any host.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from hermes_cli.jarvis_prime import model_bootstrap as mb


@pytest.fixture()
def hermes_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    return tmp_path


def _which_none(_binary: str):
    return None


def _which_only(*available: str):
    def which(binary: str):
        return f"/usr/bin/{binary}" if binary in available else None

    return which


# ---------------------------------------------------------------------------
# dry-run writes nothing
# ---------------------------------------------------------------------------


def test_dry_run_produces_no_writes(hermes_home: Path) -> None:
    result = mb.bootstrap(
        dry_run=True, which=_which_none, env={}, record_memory=False
    )
    assert result.ok is True
    assert result.config_written is False
    assert not mb.config_path().exists()


def test_apply_writes_policy_with_secure_perms(hermes_home: Path) -> None:
    result = mb.bootstrap(
        dry_run=False, which=_which_none, env={}, record_memory=False
    )
    assert result.config_written is True
    path = mb.config_path()
    assert path.is_file()
    policy = mb.load_policy()
    assert policy is not None
    assert policy["free_first"] is True
    assert policy["route_order"][0] == "local_oss"


# ---------------------------------------------------------------------------
# --no-pull never invokes the pull command
# ---------------------------------------------------------------------------


def test_no_pull_does_not_call_pull_runner(hermes_home: Path) -> None:
    calls: list[str] = []

    def runner(model: str):
        calls.append(model)
        return True, "pulled"

    mb.bootstrap(
        dry_run=False,
        no_pull=True,
        which=_which_only("ollama"),
        env={},
        pull_runner=runner,
        record_memory=False,
    )
    assert calls == []


def test_dry_run_does_not_call_pull_runner_even_with_ollama(hermes_home: Path) -> None:
    calls: list[str] = []

    def runner(model: str):
        calls.append(model)
        return True, "pulled"

    mb.bootstrap(
        dry_run=True,
        which=_which_only("ollama"),
        env={},
        pull_runner=runner,
        record_memory=False,
    )
    assert calls == []


def test_force_pulls_via_runner_when_ollama_present(hermes_home: Path) -> None:
    calls: list[str] = []

    def runner(model: str):
        calls.append(model)
        return True, "pulled"

    result = mb.bootstrap(
        dry_run=False,
        force=True,
        which=_which_only("ollama"),
        env={},
        pull_runner=runner,
        record_memory=False,
    )
    assert calls, "expected --force to pull at least one default model"
    assert any(p.pulled for p in result.pulls)


# ---------------------------------------------------------------------------
# missing Ollama is a warning, not a failure
# ---------------------------------------------------------------------------


def test_missing_ollama_is_warning_not_failure(hermes_home: Path) -> None:
    result = mb.bootstrap(which=_which_none, env={}, record_memory=False)
    assert result.ok is True
    assert any("local model runtime" in w.lower() for w in result.warnings)
    assert result.config["routes"]["local_oss"]["enabled"] is False


# ---------------------------------------------------------------------------
# detected Ollama produces a local_oss route
# ---------------------------------------------------------------------------


def test_detected_ollama_enables_local_oss_route(hermes_home: Path) -> None:
    result = mb.bootstrap(which=_which_only("ollama"), env={}, record_memory=False)
    route = result.config["routes"]["local_oss"]
    assert route["enabled"] is True
    assert "ollama" in route["runtimes"]


# ---------------------------------------------------------------------------
# paid routes disabled unless explicitly configured
# ---------------------------------------------------------------------------


def test_paid_route_disabled_even_with_paid_key_present(hermes_home: Path) -> None:
    # A paid key present but no explicit opt-in must NOT enable paid routing.
    env = {"ANTHROPIC_API_KEY": "sk-ant-doesnotmatter"}
    result = mb.bootstrap(which=_which_none, env=env, record_memory=False)
    paid = result.config["routes"]["paid_api_explicit_only"]
    assert paid["enabled"] is False
    assert "anthropic" in result.config["paid"]["providers_detected"]


def test_paid_route_enabled_only_with_explicit_opt_in(hermes_home: Path) -> None:
    env = {"ANTHROPIC_API_KEY": "sk-ant-x", mb.PAID_OPT_IN_ENV: "1"}
    result = mb.bootstrap(which=_which_none, env=env, record_memory=False)
    assert result.config["routes"]["paid_api_explicit_only"]["enabled"] is True


def test_hosted_oss_detected_only_when_key_present(hermes_home: Path) -> None:
    env = {"OPENROUTER_API_KEY": "or-xxx"}
    result = mb.bootstrap(which=_which_none, env=env, record_memory=False)
    hosted = result.config["routes"]["hosted_free_or_user_configured_oss"]
    assert hosted["enabled"] is True
    assert "openrouter" in hosted["providers"]


# ---------------------------------------------------------------------------
# no secrets ever land in the written config
# ---------------------------------------------------------------------------


def test_secret_values_never_written_to_config(hermes_home: Path) -> None:
    secret = "sk-or-v1-THISISASECRETVALUE1234567890"
    env = {"OPENROUTER_API_KEY": secret}
    result = mb.bootstrap(which=_which_none, env=env, record_memory=False)
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


def test_local_only_disables_non_local_routes(hermes_home: Path) -> None:
    env = {"OPENROUTER_API_KEY": "or-xxx", mb.PAID_OPT_IN_ENV: "1"}
    result = mb.bootstrap(
        which=_which_only("ollama"), env=env, local_only=True, record_memory=False
    )
    routes = result.config["routes"]
    assert routes["local_oss"]["enabled"] is True
    assert routes["hosted_free_or_user_configured_oss"]["enabled"] is False
    assert routes["claude_code_worker"]["enabled"] is False
    assert routes["paid_api_explicit_only"]["enabled"] is False


# ---------------------------------------------------------------------------
# local defaults come from the catalog
# ---------------------------------------------------------------------------


def test_local_defaults_cover_reasoning_coding_embeddings() -> None:
    purposes = {d.purpose for d in mb.compute_local_defaults()}
    assert {"local_reasoning", "local_coding", "embeddings"} <= purposes


# ---------------------------------------------------------------------------
# bootstrap records the durable launch-policy memory
# ---------------------------------------------------------------------------


def test_bootstrap_records_launch_policy_memory(hermes_home: Path) -> None:
    from hermes_cli.jarvis_prime.memory import MemoryStore

    mb.bootstrap(which=_which_none, env={}, record_memory=True)
    store = MemoryStore()
    hits = store.recollect("jarvis_launch_model_policy", limit=5)
    matches = [r for r in hits if r.key == "jarvis_launch_model_policy"]
    assert matches, "expected a durable launch-policy memory record"
    assert matches[0].durability == "durable"
    assert "free-first" in matches[0].value
