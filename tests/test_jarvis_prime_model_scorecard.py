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
    assert "smoke_check" in packet and "curl" in packet["smoke_check"]
    # never claims the model is running
    assert "running" in packet["note"].lower()


def test_render_handles_empty_and_populated(tmp_path) -> None:
    book = ScorecardBook(path=tmp_path / "s.jsonl")
    assert "No scorecards" in book.render()
    book.record(
        ModelScorecard("claude", "anthropic", "coding", tests_passed=5, tests_failed=0)
    )
    assert "claude" in book.render()
