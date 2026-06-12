"""Tests for muse_cli.jarvis_prime.gates — eight verification gates."""

from __future__ import annotations

from muse_cli.jarvis_prime.gates import (
    GATES,
    GateOutcome,
    build_gate,
    owner_approval_gate,
    planning_gate,
    release_gate,
    review_gate,
    rollback_gate,
    run_gate_summary,
    security_gate,
)
from muse_cli.jarvis_prime.gates import test_gate as eval_test_gate  # rename to avoid pytest collection


def test_gates_module_exposes_eight_gates() -> None:
    assert len(GATES) == 8
    names = {g.name for g in GATES}
    assert names == {
        "planning", "build", "review", "test", "security",
        "release", "owner_approval", "rollback",
    }


def test_planning_gate_fails_on_missing_mission() -> None:
    packet: dict = {
        "repo_root": "/repo",
        "branch": "main",
        "allowed_files": ["x.py"],
        "non_goals": ["nothing else"],
        "acceptance_criteria": "compile",
    }
    result = planning_gate(packet)
    assert result.outcome == GateOutcome.FAIL
    assert "goal/mission" in result.findings


def test_planning_gate_passes_when_complete() -> None:
    packet = {
        "repo_root": "/repo",
        "branch": "main",
        "mission": "fix the parser",
        "allowed_files": ["parser.py"],
        "non_goals": ["unrelated refactor"],
        "acceptance_criteria": "tests pass",
    }
    assert planning_gate(packet).outcome == GateOutcome.PASS


def test_build_gate_flags_out_of_scope_edits() -> None:
    packet = {
        "allowed_files": ["a.py"],
        "files_changed": ["a.py", "b.py", "c.py"],
    }
    result = build_gate(packet)
    assert result.outcome == GateOutcome.FAIL
    assert any("out-of-scope" in f for f in result.findings)


def test_build_gate_flags_concurrent_editors() -> None:
    packet = {
        "allowed_files": ["a.py"],
        "files_changed": ["a.py"],
        "concurrent_editors": ["claude-code", "codex"],
    }
    result = build_gate(packet)
    assert result.outcome == GateOutcome.FAIL
    assert any("concurrent editors" in f for f in result.findings)


def test_review_gate_fails_without_diff_review() -> None:
    packet = {"contrarian_objection": "race condition"}
    assert review_gate(packet).outcome == GateOutcome.FAIL


def test_review_gate_blocking_findings_fail() -> None:
    packet = {
        "diff_reviewed": True,
        "contrarian_objection": "obj",
        "blocking_findings": ["null deref in parser.py:42"],
    }
    result = review_gate(packet)
    assert result.outcome == GateOutcome.FAIL
    assert any("null deref" in f for f in result.findings)


def test_test_gate_skipped_with_reason() -> None:
    packet = {"tests_skipped_reason": "docs-only change"}
    result = eval_test_gate(packet)
    assert result.outcome == GateOutcome.SKIPPED


def test_test_gate_fails_without_reason() -> None:
    packet = {}
    result = eval_test_gate(packet)
    assert result.outcome == GateOutcome.FAIL


def test_test_gate_passes_when_tests_run() -> None:
    packet = {"tests_run": ["test_x.py"], "tests_failed": []}
    assert eval_test_gate(packet).outcome == GateOutcome.PASS


def test_security_gate_flags_secret_added() -> None:
    packet = {"secrets_added": ["AWS_KEY"]}
    result = security_gate(packet)
    assert result.outcome == GateOutcome.FAIL


def test_security_gate_needs_owner_for_risky_actions() -> None:
    packet = {"risky_actions": ["production_deploy"], "owner_approved": False}
    result = security_gate(packet)
    assert result.outcome == GateOutcome.NEEDS_OWNER_APPROVAL


def test_release_gate_requires_rollback_plan() -> None:
    packet = {
        "files_changed": ["a.py"],
        "commits_scoped": True,
        "verification_summary": "tests pass",
        "non_goals": ["unrelated"],
        "remaining_risks": "none",
    }
    result = release_gate(packet)
    assert result.outcome == GateOutcome.FAIL
    assert any("rollback" in f for f in result.findings)


def test_owner_approval_gate_no_pending_passes() -> None:
    assert owner_approval_gate({}).outcome == GateOutcome.PASS


def test_owner_approval_gate_needs_exact_phrase() -> None:
    packet = {
        "owner_gated_actions": ["production_deploy"],
        "owner_authorization_phrase": "go ahead",
    }
    result = owner_approval_gate(packet)
    assert result.outcome == GateOutcome.NEEDS_OWNER_APPROVAL


def test_owner_approval_gate_exact_phrase_passes() -> None:
    packet = {
        "owner_gated_actions": ["production_deploy"],
        "owner_authorization_phrase": "Yes, with authorization.",
    }
    assert owner_approval_gate(packet).outcome == GateOutcome.PASS


def test_owner_approval_gate_treats_main_branch_merge_as_unknown() -> None:
    # main_branch_merge has been moved out of OWNER_GATED_ACTIONS and
    # is now governed by LaunchGate. If a packet still lists it as an
    # owner-gated action, the gate must fail closed — it must not
    # silently accept the exact phrase for an action that is no longer
    # in the runtime owner-gated set.
    packet = {
        "owner_gated_actions": ["main_branch_merge"],
        "owner_authorization_phrase": "Yes, with authorization.",
    }
    assert owner_approval_gate(packet).outcome == GateOutcome.FAIL


def test_owner_approval_gate_unknown_action_fails() -> None:
    packet = {
        "owner_gated_actions": ["take_over_the_world"],
        "owner_authorization_phrase": "Yes, with authorization.",
    }
    assert owner_approval_gate(packet).outcome == GateOutcome.FAIL


def test_rollback_gate_requires_plan_and_revert_target() -> None:
    assert rollback_gate({}).outcome == GateOutcome.FAIL
    assert rollback_gate({"rollback_plan": "git revert HEAD", "commit_hash": "abc"}).outcome == GateOutcome.PASS


def test_run_gate_summary_renders_template() -> None:
    summary = run_gate_summary({})
    rendered = summary.render()
    for line in (
        "GATE SUMMARY", "Planning gate:", "Build gate:", "Review gate:",
        "Test gate:", "Security gate:", "Release gate:",
        "Owner approval gate:", "Rollback gate:", "Result:", "Remaining risk:",
    ):
        assert line in rendered


def test_run_gate_summary_overall_fail_with_blocker() -> None:
    packet = {
        "files_changed": ["a.py"],
        "secrets_added": ["AWS"],
    }
    summary = run_gate_summary(packet)
    assert summary.overall == GateOutcome.FAIL
