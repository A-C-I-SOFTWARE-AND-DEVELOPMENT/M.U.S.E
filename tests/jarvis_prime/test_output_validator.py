"""Tests for the deterministic output-constraint validator (rec #8).

The validator enforces the per-task-class ``OutputConstraint``s declared on the
task router: trim over-limit output, flag a regenerate when it cannot be safely
fixed (min_words / banned_phrases), and surface advisory kinds as required
actions. stdlib-only, no network.
"""

from __future__ import annotations

from hermes_cli.jarvis_prime.output_validator import constraints_for, enforce
from hermes_cli.jarvis_prime.task_router import TaskClass


# ---------------------------------------------------------------------------
# Deterministic auto-fix: word cap
# ---------------------------------------------------------------------------


def test_summarization_word_cap_is_trimmed():
    text = " ".join(["word"] * 200)
    r = enforce(TaskClass.SUMMARIZATION, text)
    assert len(r.text.split()) == 150           # trimmed to the cap
    assert r.ok is True                          # max_words is a safe auto-fix
    assert r.regenerate_recommended is False
    assert any(v.kind == "max_words" for v in r.violations)
    assert r.fixes and r.to_dict()["changed"] is True
    # The advisory fidelity constraint is reported, never silently passed.
    assert any("preserve_fidelity" in a for a in r.required_actions)


def test_under_cap_summary_unchanged():
    text = "p99 latency rose while the median fell; the gain held only under 2 KB."
    r = enforce(TaskClass.SUMMARIZATION, text)
    assert r.text == text
    assert r.ok is True
    assert not any(v.kind == "max_words" for v in r.violations)


# ---------------------------------------------------------------------------
# Companion lane: min words, banned phrases, question-closer
# ---------------------------------------------------------------------------


_GOOD_COMPANION = (
    "The kettle is still warm and your chair by the window is exactly where you "
    "left it, so come in slowly, breathe, and let the quiet hold you for a little "
    "while longer tonight."
)


def test_companion_clean_reply_passes():
    r = enforce(TaskClass.COMPANION, _GOOD_COMPANION)
    assert r.ok is True
    assert r.violations == []
    assert r.regenerate_recommended is False


def test_companion_too_short_flags_regenerate():
    r = enforce(TaskClass.COMPANION, "Come sit down.")
    assert r.ok is False
    assert r.regenerate_recommended is True
    assert any(v.kind == "min_words" for v in r.violations)


def test_companion_therapy_speak_banned():
    text = (
        "I'm here for you, always and completely, no matter what happens in the "
        "long days ahead, because your feelings are valid and we will get through "
        "this difficult season together somehow."
    )
    r = enforce(TaskClass.COMPANION, text)
    assert r.ok is False
    assert r.regenerate_recommended is True
    v = next(v for v in r.violations if v.kind == "banned_phrases")
    assert "therapy_speak" in v.observed


def test_companion_question_closer_banned():
    text = (
        "The couch still has your spot and the porch light is on, the dog keeps "
        "checking the door every few minutes, and the whole house feels a little "
        "too quiet without you here tonight, so when are you coming back home?"
    )
    r = enforce(TaskClass.COMPANION, text)
    assert r.ok is False
    v = next(v for v in r.violations if v.kind == "banned_phrases")
    assert "question_closer" in v.observed


# ---------------------------------------------------------------------------
# Advisory-only lanes and no-constraint lanes
# ---------------------------------------------------------------------------


def test_research_reports_advisory_actions_only():
    r = enforce(TaskClass.RESEARCH, "The cluster-RCT ITT estimate crosses 1; verdict is uncertain.")
    assert r.ok is True                 # nothing deterministic to fail
    assert r.violations == []
    assert any("verify_pass" in a for a in r.required_actions)
    assert any("preserve_fidelity" in a for a in r.required_actions)
    assert r.text == r.original_text


def test_lane_without_constraints_is_noop():
    r = enforce(TaskClass.CODING_REVIEW, "Looks fine; ship it.")
    assert r.ok is True
    assert r.violations == []
    assert r.required_actions == []
    assert r.text == "Looks fine; ship it."


def test_constraints_for_matches_profile():
    cons = constraints_for(TaskClass.SUMMARIZATION)
    assert any(c.kind == "max_words" and c.param("limit") == 150 for c in cons)
    assert constraints_for(TaskClass.CODING_REVIEW) == ()
