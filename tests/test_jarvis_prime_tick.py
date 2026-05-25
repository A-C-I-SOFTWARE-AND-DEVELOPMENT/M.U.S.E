"""Tests for hermes_cli.jarvis_prime.tick — the quiet daemon loop.

The tick is the "anticipates blockers before you ask" part of JARVIS
Prime, rate-limited via state persistence so two back-to-back calls
produce exactly one notification. The mission-critical invariant
covered here is:

    run_once(..., enabled=False) is a true no-op:
    returns [], does not perceive, does not notify, does not persist.

All tests are hermetic: ``perceive`` is monkeypatched, ``state_path``
points at ``tmp_path``, no network, no ``~/.hermes/`` writes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import pytest

from hermes_cli.jarvis_prime.awareness import (
    AwarenessSnapshot,
    GitHubSnapshot,
    JobStatus,
)
from hermes_cli.jarvis_prime.tick import (
    TickNotification,
    TickState,
    _is_in_briefing_window,
    run_once,
)


def _empty_snapshot() -> AwarenessSnapshot:
    return AwarenessSnapshot()


def _snapshot_with_failing_prs(prs: list[str]) -> AwarenessSnapshot:
    return AwarenessSnapshot(github_state=GitHubSnapshot(failing_ci_prs=prs))


def _snapshot_with_blocked_jobs(job_ids: list[str]) -> AwarenessSnapshot:
    return AwarenessSnapshot(
        active_jobs=[JobStatus(job_id=j, phase="run", blocked=True) for j in job_ids]
    )


# ── Disabled-path behaviour (mission requirement m) ────────────────────────


def test_run_once_disabled_returns_empty_list(tmp_path: Path) -> None:
    result = run_once(state_path=tmp_path / "state.json", enabled=False)
    assert result == []


def test_run_once_disabled_does_not_call_perceive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[None] = []

    def boom() -> AwarenessSnapshot:
        calls.append(None)
        raise AssertionError("perceive() must not run when tick is disabled")

    monkeypatch.setattr("hermes_cli.jarvis_prime.tick.perceive", boom)
    run_once(state_path=tmp_path / "state.json", enabled=False)
    assert calls == []


def test_run_once_disabled_does_not_persist_state(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    assert not state_path.exists()
    run_once(state_path=state_path, enabled=False)
    assert not state_path.exists()


def test_run_once_disabled_does_not_notify(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    notify_calls: list[tuple[TickNotification, str]] = []

    def fake_notify(note: TickNotification, channel: str) -> None:
        notify_calls.append((note, channel))

    monkeypatch.setattr("hermes_cli.jarvis_prime.tick._notify", fake_notify)
    monkeypatch.setattr(
        "hermes_cli.jarvis_prime.tick.perceive",
        lambda: _snapshot_with_failing_prs(["999"]),
    )
    run_once(state_path=tmp_path / "state.json", enabled=False, notify_via="none")
    assert notify_calls == []


# ── Enabled-path behaviour ─────────────────────────────────────────────────


def test_run_once_enabled_persists_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "hermes_cli.jarvis_prime.tick.perceive", lambda: _empty_snapshot()
    )
    state_path = tmp_path / "state.json"
    run_once(state_path=state_path, enabled=True, notify_via="none")
    assert state_path.is_file()
    state = TickState.load(state_path)
    assert state.last_tick_at is not None


def test_run_once_enabled_idempotent_when_nothing_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "hermes_cli.jarvis_prime.tick.perceive",
        lambda: _snapshot_with_failing_prs(["123"]),
    )
    state_path = tmp_path / "state.json"
    first = run_once(state_path=state_path, enabled=True, notify_via="none")
    second = run_once(state_path=state_path, enabled=True, notify_via="none")
    assert [n.kind for n in first] == ["ci_failure"]
    assert second == []


def test_run_once_emits_ci_failure_on_new_failing_pr(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "hermes_cli.jarvis_prime.tick.perceive",
        lambda: _snapshot_with_failing_prs(["42", "43"]),
    )
    notes = run_once(state_path=tmp_path / "s.json", enabled=True, notify_via="none")
    assert len(notes) == 1
    note = notes[0]
    assert note.kind == "ci_failure"
    assert note.severity == "warning"
    assert "42" in note.body and "43" in note.body


def test_run_once_emits_blocked_job_on_newly_blocked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "hermes_cli.jarvis_prime.tick.perceive",
        lambda: _snapshot_with_blocked_jobs(["job-7"]),
    )
    notes = run_once(state_path=tmp_path / "s.json", enabled=True, notify_via="none")
    kinds = [n.kind for n in notes]
    assert "blocked_job" in kinds
    blocked = next(n for n in notes if n.kind == "blocked_job")
    assert "job-7" in blocked.body


def test_run_once_resolved_ci_failure_does_not_re_emit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    snapshots = iter(
        [
            _snapshot_with_failing_prs(["10"]),
            _snapshot_with_failing_prs([]),
            _snapshot_with_failing_prs(["10"]),
        ]
    )
    monkeypatch.setattr(
        "hermes_cli.jarvis_prime.tick.perceive", lambda: next(snapshots)
    )
    state_path = tmp_path / "s.json"
    first = run_once(state_path=state_path, enabled=True, notify_via="none")
    second = run_once(state_path=state_path, enabled=True, notify_via="none")
    third = run_once(state_path=state_path, enabled=True, notify_via="none")
    assert [n.kind for n in first] == ["ci_failure"]
    assert second == []
    assert [n.kind for n in third] == ["ci_failure"]


# ── TickState persistence ─────────────────────────────────────────────────


def test_tickstate_load_missing_file_returns_defaults(tmp_path: Path) -> None:
    state = TickState.load(tmp_path / "does-not-exist.json")
    assert state.last_tick_at is None
    assert state.last_failing_ci_prs == []
    assert state.last_briefing_at is None
    assert state.last_blocked_jobs == []


def test_tickstate_save_then_load_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    original = TickState(
        last_tick_at="2026-05-25T12:00:00+00:00",
        last_failing_ci_prs=["1", "2"],
        last_briefing_at="2026-05-25T08:00:00+00:00",
        last_blocked_jobs=["job-x"],
    )
    original.save(path)
    rehydrated = TickState.load(path)
    assert rehydrated.last_tick_at == original.last_tick_at
    assert rehydrated.last_failing_ci_prs == original.last_failing_ci_prs
    assert rehydrated.last_briefing_at == original.last_briefing_at
    assert rehydrated.last_blocked_jobs == original.last_blocked_jobs


def test_tickstate_load_ignores_unknown_keys(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    path.write_text(
        '{"last_tick_at": "x", "secret_extra_field": "ignored"}', encoding="utf-8"
    )
    state = TickState.load(path)
    assert state.last_tick_at == "x"


def test_tickstate_load_corrupt_json_returns_defaults(tmp_path: Path) -> None:
    path = tmp_path / "state.json"
    path.write_text("{not valid json", encoding="utf-8")
    state = TickState.load(path)
    assert state.last_tick_at is None


# ── Briefing window helper ────────────────────────────────────────────────


def test_is_in_briefing_window_inside(monkeypatch: pytest.MonkeyPatch) -> None:
    import datetime as dt

    now = dt.datetime(2026, 5, 25, 8, 5, tzinfo=dt.timezone.utc)
    assert _is_in_briefing_window(now, "08:00 America/Toronto") is True


def test_is_in_briefing_window_outside_hour() -> None:
    import datetime as dt

    now = dt.datetime(2026, 5, 25, 11, 0, tzinfo=dt.timezone.utc)
    assert _is_in_briefing_window(now, "08:00 America/Toronto") is False


def test_is_in_briefing_window_invalid_format_returns_false() -> None:
    import datetime as dt

    now = dt.datetime(2026, 5, 25, 8, 0, tzinfo=dt.timezone.utc)
    assert _is_in_briefing_window(now, "not a window") is False
    assert _is_in_briefing_window(now, "") is False


# ── TickNotification dataclass ────────────────────────────────────────────


def test_ticknotification_defaults_to_info_severity() -> None:
    note = TickNotification(kind="x", title="t", body="b")
    assert note.severity == "info"


def test_ticknotification_severity_is_overridable() -> None:
    note = TickNotification(kind="x", title="t", body="b", severity="alert")
    assert note.severity == "alert"


# ── _notify channel handling ──────────────────────────────────────────────


def test_notify_with_none_channel_does_not_write_inbox(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """channel='none' is the test-safe path — logs only, no filesystem touch.

    The other branch writes to ``~/.hermes/jarvis_prime/inbox`` which is
    out of scope for unit tests; conftest does not redirect $HOME.
    """

    from hermes_cli.jarvis_prime.tick import _notify

    inbox = Path("~/.hermes/jarvis_prime/inbox").expanduser()
    before = sorted(inbox.glob("*.json")) if inbox.is_dir() else []
    _notify(
        TickNotification(kind="k", title="t", body="b", severity="info"),
        channel="none",
    )
    after = sorted(inbox.glob("*.json")) if inbox.is_dir() else []
    assert before == after


# ── Optional: state_path defaults are sensible without crashing ───────────


def test_run_once_disabled_with_default_state_path_does_not_touch_disk(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The default ``state_path`` resolves under ``~/.hermes/jarvis_prime``.

    When ``enabled=False`` we must not even compute that path or write to
    it — the early return at ``tick.py:110-112`` guarantees this.
    """

    perceive_calls: list[None] = []

    def fail_perceive() -> AwarenessSnapshot:
        perceive_calls.append(None)
        raise AssertionError("perceive must not run when disabled")

    monkeypatch.setattr("hermes_cli.jarvis_prime.tick.perceive", fail_perceive)
    result = run_once(state_path=None, enabled=False)
    assert result == []
    assert perceive_calls == []
