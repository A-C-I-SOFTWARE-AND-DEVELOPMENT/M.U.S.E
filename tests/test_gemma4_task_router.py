"""Gemma 4 — task-router lane tests (data-driven, scorecard-aware)."""

from __future__ import annotations

import pytest

from hermes_cli.jarvis_prime import task_router as tr


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


def test_owner_override_can_pin_gemma_and_is_reversible(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HERMES_HOME", str(tmp_path))
    tr.set_task_override("memory_curator", "gemma4-e4b")
    d = tr.route_for_task(tr.TaskClass.MEMORY_CURATOR, policy=_policy_with_gemma_local())
    assert d.owner_override == "gemma4-e4b" and tr.is_gemma(d.chosen)
    # Clearing the pin restores auto-routing.
    tr.set_task_override("memory_curator", None)
    d2 = tr.route_for_task(tr.TaskClass.MEMORY_CURATOR, policy=_policy_with_gemma_local())
    assert d2.owner_override is None
