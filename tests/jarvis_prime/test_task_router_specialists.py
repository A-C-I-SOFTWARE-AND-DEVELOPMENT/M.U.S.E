"""Tests for installed-model specialist routing (#9) in task_router.

The specialist layer is *additive*: when an installed local candidate matches the
detected lane's specialist it leads the local route; otherwise (no match, empty
catalog, or env-disabled) the legacy local ordering is preserved exactly.
"""

from __future__ import annotations

from hermes_cli.jarvis_prime.model_scorecard import ScorecardBook
from hermes_cli.jarvis_prime.task_router import (
    MODEL_SPECIALISTS,
    ModelSpecialist,
    TaskClass,
    route_for_task,
)


def _policy(*, local_models=(), local=True):
    return {
        "route_order": [
            "local_oss",
            "hosted_free_or_user_configured_oss",
            "claude_code_worker",
            "codex_worker",
            "paid_api_explicit_only",
        ],
        "routes": {
            "local_oss": {
                "enabled": local,
                "recommended_local_models": list(local_models),
            },
            "hosted_free_or_user_configured_oss": {"enabled": False, "providers": []},
            "claude_code_worker": {"enabled": False},
            "codex_worker": {"enabled": False},
            "paid_api_explicit_only": {"enabled": False, "providers_detected": []},
        },
        "paid": {"enabled": False},
        "local_defaults": [],
    }


def _empty_book(tmp_path):
    return ScorecardBook(path=tmp_path / "s.jsonl")


def _route(tc, models, tmp_path, **kw):
    return route_for_task(
        tc,
        policy=_policy(local_models=models),
        book=_empty_book(tmp_path),
        overrides={"paid_enabled": None, "task_overrides": {}},
        **kw,
    )


# ---------------------------------------------------------------------------
# Specialist table is seeded from the verified matrix
# ---------------------------------------------------------------------------


def test_specialist_table_matches_verified_matrix():
    by_pattern = {s.pattern: s for s in MODEL_SPECIALISTS}
    # coding workhorse — coding lane only, tools, no vision.
    assert by_pattern["qwen3-coder"].lanes == ("local_coding",)
    assert by_pattern["qwen3-coder"].tools is True
    assert by_pattern["qwen3-coder"].vision is False
    # reasoning/critic — gpt-oss has tools+thinking, NOT vision.
    assert "local_reasoning" in by_pattern["gpt-oss"].lanes
    assert by_pattern["gpt-oss"].vision is False
    assert by_pattern["gpt-oss"].thinking is True
    # fast/default daily — qwen3.5:9b is vision-capable, fast lane.
    assert "local_fast" in by_pattern["qwen3.5:9b"].lanes
    assert by_pattern["qwen3.5:9b"].vision is True
    # vision/general — gemma4:12b vision-capable.
    assert by_pattern["gemma4:12b"].vision is True
    # creative/companion — Qwythos-Mythos.
    assert "local_creative" in by_pattern["qwythos"].lanes
    # embedding — bge-m3, never a chat candidate.
    assert by_pattern["bge-m3"].embedding is True
    assert by_pattern["bge-m3"].lanes == ("embedding",)
    # Every chat specialist from the matrix supports tools.
    for spec in MODEL_SPECIALISTS:
        if not spec.embedding:
            assert spec.tools is True


# ---------------------------------------------------------------------------
# Specialist preference leads the matching lane
# ---------------------------------------------------------------------------


def test_coding_lane_prefers_coder_specialist(tmp_path):
    """A coding lane leads with qwen3-coder over a generalist already listed first."""
    d = _route(
        TaskClass.CODING_BUILD,
        ("qwen3.5:9b", "qwen3-coder", "gpt-oss:20b"),
        tmp_path,
    )
    assert d.chosen == "qwen3-coder"
    assert d.route_tier == "local_oss"


def test_fast_lane_prefers_fast_generalist(tmp_path):
    """A fast/chat lane leads with qwen3.5:9b over a coder/reasoner."""
    d = _route(
        TaskClass.MOBILE_CHAT,
        ("qwen3-coder", "gpt-oss:20b", "qwen3.5:9b"),
        tmp_path,
    )
    assert d.chosen == "qwen3.5:9b"


def test_reasoning_lane_prefers_reasoner(tmp_path):
    """A research/reasoning lane leads with a reasoning specialist."""
    d = _route(
        TaskClass.RESEARCH,
        ("qwen3-coder", "gpt-oss:20b"),
        tmp_path,
    )
    # RESEARCH routes off-local first, but local stays the last fallback; the
    # local candidate ORDER must still lead with the reasoner.
    local_chain = [c for c in d.fallback_chain if c in ("qwen3-coder", "gpt-oss:20b")]
    assert local_chain[0] == "gpt-oss:20b"


def test_specialist_priority_orders_two_matches(tmp_path):
    """When two specialists match a lane, MODEL_SPECIALISTS order decides the lead."""
    # local_reasoning matches both gpt-oss and gemma4:12b; gpt-oss is earlier.
    d = _route(
        TaskClass.RESEARCH,
        ("gemma4:12b", "gpt-oss:20b"),
        tmp_path,
    )
    local_chain = [c for c in d.fallback_chain if c in ("gemma4:12b", "gpt-oss:20b")]
    assert local_chain[0] == "gpt-oss:20b"


# ---------------------------------------------------------------------------
# Backward compatibility / opt-out
# ---------------------------------------------------------------------------


def test_no_specialist_match_preserves_order(tmp_path):
    """Models that match no specialist keep their legacy order (byte-for-byte)."""
    d = _route(
        TaskClass.CODING_BUILD,
        ("weak-local", "other-local"),
        tmp_path,
    )
    assert d.chosen == "weak-local"
    assert d.fallback_chain[:2] == ["weak-local", "other-local"]


def test_disable_env_restores_legacy_order(tmp_path, monkeypatch):
    """The owner escape hatch restores the pre-specialist local ordering."""
    monkeypatch.setenv("HERMES_JARVIS_SPECIALIST_ROUTING", "off")
    d = _route(
        TaskClass.CODING_BUILD,
        ("qwen3.5:9b", "qwen3-coder"),
        tmp_path,
    )
    # Without specialist routing the first listed local model leads.
    assert d.chosen == "qwen3.5:9b"


def test_embedding_specialist_never_chat_candidate(tmp_path):
    """bge-m3 (embedding) is never floated to the front of a chat lane."""
    d = _route(
        TaskClass.MEMORY_CURATOR,
        ("bge-m3:latest", "qwen3.5:9b"),
        tmp_path,
    )
    # The fast generalist leads; the embedder is not promoted over it.
    assert d.chosen == "qwen3.5:9b"


def test_provider_prefixed_tag_still_matches(tmp_path):
    """A specialist matches against the tag tail, ignoring a provider/ prefix."""
    d = _route(
        TaskClass.CODING_BUILD,
        ("ollama-local/qwen3.5:9b", "ollama-local/qwen3-coder:30b"),
        tmp_path,
    )
    assert d.chosen == "ollama-local/qwen3-coder:30b"


def test_specialist_is_a_frozen_dataclass():
    """Sanity: the table holds ModelSpecialist instances (frozen)."""
    assert all(isinstance(s, ModelSpecialist) for s in MODEL_SPECIALISTS)
