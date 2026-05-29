"""Tests for read-only job replay."""

from __future__ import annotations

from hermes_cli.orchestrator_replay import JobReplay


def test_empty_ledger_replays_cleanly():
    replay = JobReplay.load("job-none", entries=[])
    assert replay.is_empty
    assert "nothing to replay" in replay.render()


def test_replay_reconstructs_and_summarizes():
    entries = [
        {
            "kind": "goal_boundary_declared",
            "boundary": {"objective": "fix bug", "max_iterations": 3},
        },
        {
            "kind": "navigation_decision",
            "ranked_files": [{"path": "app/auth.py"}, {"path": "app/x.py"}],
        },
        {
            "kind": "repair_loop_step",
            "phase": "test",
            "passed": False,
            "failing_tests": ["t1"],
        },
        {"kind": "repair_loop_step", "phase": "patch", "summary": "patched auth"},
        {"kind": "repair_loop_result", "succeeded": True, "stop_reason": "tests green"},
    ]
    replay = JobReplay.load("job-1", entries=entries)
    assert not replay.is_empty
    assert len(replay.steps) == 5
    assert replay.by_kind("navigation_decision")
    text = replay.render()
    assert "app/auth.py" in text
    assert "succeeded=True" in text
    assert replay.to_dict()["step_count"] == 5


def test_generic_entries_get_a_summary():
    replay = JobReplay.load(
        "job-2", entries=[{"kind": "custom", "status": "ok", "extra": 1}]
    )
    assert replay.steps[0].summary.startswith("status=ok")
