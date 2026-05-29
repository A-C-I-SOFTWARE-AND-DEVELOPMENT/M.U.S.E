from __future__ import annotations

from hermes_cli.jarvis_prime.monitors import (
    MonitorBoard,
    Severity,
    failing_tests_checker,
    repo_state_checker,
)


def test_repo_state_warns_on_dirty_tree() -> None:
    r = repo_state_checker({
        "repo": {"dirty": True, "branch": "feature", "changed_files": ["a.py"]}
    })
    assert r.severity is Severity.WARNING
    assert "a.py" in r.findings


def test_failing_tests_is_critical() -> None:
    r = failing_tests_checker({"tests": {"failed": ["test_x"], "passed": 3}})
    assert r.severity is Severity.CRITICAL


def test_missing_source_is_blind_not_crash() -> None:
    r = repo_state_checker({})
    assert r.severity is Severity.BLIND


def test_board_runs_all_and_reports_coverage() -> None:
    board = MonitorBoard.default()
    context = {
        "repo": {"dirty": False, "branch": "main"},
        "open_prs": [],
        "tests": {"passed": 10, "failed": []},
        # docs, contradictions, proposals, model_failures, android omitted → blind
    }
    results = board.run(context)
    assert len(results) == 8
    coverage = board.coverage(results)
    assert coverage["total"] == 8
    assert coverage["blind_spots"]  # the omitted sources surface as blind spots
    assert 0.0 < coverage["coverage_ratio"] < 1.0


def test_throwing_monitor_becomes_blind_spot() -> None:
    board = MonitorBoard.default()

    def boom(ctx):
        raise RuntimeError("kaboom")

    board.monitors[0].checker = boom
    results = board.run({"open_prs": [], "tests": {"passed": 1, "failed": []}})
    assert results[0].severity is Severity.BLIND
    assert board.monitors[0].failure_count == 1


def test_monitor_records_last_success() -> None:
    board = MonitorBoard.default()
    board.run({
        "repo": {"dirty": False, "branch": "main"},
        "open_prs": [],
        "tests": {"passed": 1, "failed": []},
    })
    repo_mon = next(m for m in board.monitors if m.name == "repo_state")
    assert repo_mon.last_success_at is not None
