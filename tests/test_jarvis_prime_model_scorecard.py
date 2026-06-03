from __future__ import annotations

from hermes_cli.jarvis_prime.model_scorecard import (
    ModelScorecard,
    ScorecardBook,
    local_endpoint_packet,
)


def test_score_rewards_passes_and_penalizes_corrections() -> None:
    good = ModelScorecard(
        model="claude",
        provider="anthropic",
        task_type="coding",
        tests_passed=10,
        tests_failed=0,
        accepted_diff_rate=0.9,
        memory_usefulness=0.8,
    )
    bad = ModelScorecard(
        model="weak",
        provider="x",
        task_type="coding",
        tests_passed=2,
        tests_failed=8,
        accepted_diff_rate=0.2,
        owner_corrections=3,
        hallucination_corrections=2,
    )
    assert good.score > bad.score
    assert 0.0 <= bad.score <= 1.0


def test_recommend_ranks_models(tmp_path) -> None:
    book = ScorecardBook(path=tmp_path / "s.jsonl")
    book.record(
        ModelScorecard(
            "claude",
            "anthropic",
            "coding",
            tests_passed=9,
            tests_failed=1,
            accepted_diff_rate=0.9,
        )
    )
    book.record(
        ModelScorecard(
            "local",
            "vllm",
            "coding",
            tests_passed=4,
            tests_failed=6,
            accepted_diff_rate=0.4,
        )
    )
    ranked = book.recommend("coding")
    assert ranked[0][0] == "claude"
    assert ranked[0][1] >= ranked[1][1]


def test_persistence_round_trip(tmp_path) -> None:
    path = tmp_path / "s.jsonl"
    book = ScorecardBook(path=path)
    book.record(
        ModelScorecard("claude", "anthropic", "coding", tests_passed=5, tests_failed=0)
    )
    reloaded = ScorecardBook.load(path)
    assert len(reloaded.scorecards) == 1
    assert reloaded.scorecards[0].model == "claude"


def test_local_endpoint_packet_is_wired_not_confirmed() -> None:
    packet = local_endpoint_packet("qwen3-coder", endpoint="http://localhost:8000/v1")
    assert packet["status"] == "wired_not_confirmed"
    assert packet["openai_compatible"] is True
    assert "smoke_check" in packet and "curl" in str(packet["smoke_check"])
    # never claims the model is running
    assert "running" in str(packet["note"]).lower()


def test_render_handles_empty_and_populated(tmp_path) -> None:
    book = ScorecardBook(path=tmp_path / "s.jsonl")
    assert "No scorecards" in book.render()
    book.record(
        ModelScorecard("claude", "anthropic", "coding", tests_passed=5, tests_failed=0)
    )
    assert "claude" in book.render()


def test_new_dimensions_round_trip(tmp_path) -> None:
    path = tmp_path / "s.jsonl"
    book = ScorecardBook(path=path)
    book.record(
        ModelScorecard(
            "m",
            "p",
            "citation_verification",
            context_length=128000,
            tool_reliability=0.8,
            citation_accuracy=0.95,
            mobile_ux_suitability=0.6,
        )
    )
    reloaded = ScorecardBook.load(path)
    card = reloaded.scorecards[0]
    assert card.context_length == 128000
    assert card.citation_accuracy == 0.95
    assert card.tool_reliability == 0.8
    assert card.mobile_ux_suitability == 0.6


def test_score_for_weights_citation_for_citation_task() -> None:
    """citation_verification ranking is driven by citation accuracy."""
    strong_cite = ModelScorecard(
        "a", "p", "citation_verification", tests_passed=5, tests_failed=5,
        citation_accuracy=0.95,
    )
    weak_cite = ModelScorecard(
        "b", "p", "citation_verification", tests_passed=5, tests_failed=5,
        citation_accuracy=0.2,
    )
    assert strong_cite.score_for("citation_verification") > weak_cite.score_for(
        "citation_verification"
    )


def test_score_for_weights_latency_for_voice() -> None:
    """voice_reply rewards low latency."""
    fast = ModelScorecard(
        "a", "p", "voice_reply", tests_passed=5, tests_failed=5,
        latency_ms=300, mobile_ux_suitability=0.9,
    )
    slow = ModelScorecard(
        "b", "p", "voice_reply", tests_passed=5, tests_failed=5,
        latency_ms=9000, mobile_ux_suitability=0.9,
    )
    assert fast.score_for("voice_reply") > slow.score_for("voice_reply")


def test_score_for_unknown_task_falls_back_to_score() -> None:
    card = ModelScorecard("a", "p", "coding", tests_passed=8, tests_failed=2)
    assert card.score_for(None) == card.score
    assert card.score_for("not_a_task_class") == card.score
