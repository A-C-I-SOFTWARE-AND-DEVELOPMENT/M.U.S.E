"""Tests for deterministic job-state reconstruction (Sprint 4).

Folds real ``orchestrator_events`` envelopes (built with ``make_envelope``)
into a :class:`JobSnapshot` and asserts the rebuild is faithful, deterministic,
prefix-consistent, and tolerant of junk.
"""

from __future__ import annotations

from typing import Any

from muse_cli.job_replay import JobSnapshot, rebuild_snapshot
from muse_cli.orchestrator_events import (
    EVENT_APPROVAL_GRANTED,
    EVENT_APPROVAL_REJECTED,
    EVENT_APPROVAL_REQUESTED,
    EVENT_JOB_CREATED,
    EVENT_JOB_FAILED,
    EVENT_PHASE_CHANGED,
    EVENT_PUBLISH_READY,
    EVENT_VALIDATION_COMPLETED,
    EVENT_WORKER_BLOCKED,
    EVENT_WORKER_COMPLETED,
    EVENT_WORKER_STARTED,
    PHASE_CANCELLED,
    PHASE_COMPLETED,
    PHASE_EXECUTING,
    PHASE_FAILED,
    PHASE_PUBLISH_READY,
    PHASE_VALIDATING,
    make_envelope,
)

JOB = "job_abc123"


def _happy_path_events() -> list[dict]:
    return [
        make_envelope(EVENT_JOB_CREATED, JOB, {"name": "Add feature", "spec": {"goal": "x"}}, ts=1.0),
        make_envelope(EVENT_PHASE_CHANGED, JOB, {"from": "intake", "to": PHASE_EXECUTING}, ts=2.0),
        make_envelope(EVENT_WORKER_STARTED, JOB, {"worker": "claude-code"}, ts=3.0),
        make_envelope(EVENT_WORKER_COMPLETED, JOB, {"worker": "claude-code", "result": "ok"}, ts=4.0),
        make_envelope(EVENT_PHASE_CHANGED, JOB, {"from": PHASE_EXECUTING, "to": PHASE_VALIDATING}, ts=5.0),
        make_envelope(EVENT_VALIDATION_COMPLETED, JOB, {"result": {"ok": True}}, ts=6.0),
        make_envelope(EVENT_PHASE_CHANGED, JOB, {"from": PHASE_VALIDATING, "to": PHASE_PUBLISH_READY}, ts=7.0),
        make_envelope(EVENT_PUBLISH_READY, JOB, {"plan": {"pr_url": "https://github.com/x/y/pull/1"}}, ts=8.0),
        make_envelope(EVENT_PHASE_CHANGED, JOB, {"from": PHASE_PUBLISH_READY, "to": PHASE_COMPLETED}, ts=9.0),
    ]


def test_happy_path_rebuilds_completed_job():
    snap = rebuild_snapshot(_happy_path_events())
    assert snap.job_id == JOB
    assert snap.name == "Add feature"
    assert snap.spec == {"goal": "x"}
    assert snap.phase == PHASE_COMPLETED
    assert snap.status == "completed"
    assert snap.is_terminal
    assert snap.workers == {"claude-code": "completed"}
    assert snap.validation == {"ok": True}
    assert snap.pr_url == "https://github.com/x/y/pull/1"
    assert snap.failed is False
    assert snap.event_count == 9
    assert snap.last_ts == 9.0


def test_job_id_inferred_from_envelopes_when_not_passed():
    snap = rebuild_snapshot(_happy_path_events())
    assert snap.job_id == JOB
    # explicit override also honored
    snap2 = rebuild_snapshot(_happy_path_events(), job_id="explicit")
    assert snap2.job_id == "explicit"


def test_approval_lifecycle():
    events = [
        make_envelope(EVENT_JOB_CREATED, JOB, {"name": "n"}),
        make_envelope(EVENT_APPROVAL_REQUESTED, JOB, {"approval_id": "appr_1"}),
        make_envelope(EVENT_APPROVAL_GRANTED, JOB, {"approval_id": "appr_1"}),
        make_envelope(EVENT_APPROVAL_REQUESTED, JOB, {"approval_id": "appr_2"}),
    ]
    snap = rebuild_snapshot(events)
    assert snap.approvals == {"appr_1": "granted", "appr_2": "pending"}


def test_reject_marks_failed_with_error():
    events = [
        make_envelope(EVENT_JOB_CREATED, JOB, {"name": "n"}),
        make_envelope(EVENT_APPROVAL_REJECTED, JOB, {"approval_id": "appr_1"}),
        make_envelope(EVENT_JOB_FAILED, JOB, {"reason": "approval rejected"}),
    ]
    snap = rebuild_snapshot(events)
    assert snap.failed is True
    assert snap.status == "failed"
    assert snap.phase == PHASE_FAILED
    assert snap.error == "approval rejected"
    assert snap.approvals == {"appr_1": "rejected"}


def test_cancel_maps_to_cancelled_phase():
    events = [
        make_envelope(EVENT_JOB_CREATED, JOB, {"name": "n"}),
        make_envelope(EVENT_PHASE_CHANGED, JOB, {"from": "intake", "to": PHASE_CANCELLED}),
        make_envelope(EVENT_JOB_FAILED, JOB, {"reason": "cancelled"}),
    ]
    snap = rebuild_snapshot(events)
    assert snap.phase == PHASE_CANCELLED
    assert snap.status == "cancelled"
    assert snap.failed is True  # job.failed still recorded
    assert snap.is_terminal


def test_worker_state_transitions():
    events = [
        make_envelope(EVENT_JOB_CREATED, JOB, {"name": "n"}),
        make_envelope(EVENT_WORKER_STARTED, JOB, {"worker": "a"}),
        make_envelope(EVENT_WORKER_BLOCKED, JOB, {"worker": "b", "reason": "needs input"}),
        make_envelope(EVENT_WORKER_COMPLETED, JOB, {"worker": "a", "result": "ok"}),
    ]
    snap = rebuild_snapshot(events)
    assert snap.workers == {"a": "completed", "b": "blocked"}


def test_deterministic_rebuild():
    events = _happy_path_events()
    assert rebuild_snapshot(events).to_dict() == rebuild_snapshot(events).to_dict()


def test_partial_prefix_is_consistent():
    events = _happy_path_events()
    # After the first 5 events the job is mid-validation, not yet published.
    partial = rebuild_snapshot(events[:5])
    assert partial.phase == PHASE_VALIDATING
    assert partial.status == "validating"
    assert partial.pr_url is None
    assert partial.is_terminal is False
    assert partial.event_count == 5


def test_pr_url_tolerates_alternate_key():
    events = [
        make_envelope(EVENT_JOB_CREATED, JOB, {"name": "n"}),
        make_envelope(EVENT_PUBLISH_READY, JOB, {"plan": {"url": "https://example/pr/2"}}),
    ]
    snap = rebuild_snapshot(events)
    assert snap.pr_url == "https://example/pr/2"


def test_tolerates_unknown_events_and_missing_data():
    # Raw, deliberately-heterogeneous input (bypassing make_envelope, which
    # would reject unknown events). Typed list[Any] because the point of the
    # test is that the reducer tolerates junk it isn't statically promised.
    events: list[Any] = [
        {"event": "some.future.event", "job_id": JOB, "data": {"x": 1}},
        {"event": EVENT_PHASE_CHANGED, "job_id": JOB},  # no data
        {"not": "an envelope"},
        "garbage",
        {"event": EVENT_WORKER_STARTED, "job_id": JOB, "data": {"no_worker_key": True}},
    ]
    snap = rebuild_snapshot(events, job_id=JOB)
    assert snap.job_id == JOB
    assert snap.workers == {}  # worker event without a worker key folds to nothing
    # only the mapping envelopes are counted (the str is skipped)
    assert snap.event_count == 4


def test_empty_stream_yields_default_snapshot():
    snap = rebuild_snapshot([], job_id=JOB)
    assert isinstance(snap, JobSnapshot)
    assert snap.job_id == JOB
    assert snap.status == "pending"
    assert snap.phase == "intake"
    assert snap.event_count == 0
