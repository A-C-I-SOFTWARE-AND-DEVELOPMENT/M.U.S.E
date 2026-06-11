"""Tests for the verifier reward-hacking screen (Plane 1)."""

from __future__ import annotations

from hermes_cli.jarvis_prime.self_update import ProposalKind
from hermes_cli.jarvis_prime.research_fabric.verifier import (
    Candidate,
    screen_for_reward_hacking,
)


def _cand(**over) -> Candidate:
    base = dict(
        candidate_id="c",
        kind=ProposalKind.SKILL_UPDATE,
        target_path="skills/foo/SKILL.md",
        risk_class="RC1",
        domain_scores={},
    )
    base.update(over)
    return Candidate(**base)  # ty: ignore[invalid-argument-type]  # mock/duck-typed test fixture


def test_clean_candidate_has_no_signals() -> None:
    assert screen_for_reward_hacking(_cand(diff_text="def f():\n    return 1\n")) == []


def test_assert_true_is_flagged() -> None:
    sigs = screen_for_reward_hacking(_cand(diff_text="def test_x():\n    assert True\n"))
    assert any(s.kind == "reward_hacking" for s in sigs)


def test_skipped_test_is_flagged() -> None:
    sigs = screen_for_reward_hacking(
        _cand(diff_text="@pytest.mark.skip\ndef test_x():\n    ...\n")
    )
    assert any(s.kind == "reward_hacking" for s in sigs)


def test_deleted_tests_are_flagged() -> None:
    sigs = screen_for_reward_hacking(_cand(deleted_test_files=("tests/test_a.py",)))
    assert any(s.kind == "reward_hacking" for s in sigs)


def test_network_and_secret_use_are_flagged() -> None:
    sigs = screen_for_reward_hacking(_cand(used_network=True, used_secrets=True))
    kinds = {s.kind for s in sigs}
    assert kinds == {"secret_or_network_use"}


def test_type_ignore_suppression_is_flagged() -> None:
    sigs = screen_for_reward_hacking(_cand(diff_text="x = bad()  # type: ignore\n"))
    assert any(s.kind == "reward_hacking" for s in sigs)
