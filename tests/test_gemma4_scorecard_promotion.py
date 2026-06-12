"""Gemma 4 — evidence-gated scorecard promotion tests."""

from __future__ import annotations

from muse_cli.jarvis_prime.model_scorecard import (
    ModelScorecard,
    ScorecardBook,
    model_family,
    promotion_eligible,
    route_promotion_candidates,
    variant,
)


def _book(task: str, baseline_n: int, gemma_n: int, **gemma_kw) -> ScorecardBook:
    book = ScorecardBook(scorecards=[])
    for _ in range(baseline_n):
        book.scorecards.append(
            ModelScorecard(
                model="gpt-oss-20b", provider="ollama", task_type=task,
                accepted_diff_rate=0.6, memory_usefulness=0.6,
                tests_passed=6, tests_failed=4,
                hallucination_corrections=1, owner_corrections=1,
            )
        )
    defaults = dict(
        accepted_diff_rate=0.9, memory_usefulness=0.9,
        tests_passed=9, tests_failed=1,
        hallucination_corrections=0, owner_corrections=0,
    )
    defaults.update(gemma_kw)
    for _ in range(gemma_n):
        book.scorecards.append(
            ModelScorecard(model="gemma4-e4b", provider="ollama", task_type=task, **defaults)  # ty: ignore[invalid-argument-type]  # mock/duck-typed test fixture
        )
    return book


def test_family_and_variant_parsers() -> None:
    assert model_family("gemma4-e4b") == "gemma4"
    assert model_family("gemma4:e4b") == "gemma4"
    assert variant("gemma4:e4b") == "e4b"
    assert variant("gemma4-26b-a4b") == "26b-a4b"


def test_promotion_requires_enough_samples() -> None:
    book = _book("memory_curator", baseline_n=25, gemma_n=5)
    a = promotion_eligible(book, task_class="memory_curator", candidate="gemma4-e4b")
    assert not a.eligible
    assert any("samples" in r for r in a.reasons)


def test_promotion_fails_on_correction_regression() -> None:
    book = _book(
        "memory_curator", baseline_n=25, gemma_n=25,
        hallucination_corrections=3, owner_corrections=2,
        accepted_diff_rate=0.6, memory_usefulness=0.6,
    )
    a = promotion_eligible(book, task_class="memory_curator", candidate="gemma4-e4b")
    assert not a.eligible
    assert any("hallucination" in r or "owner corrections" in r for r in a.reasons)


def test_promotion_succeeds_when_gemma_beats_baseline() -> None:
    book = _book("memory_curator", baseline_n=25, gemma_n=25)
    a = promotion_eligible(book, task_class="memory_curator", candidate="gemma4-e4b")
    assert a.eligible, a.reasons
    assert a.baseline == "gpt-oss-20b"
    assert a.mean_delta >= 0.05
    candidates = route_promotion_candidates(book, "memory_curator", family="gemma4")
    assert candidates and candidates[0].eligible
    assert candidates[0].candidate == "gemma4-e4b"


def test_tool_lane_requires_high_tool_reliability() -> None:
    book = ScorecardBook(scorecards=[])
    for _ in range(25):
        book.scorecards.append(
            ModelScorecard(
                model="codex", provider="codex", task_type="coding_review",
                accepted_diff_rate=0.7, tests_passed=7, tests_failed=3,
                tool_reliability=0.99,
            )
        )
    for _ in range(25):
        book.scorecards.append(
            ModelScorecard(
                model="gemma4-26b-a4b", provider="ollama", task_type="coding_review",
                accepted_diff_rate=0.85, tests_passed=9, tests_failed=1,
                tool_reliability=0.95,  # below the 0.98 floor
            )
        )
    a = promotion_eligible(book, task_class="coding_review", candidate="gemma4-26b-a4b")
    assert not a.eligible
    assert any("tool reliability" in r for r in a.reasons)


def test_vendor_benchmarks_do_not_promote() -> None:
    # No scorecards at all → not eligible regardless of any catalog priors.
    a = promotion_eligible(
        ScorecardBook(scorecards=[]), task_class="memory_curator", candidate="gemma4-e4b"
    )
    assert not a.eligible


def test_citation_lane_requires_citation_accuracy() -> None:
    """On a citation lane, a candidate with no measured citation accuracy fails
    the citation floor even when it clears the tool-reliability floor."""
    book = ScorecardBook(scorecards=[])
    for _ in range(25):
        book.scorecards.append(
            ModelScorecard(
                model="deepseek-r1", provider="openrouter",
                task_type="citation_verification",
                accepted_diff_rate=0.7, tests_passed=7, tests_failed=3,
                tool_reliability=0.99, citation_accuracy=0.95,
            )
        )
    for _ in range(25):
        book.scorecards.append(
            ModelScorecard(
                model="glm-5", provider="openrouter",
                task_type="citation_verification",
                accepted_diff_rate=0.95, tests_passed=10, tests_failed=0,
                tool_reliability=0.99,  # clears the 0.98 tool floor
                # citation_accuracy omitted → None → must fail the citation floor
            )
        )
    a = promotion_eligible(book, task_class="citation_verification", candidate="glm-5")
    assert not a.eligible
    assert any("citation" in r for r in a.reasons)


def test_memory_lane_requires_memory_usefulness() -> None:
    """On the memory lane, a stronger-overall candidate with worse memory
    usefulness than the baseline is rejected by the memory floor."""
    book = ScorecardBook(scorecards=[])
    for _ in range(25):
        book.scorecards.append(
            ModelScorecard(
                model="gpt-oss-20b", provider="ollama", task_type="memory_curator",
                accepted_diff_rate=0.5, tests_passed=5, tests_failed=5,
                memory_usefulness=0.95,
            )
        )
    for _ in range(25):
        book.scorecards.append(
            ModelScorecard(
                model="gemma4-e4b", provider="ollama", task_type="memory_curator",
                accepted_diff_rate=0.95, tests_passed=10, tests_failed=0,
                memory_usefulness=0.5,  # worse than baseline on the memory floor
            )
        )
    a = promotion_eligible(book, task_class="memory_curator", candidate="gemma4-e4b")
    assert not a.eligible
    assert any("memory usefulness" in r for r in a.reasons)


def test_latency_budget_rejects_slow_candidate() -> None:
    """On a latency-budgeted lane (voice_reply), a candidate over the budget is
    rejected even if it is otherwise strong."""
    book = ScorecardBook(scorecards=[])
    for _ in range(25):
        book.scorecards.append(
            ModelScorecard(
                model="gemma4-e2b", provider="ollama", task_type="voice_reply",
                accepted_diff_rate=0.6, tests_passed=6, tests_failed=4,
                latency_ms=1200.0, mobile_ux_suitability=0.7,
            )
        )
    for _ in range(25):
        book.scorecards.append(
            ModelScorecard(
                model="deepseek-r1", provider="openrouter", task_type="voice_reply",
                accepted_diff_rate=0.95, tests_passed=10, tests_failed=0,
                latency_ms=9000.0,  # far over the 4s voice budget
                mobile_ux_suitability=0.9,
            )
        )
    a = promotion_eligible(book, task_class="voice_reply", candidate="deepseek-r1")
    assert not a.eligible
    assert any("budget" in r for r in a.reasons)
