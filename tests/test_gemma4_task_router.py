"""Gemma 4 — task-router lane tests (data-driven, scorecard-aware)."""

from __future__ import annotations

import pytest

from muse_cli.jarvis_prime import task_router as tr


def _policy_with_gemma_local() -> dict:
    return {
        "route_order": list(tr.ROUTE_TIERS),
        "routes": {
            "local_oss": {
                "enabled": True,
                "recommended_local_models": ["gemma4-e4b", "qwen2.5-coder-7b"],
                "runtimes": ["ollama"],
            },
            "hosted_free_or_user_configured_oss": {"enabled": False, "providers": []},
            "claude_code_worker": {"enabled": True},
            "codex_worker": {"enabled": True},
            "paid_api_explicit_only": {"enabled": False, "providers_detected": []},
        },
        "paid": {"enabled": False},
        "local_defaults": [],
    }


_NO_OVERRIDES = {"version": 1, "paid_enabled": None, "task_overrides": {}}


def test_is_gemma_recognizes_variants() -> None:
    assert tr.is_gemma("gemma4:e4b")
    assert tr.is_gemma("ollama-local/gemma4-e2b")
    assert tr.is_gemma("gemma4-26b-a4b")
    assert not tr.is_gemma("claude")
    assert not tr.is_gemma("qwen2.5-coder-7b")
    assert not tr.is_gemma(None)


@pytest.mark.parametrize(
    "tc",
    [
        tr.TaskClass.MEMORY_CURATOR,
        tr.TaskClass.MOBILE_CHAT,
        tr.TaskClass.VOICE_REPLY,
        tr.TaskClass.SUMMARIZATION,
    ],
)
def test_local_lanes_pick_gemma_when_available(tc) -> None:
    d = tr.route_for_task(
        tc, policy=_policy_with_gemma_local(), book=None, overrides=_NO_OVERRIDES
    )
    assert tr.is_gemma(d.chosen)
    assert d.route_tier == "local_oss"


def test_coding_lanes_keep_claude_and_codex_without_promotion() -> None:
    policy = _policy_with_gemma_local()
    build = tr.route_for_task(
        tr.TaskClass.CODING_BUILD, policy=policy, book=None, overrides=_NO_OVERRIDES
    )
    assert build.chosen == "claude"
    assert not tr.is_gemma(build.chosen)

    review = tr.route_for_task(
        tr.TaskClass.CODING_REVIEW, policy=policy, book=None, overrides=_NO_OVERRIDES
    )
    assert review.chosen == "codex"
    assert not tr.is_gemma(review.chosen)


def _policy_with_both_gemma_variants() -> dict:
    """An 8 GB box: both small Gemma variants are hardware-fit and installed."""
    pol = _policy_with_gemma_local()
    pol["routes"]["local_oss"]["recommended_local_models"] = [
        "gemma4-e2b",
        "gemma4-e4b",
    ]
    return pol


@pytest.mark.parametrize(
    "tc",
    [
        tr.TaskClass.MOBILE_CHAT,
        tr.TaskClass.VOICE_REPLY,
        tr.TaskClass.SUMMARIZATION,
        tr.TaskClass.MEMORY_CURATOR,
    ],
)
def test_fast_lanes_prefer_e2b(tc) -> None:
    """Fast daily lanes route to the small E2B when both variants are present."""
    d = tr.route_for_task(
        tc, policy=_policy_with_both_gemma_variants(), book=None, overrides=_NO_OVERRIDES
    )
    assert d.chosen == "gemma4-e2b"
    assert d.route_tier == "local_oss"


@pytest.mark.parametrize(
    "tc",
    [
        tr.TaskClass.CODING_PLAN,
        tr.TaskClass.CODING_BUILD,
        tr.TaskClass.CODING_REVIEW,
        tr.TaskClass.TEST_DEBUG,
    ],
)
def test_coding_lanes_prefer_e4b_locally(tc) -> None:
    """When the local lane is reached (no workers), coding/planning use E4B."""
    pol = _policy_with_both_gemma_variants()
    pol["routes"]["claude_code_worker"]["enabled"] = False
    pol["routes"]["codex_worker"]["enabled"] = False
    d = tr.route_for_task(tc, policy=pol, book=None, overrides=_NO_OVERRIDES)
    assert d.chosen == "gemma4-e4b"
    assert d.route_tier == "local_oss"


def test_e4b_load_failure_demotes_coding_to_e2b(tmp_path, monkeypatch) -> None:
    """The load-gate: a recorded E4B smoke failure falls coding back to E2B."""
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    from muse_cli.jarvis_prime import gemma_load_status as gls

    pol = _policy_with_both_gemma_variants()
    pol["routes"]["claude_code_worker"]["enabled"] = False
    pol["routes"]["codex_worker"]["enabled"] = False

    # Clean (no record) → prefers E4B.
    assert (
        tr.route_for_task(
            tr.TaskClass.CODING_BUILD, policy=pol, book=None, overrides=_NO_OVERRIDES
        ).chosen
        == "gemma4-e4b"
    )
    # Recorded failure → demote to E2B.
    gls.record_status("gemma4-e4b", ok=False, detail="OOM on 8GB")
    assert (
        tr.route_for_task(
            tr.TaskClass.CODING_BUILD, policy=pol, book=None, overrides=_NO_OVERRIDES
        ).chosen
        == "gemma4-e2b"
    )
    # A later clean smoke restores E4B.
    gls.record_status("gemma4-e4b", ok=True, detail="ok")
    assert (
        tr.route_for_task(
            tr.TaskClass.CODING_BUILD, policy=pol, book=None, overrides=_NO_OVERRIDES
        ).chosen
        == "gemma4-e4b"
    )


def test_research_routes_off_local_when_cloud_available() -> None:
    """Large research prefers a hosted/cloud route, not the small local Gemma.

    With hosted task-class routing ON (the default), the bare ``openrouter``
    provider is expanded into the ``deep_research`` lane's reasoning families
    (DeepSeek-R1 leads), not a coder — while local Gemma stays a last-ditch
    fallback.
    """
    pol = _policy_with_both_gemma_variants()
    pol["routes"]["hosted_free_or_user_configured_oss"] = {
        "enabled": True,
        "providers": ["openrouter"],
    }
    d = tr.route_for_task(
        tr.TaskClass.RESEARCH, policy=pol, book=None, overrides=_NO_OVERRIDES
    )
    assert d.local_first is False
    assert d.route_tier == "hosted_free_or_user_configured_oss"
    chosen = d.chosen
    assert chosen is not None
    assert chosen.startswith("openrouter/")
    assert "deepseek-r1" in chosen  # reasoning lane leads, not a coder
    # Local Gemma stays only as a last-ditch fallback.
    assert d.fallback_chain[-1] in {"gemma4-e2b", "gemma4-e4b"}


def test_research_hosted_legacy_bare_provider_when_disabled(monkeypatch) -> None:
    """The owner escape hatch (HERMES_JARVIS_HOSTED_TASKCLASS=0) restores the
    legacy bare-provider-id hosted candidate, byte-for-byte."""
    monkeypatch.setenv("HERMES_JARVIS_HOSTED_TASKCLASS", "0")
    pol = _policy_with_both_gemma_variants()
    pol["routes"]["hosted_free_or_user_configured_oss"] = {
        "enabled": True,
        "providers": ["openrouter"],
    }
    d = tr.route_for_task(
        tr.TaskClass.RESEARCH, policy=pol, book=None, overrides=_NO_OVERRIDES
    )
    assert d.chosen == "openrouter"
    assert d.route_tier == "hosted_free_or_user_configured_oss"


def test_big_gemma_never_auto_defaults() -> None:
    """26B/31B are sunk to the tail of the local list even if listed first."""
    pol = _policy_with_gemma_local()
    # Local-only box: no worker lanes, so the chain is purely the local order.
    pol["routes"]["claude_code_worker"]["enabled"] = False
    pol["routes"]["codex_worker"]["enabled"] = False
    pol["routes"]["local_oss"]["recommended_local_models"] = [
        "gemma4-31b",
        "gemma4-26b-a4b",
        "gemma4-e2b",
    ]
    d = tr.route_for_task(
        tr.TaskClass.MOBILE_CHAT, policy=pol, book=None, overrides=_NO_OVERRIDES
    )
    assert d.chosen == "gemma4-e2b"
    assert d.fallback_chain[-2:] == ["gemma4-31b", "gemma4-26b-a4b"]


def test_owner_override_can_pin_gemma_and_is_reversible(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    tr.set_task_override("memory_curator", "gemma4-e4b")
    d = tr.route_for_task(tr.TaskClass.MEMORY_CURATOR, policy=_policy_with_gemma_local())
    assert d.owner_override == "gemma4-e4b" and tr.is_gemma(d.chosen)
    # Clearing the pin restores auto-routing.
    tr.set_task_override("memory_curator", None)
    d2 = tr.route_for_task(tr.TaskClass.MEMORY_CURATOR, policy=_policy_with_gemma_local())
    assert d2.owner_override is None
