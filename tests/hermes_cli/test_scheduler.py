"""Recurring-task scheduler: deterministic due computation + safe execution."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from hermes_cli.jarvis_prime.scheduler import ScheduledTask, Scheduler, default_runner

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _sched(tmp_path) -> Scheduler:
    return Scheduler(path=tmp_path / "scheduler.json")


def test_add_list_remove(tmp_path):
    s = _sched(tmp_path)
    t = s.add("forge-tournament", 3600)
    assert [x.id for x in s.tasks()] == [t.id]
    assert s.remove(t.id) is True
    assert s.tasks() == []
    assert s.remove("nope") is False


def test_add_rejects_nonpositive_interval(tmp_path):
    with pytest.raises(ValueError):
        _sched(tmp_path).add("sia", 0)


def test_due_calculation(tmp_path):
    s = _sched(tmp_path)
    t = s.add("forge-tournament", 3600)
    assert [x.id for x in s.due(NOW)] == [t.id]  # never run ⇒ due
    s.mark_run(t.id, NOW)
    assert s.due(NOW + timedelta(seconds=1800)) == []  # within the interval
    assert [x.id for x in s.due(NOW + timedelta(seconds=3600))] == [t.id]  # due again


def test_disabled_task_never_due():
    assert ScheduledTask(kind="sia", interval_seconds=10, enabled=False).due(NOW) is False


def test_owner_gated_flag():
    assert ScheduledTask(kind="autoresearch", interval_seconds=10).owner_gated is True
    assert ScheduledTask(kind="forge-tournament", interval_seconds=10).owner_gated is False


def test_run_due_marks_run_and_delegates(tmp_path):
    s = _sched(tmp_path)
    s.add("forge-tournament", 3600)
    s.add("sia", 3600)
    seen: list[str] = []

    def runner(task: ScheduledTask) -> str:
        seen.append(task.kind)
        return f"ran {task.kind}"

    results = s.run_due(runner=runner, now=NOW)
    assert {r["kind"] for r in results} == {"forge-tournament", "sia"}
    assert set(seen) == {"forge-tournament", "sia"}
    assert s.due(NOW) == []  # both marked run ⇒ no longer due


def test_default_runner_refuses_owner_gated_unless_authorized():
    refusing = default_runner(allow_owner_gated=False)
    assert "skipped" in refusing(ScheduledTask(kind="autoresearch", interval_seconds=10))
    allowed = default_runner(allow_owner_gated=True)
    # authorized ⇒ no longer "skipped" (autoresearch has no offline action here)
    assert "skipped" not in allowed(ScheduledTask(kind="autoresearch", interval_seconds=10))


def test_persistence_roundtrip(tmp_path):
    s1 = _sched(tmp_path)
    t = s1.add("forge-tournament", 7200, rounds=3)
    s2 = _sched(tmp_path)  # fresh instance, same path
    loaded = s2.tasks()
    assert len(loaded) == 1
    assert loaded[0].id == t.id
    assert loaded[0].args == {"rounds": 3}
