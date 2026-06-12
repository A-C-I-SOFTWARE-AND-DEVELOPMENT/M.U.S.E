"""Tests for muse_cli.orchestrator_events — event constants + broker."""

from __future__ import annotations

import asyncio

import pytest

from muse_cli import orchestrator_events as oe
from muse_cli.orchestrator_events import (
    ALL_EVENTS,
    ALL_PHASES,
    EVENT_APPROVAL_GRANTED,
    EVENT_APPROVAL_REJECTED,
    EVENT_APPROVAL_REQUESTED,
    EVENT_ERROR,
    EVENT_EVIDENCE_UPDATED,
    EVENT_JOB_CREATED,
    EVENT_JOB_FAILED,
    EVENT_PHASE_CHANGED,
    EVENT_PUBLISH_READY,
    EVENT_SCORING_COMPLETED,
    EVENT_VALIDATION_COMPLETED,
    EVENT_WORKER_BLOCKED,
    EVENT_WORKER_COMPLETED,
    EVENT_WORKER_HEARTBEAT,
    EVENT_WORKER_STARTED,
    EventBroker,
    PHASE_AWAITING_APPROVAL,
    PHASE_COMPLETED,
    PHASE_EXECUTING,
    PHASE_INTAKE,
    PHASE_VALIDATING,
    make_envelope,
    publish_approval_requested,
    publish_error,
    publish_phase_changed,
    publish_worker_heartbeat,
)


# ---------------------------------------------------------------------------
# Event registry
# ---------------------------------------------------------------------------


def test_all_events_includes_phase18_additions():
    expected_subset = {
        EVENT_JOB_CREATED,
        EVENT_PHASE_CHANGED,
        EVENT_APPROVAL_REQUESTED,
        EVENT_APPROVAL_GRANTED,
        EVENT_APPROVAL_REJECTED,
        EVENT_WORKER_STARTED,
        EVENT_WORKER_HEARTBEAT,
        EVENT_WORKER_COMPLETED,
        EVENT_VALIDATION_COMPLETED,
        EVENT_PUBLISH_READY,
        EVENT_ERROR,
    }
    assert expected_subset.issubset(set(ALL_EVENTS))


def test_event_constants_are_dot_namespaced_strings():
    for event in ALL_EVENTS:
        assert isinstance(event, str)
        # 'error' is the one short event name; everything else namespaces.
        if event != EVENT_ERROR:
            assert "." in event, event


def test_all_phases_includes_expected_states():
    expected = {
        PHASE_INTAKE,
        PHASE_EXECUTING,
        PHASE_VALIDATING,
        PHASE_AWAITING_APPROVAL,
        PHASE_COMPLETED,
    }
    assert expected.issubset(set(ALL_PHASES))


def test_module_public_api():
    expected = {
        "ALL_EVENTS",
        "ALL_PHASES",
        "EventBroker",
        "make_envelope",
        "publish_phase_changed",
        "publish_approval_requested",
        "publish_worker_heartbeat",
        "publish_error",
    }
    assert expected.issubset(set(oe.__all__))


# ---------------------------------------------------------------------------
# make_envelope
# ---------------------------------------------------------------------------


def test_make_envelope_shape_and_defaults():
    env = make_envelope(EVENT_JOB_CREATED, "job-1", {"name": "x"})
    assert env["event"] == EVENT_JOB_CREATED
    assert env["job_id"] == "job-1"
    assert env["data"] == {"name": "x"}
    assert isinstance(env["ts"], float)
    assert env["ts"] > 0


def test_make_envelope_explicit_timestamp():
    env = make_envelope(EVENT_ERROR, "j", {"message": "oh no"}, ts=1234.0)
    assert env["ts"] == 1234.0


def test_make_envelope_rejects_unknown_event():
    with pytest.raises(ValueError, match="unknown event"):
        make_envelope("totally.fake", "j")


def test_make_envelope_copies_data_dict():
    payload = {"x": 1}
    env = make_envelope(EVENT_JOB_CREATED, "j", payload)
    payload["x"] = 2
    assert env["data"] == {"x": 1}


def test_make_envelope_none_data_becomes_empty():
    env = make_envelope(EVENT_JOB_CREATED, "j", None)
    assert env["data"] == {}


# ---------------------------------------------------------------------------
# EventBroker — basic lifecycle
# ---------------------------------------------------------------------------


class TestEventBroker:
    def test_publish_with_no_subscribers_records_history(self):
        async def _run():
            broker = EventBroker()
            envelope = await broker.publish(EVENT_JOB_CREATED, "j1", {"k": 1})
            history = await broker.history("j1")
            assert history == [envelope]
        asyncio.run(_run())

    def test_subscribe_receives_subsequent_events(self):
        async def _run():
            broker = EventBroker()
            q = await broker.subscribe("j2")
            env = await broker.publish(EVENT_WORKER_STARTED, "j2", {})
            received = await asyncio.wait_for(q.get(), timeout=1.0)
            assert received == env
        asyncio.run(_run())

    def test_subscribers_isolated_per_job(self):
        async def _run():
            broker = EventBroker()
            q_a = await broker.subscribe("a")
            q_b = await broker.subscribe("b")
            await broker.publish(EVENT_JOB_CREATED, "a", {})
            await broker.publish(EVENT_JOB_CREATED, "b", {})
            ev_a = await asyncio.wait_for(q_a.get(), timeout=1.0)
            ev_b = await asyncio.wait_for(q_b.get(), timeout=1.0)
            assert ev_a["job_id"] == "a"
            assert ev_b["job_id"] == "b"
            # Each queue only saw its own job.
            assert q_a.empty()
            assert q_b.empty()
        asyncio.run(_run())

    def test_multiple_subscribers_on_same_job(self):
        async def _run():
            broker = EventBroker()
            q1 = await broker.subscribe("j")
            q2 = await broker.subscribe("j")
            await broker.publish(EVENT_PHASE_CHANGED, "j", {"to": "executing"})
            for q in (q1, q2):
                env = await asyncio.wait_for(q.get(), timeout=1.0)
                assert env["event"] == EVENT_PHASE_CHANGED
        asyncio.run(_run())

    def test_unsubscribe_stops_delivery(self):
        async def _run():
            broker = EventBroker()
            q = await broker.subscribe("j")
            await broker.unsubscribe("j", q)
            await broker.publish(EVENT_WORKER_STARTED, "j", {})
            assert q.empty()
            assert broker.subscriber_count("j") == 0
        asyncio.run(_run())

    def test_unsubscribe_unknown_subscriber_is_noop(self):
        async def _run():
            broker = EventBroker()
            q: "asyncio.Queue" = asyncio.Queue()
            # No exception even though we never registered.
            await broker.unsubscribe("nope", q)
        asyncio.run(_run())

    def test_history_returns_copy(self):
        async def _run():
            broker = EventBroker()
            await broker.publish(EVENT_JOB_CREATED, "j", {})
            history = await broker.history("j")
            history.clear()
            again = await broker.history("j")
            assert len(again) == 1
        asyncio.run(_run())

    def test_history_bounded(self):
        async def _run():
            broker = EventBroker(history=3)
            for i in range(5):
                await broker.publish(EVENT_WORKER_HEARTBEAT, "j", {"i": i})
            history = await broker.history("j")
            assert len(history) == 3
            # The most recent three survive.
            assert [e["data"]["i"] for e in history] == [2, 3, 4]
        asyncio.run(_run())

    def test_clear_specific_job(self):
        async def _run():
            broker = EventBroker()
            await broker.publish(EVENT_JOB_CREATED, "a", {})
            await broker.publish(EVENT_JOB_CREATED, "b", {})
            await broker.clear("a")
            assert await broker.history("a") == []
            assert len(await broker.history("b")) == 1
        asyncio.run(_run())

    def test_clear_all_jobs(self):
        async def _run():
            broker = EventBroker()
            await broker.publish(EVENT_JOB_CREATED, "a", {})
            await broker.publish(EVENT_JOB_CREATED, "b", {})
            await broker.clear()
            assert broker.known_jobs() == []
        asyncio.run(_run())

    def test_known_jobs_tracks_publishes(self):
        async def _run():
            broker = EventBroker()
            assert broker.known_jobs() == []
            await broker.publish(EVENT_JOB_CREATED, "alpha", {})
            await broker.publish(EVENT_JOB_CREATED, "beta", {})
            assert set(broker.known_jobs()) == {"alpha", "beta"}
        asyncio.run(_run())

    def test_subscriber_count_tracks_lifecycle(self):
        async def _run():
            broker = EventBroker()
            assert broker.subscriber_count("j") == 0
            q1 = await broker.subscribe("j")
            q2 = await broker.subscribe("j")
            assert broker.subscriber_count("j") == 2
            await broker.unsubscribe("j", q1)
            assert broker.subscriber_count("j") == 1
            await broker.unsubscribe("j", q2)
            assert broker.subscriber_count("j") == 0
        asyncio.run(_run())

    def test_slow_subscriber_drops_events_not_block(self):
        async def _run():
            broker = EventBroker(queue_size=2)
            q = await broker.subscribe("j")
            # Fill the queue.
            for i in range(5):
                await broker.publish(EVENT_WORKER_HEARTBEAT, "j", {"i": i})
            # Queue still bounded — slow subscriber was not blocked.
            assert q.qsize() == 2
            # And history reflects all five events.
            assert len(await broker.history("j")) == 5
        asyncio.run(_run())

    def test_publish_rejects_unknown_event(self):
        async def _run():
            broker = EventBroker()
            with pytest.raises(ValueError):
                await broker.publish("not.a.real.event", "j", {})
        asyncio.run(_run())

    def test_invalid_constructor_args(self):
        with pytest.raises(ValueError):
            EventBroker(history=-1)
        with pytest.raises(ValueError):
            EventBroker(queue_size=0)

    def test_publish_returns_envelope_with_data_copy(self):
        async def _run():
            broker = EventBroker()
            payload = {"x": 1}
            env = await broker.publish(EVENT_PHASE_CHANGED, "j", payload)
            payload["x"] = 2
            assert env["data"] == {"x": 1}
        asyncio.run(_run())


# ---------------------------------------------------------------------------
# Convenience publishers
# ---------------------------------------------------------------------------


class TestConveniencePublishers:
    def test_phase_changed_helper(self):
        async def _run():
            broker = EventBroker()
            env = await publish_phase_changed(
                broker,
                "j",
                from_phase=PHASE_INTAKE,
                to_phase=PHASE_EXECUTING,
                reason="resume",
            )
            assert env["event"] == EVENT_PHASE_CHANGED
            assert env["data"] == {
                "from": PHASE_INTAKE,
                "to": PHASE_EXECUTING,
                "reason": "resume",
            }
        asyncio.run(_run())

    def test_phase_changed_rejects_unknown_phase(self):
        async def _run():
            broker = EventBroker()
            with pytest.raises(ValueError):
                await publish_phase_changed(
                    broker, "j", from_phase=None, to_phase="warp-9"
                )
        asyncio.run(_run())

    def test_phase_changed_omits_reason_when_none(self):
        async def _run():
            broker = EventBroker()
            env = await publish_phase_changed(
                broker, "j", from_phase=None, to_phase=PHASE_EXECUTING
            )
            assert "reason" not in env["data"]
        asyncio.run(_run())

    def test_approval_requested_helper(self):
        async def _run():
            broker = EventBroker()
            env = await publish_approval_requested(
                broker,
                "j",
                kind="publish",
                summary="ship?",
                payload={"channel": "stable"},
            )
            assert env["event"] == EVENT_APPROVAL_REQUESTED
            assert env["data"]["kind"] == "publish"
            assert env["data"]["payload"] == {"channel": "stable"}
        asyncio.run(_run())

    def test_approval_requested_without_payload(self):
        async def _run():
            broker = EventBroker()
            env = await publish_approval_requested(
                broker, "j", kind="manual", summary="please review"
            )
            assert "payload" not in env["data"]
        asyncio.run(_run())

    def test_worker_heartbeat_helper(self):
        async def _run():
            broker = EventBroker()
            env = await publish_worker_heartbeat(
                broker, "j", worker="alice", progress=0.75, note="halfway"
            )
            assert env["event"] == EVENT_WORKER_HEARTBEAT
            assert env["data"]["worker"] == "alice"
            assert env["data"]["progress"] == 0.75
            assert env["data"]["note"] == "halfway"
        asyncio.run(_run())

    def test_worker_heartbeat_omits_optional_fields(self):
        async def _run():
            broker = EventBroker()
            env = await publish_worker_heartbeat(broker, "j", worker="alice")
            assert env["data"] == {"worker": "alice"}
        asyncio.run(_run())

    def test_error_helper_fatal_flag(self):
        async def _run():
            broker = EventBroker()
            env = await publish_error(
                broker, "j", message="boom", fatal=True, detail={"code": 42}
            )
            assert env["event"] == EVENT_ERROR
            assert env["data"] == {
                "message": "boom",
                "fatal": True,
                "detail": {"code": 42},
            }
        asyncio.run(_run())

    def test_error_helper_defaults_non_fatal(self):
        async def _run():
            broker = EventBroker()
            env = await publish_error(broker, "j", message="hiccup")
            assert env["data"]["fatal"] is False
            assert "detail" not in env["data"]
        asyncio.run(_run())


# ---------------------------------------------------------------------------
# Integration: publishers + subscriber
# ---------------------------------------------------------------------------


def test_subscriber_receives_helper_publishes():
    async def _run():
        broker = EventBroker()
        q = await broker.subscribe("j")
        await publish_phase_changed(
            broker, "j", from_phase=None, to_phase=PHASE_VALIDATING
        )
        await publish_worker_heartbeat(broker, "j", worker="w", progress=0.5)
        await publish_error(broker, "j", message="warn", fatal=False)

        events = []
        for _ in range(3):
            envelope = await asyncio.wait_for(q.get(), timeout=1.0)
            events.append(envelope["event"])
        assert events == [
            EVENT_PHASE_CHANGED,
            EVENT_WORKER_HEARTBEAT,
            EVENT_ERROR,
        ]
    asyncio.run(_run())


def test_late_subscriber_can_replay_history():
    async def _run():
        broker = EventBroker()
        await broker.publish(EVENT_JOB_CREATED, "j", {})
        await broker.publish(EVENT_WORKER_STARTED, "j", {})
        # A late subscriber sees nothing live, but can replay history.
        history = await broker.history("j")
        events = [e["event"] for e in history]
        assert events == [EVENT_JOB_CREATED, EVENT_WORKER_STARTED]
    asyncio.run(_run())
