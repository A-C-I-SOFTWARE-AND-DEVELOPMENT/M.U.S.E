"""Tests for the free/local benchmark scorecard producer (FU-16).

These pin the artifact *schema* and its *determinism* (same inputs → identical
bytes across two runs), confirm the producer reuses the real verifier (the
known-correct built-in suite scores a perfect bar), and assert the call performs
no network I/O and never raises.
"""

from __future__ import annotations

import socket

import pytest

from hermes_cli.jarvis_prime.depth_scorecard import (
    BUILTIN_TASKS,
    SCORECARD_SCHEMA_VERSION,
    VERIFIER_MODEL,
    DepthScorecard,
    VerifiableTask,
    produce_scorecard,
    render_scorecard,
)
from hermes_cli.jarvis_prime.model_scorecard import ModelScorecard
from hermes_cli.jarvis_prime.task_router import TaskClass


def test_builtin_tasks_use_known_task_classes() -> None:
    """Every built-in task's lane is a real TaskClass value (reused vocab)."""
    valid = {tc.value for tc in TaskClass}
    assert BUILTIN_TASKS  # non-empty proof suite
    for task in BUILTIN_TASKS:
        assert task.task_class in valid


def test_known_correct_suite_scores_perfect() -> None:
    """The built-in candidates are correct-by-construction → 100% pass."""
    sc = produce_scorecard()
    assert sc.tasks_total == len(BUILTIN_TASKS)
    assert sc.tasks_passed == len(BUILTIN_TASKS)
    assert sc.overall_score == 1.0
    # Every per-class lane is fully resolved.
    assert sc.per_class  # at least one lane
    for cls in sc.per_class:
        assert cls.pass_rate == 1.0
        assert cls.tasks_passed == cls.tasks


def test_artifact_schema_is_pinned() -> None:
    """Lock the emitted dict shape so downstream consumers have a contract."""
    d = produce_scorecard().to_dict()
    assert set(d) == {
        "schema_version",
        "model",
        "provider",
        "overall_score",
        "tasks_total",
        "tasks_passed",
        "per_class",
        "cards",
        "offline",
        "deterministic",
        "notes",
    }
    assert d["schema_version"] == SCORECARD_SCHEMA_VERSION
    assert d["model"] == VERIFIER_MODEL
    assert d["offline"] is True
    assert d["deterministic"] is True
    # per_class entries have the pinned aggregate shape.
    for entry in d["per_class"]:
        assert set(entry) == {"task_class", "tasks", "tasks_passed", "pass_rate"}


def test_cards_are_model_scorecard_compatible() -> None:
    """Each card round-trips through ModelScorecard.from_dict (reused shape)."""
    d = produce_scorecard().to_dict()
    assert len(d["cards"]) == len(BUILTIN_TASKS)
    for card in d["cards"]:
        restored = ModelScorecard.from_dict(card)
        assert restored.model == VERIFIER_MODEL
        # known-correct candidate ⇒ one passing test, zero failures
        assert restored.tests_passed == 1
        assert restored.tests_failed == 0


def test_deterministic_across_two_runs() -> None:
    """Same inputs → byte-identical artifact (the proof-bar reproducibility)."""
    first = produce_scorecard()
    second = produce_scorecard()
    assert first.to_dict() == second.to_dict()
    assert first.to_json() == second.to_json()


def test_empty_suite_degrades_to_honest_zero() -> None:
    """An empty suite never raises; it yields an explicit zero scorecard."""
    sc = produce_scorecard(tasks=())
    assert isinstance(sc, DepthScorecard)
    assert sc.tasks_total == 0
    assert sc.tasks_passed == 0
    assert sc.overall_score == 0.0
    assert sc.per_class == []
    assert sc.notes  # carries the reason


def test_wrong_candidate_counts_as_failed_test() -> None:
    """A deliberately-wrong candidate is graded as a failing test, not an error."""
    bad = (
        VerifiableTask(
            task_id="wrong_reverse",
            task_class="coding_build",
            entrypoint="solve",
            candidate="def solve(s):\n    return s\n",  # not reversed
            cases=((["abc"], "cba"),),
        ),
    )
    sc = produce_scorecard(tasks=bad)
    assert sc.tasks_total == 1
    assert sc.tasks_passed == 0
    assert sc.overall_score == 0.0
    assert sc.cards[0]["tests_failed"] == 1


def test_never_raises_on_internal_failure(monkeypatch) -> None:
    """If the harness itself blows up, the producer degrades, never raises."""

    def _boom(*_a, **_k):
        raise RuntimeError("simulated harness failure")

    # Patch the symbol where it is looked up (lazy import target module).
    monkeypatch.setattr(
        "hermes_cli.jarvis_prime.research_fabric.benchmarks.run_suite",
        _boom,
    )
    sc = produce_scorecard()
    assert sc.tasks_total == 0
    assert sc.overall_score == 0.0
    assert any("grading failed" in n for n in sc.notes)


def test_no_network_at_call_time(monkeypatch) -> None:
    """The producer performs no socket I/O in this process when grading."""

    def _no_sockets(*_a, **_k):
        raise AssertionError("network access attempted during produce_scorecard")

    monkeypatch.setattr(socket, "socket", _no_sockets)
    # Also block the lower-level connection primitive for good measure.
    monkeypatch.setattr(socket, "create_connection", _no_sockets)
    sc = produce_scorecard()
    assert sc.overall_score == 1.0  # still grades the known-correct suite


def test_render_is_stable_and_summarizes() -> None:
    sc = produce_scorecard()
    text_a = render_scorecard(sc)
    text_b = render_scorecard(sc)
    assert text_a == text_b
    assert "FREE/LOCAL BENCHMARK SCORECARD" in text_a
    assert VERIFIER_MODEL in text_a


def test_schema_version_is_int_constant() -> None:
    assert isinstance(SCORECARD_SCHEMA_VERSION, int)
    assert SCORECARD_SCHEMA_VERSION >= 1


@pytest.mark.parametrize("task", list(BUILTIN_TASKS))
def test_each_builtin_candidate_defines_its_entrypoint(task: VerifiableTask) -> None:
    """Sanity: the embedded candidate actually defines the named entrypoint."""
    assert f"def {task.entrypoint}(" in task.candidate
